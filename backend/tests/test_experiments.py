"""Experiments: queueing, the background runner, permissions, cancel, delete, export and compare.

Real training takes minutes, so these tests give the runner a fake trainer that behaves like
llm.experiment.run_experiment (same callbacks, same results shape) but finishes at once. The real
pipeline is tested by tests/test_experiment.py, and test_real_training_run below (RUN_SLOW=1)."""
import os

import pytest
from flask_migrate import upgrade

from backend.app.extensions import db
from backend.app.models import ActivityEvent, Experiment, Metric, Result, User
from backend.app.services import jobs

from .conftest import build_app, csrf, signup

SETTINGS = {"name": "Rank 4", "pretrain_steps": 150, "finetune_steps": 60, "lora_rank": 4, "replay": True, "seed": 3}


def fake_results(config):
    last = config.pretrain_steps - 1
    ev = lambda acc: {"qa_seen": 1.0, "qa_heldout": acc, "completion": acc, "val_ppl": 2.5, "per_attr": {}}  # noqa: E731
    return {"pretraining": [{"step": 0, "train_loss": 7.5, "val_loss": 7.6},
                            {"step": last, "train_loss": 1.2, "val_loss": 1.3}],
            "evaluation": {"base": ev(0.0), "full-FT": ev(0.9), "LoRA": ev(0.95)}}


def fake_train(config, out_dir, on_progress, should_stop, log, fail_at=None, cancel_at=None):
    from llm.experiment import ExperimentCancelled

    total, done = config.pretrain_steps + 2 * config.finetune_steps, 0
    log("fake training")
    for phase, steps in [("pretrain", config.pretrain_steps), ("finetune-full", config.finetune_steps),
                         ("finetune-lora", config.finetune_steps)]:
        for s in range(steps):
            done += 1
            if done == fail_at:
                raise RuntimeError("out of memory")
            if done == cancel_at:
                db.session.query(Experiment).update({"cancel_requested": True})   # like POST /cancel
                db.session.commit()
            on_progress(phase, done / total, {"step": s + 1, "steps": steps, "loss": 7.0 - 5 * done / total})
            if should_stop():
                raise ExperimentCancelled("cancelled by user")
    on_progress("evaluate", 1.0, {})
    return fake_results(config)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "FLUSH_SECONDS", 0)
    app = build_app(tmp_path, RUNS_DIR=tmp_path / "runs", EXPERIMENT_TRAIN_FN=fake_train,
                    RATELIMIT_EXPERIMENTS="1000 per hour")
    with app.app_context():
        upgrade()
        yield app
        db.session.remove()
        db.engine.dispose()


def create(client, **changes):
    return client.post("/api/experiments", headers=csrf(client), json={**SETTINGS, **changes})


def test_queue_run_and_results(client, app):
    signup(client)
    r = create(client)
    assert r.status_code == 202, r.get_json()
    exp = r.get_json()["data"]["experiment"]
    assert exp["status"] == "queued" and exp["is_owner"] and r.get_json()["meta"]["queue_position"] == 1

    assert jobs.run_one(exp["id"]) == "completed"
    detail = client.get(f"/api/experiments/{exp['id']}").get_json()["data"]["experiment"]
    assert detail["status"] == "completed" and detail["progress"] == 1 and detail["finished_at"]
    assert [x["model"] for x in detail["results"]] == ["base", "full", "lora"]
    assert detail["results"][2]["trainable_params"] == 6144 * 4          # LoRA rank 4
    assert detail["results"][2]["qa_heldout"] == 0.95

    pre = db.session.query(Metric).filter_by(experiment_id=exp["id"], phase="pretrain").order_by(Metric.step).all()
    assert pre[0].step == 0 and pre[-1].step == 149 and 50 <= len(pre) <= 160
    assert pre[0].val_loss == 7.6 and pre[-1].val_loss == 1.3            # validation loss filled in at the end
    assert db.session.query(Metric).filter_by(experiment_id=exp["id"], phase="lora").count() >= 50
    event = db.session.query(ActivityEvent).one()
    assert event.type == "experiment.completed" and "95%" in event.message
    assert (app.config["RUNS_DIR"] / str(exp["id"]) / "run_log.txt").read_text().startswith("fake training")
    assert client.get(f"/api/experiments/{exp['id']}/log").get_json()["data"]["lines"] == ["fake training"]


