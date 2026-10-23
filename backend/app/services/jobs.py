"""
Training experiments in the background.

Training takes minutes, far longer than a web request may last, so POST /api/experiments only
saves the experiment as "queued" and wakes this runner. The runner is one background thread that
trains one experiment at a time (training uses the whole CPU; two at once would each be half as
fast), oldest first. While it trains it writes the progress and loss curve to the database every
second, which is what the Experiment page polls.

    queued -> running -> completed | failed | cancelled
                      -> interrupted   (the server stopped in the middle; "Run again" makes a new one)

Run the server with ONE process (`flask run`, or gunicorn -w 1): with several processes, each
would start its own runner.
"""
import shutil
import threading
import time
from dataclasses import replace
from pathlib import Path

from flask import current_app
from sqlalchemy import select, update

from ..extensions import db
from ..models import ActivityEvent, Experiment, Metric, Result
from ..models.base import utcnow

PHASE_TO_METRIC = {"pretrain": "pretrain", "finetune-full": "full", "finetune-lora": "lora"}
RESULT_KEYS = {"base": "base", "full-FT": "full", "LoRA": "lora"}      # engine name -> database name
FLUSH_SECONDS = 1.0                                                 # how often progress is saved
LORA_PARAMS_PER_RANK = 6144   # 4 layers x (qkv 96+288, proj 96+96, fc 96+384, fc2 384+96): 49,152 at rank 8
FULL_PARAMS = 512_544


