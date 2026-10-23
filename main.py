"""
Disciplina -- a GPT-style language model trained from scratch in pure NumPy.
(Latin "disciplina": training, instruction; from "discere", to learn.)

  python main.py train [--preset full|short|quick]   data + tokenizer -> pre-train -> fine-tune -> evaluate  (~30 min)
  python main.py eval              inspect the saved models: tokens, embeddings, prompting, scores     (~1 min)
  python main.py chat [--base]     talk to the fine-tuned model (--base: the pre-trained model, raw text)
  python main.py data              export the dataset to data/ and DATASET.md
  python main.py test              run all tests: backprop maths, tokenizer, trained-model accuracy, pipeline (~2 min)

Add --dir <folder> to use a folder other than artifacts/ (e.g. `train --quick --dir test_run`).
"""
import argparse
import os
import subprocess
import sys
from dataclasses import replace

import numpy as np

from llm.data import qa_prompt
from llm.dataset import export
from llm.evaluate import complete
from llm.experiment import MODELS, PRESETS, evaluate, load_run, run_experiment
from llm.model import GPT
from llm.tokenizer import BPETokenizer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "Disciplina"
BANNER = f"{NAME} · a language model trained from scratch in pure NumPy"
LOG = []


def log(s=""):
    print(s, flush=True)
    LOG.append(s)


# ----------------------------------------------------------------------------- train
def train(a):
    """The whole recipe lives in llm/experiment.py (shared with the web app); this only picks the settings."""
    config = replace(PRESETS["quick" if a.quick else a.preset], replay=not a.no_replay)
    log(f"preset {'quick' if a.quick else a.preset}: {config}")
    log(f"dataset exported to {os.path.relpath(export(ROOT), ROOT)}/")
    results = run_experiment(config, a.dir, log=log)
    log(f"\ntotal time: {results['minutes']} min; results in {os.path.relpath(a.dir, ROOT)}/")
    with open(os.path.join(a.dir, "run_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))


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
    for t in ["test_gradients", "test_tokenizer", "test_model", "test_experiment"]:
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
    sub.choices["train"].add_argument("--preset", choices=list(PRESETS), default="full",
                                      help="full ~30-40 min, short ~10 min, quick ~5 min")
    sub.choices["train"].add_argument("--quick", action="store_true", help="same as --preset quick")
    sub.choices["train"].add_argument("--no-replay", action="store_true", help="ablation: fine-tune without replay")
    sub.choices["chat"].add_argument("--base", action="store_true", help="use the pre-trained model (raw text)")
    sub.choices["chat"].add_argument("--temperature", type=float, default=0.0)
    sub.choices["chat"].add_argument("--top_k", type=int, default=None)
    a = ap.parse_args()
    if a.cmd in ("train", "eval", "test"):
        print(BANNER, flush=True)
    {"train": train, "chat": chat, "test": test,
     "eval": lambda a: evaluate(*load_run(a.dir)),
     "data": lambda a: print(f"dataset written to {os.path.relpath(export(ROOT))}/ and DATASET.md")}[a.cmd](a)
