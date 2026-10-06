"""
Embedding analysis: after training, tokens that play the same role end up close together
in embedding space. We measure that with cosine similarity and draw a 2-D PCA map (SVG, no deps).
"""
import numpy as np


def token_id(tok, word):
    """Id of ' word' if it is a single token (the leading space matters in BPE!)."""
    ids = tok.encode(" " + word)
    return ids[0] if len(ids) == 1 else None


def normalized_embeddings(model):
    E = model.params["wte"].astype(np.float64)
    return E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)


def nearest_neighbors(model, tok, word, k=5):
    tid = token_id(tok, word)
    if tid is None:
        return []
    E = normalized_embeddings(model)
    sims = E @ E[tid]
    order = [i for i in np.argsort(-sims) if i != tid][:k]
    return [(tok.decode([i]).strip(), float(sims[i])) for i in order]


def category_cohesion(model, tok, categories):
    """Mean cosine similarity within a category vs. between categories."""
    E = normalized_embeddings(model)
    groups = {c: [t for t in (token_id(tok, w) for w in ws) if t is not None]
              for c, ws in categories.items()}
    within, between = [], []
    cats = list(groups)
    for i, a in enumerate(cats):
        A = E[groups[a]]
        S = A @ A.T
        within.append(S[np.triu_indices(len(A), 1)].mean())
        for b in cats[i + 1:]:
            between.append((A @ E[groups[b]].T).mean())
    return float(np.mean(within)), float(np.mean(between))


def pca_svg(model, tok, categories, path, size=520):
    E = normalized_embeddings(model)
    pts, labels, cats = [], [], []
    for c, ws in categories.items():
        for w in ws:
            t = token_id(tok, w)
            if t is not None:
                pts.append(E[t]); labels.append(w); cats.append(c)
    X = np.array(pts) - np.mean(pts, axis=0)
    _, _, Vt = np.linalg.svd(X, full_matrices=False)
    Y = X @ Vt[:2].T
    Y = (Y - Y.min(0)) / (Y.max(0) - Y.min(0) + 1e-9) * (size - 140) + 50
    palette = ["#2a6fdb", "#d9480f", "#2b8a3e", "#ae3ec9", "#e67700"]
    color = {c: palette[i % len(palette)] for i, c in enumerate(categories)}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
           f'font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="white"/>',
           f'<text x="12" y="22" font-size="14" font-weight="bold">Token embeddings (PCA, 2-D)</text>']
    for i, c in enumerate(categories):
        out.append(f'<circle cx="{18 + i * 90}" cy="{size - 14}" r="5" fill="{color[c]}"/>'
                   f'<text x="{26 + i * 90}" y="{size - 10}">{c}</text>')
    for (x, y), lab, c in zip(Y, labels, cats):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color[c]}"/>'
                   f'<text x="{x + 6:.1f}" y="{y + 4:.1f}" fill="{color[c]}">{lab}</text>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
