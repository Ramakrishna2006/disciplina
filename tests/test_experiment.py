"""
Experiment-pipeline tests (llm/experiment.py, used by the CLI and the web app):
  * run_experiment gives bit-identical weights to the original step-by-step recipe
  * its tokenizer is identical to the published one in artifacts/
  * progress is reported in order and reaches 100%, and a run can be cancelled
  * invalid settings are rejected
Uses a tiny config, so it runs in about 30 s.  Run:  python tests/test_experiment.py
"""
import copy
import json
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from llm.data import build_world, pretraining_corpus, qa_examples  # noqa: E402
from llm.experiment import (MODELS, PHASES, PRESETS, ExperimentCancelled, ExperimentConfig,  # noqa: E402
                            load_run, run_experiment)
from llm.model import GPT, GPTConfig  # noqa: E402
from llm.tokenizer import BPETokenizer  # noqa: E402
from llm.training import finetune, pretrain  # noqa: E402

quiet = lambda *_: None  # noqa: E731
TINY = ExperimentConfig(pretrain_steps=4, pretrain_warmup=2, eval_every=4, finetune_steps=3, evaluate=False)


def original_recipe(c):
    """The training steps exactly as main.py ran them before the refactor (for comparison)."""
    world, train_p, _ = build_world(seed=0)
    corpus, val = pretraining_corpus(world, 4000, seed=1), pretraining_corpus(world, 300, seed=2)
    qa_text = "\n".join(p + ans for p, ans, *_ in qa_examples(world, list(world)))
    tok = BPETokenizer().train(corpus + qa_text, vocab_size=2048)
    tr, va = (np.array(tok.encode(t), dtype=np.int64) for t in (corpus, val))
    base = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=4, n_head=4, n_embd=96), seed=0)
    pretrain(base, tr, va, steps=c.pretrain_steps, batch_size=16, lr=3e-3, warmup=c.pretrain_warmup,
             eval_every=c.eval_every, log=quiet)
    models, sft = {"base": base}, qa_examples(world, train_p, seed=5)
    for name, lr in [("full-FT", 5e-4), ("LoRA", 3e-3)]:
        m = copy.deepcopy(base)
        if name == "LoRA":
            m.add_lora(rank=8, alpha=16, targets=("qkv", "proj", "fc", "fc2"))
        finetune(m, sft, tok, steps=c.finetune_steps, batch_size=32, lr=lr, log=quiet, log_every=20, replay_tokens=tr)
        m.merge_lora()
        models[name] = m
    return models


with tempfile.TemporaryDirectory() as d:
    events = []
    results = run_experiment(TINY, d, on_progress=lambda ph, fr, info: events.append((ph, fr, info)), log=quiet)
    tok, models = load_run(d)
    reference = original_recipe(TINY)
    for name in MODELS:
        a, b = models[name].params, reference[name].params
        assert a.keys() == b.keys(), name
        assert all(np.array_equal(a[k], b[k]) for k in a), f"{name}: weights differ from the original recipe"
    print(f"same weights   : base, full-FT and LoRA identical to the original recipe ({len(a)} tensors each)  OK")

    with open(os.path.join(d, "tokenizer.json"), encoding="utf-8") as f1, \
            open(os.path.join(ROOT, "artifacts", "tokenizer.json"), encoding="utf-8") as f2:
        assert json.load(f1) == json.load(f2), "tokenizer differs from the published one"
    print("same tokenizer : identical to artifacts/tokenizer.json  OK")

    with open(os.path.join(d, "results.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["config"] == json.loads(json.dumps(results["config"])) and len(saved["finetuning"]) == 2
    for fname in ["pretraining_loss.svg", "finetuning_loss.svg", "embeddings_pca.svg"]:
        assert os.path.getsize(os.path.join(d, fname)) > 0, fname
    print("files          : tokenizer, 3 models, 3 charts and results.json (with config) written  OK")

    phases = [e[0] for e in events]
    fractions = [e[1] for e in events]
    assert [p for p in PHASES if p in phases] == list(dict.fromkeys(phases)) == list(PHASES), phases
    assert fractions == sorted(fractions) and fractions[0] == 0 and fractions[-1] == 1.0
    steps = TINY.pretrain_steps + 2 * TINY.finetune_steps
    assert sum(1 for e in events if "step" in e[2]) == steps
    print(f"progress       : {len(events)} updates, phases in order, 0% -> 100%, {steps} training steps  OK")

with tempfile.TemporaryDirectory() as d:
    calls = []

    def stop_after_three():
        calls.append(1)
        return len(calls) > 3

    try:
        run_experiment(TINY, d, should_stop=stop_after_three, log=quiet)
        raise AssertionError("run was not cancelled")
    except ExperimentCancelled:
        pass
    assert not os.path.exists(os.path.join(d, MODELS["base"])), "cancelled during pre-training: no model saved"
    print("cancel         : run stops during pre-training when should_stop() is True  OK")

for bad in [dict(lora_rank=0), dict(pretrain_steps=-5), dict(finetune_steps=1.5), dict(seed=True)]:
    try:
        ExperimentConfig(**bad)
        raise AssertionError(f"accepted invalid config {bad}")
    except ValueError:
        pass
assert ExperimentConfig.from_dict({"lora_rank": 4, "unknown": 1}).lora_rank == 4
assert PRESETS["full"] == ExperimentConfig() and PRESETS["quick"].pretrain_steps == 150
print("validation     : bad settings rejected, unknown keys ignored, presets defined  OK")
