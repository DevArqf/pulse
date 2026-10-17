"""
Hand-rolled SVG / HTML chart builders. No plotting library: every mark is
generated here, colored through CSS custom properties so light and dark
themes swap in one place, and tagged with `data-tip` for the hover layer.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from html import escape

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def fmt(n: float) -> str:
    n = float(n)
    for unit, div in (("M", 1e6), ("k", 1e3)):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{unit}" if v < 100 else f"{v:.0f}{unit}"
    return f"{n:,.0f}"


def nice_max(v: float, ticks: int = 4) -> tuple[float, float]:
    """Round the axis top up to a friendly number; return (top, step)."""
    if v <= 0:
        return ticks, 1
    raw = v / ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return step * math.ceil(v / step), step


def tip(text: str) -> str:
    return f'data-tip="{escape(text, quote=True)}"'


def _bar_path(x: float, base: float, end: float, w: float, r: float = 4) -> str:
    """Vertical bar, square at the baseline, rounded at the data end."""
    h = abs(end - base)
    r = min(r, h, w / 2)
    if h == 0:
        return ""
    if end < base:  # grows upward
        return (f"M{x},{base}V{end + r}Q{x},{end} {x + r},{end}H{x + w - r}"
                f"Q{x + w},{end} {x + w},{end + r}V{base}Z")
    return (f"M{x},{base}V{end - r}Q{x},{end} {x + r},{end}H{x + w - r}"
            f"Q{x + w},{end} {x + w},{end - r}V{base}Z")


# --------------------------------------------------------------------------- #


def calendar(daily: dict[date, int]) -> str:
    cell, gap = 13, 3
    days = sorted(daily)
    counts = sorted(v for v in daily.values() if v)
    # quartile thresholds over active days so one outlier can't wash out the rest
    q = [counts[int(len(counts) * p)] for p in (0.25, 0.5, 0.75)] if counts else [1, 2, 3]

    def level(v: int) -> int:
        return 0 if v == 0 else 1 + sum(v > t for t in q)

    left, top = 30, 20
    weeks = len(days) // 7
    w, h = left + weeks * (cell + gap), top + 7 * (cell + gap)
    out = [f'<svg viewBox="0 0 {w} {h}" class="cal" role="img" aria-label="Daily commit calendar">']
    for i, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="0" y="{top + i * (cell + gap) + cell - 3}" class="axis">{label}</text>')
    last_month = None
    for i, d in enumerate(days):
        col, row = i // 7, (d.weekday() + 1) % 7  # Sunday-first rows
        x, y = left + col * (cell + gap), top + row * (cell + gap)
        if row == 0 and d.month != last_month and col < weeks - 1:
            out.append(f'<text x="{x}" y="11" class="axis">{d.strftime("%b")}</text>')
            last_month = d.month
        v = daily[d]
        label = f"{v} commit{'s' if v != 1 else ''} | {d.strftime('%a, %b %d %Y')}"
        out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" class="l{level(v)}" {tip(label)}/>')
    out.append("</svg>")
    legend = "".join(f'<i class="l{i}"></i>' for i in range(5))
    return "".join(out) + f'<div class="cal-legend"><span>Less</span>{legend}<span>More</span></div>'


def activity(weekly: list[tuple[date, int]]) -> str:
    W, H, L, R, T, B = 760, 260, 40, 12, 14, 30
    top, step = nice_max(max(v for _, v in weekly))
    n = len(weekly)
    xs = [L + (W - L - R) * i / max(1, n - 1) for i in range(n)]
    ys = [T + (H - T - B) * (1 - v / top) for _, v in weekly]
    base = H - B

    out = [f'<svg viewBox="0 0 {W} {H}" class="line-chart" role="img" aria-label="Weekly commits over time">',
           '<defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
           '<stop offset="0" stop-color="var(--series-1)" stop-opacity=".28"/>'
           '<stop offset="1" stop-color="var(--series-1)" stop-opacity="0"/></linearGradient></defs>']
    t = 0.0
    while t <= top + 1e-9:
        y = T + (H - T - B) * (1 - t / top)
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" class="{"baseline" if t == 0 else "grid"}"/>')
        out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" class="axis" text-anchor="end">{fmt(t)}</text>')
        t += step
    last_m = None
    for (d, _), x in zip(weekly, xs):
        if d.day <= 7 and d.month != last_m and x < W - R - 20:
            label = d.strftime("%b") if d.month != 1 else d.strftime("%Y")
            out.append(f'<text x="{x:.1f}" y="{H - 8}" class="axis" text-anchor="middle">{label}</text>')
            last_m = d.month
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    out.append(f'<polygon points="{xs[0]:.1f},{base} {pts} {xs[-1]:.1f},{base}" fill="url(#fade)"/>')
    out.append(f'<polyline points="{pts}" class="series-line"/>')

    # hover layer: shared crosshair + dot, driven by invisible full-height bands
    out.append(f'<line class="guide" x1="0" x2="0" y1="{T}" y2="{base}"/><circle class="guide-dot" r="5" cx="-10" cy="-10"/>')
    bw = (W - L - R) / max(1, n - 1)
    for (d, v), x, y in zip(weekly, xs, ys):
        label = f"{v} commits | week of {d.strftime('%b %d, %Y')}"
        out.append(f'<rect class="band" x="{x - bw / 2:.1f}" y="{T}" width="{bw:.1f}" height="{base - T}" '
                   f'data-x="{x:.1f}" data-y="{y:.1f}" {tip(label)}/>')
    out.append("</svg>")
    return "".join(out)


def punchcard(grid: list[list[int]]) -> str:
    cell, L, T = 40, 44, 8
    W, H = L + 24 * cell, T + 7 * cell + 24
    peak = max(max(r) for r in grid) or 1
    out = [f'<svg viewBox="0 0 {W} {H}" class="punch" role="img" aria-label="Commits by weekday and hour">']
    for r, day in enumerate(DAYS):
        cy = T + r * cell + cell / 2
        out.append(f'<text x="0" y="{cy + 4}" class="axis">{day}</text>')
        out.append(f'<line x1="{L}" x2="{W}" y1="{cy}" y2="{cy}" class="grid"/>')
        for h in range(24):
            v = grid[r][h]
            cx = L + h * cell + cell / 2
            rad = 0 if v == 0 else 3 + 13 * math.sqrt(v / peak)
            label = f"{v} commits | {day} {h:02d}:00 → {h:02d}:59"
            out.append(f'<g {tip(label)}><rect x="{cx - cell / 2}" y="{cy - cell / 2}" width="{cell}" height="{cell}" class="hit"/>'
                       + (f'<circle cx="{cx}" cy="{cy}" r="{rad:.1f}" class="dot"/>' if v else "") + "</g>")
    for h in range(0, 24, 3):
        out.append(f'<text x="{L + h * cell + cell / 2}" y="{H - 4}" class="axis" text-anchor="middle">'
                   f'{["12a", "3a", "6a", "9a", "12p", "3p", "6p", "9p"][h // 3]}</text>')
    out.append("</svg>")
    return "".join(out)


def churn(months: list[dict]) -> str:
    months = months[-18:]
    W, H, L, R, T, B = 760, 280, 48, 12, 12, 28
    peak = max(max(m["added"], m["deleted"]) for m in months)
    top, step = nice_max(peak, 3)
    mid = T + (H - T - B) / 2
    half = (H - T - B) / 2
    slot = (W - L - R) / len(months)
    bw = min(26, slot * 0.6)

    out = [f'<svg viewBox="0 0 {W} {H}" class="churn" role="img" aria-label="Lines added and deleted per month">']
    t = step
    while t <= top + 1e-9:
        for sign in (-1, 1):
            y = mid - sign * half * t / top
            out.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
            out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" class="axis" text-anchor="end">{"+" if sign > 0 else "−"}{fmt(t)}</text>')
        t += step
    for i, m in enumerate(months):
        x = L + i * slot + (slot - bw) / 2
        y_up = mid - half * m["added"] / top
        y_dn = mid + half * m["deleted"] / top
        label_month = date.fromisoformat(m["month"] + "-01").strftime("%b %Y")
        net = m["added"] - m["deleted"]
        t_text = f"{label_month} | +{m['added']:,} / −{m['deleted']:,} | net {net:+,}"
        out.append(f'<g {tip(t_text)}><rect x="{x - (slot - bw) / 2:.1f}" y="{T}" width="{slot:.1f}" height="{H - T - B}" class="hit"/>'
                   f'<path d="{_bar_path(x, mid - 1, y_up, bw)}" class="pos"/>'
                   f'<path d="{_bar_path(x, mid + 1, y_dn, bw)}" class="neg"/></g>')
        if i % max(1, len(months) // 9) == 0:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{H - 8}" class="axis" text-anchor="middle">'
                       f'{date.fromisoformat(m["month"] + "-01").strftime("%b")}</text>')
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{mid}" y2="{mid}" class="baseline"/></svg>')
    return "".join(out)


def sparkline(values: list[int], w: int = 120, h: int = 34) -> str:
    peak = max(values) or 1
    xs = [w * i / max(1, len(values) - 1) for i in range(len(values))]
    ys = [h - 3 - (h - 6) * v / peak for v in values]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return (f'<svg viewBox="0 0 {w} {h}" class="spark" aria-hidden="true"><polyline points="{pts}" class="series-line"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3" class="end-dot"/></svg>')


def hbars(rows: list[tuple[str, float, str]], unit: str = "") -> str:
    """Ranked horizontal bars as HTML: (label, value, tooltip)."""
    peak = max((v for _, v, _ in rows), default=1) or 1
    items = []
    for label, v, t in rows:
        items.append(f'<div class="hbar" {tip(t)}><span class="hbar-label">{escape(label)}</span>'
                     f'<span class="hbar-track"><i style="width:{max(1.5, 100 * v / peak):.1f}%"></i></span>'
                     f'<span class="hbar-value">{fmt(v)}{unit}</span></div>')
    return "".join(items)


def stacked_share(parts: list[tuple[str, int]], slots: int = 8) -> str:
    """100% bar in fixed categorical order; past the slot budget, fold into Other."""
    named = [p for p in parts if p[0] != "Other"]
    other = sum(v for k, v in parts if k == "Other")
    if len(named) + (other > 0) > slots:
        other += sum(v for _, v in named[slots - 1:])
        named = named[: slots - 1]
    parts = named + ([("Other", other)] if other else [])
    total = sum(v for _, v in parts) or 1
    segs, legend = [], []
    for i, (name, v) in enumerate(parts):
        pct = 100 * v / total
        color = "var(--muted)" if name == "Other" else f"var(--series-{i + 1})"
        segs.append(f'<i style="flex:{v};background:{color}" {tip(f"{name} | {pct:.1f}% | {v:,} lines changed")}></i>')
        legend.append(f'<li><b style="background:{color}"></b>{escape(name)}<span>{pct:.1f}%</span></li>')
    return f'<div class="stack">{"".join(segs)}</div><ul class="legend">{"".join(legend)}</ul>'
