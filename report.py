"""Assemble the single-file HTML dashboard."""

from __future__ import annotations

from datetime import datetime
from html import escape

import charts
from charts import fmt, tip
from stats import Report


def insights(r: Report) -> list[tuple[str, str]]:
    total = r.commits
    # bus factor: fewest people who together wrote half the commits
    acc, bus = 0, 0
    for c in r.contributors:
        acc += c["commits"]
        bus += 1
        if acc >= total / 2:
            break
    day_i, hour = max(((d, h) for d in range(7) for h in range(24)), key=lambda dh: r.punchcard[dh[0]][dh[1]])
    weekend = sum(sum(r.punchcard[d]) for d in (5, 6)) / total
    night = sum(r.punchcard[d][h] for d in range(7) for h in (*range(0, 6), 22, 23)) / total
    top = r.contributors[0]
    kind, kind_n = r.kinds[0]
    fix_share = dict(r.kinds).get("fix", 0) / total
    return [
        ("Bus factor", f"<b>{bus}</b> {'person writes' if bus == 1 else 'people write'} half of all commits"),
        ("Peak hour", f"<b>{charts.DAYS[day_i]}s at {hour:02d}:00</b> is when the team ships most"),
        ("Top contributor", f"<b>{escape(top['name'])}</b> authored {top['commits'] / total:.0%} of commits"),
        ("Busiest day", f"<b>{r.busiest_day[1]} commits</b> on {r.busiest_day[0].strftime('%b %d, %Y')}"),
        ("Work-life", f"<b>{weekend:.0%}</b> of commits land on weekends, <b>{night:.0%}</b> late at night"),
        ("Commit style", f"<b>{escape(kind)}</b> is the most common type; fixes are {fix_share:.0%} of history"),
    ]


def render(r: Report) -> str:
    span_days = (r.last - r.first).days + 1
    recent = [v for _, v in r.weekly[-26:]]
    top_people = r.contributors[:9] if len(r.contributors) <= 9 else r.contributors[:8]
    people = charts.hbars([
        (c["name"], c["commits"],
         f"{c['name']} | {c['commits']:,} commits | +{c['added']:,} / −{c['deleted']:,} | {c['days']} active days")
        for c in top_people
    ])
    if len(r.contributors) > 9:
        rest = r.contributors[8:]
        people += charts.hbars([(f"{len(rest)} others", sum(c["commits"] for c in rest), "Everyone else combined")])
    kinds = charts.hbars([(k, n, f"{k} | {n:,} commits ({n / r.commits:.0%})") for k, n in r.kinds[:7]])
    hot_rows = "".join(
        f"<tr><td><code>{escape(f['path'])}</code></td><td>{f['commits']}</td><td>{fmt(f['churn'])}</td>"
        f"<td>{f['authors']}</td></tr>" for f in r.hot_files
    )
    weekly_rows = "".join(f"<tr><td>{d.isoformat()}</td><td>{v}</td></tr>" for d, v in r.weekly)
    insight_cards = "".join(f'<div class="insight"><small>{k}</small><p>{v}</p></div>' for k, v in insights(r))

    tiles = f"""
      <div class="tile hero-tile">
        <small>Commits</small><b>{r.commits:,}</b>
        {charts.sparkline(recent)}
        <span class="sub">last 26 weeks</span>
      </div>
      <div class="tile"><small>Contributors</small><b>{r.authors}</b><span class="sub">{r.active_days} active days</span></div>
      <div class="tile"><small>Lines changed</small><b>{fmt(r.added + r.deleted)}</b>
        <span class="sub"><span {tip(f"{r.added:,} lines added")}>+{fmt(r.added)}</span> | <span {tip(f"{r.deleted:,} lines deleted")}>−{fmt(r.deleted)}</span></span></div>
      <div class="tile"><small>Longest streak</small><b>{r.longest_streak}<em>days</em></b><span class="sub">ended {r.streak_end.strftime('%b %d, %Y')}</span></div>
      <div class="tile"><small>Files touched</small><b>{fmt(r.files)}</b><span class="sub">{r.active_days / span_days:.0%} of days had commits</span></div>
    """

    return TEMPLATE.format(
        name=escape(r.name),
        period=f"{r.first.strftime('%b %d, %Y')} → {r.last.strftime('%b %d, %Y')}",
        span=f"{span_days:,} days",
        generated=datetime.now().strftime("%b %d, %Y at %H:%M"),
        tiles=tiles,
        insights=insight_cards,
        calendar=charts.calendar(r.daily),
        activity=charts.activity(r.weekly),
        weekly_rows=weekly_rows,
        punchcard=charts.punchcard(r.punchcard),
        people=people,
        churn=charts.churn(r.churn),
        languages=charts.stacked_share(r.languages),
        kinds=kinds,
        hot_rows=hot_rows,
        css=CSS,
        js=JS,
    )


CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --raise: #ffffff;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --ring: rgba(11,11,11,.10);
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #eda100;
  --series-5: #e87ba4; --series-6: #008300; --series-7: #4a3aa7; --series-8: #e34948;
  --pos: #2a78d6; --neg: #e34948;
  --l0: #f0efec; --l1: #b7d3f6; --l2: #6da7ec; --l3: #2a78d6; --l4: #104281;
  --glow: rgba(42,120,214,.10);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --raise: #20201f;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,.10);
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
    --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
    --pos: #3987e5; --neg: #e66767;
    --l0: #262624; --l1: #104281; --l2: #1c5cab; --l3: #3987e5; --l4: #9ec5f4;
    --glow: rgba(57,135,229,.16);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --raise: #20201f;
  --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,.10);
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
  --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
  --pos: #3987e5; --neg: #e66767;
  --l0: #262624; --l1: #104281; --l2: #1c5cab; --l3: #3987e5; --l4: #9ec5f4;
  --glow: rgba(57,135,229,.16);
}
* { box-sizing: border-box; margin: 0; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--page); color: var(--ink);
  -webkit-font-smoothing: antialiased; line-height: 1.45;
  background-image: radial-gradient(1200px 500px at 15% -10%, var(--glow), transparent 70%);
  background-repeat: no-repeat;
}
.wrap { max-width: 1280px; margin: 0 auto; padding: 32px clamp(16px, 4vw, 48px) 64px; }
header.top { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap; margin-bottom: 28px; }
.kicker { display: flex; gap: 10px; align-items: center; color: var(--ink-2); font-size: .85rem; font-weight: 500; }
.pulse-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--series-1); box-shadow: 0 0 0 0 var(--series-1); animation: beat 2.2s infinite; }
@keyframes beat { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--series-1) 60%, transparent); } 70% { box-shadow: 0 0 0 12px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
h1 { font-size: clamp(2.2rem, 5vw, 3.6rem); letter-spacing: -.035em; line-height: 1.05; margin-top: 10px; word-break: break-word; }
.meta { color: var(--ink-2); margin-top: 8px; }
.meta b { color: var(--ink); font-weight: 600; }
.toggle {
  font: inherit; font-size: .85rem; color: var(--ink); background: var(--surface); border: 1px solid var(--ring);
  border-radius: 999px; padding: 8px 14px; cursor: pointer;
}
.toggle:hover { background: var(--raise); }
.tiles { display: grid; grid-template-columns: 1.4fr repeat(4, 1fr); gap: 12px; }
.tile, .card, .insight { background: var(--surface); border: 1px solid var(--ring); border-radius: 16px; }
.tile { padding: 18px 20px; display: flex; flex-direction: column; gap: 4px; position: relative; overflow: hidden; }
.tile small, .insight small, .card h2 small { color: var(--muted); font-size: .78rem; font-weight: 500; }
.tile small { text-transform: uppercase; letter-spacing: .06em; }
.tile b { font-size: 2.1rem; font-weight: 650; letter-spacing: -.03em; }
.tile b em { font-style: normal; font-size: 1rem; color: var(--ink-2); font-weight: 500; margin-left: 6px; }
.tile .sub { color: var(--ink-2); font-size: .85rem; }
.hero-tile .spark { position: absolute; right: 18px; top: 22px; width: 45%; height: 52px; }
.spark .series-line { stroke-width: 2; }
.end-dot { fill: var(--series-1); stroke: var(--surface); stroke-width: 2; }
.insights { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 12px 0 24px; }
.insight { padding: 14px 16px; }
.insight p { color: var(--ink-2); font-size: .92rem; margin-top: 2px; }
.insight b { color: var(--ink); font-weight: 600; }
.grid2 { display: grid; grid-template-columns: 1.55fr 1fr; gap: 16px; margin-top: 16px; }
.grid2.even { grid-template-columns: 1fr 1fr; }
.card { padding: 20px 22px; min-width: 0; }
.card h2 { font-size: 1.02rem; font-weight: 600; letter-spacing: -.01em; display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.card.full { margin-top: 16px; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text.axis { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.grid { stroke: var(--grid); stroke-width: 1; }
.baseline { stroke: var(--axis); stroke-width: 1; }
.series-line { fill: none; stroke: var(--series-1); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.guide { stroke: var(--ink-2); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0; }
.guide-dot { fill: var(--series-1); stroke: var(--surface); stroke-width: 2; opacity: 0; }
.line-chart:hover .guide, .line-chart:hover .guide-dot { opacity: 1; }
.band, .hit { fill: transparent; }
.cal { min-width: 720px; }
.cal-scroll { overflow-x: auto; padding-bottom: 4px; }
.cal rect { stroke: var(--surface); stroke-width: 0; transition: transform .1s; transform-box: fill-box; transform-origin: center; }
.cal rect:hover { stroke: var(--ink); stroke-width: 1.5; }
.l0 { fill: var(--l0); background: var(--l0); } .l1 { fill: var(--l1); background: var(--l1); }
.l2 { fill: var(--l2); background: var(--l2); } .l3 { fill: var(--l3); background: var(--l3); }
.l4 { fill: var(--l4); background: var(--l4); }
.cal-legend { display: flex; justify-content: flex-end; align-items: center; gap: 4px; color: var(--muted); font-size: .75rem; margin-top: 10px; }
.cal-legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.cal-legend span { margin: 0 4px; }
.dot { fill: var(--series-1); stroke: var(--surface); stroke-width: 2; }
.punch g:hover .dot { fill: var(--l4); }
.pos { fill: var(--pos); } .neg { fill: var(--neg); }
.churn g:hover path { opacity: .8; }
.key { display: flex; gap: 14px; font-size: .8rem; color: var(--ink-2); font-weight: 400; }
.key i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.hbar { display: grid; grid-template-columns: 130px 1fr 52px; gap: 12px; align-items: center; padding: 5px 0; border-radius: 8px; }
.hbar:hover { background: var(--raise); }
.hbar-label { font-size: .88rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hbar-track { height: 10px; }
.hbar-track i { display: block; height: 100%; background: var(--series-1); border-radius: 0 4px 4px 0; min-width: 4px; }
.hbar-value { text-align: right; font-size: .85rem; color: var(--ink-2); font-variant-numeric: tabular-nums; }
.stack { display: flex; height: 28px; gap: 2px; border-radius: 6px; overflow: hidden; }
.stack i { display: block; min-width: 3px; }
.stack i:first-child { border-radius: 4px 0 0 4px; } .stack i:last-child { border-radius: 0 4px 4px 0; }
.stack i:hover { filter: brightness(1.1); }
.legend { list-style: none; padding: 0; margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; }
.legend li { display: flex; align-items: center; gap: 8px; font-size: .88rem; }
.legend b { width: 10px; height: 10px; border-radius: 3px; flex: none; }
.legend span { margin-left: auto; color: var(--ink-2); font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; font-size: .88rem; }
th { text-align: left; color: var(--muted); font-weight: 500; font-size: .78rem; padding: 6px 8px; border-bottom: 1px solid var(--grid); }
td { padding: 8px; border-bottom: 1px solid var(--grid); font-variant-numeric: tabular-nums; }
td:not(:first-child), th:not(:first-child) { text-align: right; }
tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: var(--raise); }
code { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: .82rem; }
details { margin-top: 10px; font-size: .82rem; color: var(--ink-2); }
details summary { cursor: pointer; }
details .scroll { max-height: 220px; overflow: auto; margin-top: 8px; }
#tip {
  position: fixed; z-index: 10; pointer-events: none; padding: 8px 11px; border-radius: 10px; font-size: .82rem;
  background: var(--raise); color: var(--ink); border: 1px solid var(--ring); box-shadow: 0 8px 24px rgba(0,0,0,.18);
  opacity: 0; transform: translateY(4px); transition: opacity .12s, transform .12s; max-width: 320px;
}
#tip.on { opacity: 1; transform: none; }
footer { color: var(--muted); font-size: .8rem; text-align: center; margin-top: 40px; }
@media (max-width: 1000px) {
  .tiles { grid-template-columns: 1fr 1fr; }
  .hero-tile { grid-column: 1 / -1; }
  .grid2, .grid2.even { grid-template-columns: 1fr; }
}
@media (max-width: 720px) { .insights { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .legend { grid-template-columns: 1fr; } .hbar { grid-template-columns: 96px 1fr 44px; } }
@media (forced-colors: active) { .stack i, .hbar-track i, .pos, .neg, .dot { forced-color-adjust: none; } }
"""

JS = """
const tipEl = document.getElementById('tip');
document.addEventListener('mousemove', (e) => {
  const t = e.target.closest('[data-tip]');
  if (!t) { tipEl.classList.remove('on'); return; }
  tipEl.textContent = t.dataset.tip;
  tipEl.classList.add('on');
  const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
  let x = e.clientX + 14, y = e.clientY - h - 12;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y < 8) y = e.clientY + 18;
  tipEl.style.left = x + 'px'; tipEl.style.top = y + 'px';
  if (t.classList.contains('band')) {
    const svg = t.ownerSVGElement;
    const g = svg.querySelector('.guide'), d = svg.querySelector('.guide-dot');
    g.setAttribute('x1', t.dataset.x); g.setAttribute('x2', t.dataset.x);
    d.setAttribute('cx', t.dataset.x); d.setAttribute('cy', t.dataset.y);
  }
});
document.addEventListener('mouseleave', () => tipEl.classList.remove('on'));
const btn = document.getElementById('theme');
const dark = () => document.documentElement.dataset.theme === 'dark' ||
  (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
const label = () => btn.textContent = dark() ? '☀ Light' : '☾ Dark';
btn.addEventListener('click', () => {
  document.documentElement.dataset.theme = dark() ? 'light' : 'dark';
  try { localStorage.setItem('pulse-theme', document.documentElement.dataset.theme); } catch {}
  label();
});
try { const s = localStorage.getItem('pulse-theme'); if (s) document.documentElement.dataset.theme = s; } catch {}
label();
"""

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pulse | {name}</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <div class="kicker"><span class="pulse-dot"></span>Pulse | repository health report</div>
      <h1>{name}</h1>
      <p class="meta"><b>{period}</b> | {span} of history | generated {generated}</p>
    </div>
    <button class="toggle" id="theme">☾ Dark</button>
  </header>

  <section class="tiles">{tiles}</section>
  <section class="insights">{insights}</section>

  <div class="card">
    <h2>Contribution calendar <small>last 53 weeks</small></h2>
    <div class="cal-scroll">{calendar}</div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Commits per week <small>full history</small></h2>
      {activity}
      <details><summary>Show data table</summary><div class="scroll"><table>
        <thead><tr><th>Week of</th><th>Commits</th></tr></thead><tbody>{weekly_rows}</tbody></table></div></details>
    </div>
    <div class="card">
      <h2>Top contributors <small>by commits</small></h2>
      {people}
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Code churn <span class="key"><span><i style="background:var(--pos)"></i>Lines added</span><span><i style="background:var(--neg)"></i>Lines deleted</span></span></h2>
      {churn}
    </div>
    <div class="card">
      <h2>Languages <small>share of lines changed</small></h2>
      {languages}
    </div>
  </div>

  <div class="card full">
    <h2>When the team commits <small>author local time</small></h2>
    {punchcard}
  </div>

  <div class="grid2 even">
    <div class="card">
      <h2>Hottest files <small>most frequently changed</small></h2>
      <table><thead><tr><th>File</th><th>Commits</th><th>Churn</th><th>Authors</th></tr></thead><tbody>{hot_rows}</tbody></table>
    </div>
    <div class="card">
      <h2>Commit types <small>conventional prefixes &amp; keywords</small></h2>
      {kinds}
    </div>
  </div>

  <footer>Generated by Pulse: pure-Python git analytics, every chart drawn by hand in SVG.</footer>
</div>
<div id="tip" role="tooltip"></div>
<script>{js}</script>
</body>
</html>
"""
