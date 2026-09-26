"""Reading lists: one tracking issue per category, processed as one PR per batch.

    python -m pipeline.reading_list create config/reading-lists/dsec-refs.yaml [--dry-run]
    python -m pipeline.reading_list next <issue> [--max 8]      # JSON of unticked items
    python -m pipeline.reading_list tick <issue> <id> [<id>…]    # tick finished items
    python -m pipeline.reading_list left <issue>                 # count of unticked items

Issue bodies use the same hidden marker as daily PRs, so `inbox_issues.ITEM`-style parsing
works on them: `- [ ] **Title** — why <!-- read type=… id=… url=… -->`.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from .common import log
from .inbox_issues import gh

LINE = re.compile(
    r"^- \[(?P<done>[ xX])\] \*\*(?P<title>.+?)\*\*(?: — (?P<why>.*?))? "
    r"<!-- read type=(?P<type>\w+) id=(?P<id>\S+) url=(?P<url>\S+) -->\s*$"
)
LIST_MARK = "<!-- reading-list name={name} key={key} parent={parent} -->"
MARK = re.compile(r"<!-- reading-list name=(\S+) key=(\S+) parent=(\S*) -->")


def issue_title(spec: dict, cat: dict) -> str:
    return f"[reading-list] {spec['name']} · {cat['key']} {cat['title']}"


def render_body(spec: dict, cat: dict) -> str:
    parent = spec.get("parent") or {}
    lines = [
        LIST_MARK.format(name=spec["name"], key=cat["key"], parent=parent.get("id", "")),
        "",
    ]
    if parent:
        lines += [f"**母论文**：[{parent['title']}]({parent['url']}) · `[[{parent['id']}]]`", ""]
    lines += [cat.get("description", "").strip(), "", "### 清单", ""]
    for it in cat["items"]:
        lines.append(
            f"- [ ] **{it['title']}** — {it.get('why', '')} "
            f"<!-- read type={it['type']} id={it['id']} url={it['url']} -->"
        )
    lines += [
        "",
        "---",
        "给本 issue 打上 `to-read` 标签，本地 queue 会把整个分类精读成**一个 PR**"
        "（每个 PR 最多 `BATCH_MAX` 篇，剩余的顺延）；读完的条目会自动打勾。",
        f"清单源文件：`config/reading-lists/{spec['name']}.yaml`",
    ]
    return "\n".join(lines) + "\n"


def items(body: str) -> list[dict]:
    out = []
    for line in body.splitlines():
        m = LINE.match(line.strip())
        if m:
            d = m.groupdict()
            d["done"] = d["done"].lower() == "x"
            out.append(d)
    return out


def parent_of(body: str) -> str:
    m = MARK.search(body)
    return m.group(3) if m else ""


def body_of(issue: str) -> str:
    return json.loads(gh("issue", "view", issue, "--json", "body"))["body"] or ""


def cmd_create(path: str, dry_run: bool) -> None:
    spec = yaml.safe_load(Path(path).read_text())
    existing = {
        i["title"]: i["number"]
        for i in json.loads(gh("issue", "list", "--state", "all", "--label", "reading-list",
                               "--json", "number,title", "--limit", "200"))
    } if not dry_run else {}
    for cat in spec["categories"]:
        title = issue_title(spec, cat)
        if title in existing:
            log(f"  exists #{existing[title]}  {title}")
            continue
        body = render_body(spec, cat)
        if dry_run:
            print(f"==== {title}\n{body}")
            continue
        args = ["issue", "create", "--title", title, "--body", body]
        for label in spec.get("labels", ["reading-list"]):
            args += ["--label", label]
        url = gh(*args).strip()
        log(f"  created {url}  {title}")


def cmd_next(issue: str, limit: int) -> None:
    body = body_of(issue)
    todo = [i for i in items(body) if not i["done"]][:limit]
    parent = parent_of(body)
    for i in todo:
        i["parent"] = parent
    print(json.dumps(todo, ensure_ascii=False, indent=2))


def cmd_tick(issue: str, ids: list[str]) -> None:
    body = body_of(issue)
    wanted = set(ids)
    new = []
    for line in body.splitlines():
        m = LINE.match(line.strip())
        if m and m["id"] in wanted:
            line = line.replace("- [ ]", "- [x]", 1)
        new.append(line)
    gh("issue", "edit", issue, "--body", "\n".join(new) + "\n")
    log(f"  ticked {len(wanted)} item(s) on #{issue}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("path"); c.add_argument("--dry-run", action="store_true")
    n = sub.add_parser("next"); n.add_argument("issue"); n.add_argument("--max", type=int, default=8)
    t = sub.add_parser("tick"); t.add_argument("issue"); t.add_argument("ids", nargs="+")
    left = sub.add_parser("left"); left.add_argument("issue")
    a = ap.parse_args()
    if a.cmd == "create":
        cmd_create(a.path, a.dry_run)
    elif a.cmd == "next":
        cmd_next(a.issue, a.max)
    elif a.cmd == "tick":
        cmd_tick(a.issue, a.ids)
    else:
        print(sum(1 for i in items(body_of(a.issue)) if not i["done"]))


if __name__ == "__main__":
    main()
