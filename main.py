"""
Disciplina -- a GPT-style language model trained from scratch in pure NumPy.
(Latin "disciplina": training, instruction; from "discere", to learn.)

  python main.py train [--quick]   data + tokenizer -> pre-train -> fine-tune (full + LoRA) -> evaluate  (~30 min)
  python main.py eval              inspect the saved models: tokens, embeddings, prompting, scores     (~1 min)
  python main.py chat [--base]     talk to the fine-tuned model (--base: the pre-trained model, raw text)
  python main.py data              export the dataset to data/ and DATASET.md
  python main.py test              run all tests: backprop maths, tokenizer, trained-model accuracy (~1 min)

Add --dir <folder> to use a folder other than artifacts/ (e.g. `train --quick --dir test_run`).
"""
import argparse
import copy
import json
import os
import subprocess
import sys
import time

import numpy as np

from llm.data import ATTRS, build_world, pretraining_corpus, qa_examples, qa_prompt
from llm.dataset import export, splits
from llm.embeddings import category_cohesion, nearest_neighbors, pca_svg
from llm.evaluate import complete, perplexity, qa_accuracy
from llm.model import GPT, GPTConfig
from llm.plots import line_chart_svg
from llm.prompts import PROMPT_STYLES, prompt_functions
from llm.tokenizer import BPETokenizer
from llm.training import finetune, pretrain

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "Disciplina"
BANNER = f"{NAME} · a language model trained from scratch in pure NumPy"
MODELS = {"base": "base_model.npz", "full-FT": "finetuned_full.npz", "LoRA": "finetuned_lora_merged.npz"}
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(s)


