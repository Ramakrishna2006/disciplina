"""
The trained models, loaded once and shared by every request.

Loading the tokenizer and the three published models from artifacts/ takes about a second, so it
happens on the first request that needs them (not at start-up, which keeps `flask db upgrade` and
the tests fast) and the result is kept in memory. Generating text does not change a model
(forward(..., keep_cache=False) stores nothing), so many requests can use the same models at once.

    engine = get_engine()             # the shared Engine for this app
    engine.reply("lora", "Where does Asha live?")
"""
import threading
import time
from pathlib import Path

import numpy as np
from flask import current_app

# Database / API name -> file in artifacts/ (the engine's own names are "base", "full-FT", "LoRA")
MODEL_FILES = {"base": "base_model.npz", "full": "finetuned_full.npz", "lora": "finetuned_lora_merged.npz"}
MODEL_INFO = {
    "base": {"label": "Base", "description": "Pre-trained only. Continues text: type the start of a sentence."},
    "full": {"label": "Full fine-tune", "description": "Every weight trained on questions and answers."},
    "lora": {"label": "LoRA", "description": "Only 49,152 adapter weights trained on questions and answers."},
}
CATEGORY_LABELS = {"city": "City", "job": "Job", "food": "Food"}


class EngineUnavailable(Exception):
    """The model files are missing (run `python main.py train`)."""


class Engine:
    def __init__(self, artifacts_dir):
        self.dir = Path(artifacts_dir)
        self._lock = threading.Lock()
        self._tok = None
        self._models = None
        self._points = {}

    # ------------------------------------------------------------------ loading
    @property
    def loaded(self):
        return self._models is not None

    def available(self):
        return (self.dir / "tokenizer.json").is_file() and all((self.dir / f).is_file() for f in MODEL_FILES.values())

    def load(self):
        """Load everything once. The lock makes sure two first requests do not both load."""
        if self._models is None:
            with self._lock:
                if self._models is None:
                    if not self.available():
                        raise EngineUnavailable(f"The trained models are missing from {self.dir}. "
                                                "Run `python main.py train` first.")
                    from llm.model import GPT
                    from llm.tokenizer import BPETokenizer
                    self._tok = BPETokenizer.load(str(self.dir / "tokenizer.json"))
                    self._models = {k: GPT.load(str(self.dir / f)) for k, f in MODEL_FILES.items()}
        return self._tok, self._models

    @property
    def tokenizer(self):
        return self.load()[0]

    def model(self, name):
        return self.load()[1][name]

    # ------------------------------------------------------------------ chat
    def reply(self, model, message, temperature=0.0, top_k=None, rng=None):
        """
        The fine-tuned models get the question in the Q&A format they were trained on and answer
        in a few tokens. The base model was only pre-trained, so it simply continues the text.
        Returns (reply text, number of generated tokens, milliseconds).
        """
        from llm.data import qa_prompt

        tok = self.tokenizer
        m = self.model(model)
        prompt = message if model == "base" else qa_prompt(message)
        ids = tok.encode(prompt)[-(m.cfg.block_size - 1):]          # keep the end if it is too long
        t0 = time.perf_counter()
        out = m.generate(ids, max_new_tokens=24 if model == "base" else 8, temperature=temperature,
                         top_k=top_k, stop_ids=(tok.eot_id,), rng=rng or np.random.default_rng())
        ms = round((time.perf_counter() - t0) * 1000)
        new = [t for t in out[len(ids):] if t != tok.eot_id]
        text = tok.decode(new)
        text = text.split("\n")[0].strip() if model != "base" else text.strip()
        return text or "(no answer)", len(new), ms

    # ------------------------------------------------------------------ tokenizer
    def tokenize(self, text):
        tok = self.tokenizer
        ids = tok.encode(text)
        pieces = tok.token_strings(ids)
        return [{"id": int(i), "text": p} for i, p in zip(ids, pieces, strict=True)]

    # ------------------------------------------------------------------ embeddings
    def embedding_points(self, model="base"):
        """Every city, job and food word as a point on a 2-D map (PCA of the token embeddings),
        scaled to 0..1. Words that play the same role end up close together after training."""
        if model not in self._points:
            from llm.data import ATTRS
            from llm.embeddings import normalized_embeddings, token_id

            tok, m = self.tokenizer, self.model(model)
            E = normalized_embeddings(m)
            words = [(c, w, token_id(tok, w)) for c, ws in ATTRS.items() for w in ws]
            words = [(c, w, t) for c, w, t in words if t is not None]
            X = np.array([E[t] for _, _, t in words])
            X = X - X.mean(axis=0)
            _, _, vt = np.linalg.svd(X, full_matrices=False)
            Y = X @ vt[:2].T
            Y = (Y - Y.min(0)) / (Y.max(0) - Y.min(0) + 1e-9)
            self._points[model] = [{"word": w, "category": c, "x": round(float(x), 4), "y": round(float(y), 4)}
                                   for (c, w, _), (x, y) in zip(words, Y, strict=True)]
        return self._points[model]

    def neighbors(self, word, k=5, model="base"):
        """The k tokens whose embeddings point the most in the same direction (cosine similarity),
        or None if the word is not a single token."""
        from llm.embeddings import nearest_neighbors, token_id

        tok, m = self.tokenizer, self.model(model)
        if token_id(tok, word) is None:
            return None
        return [{"word": w, "similarity": round(s, 4)} for w, s in nearest_neighbors(m, tok, word, k)]


_engines = {}
_engines_lock = threading.Lock()


def get_engine():
    """The Engine for this app's ARTIFACTS_DIR (one per folder, shared by all requests)."""
    key = str(current_app.config["ARTIFACTS_DIR"])
    with _engines_lock:
        if key not in _engines:
            _engines[key] = Engine(key)
        return _engines[key]
