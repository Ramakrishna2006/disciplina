"""
A GPT-style decoder-only Transformer written in pure NumPy, with a hand-written backward pass.

Architecture (same family as GPT-2 / Llama, just tiny):

    token ids --> token embedding + position embedding
              --> N x [ LayerNorm -> causal multi-head self-attention -> residual add
                        LayerNorm -> MLP (Linear -> GELU -> Linear)     -> residual add ]
              --> final LayerNorm --> logits = h @ token_embedding^T  (weight tying)
              --> softmax over the vocabulary = probability of the NEXT token

Also supports LoRA (Low-Rank Adaptation) adapters on any linear layer for
parameter-efficient fine-tuning:  W x  becomes  W x + (alpha/r) * B(A x),  with W frozen.
"""
import json
from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class GPTConfig:
    vocab_size: int = 512
    block_size: int = 64      # maximum context length (tokens)
    n_layer: int = 4
    n_head: int = 4
    n_embd: int = 128
    dtype: str = "float32"


# ----------------------------------------------------------------------------- building blocks
def layernorm_fwd(x, g, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)
    rstd = 1.0 / np.sqrt(var + eps)
    xhat = (x - mu) * rstd
    return xhat * g + b, (xhat, rstd, g)


def layernorm_bwd(dy, cache):
    xhat, rstd, g = cache
    dg = (dy * xhat).reshape(-1, xhat.shape[-1]).sum(0)
    db = dy.reshape(-1, xhat.shape[-1]).sum(0)
    dxhat = dy * g
    dx = rstd * (dxhat - dxhat.mean(-1, keepdims=True)
                 - xhat * (dxhat * xhat).mean(-1, keepdims=True))
    return dx, dg, db


_GELU_K = np.sqrt(2.0 / np.pi)


def gelu_fwd(x):
    t = np.tanh(_GELU_K * (x + 0.044715 * x ** 3))
    return 0.5 * x * (1.0 + t), (x, t)


def gelu_bwd(dy, cache):
    x, t = cache
    dt = _GELU_K * (1.0 + 3 * 0.044715 * x ** 2)
    return dy * (0.5 * (1.0 + t) + 0.5 * x * (1.0 - t ** 2) * dt)


def softmax(x, axis=-1):
    x = x - x.max(axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis, keepdims=True)


