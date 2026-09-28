"""Reading lists: one tracking issue per category, processed as one PR per batch.

    python -m pipeline.reading_list create config/reading-lists/dsec-refs.yaml [--dry-run]
    python -m pipeline.reading_list next <issue> [--max 8]           # JSON of the next batch
    python -m pipeline.reading_list done <issue> --pr N <id> [<id>…]  # mark items read
    python -m pipeline.reading_list mark <issue> --text "…" <id>…     # custom end-of-line mark
    python -m pipeline.reading_list left <issue> [--scope all|queue]  # items still to read

Checkbox semantics match daily PRs: **ticked = "I want to read this"**.
  - some unread items ticked → the next batch reads only the ticked ones
  - nothing ticked           → the next batch reads every unread item
Finished items are marked at the end of the line (` ✅ 已读（#PR）`) and unticked;
the checkbox never means "done".

Line format (same hidden marker as daily PRs):
  - [ ] **Title** — why <!-- read type=… id=… url=… --> ✅ 已读（#33）
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from .common import ROOT, log, read_json, write_json
from .inbox_issues import gh

LINE = re.compile(
    r"^- \[(?P<sel>[ xX])\] \*\*(?P<title>.+?)\*\*(?: — (?P<why>.*?))? "
    r"<!-- read type=(?P<type>\w+) id=(?P<id>\S+) url=(?P<url>\S+) -->(?P<mark>\s*[✅↪].*?)?\s*$"
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
        "给本 issue 打上 `to-read` 标签，本地 queue 会按分类精读成**一个 PR**（每个 PR 最多 `BATCH_MAX` 篇，剩余的顺延）。",
        "**勾选 = 我要读**：勾了部分条目就只读勾选的；一个都不勾就读全部。读完的条目行尾会标上 `✅ 已读（#PR）`。",
        f"清单源文件：`config/reading-lists/{spec['name']}.yaml`",
    ]
    return "\n".join(lines) + "\n"


def items(body: str) -> list[dict]:
    out = []
    for line in body.splitlines():
        m = LINE.match(line.strip())
        if m:
            d = m.groupdict()
            d["selected"] = d.pop("sel").lower() == "x"
            d["done"] = bool((d.pop("mark") or "").strip())
            out.append(d)
    return out


def queue(all_items: list[dict]) -> list[dict]:
    """Unread items the next batch should take: the ticked ones if any, else all."""
    unread = [i for i in all_items if not i["done"]]
    picked = [i for i in unread if i["selected"]]
    return picked or unread


def parent_of(body: str) -> str:
    m = MARK.search(body)
    return m.group(3) if m else ""


def body_of(issue: str) -> str:
    return json.loads(gh("issue", "view", issue, "--json", "body"))["body"] or ""


def cmd_create(path: str, dry_run: bool) -> None:
    """Idempotent. GitHub's issue listing lags a few seconds behind creation, so the
    source of truth is state/reading-lists/<name>.json (committed); the listing (matched
    on the hidden name/key marker) only covers issues created elsewhere."""
    spec = yaml.safe_load(Path(path).read_text())
    state_path = ROOT / "state" / "reading-lists" / f"{spec['name']}.json"
    state: dict[str, int] = read_json(state_path, {})
    if not dry_run:
        for i in json.loads(gh("issue", "list", "--state", "open", "--limit", "300", "--json", "number,body")):
            m = MARK.search(i["body"] or "")
            if m and m.group(1) == spec["name"]:
                state.setdefault(m.group(2), i["number"])
    for cat in spec["categories"]:
        title = issue_title(spec, cat)
        if cat["key"] in state:
            log(f"  exists #{state[cat['key']]}  {title}")
            continue
        body = render_body(spec, cat)
        if dry_run:
            print(f"==== {title}\n{body}")
            continue
        args = ["issue", "create", "--title", title, "--body", body]
        for label in spec.get("labels", ["reading-list"]):
            args += ["--label", label]
        url = gh(*args).strip()
        state[cat["key"]] = int(url.rsplit("/", 1)[-1])
        write_json(state_path, dict(sorted(state.items())))  # after each create: safe on crash
        log(f"  created {url}  {title}")
    if not dry_run:
        write_json(state_path, dict(sorted(state.items())))


def cmd_next(issue: str, limit: int) -> None:
    body = body_of(issue)
    todo = queue(items(body))[:limit]
    parent = parent_of(body)
    for i in todo:
        i["parent"] = parent
    print(json.dumps(todo, ensure_ascii=False, indent=2))


def cmd_mark(issue: str, ids: list[str], text: str) -> None:
    """Append an end-of-line mark (and untick) — the only way an item becomes done."""
    body = body_of(issue)
    wanted = set(ids)
    new, n = [], 0
    for line in body.splitlines():
        m = LINE.match(line.strip())
        if m and m["id"] in wanted:
            line = line.rstrip()
            if m["mark"]:
                line = line[: len(line) - len(m["mark"].rstrip())].rstrip()
            line = line.replace("- [x]", "- [ ]", 1).replace("- [X]", "- [ ]", 1) + f" {text}"
            n += 1
        new.append(line)
    gh("issue", "edit", issue, "--body", "\n".join(new) + "\n")
    log(f"  marked {n} item(s) on #{issue}: {text}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("path"); c.add_argument("--dry-run", action="store_true")
    n = sub.add_parser("next"); n.add_argument("issue"); n.add_argument("--max", type=int, default=8)
    d = sub.add_parser("done"); d.add_argument("issue"); d.add_argument("--pr", required=True); d.add_argument("ids", nargs="+")
    mk = sub.add_parser("mark"); mk.add_argument("issue"); mk.add_argument("--text", required=True); mk.add_argument("ids", nargs="+")
    left = sub.add_parser("left"); left.add_argument("issue"); left.add_argument("--scope", choices=["all", "queue"], default="all")
    a = ap.parse_args()
    if a.cmd == "create":
        cmd_create(a.path, a.dry_run)
    elif a.cmd == "next":
        cmd_next(a.issue, a.max)
    elif a.cmd == "done":
        cmd_mark(a.issue, a.ids, f"✅ 已读（#{a.pr}）")
    elif a.cmd == "mark":
        cmd_mark(a.issue, a.ids, a.text)
    else:
        its = items(body_of(a.issue))
        print(len(queue(its)) if a.scope == "queue" else sum(1 for i in its if not i["done"]))


if __name__ == "__main__":
    main()
