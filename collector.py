"""
Read a repository's history straight out of `git log`, or synthesise a
realistic one for demos. Both paths produce the same list of `Commit`s.
"""

from __future__ import annotations

import math
import random
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

RS, US = "\x1e", "\x1f"  # record / unit separators: never appear in commit text


@dataclass
class FileChange:
    path: str
    added: int
    deleted: int


@dataclass
class Commit:
    sha: str
    author: str
    when: datetime  # author's local time, tz-aware
    subject: str
    files: list[FileChange] = field(default_factory=list)

    @property
    def added(self) -> int:
        return sum(f.added for f in self.files)

    @property
    def deleted(self) -> int:
        return sum(f.deleted for f in self.files)


class GitError(RuntimeError):
    pass


def from_git(repo: Path, since: str | None = None) -> list[Commit]:
    cmd = [
        "git", "-C", str(repo), "log", "--no-merges", "--date=iso-strict", "--numstat",
        f"--pretty=format:{RS}%H{US}%aN{US}%ad{US}%s",
    ]
    if since:
        cmd.append(f"--since={since}")
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, text=True, encoding="utf-8", errors="replace").stdout
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH") from None
    except subprocess.CalledProcessError as e:
        raise GitError(e.stderr.strip() or f"{repo} is not a git repository") from None

    commits = []
    for record in out.split(RS)[1:]:
        header, *stat_lines = record.strip("\n").split("\n")
        sha, author, date, subject = header.split(US, 3)
        c = Commit(sha, author, datetime.fromisoformat(date), subject)
        for line in stat_lines:
            parts = line.split("\t", 2)
            if len(parts) == 3:
                a, d, path = parts
                # binary files report "-"; renames look like "src/{a => b}.py"
                c.files.append(FileChange(path, int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0))
        commits.append(c)
    return commits


# --------------------------------------------------------------------------- #
#  Demo data: a believable year in the life of a product team                 #
# --------------------------------------------------------------------------- #

_AUTHORS = [
    # name, weight, utc offset, start hour, weekend fondness
    ("Maya Chen", 1.00, -8, 9, 0.10),
    ("Lukas Brandt", 0.80, 1, 8, 0.05),
    ("Priya Natarajan", 0.70, 5.5, 10, 0.15),
    ("Diego Alvarez", 0.55, -5, 11, 0.30),
    ("Sora Tanaka", 0.45, 9, 10, 0.05),
    ("Amara Okafor", 0.35, 0, 9, 0.10),
    ("Elliot Park", 0.20, -8, 13, 0.45),
    ("Noor Haddad", 0.12, 2, 9, 0.05),
    ("dependabot", 0.10, 0, 3, 1.00),
]
_FILES = [
    ("src/engine/renderer.py", 9), ("src/engine/scene.py", 7), ("src/engine/shaders.glsl", 4),
    ("src/api/routes.py", 8), ("src/api/auth.py", 5), ("src/api/schemas.py", 4),
    ("web/src/App.tsx", 7), ("web/src/components/Canvas.tsx", 6), ("web/src/hooks/useScene.ts", 4),
    ("web/src/styles/theme.css", 3), ("core/physics.rs", 5), ("core/math.rs", 3),
    ("tests/test_renderer.py", 5), ("tests/test_api.py", 4), ("docs/guide.md", 3), ("README.md", 2),
    ("pyproject.toml", 1), ("web/package.json", 2), (".github/workflows/ci.yml", 1), ("scripts/deploy.sh", 1),
]
_VERBS = {
    "feat": ["add", "introduce", "support", "implement"],
    "fix": ["fix", "resolve", "patch", "handle"],
    "refactor": ["simplify", "extract", "restructure", "clean up"],
    "perf": ["speed up", "cache", "batch", "optimise"],
    "docs": ["document", "explain", "update docs for"],
    "test": ["cover", "add tests for", "stabilise tests for"],
}
_NOUNS = ["shadow pass", "scene graph", "auth tokens", "websocket sync", "camera controls", "asset loader",
          "frustum culling", "rate limiter", "theme tokens", "physics step", "HDR pipeline", "export dialog"]


def demo(seed: int = 42, days: int = 420) -> list[Commit]:
    rng = random.Random(seed)
    end = datetime(2026, 10, 14, 18, tzinfo=timezone.utc)
    start = end - timedelta(days=days)
    releases = [start + timedelta(days=d) for d in range(55, days, 63)]
    file_names, file_w = zip(*_FILES)
    commits: list[Commit] = []

    for day in range(days):
        date = start + timedelta(days=day)
        growth = 0.55 + 0.45 * day / days  # the team grows over time
        crunch = sum(math.exp(-((date - r).days / 6) ** 2) for r in releases)
        holiday = 0.15 if (date.month == 12 and date.day > 20) or (date.month == 1 and date.day < 3) else 1
        for name, weight, tz_off, start_h, weekend in _AUTHORS:
            local = date + timedelta(hours=tz_off)
            is_weekend = local.weekday() >= 5
            rate = weight * growth * holiday * (1 + 1.6 * crunch) * (weekend if is_weekend else 1) * 2.2
            if name == "dependabot":
                rate = 0.9 if local.weekday() == 0 else 0
            for _ in range(_poisson(rng, rate)):
                hour = min(23.9, max(0, rng.gauss(start_h + 4.5, 3.2) + (rng.random() < 0.08) * 7))
                tz = timezone(timedelta(hours=tz_off))
                when = datetime(local.year, local.month, local.day, tzinfo=tz) + timedelta(hours=hour)
                commits.append(_fake_commit(rng, name, when, file_names, file_w))

    commits.sort(key=lambda c: c.when, reverse=True)
    return commits


def _fake_commit(rng, name, when, file_names, file_w) -> Commit:
    if name == "dependabot":
        pkg = rng.choice(["vite", "pydantic", "fastapi", "react", "pytest", "ruff"])
        files = [FileChange(rng.choice(["web/package.json", "pyproject.toml"]), 1, 1)]
        return Commit(f"{rng.getrandbits(160):040x}", name, when, f"chore(deps): bump {pkg}", files)
    kind = rng.choices(list(_VERBS), weights=[5, 4, 2, 1, 1, 1.5])[0]
    subject = f"{kind}: {rng.choice(_VERBS[kind])} {rng.choice(_NOUNS)}"
    touched = set(rng.choices(file_names, weights=file_w, k=rng.choice([1, 1, 2, 2, 3, 4, 6])))
    scale = {"feat": 60, "refactor": 45, "perf": 25, "fix": 12, "docs": 20, "test": 30}[kind]
    files = []
    for path in touched:
        added = int(rng.expovariate(1 / scale)) + 1
        ratio = {"refactor": 0.9, "perf": 0.6, "fix": 0.5}.get(kind, 0.25)
        files.append(FileChange(path, added, int(added * ratio * rng.uniform(0.4, 1.6))))
    return Commit(f"{rng.getrandbits(160):040x}", name, when, subject, files)


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1
