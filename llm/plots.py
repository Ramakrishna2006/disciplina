"""Dependency-free SVG line chart (used for the training curves in the README)."""
import numpy as np

COLORS = ["#2a6fdb", "#d9480f", "#2b8a3e", "#ae3ec9"]


def nice_ticks(hi, n=5):
    """Round tick values 0, step, 2*step, ... covering [0, hi], with step = 1, 2 or 5 x 10^k."""
    raw = hi / n
    mag = 10 ** np.floor(np.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    return np.arange(0, hi + step * 0.999, step)


def line_chart_svg(path, series, title, xlabel, ylabel, w=640, h=360):
    """series: {name: (xs, ys)}. Draws each series as a line on shared axes and saves an SVG."""
    L, R, T, B = 64, 150, 44, 52                      # margins: left, right (legend), top, bottom
    xs_all = np.concatenate([np.asarray(x, float) for x, _ in series.values()])
    ys_all = np.concatenate([np.asarray(y, float) for _, y in series.values()])
    xt, yt = nice_ticks(xs_all.max()), nice_ticks(ys_all.max())
    x0, x1, y0, y1 = 0.0, max(xt[-1], xs_all.max()), 0.0, yt[-1]
    X = lambda v: L + (v - x0) / (x1 - x0 or 1) * (w - L - R)      # noqa: E731
    Y = lambda v: h - B - (v - y0) / (y1 - y0 or 1) * (h - T - B)  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="sans-serif" '
           f'font-size="12"><rect width="100%" height="100%" fill="white"/>',
           f'<text x="{L}" y="24" font-size="15" font-weight="bold">{title}</text>']
    for v in yt:                                      # horizontal grid + y labels
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#e5e5e5"/>'
                   f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="#555">{v:g}</text>')
    for v in xt:                                      # x labels
        out.append(f'<text x="{X(v):.1f}" y="{h - B + 18}" text-anchor="middle" fill="#555">{v:,.0f}</text>')
    out.append(f'<text x="{(L + w - R) / 2}" y="{h - 10}" text-anchor="middle" fill="#333">{xlabel}</text>'
               f'<text x="16" y="{(T + h - B) / 2}" text-anchor="middle" fill="#333" '
               f'transform="rotate(-90 16 {(T + h - B) / 2})">{ylabel}</text>')
    for i, (name, (xs, ys)) in enumerate(series.items()):
        c = COLORS[i % len(COLORS)]
        pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(xs, ys))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2"/>'
                   f'<line x1="{w - R + 16}" x2="{w - R + 36}" y1="{T + 10 + 22 * i}" y2="{T + 10 + 22 * i}" '
                   f'stroke="{c}" stroke-width="2"/><text x="{w - R + 42}" y="{T + 14 + 22 * i}" '
                   f'fill="#333">{name}</text>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