def engine_config(exp):
    """The engine settings for an experiment. If its step counts match a preset (quick, short,
    full), the preset's warm-up and evaluation interval are used too, so the run is identical to
    `python main.py train --preset ...`."""
    from llm.experiment import PRESETS, ExperimentConfig

    chosen = {"lora_rank": exp.lora_rank, "replay": exp.replay, "seed": exp.seed,
              "evaluate": current_app.config.get("EXPERIMENT_EVALUATE", True)}
    for preset in PRESETS.values():
        if (preset.pretrain_steps, preset.finetune_steps) == (exp.pretrain_steps, exp.finetune_steps):
            return replace(preset, **chosen)
    return ExperimentConfig(pretrain_steps=exp.pretrain_steps, finetune_steps=exp.finetune_steps,
                            pretrain_warmup=min(100, max(10, exp.pretrain_steps // 3)),
                            eval_every=max(10, exp.pretrain_steps // 20), **chosen)


def run_dir(exp_id):
    return Path(current_app.config["RUNS_DIR"]) / str(int(exp_id))


def delete_run_files(exp_id):
    path = run_dir(exp_id)
    if path.is_dir() and path.parent == Path(current_app.config["RUNS_DIR"]):
        shutil.rmtree(path, ignore_errors=True)


def add_event(exp, kind, message):
    db.session.add(ActivityEvent(user_id=exp.owner_id, type=kind, message=message[:200], experiment_id=exp.id))


class Recorder:
    """Collects progress and loss points during training and saves them in small batches."""

    def __init__(self, exp_id):
        self.exp_id = exp_id
        self.pending = []
        self.phase, self.progress = None, 0.0
        self.last_flush = 0.0
        self.last_cancel_check = 0.0
        self.cancel = False
        self.pretrain_rows = {}           # step -> Metric, to add validation loss at the end

    def on_progress(self, phase, fraction, info):
        self.phase, self.progress = phase, min(1.0, max(0.0, fraction))
        metric_phase = PHASE_TO_METRIC.get(phase)
        if metric_phase and "step" in info:
            step, steps = info["step"] - 1, info["steps"]          # the engine counts from 0 in its history
            every = max(1, steps // 100)                            # about 100 points per curve
            if step % every == 0 or step == steps - 1:
                m = Metric(experiment_id=self.exp_id, phase=metric_phase, step=step, train_loss=info["loss"])
                self.pending.append(m)
                if metric_phase == "pretrain":
                    self.pretrain_rows[step] = m
        if time.monotonic() - self.last_flush >= FLUSH_SECONDS or phase == "evaluate":
            self.flush()

    def flush(self):
        db.session.execute(update(Experiment).where(Experiment.id == self.exp_id)
                           .values(phase=self.phase, progress=self.progress))
        db.session.add_all(self.pending)
        self.pending = []
        db.session.commit()
        self.last_flush = time.monotonic()

    def should_stop(self):
        if time.monotonic() - self.last_cancel_check >= FLUSH_SECONDS:
            self.last_cancel_check = time.monotonic()
            self.cancel = bool(db.session.scalar(select(Experiment.cancel_requested)
                                                 .where(Experiment.id == self.exp_id)))
        return self.cancel


def claim(exp_id):
    """queued -> running, but only if it is still queued (it may have been cancelled or deleted)."""
    result = db.session.execute(update(Experiment)
                                .where(Experiment.id == exp_id, Experiment.status == "queued")
                                .values(status="running", started_at=utcnow(), phase="data", progress=0.0))
    db.session.commit()
    return result.rowcount == 1


def run_one(exp_id):
    """Train one queued experiment from start to finish (in the current app context)."""
    from llm.experiment import ExperimentCancelled, run_experiment

    if not claim(exp_id):
        return None
    exp = db.session.get(Experiment, exp_id)
    log = current_app.logger
    train = current_app.config.get("EXPERIMENT_TRAIN_FN") or run_experiment
    rec = Recorder(exp_id)
    out = run_dir(exp_id)
    out.mkdir(parents=True, exist_ok=True)
    log.info("experiment %s: training started", exp_id)
    with open(out / "run_log.txt", "w", encoding="utf-8") as log_file:
        def write_log(line=""):
            log_file.write(f"{line}\n")
            log_file.flush()
        try:
            results = train(engine_config(exp), str(out), on_progress=rec.on_progress,
                            should_stop=rec.should_stop, log=write_log)
            rec.flush()
            save_results(exp, rec, results)
            exp.status, exp.progress = "completed", 1.0
            held = {r.model: r.qa_heldout for r in exp.results}
            summary = f" LoRA answered {held['lora']:.0%} of held-out questions." if "lora" in held else ""
            add_event(exp, "experiment.completed", f"\"{exp.name}\" finished.{summary}")
        except ExperimentCancelled:
            db.session.rollback()
            rec.pending = []
            exp = db.session.get(Experiment, exp_id)
            exp.status = "cancelled"
            add_event(exp, "experiment.cancelled", f"\"{exp.name}\" was cancelled.")
        except Exception as err:  # noqa: BLE001 - any failure is shown on the experiment page
            db.session.rollback()
            log.exception("experiment %s failed", exp_id)
            write_log(f"\nERROR: {err!r}")
            exp = db.session.get(Experiment, exp_id)
            exp.status = "failed"
            exp.error = f"{type(err).__name__}: {err}"[:1000]
            add_event(exp, "experiment.failed", f"\"{exp.name}\" failed: {type(err).__name__}.")
    exp.finished_at = utcnow()
    db.session.commit()
    log.info("experiment %s: %s", exp_id, exp.status)
    return exp.status


def save_results(exp, rec, results):
    """Validation loss for the pre-training curve, and the scores of the three models."""
    for h in results.get("pretraining", []):
        row = rec.pretrain_rows.get(h["step"])
        if row is None:
            db.session.add(Metric(experiment_id=exp.id, phase="pretrain", step=h["step"],
                                  train_loss=float(h["train_loss"]), val_loss=float(h["val_loss"])))
        else:
            row.val_loss = float(h["val_loss"])
    for key, ev in results.get("evaluation", {}).items():
        model = RESULT_KEYS[key]
        params = LORA_PARAMS_PER_RANK * exp.lora_rank if model == "lora" else FULL_PARAMS
        db.session.add(Result(experiment_id=exp.id, model=model, qa_seen=ev["qa_seen"], qa_heldout=ev["qa_heldout"],
                              completion=ev["completion"], perplexity=ev["val_ppl"], trainable_params=params))
    db.session.flush()
    db.session.refresh(exp)


def mark_interrupted():
    """At start-up: anything still "running" belongs to a server that stopped. It cannot be resumed."""
    rows = db.session.scalars(select(Experiment).where(Experiment.status == "running")).all()
    for exp in rows:
        exp.status, exp.finished_at = "interrupted", utcnow()
        exp.error = "The server stopped while this experiment was training. Use \"Run again\" to start it fresh."
        add_event(exp, "experiment.interrupted", f"\"{exp.name}\" was interrupted by a server restart.")
    db.session.commit()
    return len(rows)


def next_queued():
    return db.session.scalar(select(Experiment.id).where(Experiment.status == "queued")
                             .order_by(Experiment.created_at, Experiment.id).limit(1))


class JobRunner:
    """The one background thread. `wake()` after queueing an experiment."""

    def __init__(self, app):
        self.app = app
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._thread = None

    @property
    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self.alive:
                return
            with self.app.app_context():
                n = mark_interrupted()
                if n:
                    self.app.logger.warning("%d experiment(s) were interrupted by a restart", n)
            self._thread = threading.Thread(target=self._loop, name="experiment-runner", daemon=True)
            self._thread.start()

    def wake(self):
        self.start()
        self._event.set()

    def _loop(self):
        while True:
            try:
                with self.app.app_context():
                    exp_id = next_queued()
                    if exp_id is not None:
                        run_one(exp_id)
                        db.session.remove()
                        continue
                    db.session.remove()
            except Exception:  # noqa: BLE001 - keep the runner alive whatever happens
                self.app.logger.exception("experiment runner error")
            self._event.wait(timeout=30)
            self._event.clear()


def init_jobs(app):
    """Attach the runner to the app. It starts on the first request (not at import or during
    `flask db upgrade`), when JOBS_AUTOSTART is on; tests call run_one() themselves."""
    runner = JobRunner(app)
    app.extensions["jobs"] = runner

    if app.config.get("JOBS_AUTOSTART", True):
        @app.before_request
        def _start_runner():
            if not runner.alive and app.config["TRAINING_ENABLED"]:
                runner.start()
    return runner


def wake():
    runner = current_app.extensions["jobs"]
    if current_app.config.get("JOBS_AUTOSTART", True):
        runner.wake()
