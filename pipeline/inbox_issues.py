"""Turn ticked checklist items in merged PRs into `to-read` issues (runs locally via `gh`).

    python -m pipeline.inbox_issues --recent-days 14 [--dry-run]   # scan recently merged PRs
    python -m pipeline.inbox_issues --pr 12 [--dry-run]            # one PR

Idempotent: an item whose id already appears in any issue body is skipped, so it is
safe to run on every local sync.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import timedelta

from .common import log, today

ITEM = re.compile(r"^- \[[xX]\] (?P<text>.*?)<!-- read type=(?P<type>\w+) id=(?P<id>\S+) url=(?P<url>\S+) -->")
TITLE = re.compile(r"\*\*(.+?)\*\*")


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def ticked(body: str) -> list[dict]:
    out = []
    for line in body.splitlines():
        m = ITEM.match(line.strip())
        if m:
            t = TITLE.search(m["text"])
            out.append({"type": m["type"], "id": m["id"], "url": m["url"],
                        "title": t.group(1) if t else m["id"]})
    return out


def already_tracked(item_id: str) -> bool:
    found = json.loads(gh("issue", "list", "--state", "all", "--search", f'"{item_id}" in:body',
                          "--json", "number", "--limit", "1"))
    return bool(found)


def convert(pr: str, body: str, dry_run: bool) -> int:
    created = 0
    for it in ticked(body):
        if already_tracked(it["id"]):
            continue
        issue_body = "\n".join([
            f"- 类型：{it['type']}",
            f"- ID：`{it['id']}`",
            f"- 链接：{it['url']}",
            f"- 来源：PR #{pr}",
        ])
        title = f"[read] {it['title']}"
        if dry_run:
            log(f"  would create: {title}")
            continue
        url = gh("issue", "create", "--title", title, "--body", issue_body,
                 "--label", "to-read", "--label", f"source:{it['type']}").strip()
        log(f"  created {url}  {title}")
        created += 1
    return created


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pr")
    g.add_argument("--recent-days", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.pr:
        prs = [{"number": a.pr, "body": json.loads(gh("pr", "view", a.pr, "--json", "body"))["body"] or ""}]
    else:
        since = (today() - timedelta(days=a.recent_days)).isoformat()
        prs = json.loads(gh("pr", "list", "--state", "merged", "--search", f"merged:>={since}",
                            "--json", "number,body", "--limit", "100"))
    total = 0
    for pr in prs:
        if "<!-- read type=" in (pr["body"] or ""):
            total += convert(str(pr["number"]), pr["body"], a.dry_run)
    log(f"[sync] scanned {len(prs)} merged PR(s), created {total} issue(s)")


if __name__ == "__main__":
    main()