def section(title):
    log(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def load(d):
    return BPETokenizer.load(os.path.join(d, "tokenizer.json")), {k: GPT.load(os.path.join(d, f)) for k, f in MODELS.items()}


# ----------------------------------------------------------------------------- train
def train(a):
    t0, d, Q = time.time(), a.dir, a.quick
    os.makedirs(d, exist_ok=True)
    section("1. DATA + TOKENIZER")
    world, train_p, _ = build_world(seed=0)
    corpus, val = pretraining_corpus(world, 4000, seed=1), pretraining_corpus(world, 300, seed=2)
    qa_text = "\n".join(p + ans for p, ans, *_ in qa_examples(world, list(world)))
    tok = BPETokenizer().train(corpus + qa_text, vocab_size=2048)
    tok.save(os.path.join(d, "tokenizer.json"))
    tr, va = (np.array(tok.encode(t), dtype=np.int64) for t in (corpus, val))
    log(f"{len(corpus):,} chars -> {len(tr):,} tokens, vocab {tok.vocab_size}; dataset exported to "
        f"{os.path.relpath(export(ROOT), ROOT)}/")

    section("2. PRE-TRAINING (next-token prediction)")
    base = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=4, n_head=4, n_embd=96), seed=0)
    log(f"{base.num_params():,} parameters; untrained perplexity {perplexity(base, va):.1f}")
    h_pre = pretrain(base, tr, va, steps=150 if Q else 2000, batch_size=16, lr=3e-3,
                     warmup=50 if Q else 100, eval_every=25 if Q else 100, log=log)
    base.save(os.path.join(d, MODELS["base"]))

    section(f"3. FINE-TUNING on Q&A {'WITHOUT' if a.no_replay else 'with'} replay (full vs LoRA)")
    sft, steps, hist = qa_examples(world, train_p, seed=5), 60 if Q else 400, {}
    for name, lr in [("full-FT", 5e-4), ("LoRA", 3e-3)]:
        m = copy.deepcopy(base)
        if name == "LoRA":
            m.add_lora(rank=8, alpha=16, targets=("qkv", "proj", "fc", "fc2"))
        log(f"\n{name}: {m.num_params(True):,} trainable of {m.num_params():,} parameters")
        hist[name] = finetune(m, sft, tok, steps=steps, batch_size=32, lr=lr, log=log, log_every=20,
                              replay_tokens=None if a.no_replay else tr)   # replay: stops forgetting
        m.merge_lora()
        m.save(os.path.join(d, MODELS[name]))

    line_chart_svg(os.path.join(d, "pretraining_loss.svg"),
                   {"train": ([h["step"] for h in h_pre], [h["train_loss"] for h in h_pre]),
                    "validation": ([h["step"] for h in h_pre], [h["val_loss"] for h in h_pre])},
                   "Pre-training loss", "step", "cross-entropy")
    line_chart_svg(os.path.join(d, "finetuning_loss.svg"),
                   {k: ([h["step"] for h in v], [h["loss"] for h in v]) for k, v in hist.items()},
                   "Fine-tuning loss (answers + replayed text)", "step", "cross-entropy")
    pca_svg(base, tok, dict(ATTRS), os.path.join(d, "embeddings_pca.svg"))
    results = report(*load(d))
    results.update(pretraining=h_pre, finetuning=hist, minutes=round((time.time() - t0) / 60, 1))
    log(f"\ntotal time: {results['minutes']} min; results in {os.path.relpath(d, ROOT)}/")
    with open(os.path.join(d, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    with open(os.path.join(d, "run_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))


# ----------------------------------------------------------------------------- evaluate
def report(tok, models):
    s, base = splits(), models["base"]
    world, held = s["world"], s["test"]
    seen = qa_examples(world, s["train_people"], seed=4, all_templates=False)
    va = np.array(tok.encode("<|endoftext|>".join(s["val"]) + "<|endoftext|>"))
    pf = prompt_functions(world, s["train_people"])

    section("TOKENIZER")
    for t in ["Asha lives in Pune.", "asha lives in pune.", "Bengaluru is new!"]:
        log(f"  {t!r:24} -> {tok.token_strings(tok.encode(t))}")

    section("EMBEDDINGS (base model)")
    within, between = category_cohesion(base, tok, dict(ATTRS))
    log(f"  cosine similarity: same category {within:+.2f}, different category {between:+.2f}")
    for w in ["Pune", "teacher", "biryani"]:
        log(f"  nearest to {w!r:9}: " + ", ".join(f"{x} ({c:.2f})" for x, c in nearest_neighbors(base, tok, w, 4)))

    section("PROMPT ENGINEERING (base model, held-out people)")
    prompting = {st: qa_accuracy(base, tok, held, pf[st])[0] for st in PROMPT_STYLES}
    for st in PROMPT_STYLES:
        log(f"  {st:10} {prompting[st]:5.0%}   {pf[st](held[0])!r:.60} -> {complete(base, tok, pf[st](held[0]))!r}")
    rng = np.random.default_rng(0)
    for name, kw in [("greedy", {}), ("T=0.8,k=10", dict(temperature=0.8, top_k=10)), ("T=2.0", dict(temperature=2.0))]:
        log(f"  {name:10} 'Meera' -> {complete(base, tok, 'Meera', max_new_tokens=14, rng=rng, **kw)!r}")

    section("EVALUATION (each row takes ~10-30 s on a laptop)")
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


# ----------------------------------------------------------------------------- chat
def chat(a):
    tok, m = BPETokenizer.load(os.path.join(a.dir, "tokenizer.json")), GPT.load(os.path.join(a.dir, MODELS["base" if a.base else "LoRA"]))
    rng = np.random.default_rng()
    print(f"{BANNER}\n{'base model: type the start of a sentence' if a.base else 'ask about any of the 40 people'}. Ctrl-C to quit.")
    while True:
        try:
            text = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text:
            out = complete(m, tok, text if a.base else qa_prompt(text), max_new_tokens=20 if a.base else 6,
                           temperature=a.temperature, top_k=a.top_k, rng=rng)
            print("disciplina>", out.split("\n")[0].strip())


# ----------------------------------------------------------------------------- test
def test(a):
    for t in ["test_gradients", "test_tokenizer", "test_model"]:
        print(f"\n--- tests/{t}.py", flush=True)
        if subprocess.call([sys.executable, os.path.join(ROOT, "tests", f"{t}.py")]):
            sys.exit(f"\nFAILED: tests/{t}.py")
    print(f"\nALL TESTS PASSED ({NAME})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ["train", "eval", "chat", "data", "test"]:
        p = sub.add_parser(cmd)
        p.add_argument("--dir", default=os.path.join(ROOT, "artifacts"), help="where models are saved / loaded")
    sub.choices["train"].add_argument("--quick", action="store_true", help="3-minute smoke test")
    sub.choices["train"].add_argument("--no-replay", action="store_true", help="ablation: fine-tune without replay")
    sub.choices["chat"].add_argument("--base", action="store_true", help="use the pre-trained model (raw text)")
    sub.choices["chat"].add_argument("--temperature", type=float, default=0.0)
    sub.choices["chat"].add_argument("--top_k", type=int, default=None)
    a = ap.parse_args()
    if a.cmd in ("train", "eval", "test"):
        print(BANNER, flush=True)
    {"train": train, "chat": chat, "test": test,
     "eval": lambda a: report(*load(a.dir)),
     "data": lambda a: print(f"dataset written to {os.path.relpath(export(ROOT))}/ and DATASET.md")}[a.cmd](a)
