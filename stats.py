"""Turn a list of commits into the aggregates the dashboard draws."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import PurePosixPath

from collector import Commit

LANGUAGES = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
    ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".swift": "Swift", ".rb": "Ruby",
    ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cs": "C#", ".php": "PHP",
    ".css": "CSS", ".scss": "CSS", ".html": "HTML", ".vue": "Vue", ".svelte": "Svelte",
    ".md": "Markdown", ".rst": "Markdown", ".json": "Config", ".toml": "Config", ".yml": "Config",
    ".yaml": "Config", ".ini": "Config", ".sh": "Shell", ".ps1": "Shell", ".sql": "SQL",
    ".glsl": "GLSL", ".ipynb": "Jupyter",
}
RENAME = re.compile(r"\{([^{}]*?) => ([^{}]*?)\}")


def _clean_path(path: str) -> str:
    """git numstat renders renames as `a/{old => new}/b`; keep the new name."""
    if "=>" not in path:
        return path
    if "{" in path:
        return RENAME.sub(lambda m: m.group(2), path).replace("//", "/")
    return path.split(" => ")[-1]


def language_of(path: str) -> str:
    return LANGUAGES.get(PurePosixPath(path).suffix.lower(), "Other")


@dataclass
class Report:
    name: str
    commits: int
    authors: int
    added: int
    deleted: int
    files: int
    first: date
    last: date
    active_days: int
    longest_streak: int
    streak_end: date
    busiest_day: tuple[date, int]
    daily: dict[date, int]           # last 53 weeks, every day present
    weekly: list[tuple[date, int]]   # whole history, week start -> commits
    punchcard: list[list[int]]       # [weekday][hour]
    contributors: list[dict]
    churn: list[dict]                # per month: added / deleted
    languages: list[tuple[str, int]]
    hot_files: list[dict]
    kinds: list[tuple[str, int]]


def build(name: str, commits: list[Commit]) -> Report:
    if not commits:
        raise ValueError("No commits to analyse.")
    days = Counter(c.when.date() for c in commits)
    first, last = min(days), max(days)

    # streaks
    longest, run, streak_end, prev = 0, 0, first, None
    for d in sorted(days):
        run = run + 1 if prev and (d - prev).days == 1 else 1
        if run > longest:
            longest, streak_end = run, d
        prev = d

    # calendar: 53 full weeks ending on the Saturday after the last commit
    cal_end = last + timedelta(days=(5 - last.weekday()) % 7)
    cal_start = cal_end - timedelta(days=53 * 7 - 1)
    daily = {cal_start + timedelta(days=i): days.get(cal_start + timedelta(days=i), 0) for i in range(53 * 7)}

    # weekly series, Monday-based, gaps filled with zero
    weeks = Counter(d - timedelta(days=d.weekday()) for d in (c.when.date() for c in commits))
    w, weekly = min(weeks), []
    while w <= max(weeks):
        weekly.append((w, weeks.get(w, 0)))
        w += timedelta(days=7)

    punch = [[0] * 24 for _ in range(7)]
    for c in commits:
        punch[c.when.weekday()][c.when.hour] += 1

    by_author: dict[str, dict] = defaultdict(lambda: {"commits": 0, "added": 0, "deleted": 0, "days": set()})
    for c in commits:
        a = by_author[c.author]
        a["commits"] += 1
        a["added"] += c.added
        a["deleted"] += c.deleted
        a["days"].add(c.when.date())
    contributors = sorted(
        ({"name": n, "commits": v["commits"], "added": v["added"], "deleted": v["deleted"], "days": len(v["days"])}
         for n, v in by_author.items()),
        key=lambda r: -r["commits"],
    )

    months: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    lang = Counter()
    file_hits: dict[str, list[int]] = defaultdict(lambda: [0, 0, set()])  # commits, churn, authors
    touched = set()
    for c in commits:
        m = months[c.when.strftime("%Y-%m")]
        m[0] += c.added
        m[1] += c.deleted
        for f in c.files:
            path = _clean_path(f.path)
            touched.add(path)
            lang[language_of(path)] += f.added + f.deleted
            h = file_hits[path]
            h[0] += 1
            h[1] += f.added + f.deleted
            h[2].add(c.author)
    churn = [{"month": k, "added": v[0], "deleted": v[1]} for k, v in sorted(months.items())]
    hot = sorted(file_hits.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))[:10]

    kinds = Counter()
    for c in commits:
        m = re.match(r"(\w+)(\(.+?\))?!?:", c.subject)
        kinds[m.group(1).lower() if m else _guess_kind(c.subject)] += 1

    busiest = max(days.items(), key=lambda kv: kv[1])
    return Report(
        name=name,
        commits=len(commits),
        authors=len(by_author),
        added=sum(c.added for c in commits),
        deleted=sum(c.deleted for c in commits),
        files=len(touched),
        first=first,
        last=last,
        active_days=len(days),
        longest_streak=longest,
        streak_end=streak_end,
        busiest_day=busiest,
        daily=daily,
        weekly=weekly,
        punchcard=punch,
        contributors=contributors,
        churn=churn,
        languages=lang.most_common(),
        hot_files=[{"path": p, "commits": v[0], "churn": v[1], "authors": len(v[2])} for p, v in hot],
        kinds=kinds.most_common(),
    )


def _guess_kind(subject: str) -> str:
    s = subject.lower()
    for kind, words in (("fix", ("fix", "bug", "patch", "resolve")), ("feat", ("add", "implement", "support", "new")),
                        ("docs", ("doc", "readme")), ("test", ("test",)), ("refactor", ("refactor", "clean", "rename")),
                        ("chore", ("bump", "merge", "release", "version"))):
        if any(w in s for w in words):
            return kind
    return "other"
