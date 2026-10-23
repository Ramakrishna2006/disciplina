"""
One experiment = the whole Disciplina recipe with one set of settings:

    data + tokenizer -> pre-train -> fine-tune (full and LoRA) -> charts -> evaluation

Both the CLI (`python main.py train`) and the web app (Disciplina Studio) call `run_experiment`,
so there is exactly one implementation of the training pipeline. The default config reproduces
the published models bit for bit (tests/test_experiment.py checks this).
"""
import copy
import json
import os
import time
from dataclasses import asdict, dataclass, fields

import numpy as np

from .data import ATTRS, build_world, pretraining_corpus, qa_examples
from .dataset import splits
from .embeddings import category_cohesion, nearest_neighbors, pca_svg
from .evaluate import complete, perplexity, qa_accuracy
from .model import GPT, GPTConfig
from .plots import line_chart_svg
from .prompts import PROMPT_STYLES, prompt_functions
from .tokenizer import BPETokenizer
from .training import finetune, pretrain

MODELS = {"base": "base_model.npz", "full-FT": "finetuned_full.npz", "LoRA": "finetuned_lora_merged.npz"}
PHASES = ("data", "pretrain", "finetune-full", "finetune-lora", "evaluate")


@dataclass
class ExperimentConfig:
    """Every setting a user can change. The defaults are the published "full" run."""
    pretrain_steps: int = 2000
    pretrain_warmup: int = 100
    eval_every: int = 100
    finetune_steps: int = 400
    lora_rank: int = 8
    lora_alpha: int = 16
    replay: bool = True
    seed: int = 0              # model initialisation and batch sampling (the dataset itself is fixed)
    evaluate: bool = True      # run the evaluation report at the end (~1 min)

    def __post_init__(self):
        limits = {"pretrain_steps": (1, 5000), "pretrain_warmup": (0, 1000), "eval_every": (1, 5000),
                  "finetune_steps": (1, 2000), "lora_rank": (1, 32), "lora_alpha": (1, 128), "seed": (0, 10**6)}
        for name, (lo, hi) in limits.items():
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                raise ValueError(f"{name} must be an integer from {lo} to {hi}, got {v!r}")

    @classmethod
    def from_dict(cls, d):
        """Build a config from JSON, ignoring unknown keys (e.g. from an older app version)."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


PRESETS = {   # approximate laptop CPU times
    "full": ExperimentConfig(),                                                          # 30-40 min
    "short": ExperimentConfig(pretrain_steps=600, finetune_steps=150, eval_every=50),    # 8-12 min
    "quick": ExperimentConfig(pretrain_steps=150, pretrain_warmup=50, eval_every=25,
                              finetune_steps=60),                                        # 4-7 min
}


class ExperimentCancelled(Exception):
    """Raised inside a run when `should_stop()` returns True."""


def run_experiment(config, out_dir, on_progress=None, should_stop=None, log=print):
    """
    Train everything into `out_dir` and return the results dict (also saved as results.json).

    on_progress(phase, fraction, info): optional; phase is one of PHASES, fraction goes 0 -> 1,
        info has step / steps / loss while training.
    should_stop(): optional; checked after every step. If it returns True the run stops with
        ExperimentCancelled (files written so far stay in out_dir).
    """
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    total = config.pretrain_steps + 2 * config.finetune_steps
    done = 0                                     # training steps finished across all phases

    def progress(phase, info=None):
        if on_progress:
            on_progress(phase, done / total if phase != "evaluate" else 1.0, info or {})

    def check():
        if should_stop and should_stop():
            raise ExperimentCancelled("cancelled by user")

    def stepper(phase):
        def on_step(step, steps, loss):
            nonlocal done
            done += 1
            progress(phase, {"step": step + 1, "steps": steps, "loss": float(loss)})
            check()
        return on_step

    # 1. data + tokenizer
    progress("data")
    _section(log, "1. DATA + TOKENIZER")
    world, train_p, _ = build_world(seed=0)
    corpus, val = pretraining_corpus(world, 4000, seed=1), pretraining_corpus(world, 300, seed=2)
    qa_text = "\n".join(p + ans for p, ans, *_ in qa_examples(world, list(world)))
    tok = BPETokenizer().train(corpus + qa_text, vocab_size=2048)
    tok.save(os.path.join(out_dir, "tokenizer.json"))
    tr, va = (np.array(tok.encode(t), dtype=np.int64) for t in (corpus, val))
    log(f"{len(corpus):,} chars -> {len(tr):,} tokens, vocab {tok.vocab_size}")
    check()

    # 2. pre-training
    _section(log, "2. PRE-TRAINING (next-token prediction)")
    base = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=4, n_head=4, n_embd=96), seed=config.seed)
    log(f"{base.num_params():,} parameters; untrained perplexity {perplexity(base, va):.1f}")
    h_pre = pretrain(base, tr, va, steps=config.pretrain_steps, batch_size=16, lr=3e-3, warmup=config.pretrain_warmup,
                     eval_every=config.eval_every, seed=config.seed, log=log, on_step=stepper("pretrain"))
    base.save(os.path.join(out_dir, MODELS["base"]))

    # 3. fine-tuning: full vs LoRA, from the same base model
    _section(log, f"3. FINE-TUNING on Q&A {'with' if config.replay else 'WITHOUT'} replay (full vs LoRA)")
    sft, hist = qa_examples(world, train_p, seed=5), {}
    for name, lr, phase in [("full-FT", 5e-4, "finetune-full"), ("LoRA", 3e-3, "finetune-lora")]:
        m = copy.deepcopy(base)
        if name == "LoRA":
            m.add_lora(rank=config.lora_rank, alpha=config.lora_alpha, targets=("qkv", "proj", "fc", "fc2"))
        log(f"\n{name}: {m.num_params(True):,} trainable of {m.num_params():,} parameters")
        hist[name] = finetune(m, sft, tok, steps=config.finetune_steps, batch_size=32, lr=lr, seed=config.seed,
                              log=log, log_every=20, replay_tokens=tr if config.replay else None,  # replay: stops forgetting
                              on_step=stepper(phase))
        m.merge_lora()
        m.save(os.path.join(out_dir, MODELS[name]))

    # 4. charts + evaluation
    progress("evaluate")
    line_chart_svg(os.path.join(out_dir, "pretraining_loss.svg"),
                   {"train": ([h["step"] for h in h_pre], [h["train_loss"] for h in h_pre]),
                    "validation": ([h["step"] for h in h_pre], [h["val_loss"] for h in h_pre])},
                   "Pre-training loss", "step", "cross-entropy")
    line_chart_svg(os.path.join(out_dir, "finetuning_loss.svg"),
                   {k: ([h["step"] for h in v], [h["loss"] for h in v]) for k, v in hist.items()},
                   "Fine-tuning loss (answers + replayed text)", "step", "cross-entropy")
    pca_svg(base, tok, dict(ATTRS), os.path.join(out_dir, "embeddings_pca.svg"))
    results = evaluate(*load_run(out_dir), log=log) if config.evaluate else {}
    results.update(config=asdict(config), pretraining=h_pre, finetuning=hist, minutes=round((time.time() - t0) / 60, 1))
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    return results


def load_run(d):
    """Tokenizer and the three models saved by a run."""
    return BPETokenizer.load(os.path.join(d, "tokenizer.json")), {k: GPT.load(os.path.join(d, f)) for k, f in MODELS.items()}


def _section(log, title):
    log(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def evaluate(tok, models, log=print):
    """The evaluation report: tokenizer, embeddings, prompting, and the accuracy/perplexity table."""
    s, base = splits(), models["base"]
    world, held = s["world"], s["test"]
    seen = qa_examples(world, s["train_people"], seed=4, all_templates=False)
    va = np.array(tok.encode("<|endoftext|>".join(s["val"]) + "<|endoftext|>"))
    pf = prompt_functions(world, s["train_people"])

    _section(log, "TOKENIZER")
    for t in ["Asha lives in Pune.", "asha lives in pune.", "Bengaluru is new!"]:
        log(f"  {t!r:24} -> {tok.token_strings(tok.encode(t))}")

    _section(log, "EMBEDDINGS (base model)")
    within, between = category_cohesion(base, tok, dict(ATTRS))
    log(f"  cosine similarity: same category {within:+.2f}, different category {between:+.2f}")
    for w in ["Pune", "teacher", "biryani"]:
        log(f"  nearest to {w!r:9}: " + ", ".join(f"{x} ({c:.2f})" for x, c in nearest_neighbors(base, tok, w, 4)))

    _section(log, "PROMPT ENGINEERING (base model, held-out people)")
    prompting = {st: qa_accuracy(base, tok, held, pf[st])[0] for st in PROMPT_STYLES}
    for st in PROMPT_STYLES:
        log(f"  {st:10} {prompting[st]:5.0%}   {pf[st](held[0])!r:.60} -> {complete(base, tok, pf[st](held[0]))!r}")
    rng = np.random.default_rng(0)
    for name, kw in [("greedy", {}), ("T=0.8,k=10", dict(temperature=0.8, top_k=10)), ("T=2.0", dict(temperature=2.0))]:
        log(f"  {name:10} 'Meera' -> {complete(base, tok, 'Meera', max_new_tokens=14, rng=rng, **kw)!r}")

    _section(log, "EVALUATION (each row takes ~10-30 s on a laptop)")
    table = {}
    log(f"  {'model':8} | {'QA seen':>7} | {'QA held-out':>11} | {'completion':>10} | {'perplexity':>10}")
    for name, m in models.items():
        acc, per, rows = qa_accuracy(m, tok, held, pf["zero-shot"], return_rows=True)
        r = table[name] = dict(qa_seen=qa_accuracy(m, tok, seen, pf["zero-shot"])[0], qa_heldout=acc, per_attr=per,
                               completion=qa_accuracy(m, tok, held, pf["completion"])[0], val_ppl=perplexity(m, va))
        log(f"  {name:8} | {r['qa_seen']:7.0%} | {r['qa_heldout']:11.0%} | {r['completion']:10.0%} | {r['val_ppl']:10.2f}")
    log("\n  held-out examples (LoRA):")
    for r in rows[:6]:
        log(f"  {'✓' if r['correct'] else '✗'} {r['prompt'].splitlines()[0]:42} -> {r['generated'].strip():9} (truth {r['gold']})")
    return dict(embeddings=dict(within=within, between=between), prompting=prompting, evaluation=table)