# ----------------------------------------------------------------------------- the model
class GPT:
    def __init__(self, cfg: GPTConfig, seed=0):
        self.cfg = cfg
        dt = np.dtype(cfg.dtype)
        rng = np.random.default_rng(seed)
        C, L = cfg.n_embd, cfg.n_layer

        def normal(*shape, std=0.02):
            return (rng.standard_normal(shape) * std).astype(dt)

        P = {
            "wte": normal(cfg.vocab_size, C),     # token embeddings (also the output head)
            "wpe": normal(cfg.block_size, C),     # learned position embeddings
            "lnf.g": np.ones(C, dt), "lnf.b": np.zeros(C, dt),
        }
        proj_std = 0.02 / np.sqrt(2 * L)          # GPT-2 trick: scale residual projections
        for l in range(L):
            p = f"h{l}."
            P[p + "ln1.g"], P[p + "ln1.b"] = np.ones(C, dt), np.zeros(C, dt)
            P[p + "qkv.w"], P[p + "qkv.b"] = normal(C, 3 * C), np.zeros(3 * C, dt)
            P[p + "proj.w"], P[p + "proj.b"] = normal(C, C, std=proj_std), np.zeros(C, dt)
            P[p + "ln2.g"], P[p + "ln2.b"] = np.ones(C, dt), np.zeros(C, dt)
            P[p + "fc.w"], P[p + "fc.b"] = normal(C, 4 * C), np.zeros(4 * C, dt)
            P[p + "fc2.w"], P[p + "fc2.b"] = normal(4 * C, C, std=proj_std), np.zeros(C, dt)
        self.params = P
        self.frozen = set()          # names of parameters that are NOT trained
        self.lora_scale = 0.0
        self._mask = np.triu(np.full((cfg.block_size, cfg.block_size), -1e9, dt), k=1)

    # ------------------------------------------------------------------ helpers
    def num_params(self, trainable_only=False):
        return int(sum(v.size for k, v in self.params.items()
                       if not (trainable_only and k in self.frozen)))

    def trainable_names(self):
        return [k for k in self.params if k not in self.frozen]

    def add_lora(self, rank=8, alpha=16, targets=("qkv", "fc"), seed=1):
        """Freeze every existing weight and attach low-rank adapters A (in x r), B (r x out)."""
        rng = np.random.default_rng(seed)
        dt = np.dtype(self.cfg.dtype)
        self.frozen = set(self.params)                 # freeze the whole base model
        self.lora_scale = alpha / rank
        for l in range(self.cfg.n_layer):
            for t in targets:
                W = self.params[f"h{l}.{t}.w"]
                fan_in, fan_out = W.shape
                self.params[f"h{l}.{t}.lora_A"] = (rng.standard_normal((fan_in, rank))
                                                   / np.sqrt(fan_in)).astype(dt)
                self.params[f"h{l}.{t}.lora_B"] = np.zeros((rank, fan_out), dt)  # starts as no-op

    def merge_lora(self):
        """Fold adapters into the base weights (W += s*A@B) -> zero inference overhead."""
        for k in [k for k in self.params if k.endswith(".lora_A")]:
            base = k[: -len(".lora_A")]
            A, B = self.params.pop(k), self.params.pop(base + ".lora_B")
            self.params[base + ".w"] = self.params[base + ".w"] + self.lora_scale * (A @ B)
        self.frozen = set()

    # ------------------------------------------------------------------ linear layer (+LoRA)
    def _lin_fwd(self, x, name):
        P = self.params
        out = x @ P[name + ".w"] + P[name + ".b"]
        xa = None
        if name + ".lora_A" in P:
            xa = x @ P[name + ".lora_A"]
            out = out + self.lora_scale * (xa @ P[name + ".lora_B"])
        return out, (x, xa)

    def _lin_bwd(self, dout, name, cache, grads):
        P = self.params
        x, xa = cache
        W = P[name + ".w"]
        x2 = x.reshape(-1, x.shape[-1])
        d2 = dout.reshape(-1, dout.shape[-1])
        if name + ".w" not in self.frozen:
            grads[name + ".w"] += x2.T @ d2
            grads[name + ".b"] += d2.sum(0)
        dx = dout @ W.T
        if xa is not None:
            s = self.lora_scale
            Bm = P[name + ".lora_B"]
            grads[name + ".lora_B"] += s * (xa.reshape(-1, xa.shape[-1]).T @ d2)
            dxa = s * (d2 @ Bm.T)
            grads[name + ".lora_A"] += x2.T @ dxa
            dx = dx + (dxa @ P[name + ".lora_A"].T).reshape(x.shape)
        return dx

    # ------------------------------------------------------------------ forward
    def forward(self, idx, targets=None, loss_mask=None, keep_cache=True):
        """
        idx: (B, T) int token ids.  targets: (B, T) next-token ids.
        loss_mask: (B, T) weights -- e.g. 1 only on the answer tokens during instruction tuning.
        Returns logits (B, T, V) and the mean cross-entropy loss (or None).
        """
        cfg, P = self.cfg, self.params
        B, T = idx.shape
        C, nh = cfg.n_embd, cfg.n_head
        hd = C // nh
        scale = 1.0 / np.sqrt(hd)

        x = P["wte"][idx] + P["wpe"][:T]
        caches = []
        for l in range(cfg.n_layer):
            p = f"h{l}."
            # ---- attention sub-layer
            h, c_ln1 = layernorm_fwd(x, P[p + "ln1.g"], P[p + "ln1.b"])
            qkv, c_qkv = self._lin_fwd(h, p + "qkv")
            q, k, v = np.split(qkv, 3, axis=-1)
            q, k, v = (t.reshape(B, T, nh, hd).transpose(0, 2, 1, 3) for t in (q, k, v))
            att = (q @ k.transpose(0, 1, 3, 2)) * scale + self._mask[:T, :T]  # causal mask
            att = softmax(att)                                                 # (B, nh, T, T)
            y = (att @ v).transpose(0, 2, 1, 3).reshape(B, T, C)
            o, c_proj = self._lin_fwd(y, p + "proj")
            x = x + o
            # ---- MLP sub-layer
            h2, c_ln2 = layernorm_fwd(x, P[p + "ln2.g"], P[p + "ln2.b"])
            f, c_fc = self._lin_fwd(h2, p + "fc")
            g, c_gelu = gelu_fwd(f)
            m, c_fc2 = self._lin_fwd(g, p + "fc2")
            x = x + m
            if keep_cache:
                caches.append((c_ln1, c_qkv, q, k, v, att, c_proj, c_ln2, c_fc, c_gelu, c_fc2))
        xf, c_lnf = layernorm_fwd(x, P["lnf.g"], P["lnf.b"])
        logits = xf @ P["wte"].T                                                # weight tying

        loss = None
        if targets is not None:
            if loss_mask is None:
                loss_mask = np.ones((B, T), logits.dtype)
            probs = softmax(logits)
            p_t = np.take_along_axis(probs, targets[..., None], -1)[..., 0]
            denom = max(loss_mask.sum(), 1e-8)
            loss = float(-(np.log(p_t + 1e-12) * loss_mask).sum() / denom)
            if keep_cache:
                dlogits = probs
                np.put_along_axis(dlogits, targets[..., None],
                                  np.take_along_axis(dlogits, targets[..., None], -1) - 1, -1)
                dlogits *= (loss_mask / denom)[..., None]
                self._cache = (idx, caches, xf, c_lnf, dlogits.astype(logits.dtype))
        return logits, loss

    # ------------------------------------------------------------------ backward
    def backward(self):
        """Back-propagate the loss of the last forward() call. Returns {name: gradient}."""
        cfg, P = self.cfg, self.params
        idx, caches, xf, c_lnf, dlogits = self._cache
        B, T = idx.shape
        C, nh = cfg.n_embd, cfg.n_head
        hd = C // nh
        scale = 1.0 / np.sqrt(hd)
        grads = {k: np.zeros_like(P[k]) for k in self.trainable_names()}
        train_emb = "wte" not in self.frozen

        dl2 = dlogits.reshape(-1, dlogits.shape[-1])
        if train_emb:
            grads["wte"] += dl2.T @ xf.reshape(-1, C)
        dxf = dlogits @ P["wte"]
        dx, dg, db = layernorm_bwd(dxf, c_lnf)
        if "lnf.g" in grads:
            grads["lnf.g"] += dg; grads["lnf.b"] += db

        for l in reversed(range(cfg.n_layer)):
            p = f"h{l}."
            (c_ln1, c_qkv, q, k, v, att, c_proj, c_ln2, c_fc, c_gelu, c_fc2) = caches[l]
            # ---- MLP
            dg_ = self._lin_bwd(dx, p + "fc2", c_fc2, grads)
            df = gelu_bwd(dg_, c_gelu)
            dh2 = self._lin_bwd(df, p + "fc", c_fc, grads)
            d, dgam, dbet = layernorm_bwd(dh2, c_ln2)
            if p + "ln2.g" in grads:
                grads[p + "ln2.g"] += dgam; grads[p + "ln2.b"] += dbet
            dx = dx + d
            # ---- attention
            dy = self._lin_bwd(dx, p + "proj", c_proj, grads)
            dy = dy.reshape(B, T, nh, hd).transpose(0, 2, 1, 3)
            datt = dy @ v.transpose(0, 1, 3, 2)
            dv = att.transpose(0, 1, 3, 2) @ dy
            ds = att * (datt - (datt * att).sum(-1, keepdims=True)) * scale   # softmax backward
            dq = ds @ k
            dk = ds.transpose(0, 1, 3, 2) @ q
            dqkv = np.concatenate([t.transpose(0, 2, 1, 3).reshape(B, T, C)
                                   for t in (dq, dk, dv)], axis=-1)
            dh = self._lin_bwd(dqkv, p + "qkv", c_qkv, grads)
            d, dgam, dbet = layernorm_bwd(dh, c_ln1)
            if p + "ln1.g" in grads:
                grads[p + "ln1.g"] += dgam; grads[p + "ln1.b"] += dbet
            dx = dx + d

        if train_emb:
            np.add.at(grads["wte"], idx, dx)
        if "wpe" in grads:
            grads["wpe"][:T] += dx.sum(0)
        self._cache = None
        return grads

    # ------------------------------------------------------------------ text generation
    def generate(self, ids, max_new_tokens=20, temperature=0.0, top_k=None,
                 stop_ids=(), rng=None):
        """
        Autoregressive decoding: predict a token, append it, repeat.
        temperature=0 -> greedy (always the most likely token).
        temperature>0 -> sample; top_k keeps only the k most likely tokens.
        """
        rng = rng or np.random.default_rng()
        ids = list(ids)
        for _ in range(max_new_tokens):
            ctx = np.array([ids[-self.cfg.block_size:]])
            logits, _ = self.forward(ctx, keep_cache=False)
            logits = logits[0, -1].astype(np.float64)
            if temperature <= 0:
                nxt = int(logits.argmax())
            else:
                logits = logits / temperature
                if top_k:
                    kth = np.sort(logits)[-top_k]
                    logits = np.where(logits < kth, -np.inf, logits)
                nxt = int(rng.choice(len(logits), p=softmax(logits)))
            ids.append(nxt)
            if nxt in stop_ids:
                break
        return ids

    # ------------------------------------------------------------------ save / load
    def save(self, path):
        np.savez(path, __config__=json.dumps(asdict(self.cfg)),
                 __lora_scale__=self.lora_scale, **self.params)

    @classmethod
    def load(cls, path):
        d = np.load(path)
        m = cls(GPTConfig(**json.loads(str(d["__config__"]))))
        m.params = {k: d[k] for k in d.files if not k.startswith("__")}
        m.lora_scale = float(d["__lora_scale__"])
        return m


