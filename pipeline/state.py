"""Dedup state.

One file per day (state/seen/YYYY-MM-DD.txt) so parallel daily PRs never conflict.
`.cache/extra_seen.txt` holds keys from still-open daily/* branches (collected by the
run-local.sh), so an unmerged PR's items are not re-pushed the next day.
"""
from __future__ import annotations

from datetime import date

from .common import CACHE, ROOT

SEEN_DIR = ROOT / "state" / "seen"


def load_seen() -> set[str]:
    seen: set[str] = set()
    files = list(SEEN_DIR.glob("*.txt"))
    extra = CACHE / "extra_seen.txt"
    if extra.exists():
        files.append(extra)
    for f in files:
        seen.update(line.strip() for line in f.read_text().splitlines() if line.strip())
    return seen


def write_seen(day: date, keys: list[str]) -> None:
    SEEN_DIR.mkdir(parents=True, exist_ok=True)
    path = SEEN_DIR / f"{day.isoformat()}.txt"
    existing = set(path.read_text().split()) if path.exists() else set()
    path.write_text("\n".join(sorted(existing | set(keys))) + "\n")
