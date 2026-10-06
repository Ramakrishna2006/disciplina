"""Training loops: next-token pre-training and supervised (instruction) fine-tuning."""
import time

import numpy as np

from .model import AdamW, cosine_lr


# ----------------------------------------------------------------------------- pre-training
def lm_batch(tokens, batch_size, block_size, rng):
    """Random windows of the token stream. Target = input shifted by one (next-token prediction)."""
    ix = rng.integers(0, len(tokens) - block_size - 1, batch_size)
    x = np.stack([tokens[i:i + block_size] for i in ix])
    y = np.stack([tokens[i + 1:i + block_size + 1] for i in ix])
    return x, y


def pretrain(model, train_tokens, val_tokens, steps=2000, batch_size=32, lr=3e-3,
             warmup=100, eval_every=250, seed=0, log=print):
    rng = np.random.default_rng(seed)
    opt = AdamW(model, lr=lr, weight_decay=0.1)
    T = model.cfg.block_size
    history, t0 = [], time.time()
    for step in range(steps):
        x, y = lm_batch(train_tokens, batch_size, T, rng)
        _, loss = model.forward(x, y)
        grads = model.backward()
        gnorm = opt.step(grads, lr=cosine_lr(step, steps, lr, warmup))
        if step % eval_every == 0 or step == steps - 1:
            from .evaluate import perplexity
            vl = np.log(perplexity(model, val_tokens, max_batches=8))
            history.append({"step": step, "train_loss": loss, "val_loss": vl})
            log(f"  step {step:5d} | train loss {loss:.3f} | val loss {vl:.3f} "
                f"| ppl {np.exp(vl):6.2f} | grad-norm {gnorm:.2f} | {time.time() - t0:5.0f}s")
    return history


# ----------------------------------------------------------------------------- fine-tuning
def sft_batch(examples, tok, block_size):
    """
    Build an instruction-tuning batch.  The sequence is  [prompt][answer]<|endoftext|>,
    but the loss mask is 1 ONLY on answer tokens: the model learns to *answer*,
    not to re-generate the question. Padding uses the EOT id with mask 0.
    """
    B = len(examples)
    x = np.full((B, block_size), tok.eot_id, dtype=np.int64)
    y = np.full((B, block_size), tok.eot_id, dtype=np.int64)
    mask = np.zeros((B, block_size), dtype=np.float32)
    for b, (prompt, answer, *_rest) in enumerate(examples):
        p_ids = tok.encode(prompt)
        a_ids = tok.encode(answer) + [tok.eot_id]
        seq = (p_ids + a_ids)[: block_size + 1]
        n = len(seq) - 1
        x[b, :n] = seq[:-1]
        y[b, :n] = seq[1:]
        mask[b, len(p_ids) - 1: n] = 1.0          # positions whose *target* is an answer token
    return x, y, mask


def finetune(model, examples, tok, steps=300, batch_size=32, lr=1e-3, warmup=20,
             seed=0, log=print, log_every=50, replay_tokens=None, replay_rows=8, replay_weight=0.5):
    """
    Supervised fine-tuning. With `replay_tokens` (the pre-training token stream), each batch also gets
    `replay_rows` windows of plain text, together weighted `replay_weight` x the answer tokens.
    This "replay" stops catastrophic forgetting: the model keeps its plain-text ability (same
    perplexity as the base model) while learning to answer questions.
    """
    rng = np.random.default_rng(seed)
    opt = AdamW(model, lr=lr, weight_decay=0.0)
    T = model.cfg.block_size
    history, t0 = [], time.time()
    for step in range(steps):
        batch = [examples[i] for i in rng.integers(0, len(examples), batch_size)]
        x, y, m = sft_batch(batch, tok, T)
        if replay_tokens is not None:
            xr, yr = lm_batch(replay_tokens, replay_rows, T, rng)
            mr = np.full(xr.shape, replay_weight * m.sum() / xr.size, np.float32)
            x, y, m = np.concatenate([x, xr]), np.concatenate([y, yr]), np.concatenate([m, mr])
        _, loss = model.forward(x, y, m.astype(model.params["wte"].dtype))
        grads = model.backward()
        opt.step(grads, lr=cosine_lr(step, steps, lr, warmup))
        if step % log_every == 0 or step == steps - 1:
            history.append({"step": step, "loss": loss})
            log(f"  step {step:4d} | loss {loss:.3f} | {time.time() - t0:4.0f}s")
    return history
