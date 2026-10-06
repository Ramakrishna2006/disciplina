"""
Tokenizer tests: lossless round-trip on seen, unseen and non-English text, special token
handling, and save/load giving identical ids. Run:  python tests/test_tokenizer.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm.data import build_world, pretraining_corpus  # noqa: E402
from llm.tokenizer import EOT, BPETokenizer  # noqa: E402

world, _, _ = build_world(seed=0)
tok = BPETokenizer().train(pretraining_corpus(world, n_docs=500, seed=1), vocab_size=2048)

samples = ["Asha lives in Indore.", "Bengaluru is new!", "  spaces\tand\nlines ",
           "नमस्ते, తెలుగు", "Q: Where does Asha live?\nA: Indore" + EOT]
for s in samples:
    assert tok.decode(tok.encode(s)) == s, f"round-trip failed for {s!r}"
print(f"round-trip      : {len(samples)} texts (incl. Hindi/Telugu, whitespace) decode exactly  OK")

ids = tok.encode("Asha" + EOT + "Ravi")
assert ids.count(tok.eot_id) == 1 and tok.encode(EOT) == [tok.eot_id]
print("special token   : <|endoftext|> is always exactly one token  OK")

assert len(tok.encode(" Indore")) == 1 and len(tok.encode(" Indore")) < len(" Indore".encode())
print("compression     : frequent words become a single token  OK")

with tempfile.TemporaryDirectory() as d:
    tok.save(os.path.join(d, "t.json"))
    tok2 = BPETokenizer.load(os.path.join(d, "t.json"))
assert all(tok2.encode(s) == tok.encode(s) for s in samples)
print("save / load     : reloaded tokenizer gives identical ids  OK")