def test_engine_config_uses_presets(app):
    from llm.experiment import PRESETS
    exp = Experiment(owner_id=1, name="q", pretrain_steps=150, finetune_steps=60, lora_rank=8, replay=False, seed=1)
    cfg = jobs.engine_config(exp)
    assert (cfg.pretrain_warmup, cfg.eval_every) == (PRESETS["quick"].pretrain_warmup, PRESETS["quick"].eval_every)
    assert (cfg.replay, cfg.seed) == (False, 1)
    custom = jobs.engine_config(Experiment(owner_id=1, name="c", pretrain_steps=300, finetune_steps=20,
                                           lora_rank=2, replay=True, seed=0))
    assert (custom.pretrain_steps, custom.eval_every, custom.pretrain_warmup, custom.lora_rank) == (300, 15, 100, 2)


@pytest.mark.parametrize("change, field", [
    ({"name": " "}, "name"), ({"pretrain_steps": 49}, "pretrain_steps"), ({"pretrain_steps": 5001}, "pretrain_steps"),
    ({"finetune_steps": 19}, "finetune_steps"), ({"lora_rank": 33}, "lora_rank"), ({"seed": 10000}, "seed"),
    ({"description": "x" * 501}, "description"), ({"status": "completed"}, "status"), ({"is_public": True}, "is_public"),
])
def test_create_validation(client, change, field):
    signup(client)
    r = create(client, **change)
    assert r.status_code == 400 and field in r.get_json()["error"]["fields"]


def test_one_active_experiment_per_user(app):
    a, b = app.test_client(), app.test_client()
    signup(a)
    signup(b, email="b@example.com")
    assert create(a).status_code == 202
    r = create(a)
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "experiment_active"
    r = create(b)
    assert r.status_code == 202 and r.get_json()["meta"]["queue_position"] == 2


def test_training_disabled(tmp_path):
    app = build_app(tmp_path, TRAINING_ENABLED=False)
    with app.app_context():
        upgrade()
        c = app.test_client()
        signup(c)
        r = create(c)
        assert r.status_code == 403 and r.get_json()["error"]["code"] == "training_disabled"
        assert c.get("/api/config").get_json()["data"]["training_enabled"] is False
        db.session.remove()
        db.engine.dispose()


def test_private_experiments_are_hidden(app):
    owner, other = app.test_client(), app.test_client()
    signup(owner)
    signup(other, email="other@example.com")
    eid = create(owner).get_json()["data"]["experiment"]["id"]
    for path in ("", "/metrics", "/log", "/export.csv"):
        assert other.get(f"/api/experiments/{eid}{path}").status_code == 404, path
    assert other.post(f"/api/experiments/{eid}/cancel", headers=csrf(other)).status_code == 404
    assert other.delete(f"/api/experiments/{eid}", headers=csrf(other)).status_code == 404
    assert other.get(f"/api/experiments/compare?ids={eid},{eid + 1}").status_code == 404
    assert other.get("/api/experiments").get_json()["meta"]["total"] == 0


def test_published_experiments_are_read_only_for_others(app):
    owner, other = app.test_client(), app.test_client()
    signup(owner)
    signup(other, email="other@example.com")
    eid = create(owner).get_json()["data"]["experiment"]["id"]
    jobs.run_one(eid)
    db.session.get(Experiment, eid).is_public = True
    db.session.commit()
    assert other.get(f"/api/experiments/{eid}").get_json()["data"]["experiment"]["is_owner"] is False
    assert other.get("/api/experiments?scope=public").get_json()["meta"]["total"] == 1
    r = other.patch(f"/api/experiments/{eid}", headers=csrf(other), json={"name": "mine now"})
    assert r.status_code == 403
    assert other.delete(f"/api/experiments/{eid}", headers=csrf(other)).status_code == 403


