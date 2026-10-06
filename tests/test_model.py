"""
Model tests: check the TRAINED models in artifacts/ against the dataset.

  1. every held-out question (60) is answered correctly by both fine-tuned models
  2. fine-tuning did not cause forgetting: completion prompts 100%, perplexity within 2% of the base model
  3. the base model knows the facts but cannot answer questions (why fine-tuning is needed)
  4. answers stop cleanly after one word (the model learned the <|endoftext|> stop token)
  5. a few hand-written cases, including lowercase input

Run:  python tests/test_model.py      (about 1 minute)
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from llm.dataset import splits  # noqa: E402
from llm.data import qa_prompt  # noqa: E402
from llm.evaluate import complete, perplexity, qa_accuracy  # noqa: E402
from llm.model import GPT  # noqa: E402
from llm.prompts import prompt_functions  # noqa: E402
from llm.tokenizer import EOT, BPETokenizer  # noqa: E402

A = os.path.join(ROOT, "artifacts")
tok = BPETokenizer.load(os.path.join(A, "tokenizer.json"))
base, full, lora = (GPT.load(os.path.join(A, f)) for f in
                    ("base_model.npz", "finetuned_full.npz", "finetuned_lora_merged.npz"))
s = splits()
pf = prompt_functions(s["world"], s["train_people"])
val = np.array(tok.encode(EOT.join(s["val"]) + EOT))

base_ppl = perplexity(base, val)
for name, m in [("full fine-tune", full), ("LoRA fine-tune", lora)]:
    acc, _, rows = qa_accuracy(m, tok, s["test"], pf["zero-shot"], return_rows=True)
    wrong = [r for r in rows if not r["correct"]]
    assert acc == 1.0, f"{name}: wrong answers {wrong[:3]}"
    assert all(len(r["generated"].split()) == 1 for r in rows), f"{name}: answers do not stop after one word"
    comp = qa_accuracy(m, tok, s["test"], pf["completion"])[0]
    ppl = perplexity(m, val)
    assert comp == 1.0 and ppl < base_ppl * 1.02, f"{name}: forgetting (completion {comp:.0%}, ppl {ppl:.2f})"
    print(f"{name:15}: {len(rows)}/{len(rows)} held-out answers correct, one word each; "
          f"no forgetting (completion {comp:.0%}, perplexity {ppl:.2f} vs base {base_ppl:.2f})  OK")

assert qa_accuracy(base, tok, s["test"], pf["zero-shot"])[0] == 0.0
assert qa_accuracy(base, tok, s["test"], pf["completion"])[0] == 1.0
print("base model     : knows every fact as text (100%) but answers no questions (0%)  OK")

cases = [("Where does Asha live?", "Indore"), ("What is the job of Ravi?", "engineer"),
         ("What food does Meera like?", "apples"), ("Which city is Leela from?", "Surat"),
         ("where does asha live?", "Indore")]
for q, want in cases:
    got = complete(lora, tok, qa_prompt(q)).strip()
    assert got == want, f"{q!r}: expected {want!r}, got {got!r}"
print(f"hand-written   : {len(cases)} questions (incl. lowercase) answered exactly  OK")
