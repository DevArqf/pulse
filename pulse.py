"""
Pulse - turn any git repository into a beautiful, self-contained analytics dashboard.

    python pulse.py                      # analyse the repo you're standing in
    python pulse.py path/to/repo --open  # analyse another repo and open the report
    python pulse.py --demo --open        # generate a showcase report from synthetic history
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from pathlib import Path

import collector
import report
import stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pulse", description="Git repository analytics dashboard generator.")
    p.add_argument("repo", nargs="?", default=".", help="path to a git repository (default: current directory)")
    p.add_argument("-o", "--output", type=Path, help="where to write the HTML report")
    p.add_argument("--since", help='only include commits after this date, e.g. "2025-01-01" or "6 months ago"')
    p.add_argument("--name", help="display name for the report header")
    p.add_argument("--demo", action="store_true", help="use realistic synthetic history instead of a real repo")
    p.add_argument("--open", action="store_true", help="open the report in your browser when done")
    args = p.parse_args(argv)

    started = time.perf_counter()
    if args.demo:
        name = args.name or "aurora-engine"
        commits = collector.demo()
    else:
        repo = Path(args.repo).resolve()
        name = args.name or repo.name
        try:
            commits = collector.from_git(repo, args.since)
        except collector.GitError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1
        if not commits:
            print("✗ No commits found. Try a different --since, or run with --demo.", file=sys.stderr)
            return 1

    data = stats.build(name, commits)
    out = args.output or Path(f"pulse-{name}.html")
    out.write_text(report.render(data), encoding="utf-8")

    elapsed = time.perf_counter() - started
    plural = lambda n, word: f"{n:,} {word}{'s' if n != 1 else ''}"
    print(f"✓ {plural(data.commits, 'commit')} by {plural(data.authors, 'contributor')} "
          f"({data.first:%b %Y} → {data.last:%b %Y}) analysed in {elapsed:.2f}s")
    print(f"✓ Report written to {out.resolve()}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
