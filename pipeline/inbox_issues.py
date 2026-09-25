"""After a daily PR is merged: turn ticked checklist items into `to-read` issues.

    python -m pipeline.inbox_issues --pr 12 [--dispatch] [--dry-run]

Issues created with the workflow's GITHUB_TOKEN do not fire `issues` events, so with
--dispatch we explicitly start deep-read.yml via workflow_dispatch for each new issue.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess

from .common import log

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True)
    ap.add_argument("--dispatch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    body = json.loads(gh("pr", "view", a.pr, "--json", "body"))["body"] or ""
    items = ticked(body)
    log(f"PR #{a.pr}: {len(items)} ticked item(s)")
    for it in items:
        if already_tracked(it["id"]):
            log(f"  skip {it['id']}: issue already exists")
            continue
        issue_body = "\n".join([
            f"- 类型：{it['type']}",
            f"- ID：`{it['id']}`",
            f"- 链接：{it['url']}",
            f"- 来源：每日推送 PR #{a.pr}",
            "",
            "<!-- created by inbox_issues.py -->",
        ])
        title = f"[read] {it['title']}"
        if a.dry_run:
            log(f"  would create: {title}")
            continue
        url = gh("issue", "create", "--title", title, "--body", issue_body,
                 "--label", "to-read", "--label", f"source:{it['type']}").strip()
        number = url.rsplit("/", 1)[-1]
        log(f"  created #{number} {title}")
        if a.dispatch:
            gh("workflow", "run", "deep-read.yml", "-f", f"issue={number}")
            log(f"  dispatched deep-read for #{number}")


if __name__ == "__main__":
    main()