def test_only_admins_publish(app):
    c = app.test_client()
    signup(c)
    eid = create(c).get_json()["data"]["experiment"]["id"]
    jobs.run_one(eid)
    r = c.patch(f"/api/experiments/{eid}", headers=csrf(c), json={"is_public": True})
    assert r.status_code == 403 and r.get_json()["error"]["code"] == "admin_only"
    db.session.query(User).update({"role": "admin"})
    db.session.commit()
    r = c.patch(f"/api/experiments/{eid}", headers=csrf(c), json={"is_public": True, "name": "  Best  run "})
    assert r.status_code == 200 and r.get_json()["data"]["experiment"]["is_public"] is True
    assert r.get_json()["data"]["experiment"]["name"] == "Best run"
    assert c.patch(f"/api/experiments/{eid}", headers=csrf(c), json={"name": None}).status_code == 400


def test_cancel_queued_and_running(app):
    c = app.test_client()
    signup(c)
    eid = create(c).get_json()["data"]["experiment"]["id"]
    r = c.post(f"/api/experiments/{eid}/cancel", headers=csrf(c))
    assert r.get_json()["data"]["experiment"]["status"] == "cancelled"
    assert jobs.run_one(eid) is None                                  # the runner skips it
    assert c.post(f"/api/experiments/{eid}/cancel", headers=csrf(c)).status_code == 409

    eid = create(c).get_json()["data"]["experiment"]["id"]
    app.config["EXPERIMENT_TRAIN_FN"] = lambda *a, **kw: fake_train(*a, **kw, cancel_at=40)
    assert jobs.run_one(eid) == "cancelled"
    exp = db.session.get(Experiment, eid)
    assert 0 < exp.progress < 0.3 and exp.finished_at and not exp.results
    assert db.session.query(ActivityEvent).filter_by(type="experiment.cancelled").count() == 2


def test_failed_run_keeps_the_error(app):
    c = app.test_client()
    signup(c)
    eid = create(c).get_json()["data"]["experiment"]["id"]
    app.config["EXPERIMENT_TRAIN_FN"] = lambda *a, **kw: fake_train(*a, **kw, fail_at=10)
    assert jobs.run_one(eid) == "failed"
    exp = c.get(f"/api/experiments/{eid}").get_json()["data"]["experiment"]
    assert exp["error"] == "RuntimeError: out of memory"
    assert create(c).status_code == 202                               # a failed run does not block a new one


def test_restart_marks_running_as_interrupted(app):
    c = app.test_client()
    signup(c)
    eid = create(c).get_json()["data"]["experiment"]["id"]
    db.session.get(Experiment, eid).status = "running"
    db.session.commit()
    assert jobs.mark_interrupted() == 1
    exp = db.session.get(Experiment, eid)
    assert exp.status == "interrupted" and "Run again" in exp.error
    assert db.session.query(ActivityEvent).one().type == "experiment.interrupted"


def test_runner_thread_trains_queued_experiments(app):
    import time
    c = app.test_client()
    signup(c)
    eid = create(c).get_json()["data"]["experiment"]["id"]
    runner = app.extensions["jobs"]
    runner.wake()
    for _ in range(100):
        db.session.expire_all()
        if db.session.get(Experiment, eid).status == "completed":
            break
        time.sleep(0.05)
    assert db.session.get(Experiment, eid).status == "completed" and runner.alive


def test_metrics_polling(app):
    c = app.test_client()
    signup(c)
    eid = create(c).get_json()["data"]["experiment"]["id"]
    r = c.get(f"/api/experiments/{eid}/metrics").get_json()
    assert r["data"] == [] and r["meta"]["complete"] is False and r["meta"]["status"] == "queued"
    jobs.run_one(eid)
    r = c.get(f"/api/experiments/{eid}/metrics").get_json()
    assert r["meta"]["complete"] and len(r["data"]) > 100
    last = r["data"][50]["id"]
    newer = c.get(f"/api/experiments/{eid}/metrics?after_id={last}").get_json()
    assert newer["data"][0]["id"] == last + 1 and len(newer["data"]) == len(r["data"]) - 51


