"""Collect a deterministic summary of the past N days for the weekly-report skill.

    python -m pipeline.week_context [--days 7]   # writes .cache/week.json

Uses git history (what landed on the default branch) and, when `gh` is available,
merged PRs / closed issues. The LLM then reads the listed files itself.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import timedelta

from .common import CACHE, ROOT, log, today, write_json

TRACKED = ("inbox/", "notes/", "wiki/", "reports/topics/")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    end = today()
    start = end - timedelta(days=a.days)

    changes: dict[str, set[str]] = {"added": set(), "modified": set()}
    out = git("log", f"--since={start.isoformat()}", "--name-status", "--pretty=format:")
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or not parts[-1].startswith(TRACKED):
            continue
        (changes["added"] if parts[0] == "A" else changes["modified"]).add(parts[-1])
    changes["modified"] -= changes["added"]

    ctx = {
        "range": [start.isoformat(), end.isoformat()],
        "files_added": sorted(changes["added"]),
        "files_modified": sorted(changes["modified"]),
        "merged_prs": [],
        "closed_issues": [],
        "open_topics": [],
    }
    if shutil.which("gh"):
        def gh_json(*args):
            try:
                return json.loads(subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout)
            except Exception as e:
                log(f"  [WARN] gh {' '.join(args[:2])}: {e}")
                return []
        ctx["merged_prs"] = gh_json("pr", "list", "--state", "merged", "--search", f"merged:>={start}",
                                    "--json", "number,title,labels,mergedAt", "--limit", "100")
        ctx["closed_issues"] = gh_json("issue", "list", "--state", "closed", "--search", f"closed:>={start}",
                                       "--json", "number,title,labels", "--limit", "100")
        ctx["open_topics"] = gh_json("issue", "list", "--state", "open", "--label", "research-topic",
                                     "--json", "number,title", "--limit", "50")
    write_json(CACHE / "week.json", ctx)
    log(f"[week] {start}..{end}: +{len(ctx['files_added'])} files, {len(ctx['merged_prs'])} PRs")


if __name__ == "__main__":
    main()
