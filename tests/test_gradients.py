"""
Gradient check: compares the hand-written backward pass against numerical finite differences.
If backprop has a bug, the relative error explodes. Run:  python tests/test_gradients.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm.model import GPT, GPTConfig  # noqa: E402


def check(model, idx, tgt, mask, n_checks=6, eps=1e-5, tol=1e-5, seed=0):
    rng = np.random.default_rng(seed)
    model.forward(idx, tgt, mask)
    grads = model.backward()
    worst, checked = 0.0, 0
    for name, g in grads.items():
        p = model.params[name]
        for _ in range(n_checks):
            i = tuple(rng.integers(0, s) for s in p.shape)
            old = p[i]
            p[i] = old + eps; _, lp = model.forward(idx, tgt, mask, keep_cache=False)
            p[i] = old - eps; _, lm = model.forward(idx, tgt, mask, keep_cache=False)
            p[i] = old
            num = (lp - lm) / (2 * eps)
            if abs(num) + abs(g[i]) < 1e-7:       # both ~0 (e.g. masked position): skip
                continue
            rel = abs(num - g[i]) / (abs(num) + abs(g[i]))
            worst = max(worst, rel)
            checked += 1
    assert worst < tol, f"gradient check failed, worst relative error {worst:.2e}"
    return worst, checked


if __name__ == "__main__":
    cfg = GPTConfig(vocab_size=23, block_size=8, n_layer=2, n_head=2, n_embd=16, dtype="float64")
    rng = np.random.default_rng(0)
    idx = rng.integers(0, 23, (3, 8))
    tgt = rng.integers(0, 23, (3, 8))
    mask = (rng.random((3, 8)) > 0.4).astype(np.float64)

    m = GPT(cfg, seed=0)
    for k in m.params:                 # randomise so LN / biases aren't trivially 1/0
        m.params[k] = m.params[k] + rng.standard_normal(m.params[k].shape) * 0.1
    w, n = check(m, idx, tgt, mask)
    print(f"full model     : {n} gradients checked, worst rel. error {w:.1e}  OK")

    m.add_lora(rank=4, alpha=8, targets=("qkv", "proj", "fc", "fc2"))
    for k in m.params:
        if "lora_B" in k:              # B starts at zero; perturb it so A gets a gradient too
            m.params[k] += rng.standard_normal(m.params[k].shape) * 0.1
    w, n = check(m, idx, tgt, mask)
    print(f"LoRA adapters  : {n} gradients checked, worst rel. error {w:.1e}  OK")

    logits_before, _ = m.forward(idx, keep_cache=False)
    m.merge_lora()
    logits_after, _ = m.forward(idx, keep_cache=False)
    assert np.allclose(logits_before, logits_after)
    print("LoRA merge     : outputs identical after folding adapters into weights  OK")