# ----------------------------------------------------------------------------- optimizer
class AdamW:
    """Adam with decoupled weight decay + global gradient-norm clipping."""

    def __init__(self, model, lr=3e-4, betas=(0.9, 0.95), eps=1e-8, weight_decay=0.1, clip=1.0):
        self.model, self.lr, self.betas, self.eps = model, lr, betas, eps
        self.wd, self.clip, self.t = weight_decay, clip, 0
        self.m = {k: np.zeros_like(model.params[k]) for k in model.trainable_names()}
        self.v = {k: np.zeros_like(model.params[k]) for k in model.trainable_names()}

    def step(self, grads, lr=None):
        lr = self.lr if lr is None else lr
        self.t += 1
        b1, b2 = self.betas
        gnorm = float(np.sqrt(sum(float((g.astype(np.float64) ** 2).sum()) for g in grads.values())))
        c = min(1.0, self.clip / (gnorm + 1e-6))
        for k, g in grads.items():
            g = g * c
            self.m[k] = b1 * self.m[k] + (1 - b1) * g
            self.v[k] = b2 * self.v[k] + (1 - b2) * g * g
            mhat = self.m[k] / (1 - b1 ** self.t)
            vhat = self.v[k] / (1 - b2 ** self.t)
            p = self.model.params[k]
            decay = self.wd if (p.ndim == 2 and "lora" not in k) else 0.0
            self.model.params[k] = (p - lr * (mhat / (np.sqrt(vhat) + self.eps) + decay * p)).astype(p.dtype)
        return gnorm


def cosine_lr(step, total, base_lr, warmup=100, min_ratio=0.1):
    if step < warmup:
        return base_lr * (step + 1) / warmup
    progress = (step - warmup) / max(1, total - warmup)
    return base_lr * (min_ratio + (1 - min_ratio) * 0.5 * (1 + np.cos(np.pi * progress)))
