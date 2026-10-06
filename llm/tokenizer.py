"""
Byte-level BPE (Byte Pair Encoding) tokenizer -- the same idea used by GPT-2/3/4, Llama, etc.

How it works
------------
1. Start from raw UTF-8 bytes: every text is a sequence of ids 0..255 (so ANY text can be encoded,
   no "unknown token" problem).
2. Training: repeatedly find the most frequent ADJACENT pair of ids in the corpus and merge it
   into a new id (256, 257, ...). Frequent words / sub-words end up as single tokens.
3. Encoding: split text into "pre-tokens" (words with their leading space, digits, punctuation),
   then apply the learned merges in the order they were learned.
4. Decoding: map every id back to its bytes and join them.
"""
import json
import re
from collections import Counter

EOT = "<|endoftext|>"   # special token that separates documents / ends an answer

# Pre-tokenizer: GPT-2 style split. Merges never cross these boundaries, so " Paris" and "Paris."
# don't create junk tokens like "s." that glue words to punctuation.
PAT = re.compile(r" ?[A-Za-z]+| ?\d| ?[^\sA-Za-z\d]+|\s+(?!\S)|\s+")
SPECIAL_SPLIT = re.compile("(" + re.escape(EOT) + ")")


def _merge(ids, pair, new_id):
    """Replace every occurrence of `pair` in `ids` with `new_id`."""
    out, i = [], 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out


class BPETokenizer:
    def __init__(self):
        self.merges = {}                                   # (id_a, id_b) -> new_id, in learn order
        self.vocab = {i: bytes([i]) for i in range(256)}   # id -> bytes
        self.eot_id = None
        self._cache = {}

    # ------------------------------------------------------------------ training
    def train(self, text, vocab_size=512, verbose=False):
        assert vocab_size > 257
        num_merges = vocab_size - 257                      # 256 bytes + 1 special token
        text = text.replace(EOT, " ")
        chunk_counts = Counter(PAT.findall(text))
        # work on unique chunks weighted by frequency -> fast even for big corpora
        chunks = {tuple(c.encode("utf-8")): n for c, n in chunk_counts.items()}

        for i in range(num_merges):
            pair_counts = Counter()
            for ids, n in chunks.items():
                for a, b in zip(ids, ids[1:]):
                    pair_counts[(a, b)] += n
            if not pair_counts:
                break
            best = max(pair_counts, key=pair_counts.get)
            new_id = 256 + i
            self.merges[best] = new_id
            self.vocab[new_id] = self.vocab[best[0]] + self.vocab[best[1]]
            chunks = {tuple(_merge(list(ids), best, new_id)): n for ids, n in chunks.items()}
            if verbose and (i < 10 or i % 50 == 0):
                print(f"  merge {i:4d}: {self.vocab[best[0]]!r} + {self.vocab[best[1]]!r} "
                      f"-> {self.vocab[new_id]!r}  (seen {pair_counts[best]}x)")
        self.eot_id = 256 + len(self.merges)
        self.vocab[self.eot_id] = EOT.encode("utf-8")
        self._cache = {}
        return self

    @property
    def vocab_size(self):
        return len(self.vocab)

    # ------------------------------------------------------------------ encode / decode
    def _encode_chunk(self, chunk):
        if chunk in self._cache:
            return self._cache[chunk]
        ids = list(chunk.encode("utf-8"))
        while len(ids) >= 2:
            # pick the pair that was learned EARLIEST (lowest new id)
            pairs = set(zip(ids, ids[1:]))
            best = min(pairs, key=lambda p: self.merges.get(p, float("inf")))
            if best not in self.merges:
                break
            ids = _merge(ids, best, self.merges[best])
        self._cache[chunk] = ids
        return ids

    def encode(self, text):
        out = []
        for part in SPECIAL_SPLIT.split(text):
            if part == EOT:
                out.append(self.eot_id)
            elif part:
                for chunk in PAT.findall(part):
                    out.extend(self._encode_chunk(chunk))
        return out

    def decode(self, ids):
        return b"".join(self.vocab[i] for i in ids).decode("utf-8", errors="replace")

    def token_strings(self, ids):
        """Show how a text was split -- handy for learning."""
        return [self.vocab[i].decode("utf-8", errors="replace") for i in ids]

    # ------------------------------------------------------------------ persistence
    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"merges": [[a, b, n] for (a, b), n in self.merges.items()]}, f)

    @classmethod
    def load(cls, path):
        tok = cls()
        with open(path, encoding="utf-8") as f:
            for a, b, n in json.load(f)["merges"]:
                tok.merges[(a, b)] = n
                tok.vocab[n] = tok.vocab[a] + tok.vocab[b]
        tok.eot_id = 256 + len(tok.merges)
        tok.vocab[tok.eot_id] = EOT.encode("utf-8")
        return tok