def test_delete(app):
    c = app.test_client()
    signup(c)
    eid = create(c).get_json()["data"]["experiment"]["id"]
    db.session.get(Experiment, eid).status = "running"
    db.session.commit()
    r = c.delete(f"/api/experiments/{eid}", headers=csrf(c))
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "experiment_running"
    db.session.get(Experiment, eid).status = "queued"
    db.session.commit()
    jobs.run_one(eid)
    folder = app.config["RUNS_DIR"] / str(eid)
    assert folder.is_dir()
    assert c.delete(f"/api/experiments/{eid}", headers=csrf(c)).status_code == 204
    assert not folder.exists() and db.session.query(Metric).count() == 0 and db.session.query(Result).count() == 0
    assert db.session.query(ActivityEvent).one().experiment_id is None     # the event stays, unlinked


def test_list_filters_and_sorting(app):
    c = app.test_client()
    signup(c)
    ids = []
    for i, (name, replay) in enumerate([("alpha", True), ("beta", False), ("gamma", True)]):
        eid = create(c, name=name, replay=replay).get_json()["data"]["experiment"]["id"]
        if i < 2:
            jobs.run_one(eid)
        ids.append(eid)
    data = lambda q: c.get(f"/api/experiments?{q}").get_json()["data"]  # noqa: E731
    assert [e["name"] for e in data("")] == ["gamma", "beta", "alpha"]
    assert [e["name"] for e in data("sort=name&order=asc")] == ["alpha", "beta", "gamma"]
    assert [e["name"] for e in data("status=completed")] == ["beta", "alpha"]
    assert [e["name"] for e in data("replay=false")] == ["beta"]
    assert [e["name"] for e in data("search=ALP")] == ["alpha"]
    assert data("sort=qa_heldout")[-1]["name"] == "gamma"                 # no results yet: last
    assert c.get("/api/experiments?status=done").status_code == 400


def test_compare_and_export(app):
    c = app.test_client()
    signup(c)
    a = create(c, name="A, the first").get_json()["data"]["experiment"]["id"]
    jobs.run_one(a)
    b = create(c, name="B").get_json()["data"]["experiment"]["id"]
    jobs.run_one(b)
    r = c.get(f"/api/experiments/compare?ids={a},{b}").get_json()["data"]
    assert [e["id"] for e in r["experiments"]] == [a, b] and set(r["metrics"]) == {str(a), str(b)}
    assert c.get(f"/api/experiments/compare?ids={a}").status_code == 400
    assert c.get("/api/experiments/compare?ids=1,2,3,4,5").status_code == 400
    assert c.get("/api/experiments/compare?ids=a,b").status_code == 400

    r = c.get(f"/api/experiments/{a}/export.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert f'experiment-{a}-a--the-first.csv' in r.headers["Content-Disposition"]
    text = r.get_data(as_text=True)
    assert text.startswith("phase,step,train_loss,val_loss\n") and "lora,1.0,0.95,0.95" in text
    assert text.splitlines()[1] == "pretrain,0,6.98148,7.60000"


@pytest.mark.skipif(not os.environ.get("RUN_SLOW"), reason="real training takes about a minute; set RUN_SLOW=1")
def test_real_training_run(tmp_path):
    """The real engine through the real runner (no evaluation, to keep it to about a minute)."""
    app = build_app(tmp_path, RUNS_DIR=tmp_path / "runs", EXPERIMENT_EVALUATE=False)
    with app.app_context():
        upgrade()
        c = app.test_client()
        signup(c)
        eid = create(c, pretrain_steps=50, finetune_steps=20).get_json()["data"]["experiment"]["id"]
        assert jobs.run_one(eid) == "completed"
        assert db.session.query(Metric).filter_by(experiment_id=eid, phase="pretrain").count() == 50
        assert db.session.query(Metric).filter(Metric.val_loss.isnot(None)).count() >= 2
        assert (tmp_path / "runs" / str(eid) / "finetuned_lora_merged.npz").is_file()
        db.session.remove()
        db.engine.dispose()
