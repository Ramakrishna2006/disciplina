"""Evaluation: perplexity, exact-match accuracy on QA, and decoding helpers."""
import numpy as np


def perplexity(model, tokens, batch_size=16, max_batches=None):
    """exp(average next-token cross-entropy) on non-overlapping windows. Lower = better.
    A perplexity of k means the model is, on average, as unsure as picking among k tokens."""
    T = model.cfg.block_size
    n_win = (len(tokens) - 1) // T
    starts = np.arange(n_win) * T
    if max_batches:
        starts = starts[: batch_size * max_batches]
    total, count = 0.0, 0
    for i in range(0, len(starts), batch_size):
        s = starts[i:i + batch_size]
        x = np.stack([tokens[j:j + T] for j in s])
        y = np.stack([tokens[j + 1:j + T + 1] for j in s])
        _, loss = model.forward(x, y, keep_cache=False)
        total += loss * x.size
        count += x.size
    return float(np.exp(total / count))


def complete(model, tok, prompt, max_new_tokens=6, **kw):
    ids = tok.encode(prompt)
    out = model.generate(ids, max_new_tokens=max_new_tokens, stop_ids=(tok.eot_id,), **kw)
    return tok.decode([t for t in out[len(ids):] if t != tok.eot_id])


def first_word(text):
    """Normalise a generated answer: 'a doctor.\\nQ:' -> 'doctor'."""
    words = text.replace("\n", " ").replace(".", " ").replace(",", " ").split()
    words = [w for w in words if w.lower() not in ("a", "an", "the", "in")]
    return words[0].lower() if words else ""


def qa_accuracy(model, tok, items, prompt_fn, return_rows=False):
    """
    items: (question_prompt, gold_answer, attr, name) tuples.
    prompt_fn(item) -> the actual text sent to the model (lets us compare prompt styles).
    """
    rows, correct = [], 0
    by_attr = {}
    for it in items:
        gen = complete(model, tok, prompt_fn(it))
        ok = first_word(gen) == it[1].strip().lower()
        correct += ok
        by_attr.setdefault(it[2], []).append(ok)
        rows.append({"prompt": prompt_fn(it), "gold": it[1].strip(), "generated": gen, "correct": ok})
    acc = correct / max(1, len(items))
    per_attr = {a: float(np.mean(v)) for a, v in by_attr.items()}
    return (acc, per_attr, rows) if return_rows else (acc, per_attr)
