"""Deterministic knowledge-base health check (the "lint" op of the LLM-wiki pattern).

    python -m pipeline.wiki_lint              # prints report, writes .cache/lint.md
    exit code 0 always; `.cache/lint_count` holds the number of problems.

Checks:
  - broken [[wikilinks]] (target page doesn't exist anywhere in the KB)
  - orphan concept pages (no note/wiki page links to them)
  - notes that link to no concept page at all
  - notes missing required frontmatter fields
"""
from __future__ import annotations

import re

from .common import CACHE, ROOT, log

LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
KB_DIRS = ("notes", "wiki", "reports")
REQUIRED = ("title", "type", "source_url", "created")


def pages() -> dict[str, list]:
    out: dict[str, list] = {}
    for d in KB_DIRS:
        for p in (ROOT / d).rglob("*.md"):
            out.setdefault(p.stem, []).append(p)
    return out


def frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[3:end]
    return ""


def main() -> None:
    index = pages()
    inbound: dict[str, int] = {name: 0 for name in index}
    broken, lonely, bad_fm = [], [], []

    for name, paths in index.items():
        for path in paths:
            text = path.read_text()
            rel = path.relative_to(ROOT)
            targets = {t.strip() for t in LINK.findall(text)}
            for t in targets:
                if t in index:
                    if t != name:
                        inbound[t] += 1
                else:
                    broken.append(f"`{rel}` → `[[{t}]]`")
            if rel.parts[0] == "notes":
                if not any((ROOT / "wiki" / "concepts" / f"{t}.md").exists() for t in targets):
                    lonely.append(f"`{rel}`")
                fm = frontmatter(text)
                missing = [k for k in REQUIRED if not re.search(rf"^{k}:", fm, re.M)]
                if missing:
                    bad_fm.append(f"`{rel}` 缺少 {', '.join(missing)}")

    orphans = [f"`{p.relative_to(ROOT)}`" for p in (ROOT / "wiki" / "concepts").glob("*.md") if inbound.get(p.stem, 0) == 0]

    sections = [
        ("断链", broken, "创建对应概念页，或改成已有页面名"),
        ("孤儿概念页", orphans, "在相关笔记里链接它，或合并进其它概念页"),
        ("未链接任何概念的笔记", lonely, "跑 ingest-wiki 把笔记编译进概念页"),
        ("frontmatter 不完整", bad_fm, "补齐字段"),
    ]
    total = sum(len(items) for _, items, _ in sections)
    md = [f"共发现 **{total}** 个问题。", ""]
    for title, items, hint in sections:
        if items:
            md += [f"### {title}（{len(items)}）", f"_建议：{hint}_", ""] + [f"- {i}" for i in items[:100]] + [""]
    CACHE.mkdir(exist_ok=True)
    (CACHE / "lint.md").write_text("\n".join(md))
    (CACHE / "lint_count").write_text(str(total))
    log("\n".join(md))


if __name__ == "__main__":
    main()
