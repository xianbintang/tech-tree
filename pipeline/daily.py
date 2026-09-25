"""Daily ingest: deterministic fetch → (LLM triage) → render inbox + PR body.

    python -m pipeline.daily fetch  [--date YYYY-MM-DD]   # writes .cache/candidates.json
    # optional: triage skill writes .cache/triage.json
    python -m pipeline.daily render                        # writes inbox/, state/, .cache/pr_*.md
"""
from __future__ import annotations

import argparse
import os
from datetime import date

from .common import CACHE, ROOT, Scorer, load_config, log, read_json, today, write_json
from .papers import fetch_papers
from .posts import fetch_posts
from .state import load_seen, write_seen

CANDIDATES = CACHE / "candidates.json"
TRIAGE = CACHE / "triage.json"


def _age_months(arxiv_id: str, day: date) -> int:
    """arXiv ids start with YYMM of first submission."""
    yy, mm = int(arxiv_id[:2]), int(arxiv_id[2:4])
    return (day.year - 2000 - yy) * 12 + (day.month - mm)


def cmd_fetch(day: date) -> None:
    interests = load_config("interests")
    sources = load_config("sources")
    limits = interests["limits"]
    scorer = Scorer(interests)
    seen = load_seen()
    log(f"[fetch] {day}  seen={len(seen)}")

    papers = [
        p for p in fetch_papers(day, sources["papers"], scorer)
        if p["score"] >= limits["paper_min_score"] and p["key"] not in seen
        and _age_months(p["id"], day) <= limits.get("paper_max_age_months", 3)
    ]
    papers.sort(key=lambda p: (p["score"], p.get("hf_upvotes") or 0), reverse=True)
    papers = papers[: limits["candidates_papers"]]

    posts, bootstrap = fetch_posts(day, sources["posts"], seen, scorer)
    posts = [p for p in posts if p["score"] >= limits["post_min_score"] and p["key"] not in seen]
    # the same URL can appear in two feeds
    posts = list({p["key"]: p for p in sorted(posts, key=lambda p: p["score"])}.values())
    posts.sort(key=lambda p: p["score"], reverse=True)
    posts = posts[: limits["candidates_posts"]]

    for item in papers + posts:
        item["abstract"] = (item.get("abstract") or "")[:1500]

    write_json(CANDIDATES, {"date": day.isoformat(), "papers": papers, "posts": posts, "bootstrap": bootstrap})
    log(f"[fetch] candidates: {len(papers)} papers, {len(posts)} posts (+{len(bootstrap)} bootstrap keys)")


def _pick(cands: list[dict], triaged: list[dict] | None, n: int) -> list[dict]:
    """Merge LLM triage (ids + text only) onto candidates; never trust LLM-made URLs."""
    by_id = {c["id"]: c for c in cands}
    if triaged is None:
        return [dict(c) for c in cands[:n]]
    out = []
    for t in triaged:
        c = by_id.get(str(t.get("id")))
        if c:
            out.append({**c, **{k: t[k] for k in ("tldr", "why", "tags", "must_read") if k in t}})
    return out


def _meta(p: dict) -> str:
    bits = [f"`{p['id']}`" if p["type"] == "paper" else f"`{p['source']}`", f"score {p['score']}"]
    if p.get("hf_upvotes"):
        bits.append(f"HF👍 {p['hf_upvotes']}")
    if p.get("date"):
        bits.append(p["date"])
    link = f"[arXiv]({p['url']}) · [PDF]({p['pdf']})" if p["type"] == "paper" else f"[原文]({p['url']})"
    return " · ".join(bits) + " · " + link


def _section(items: list[dict]) -> list[str]:
    lines = []
    for i, p in enumerate(items, 1):
        star = " ⭐" if p.get("must_read") else ""
        lines += [f"### {i}. {p['title']}{star}", "", _meta(p), ""]
        if p.get("tldr"):
            lines += [f"**TL;DR**：{p['tldr']}", ""]
        if p.get("why"):
            lines += [f"**推荐理由**：{p['why']}", ""]
        if p.get("tags"):
            lines += [" ".join(f"`#{t}`" for t in p["tags"]), ""]
        if p.get("abstract"):
            lines += ["<details><summary>摘要</summary>", "", p["abstract"], "", "</details>", ""]
    return lines


def _checklist(items: list[dict]) -> list[str]:
    out = []
    for p in items:
        star = "⭐ " if p.get("must_read") else ""
        tldr = f" — {p['tldr']}" if p.get("tldr") else ""
        title = p["title"].replace("*", "")
        out.append(f"- [ ] {star}**{title}**{tldr} <!-- read type={p['type']} id={p['id']} url={p['url']} -->")
    return out


def cmd_render(edition: str = "") -> None:
    cands = read_json(CANDIDATES)
    if cands is None:
        raise SystemExit("no .cache/candidates.json — run `fetch` first")
    limits = load_config("interests")["limits"]
    triage = read_json(TRIAGE)
    mode = "claude" if triage else "keyword"
    papers = _pick(cands["papers"], triage.get("papers") if triage else None, limits["pick_papers"])
    posts = _pick(cands["posts"], triage.get("posts") if triage else None, limits["pick_posts"])
    day = cands["date"]
    name = f"{day}{edition}"  # inbox file / title; state stays per calendar day

    # Everything we showed to the LLM counts as seen, picked or not.
    keys = [c["key"] for c in cands["papers"] + cands["posts"]] + cands.get("bootstrap", [])
    if keys:
        write_seen(date.fromisoformat(day), keys)

    total = len(papers) + len(posts)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"count={total}\nstate_changed={'true' if keys else 'false'}\n")
    if total == 0:
        log("[render] nothing picked today")
        return

    overview = (triage or {}).get("summary", "")
    picked_ids = {p["id"] for p in papers + posts}
    rest = [c for c in cands["papers"] + cands["posts"] if c["id"] not in picked_ids]

    md = [
        "---",
        f"date: {day}",
        f"papers: {len(papers)}",
        f"posts: {len(posts)}",
        f"triage: {mode}",
        "---",
        "",
        f"# 每日推送 · {name}",
        "",
    ]
    if overview:
        md += [f"> {overview}", ""]
    md += [f"候选 {len(cands['papers'])} 篇论文 / {len(cands['posts'])} 篇博文 → 入选 {len(papers)} + {len(posts)}（精排：{mode}）", ""]
    if papers:
        md += ["## 论文", ""] + _section(papers)
    if posts:
        md += ["## 博文 / 技术报告", ""] + _section(posts)
    if rest:
        md += ["## 未入选候选", ""] + [f"- [{c['title']}]({c['url']}) · score {c['score']}" for c in rest] + [""]
    (ROOT / "inbox").mkdir(exist_ok=True)
    (ROOT / "inbox" / f"{name}.md").write_text("\n".join(md))

    body = [f"## 📚 {name} 每日推送", ""]
    if overview:
        body += [f"> {overview}", ""]
    body += [
        "**勾选想精读的条目，然后合并本 PR** —— 下次本地运行（`run-local.sh all`）会为勾选项创建 `to-read` issue 并精读。",
        f"TL;DR、推荐理由和摘要见本 PR「Files changed」里的 `inbox/{name}.md`。",
        "",
    ]
    if papers:
        body += ["### 论文", ""] + _checklist(papers) + [""]
    if posts:
        body += ["### 博文 / 技术报告", ""] + _checklist(posts) + [""]
    body += [
        f"<sub>候选 {len(cands['papers'])}+{len(cands['posts'])} → 入选 {len(papers)}+{len(posts)} · 精排：{mode} · 由 daily-ingest 自动生成</sub>",
    ]
    (CACHE / "pr_body.md").write_text("\n".join(body) + "\n")
    title = f"daily: {name} ({len(papers)} papers, {len(posts)} posts)"
    (CACHE / "pr_title.txt").write_text(title)
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"title={title}\n")
    log(f"[render] inbox/{name}.md  ({len(papers)} papers, {len(posts)} posts, triage={mode})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "render"])
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in TECH_TREE_TZ)")
    ap.add_argument("--edition", default="", help="suffix for a 2nd run on the same day, e.g. -2")
    args = ap.parse_args()
    if args.cmd == "fetch":
        cmd_fetch(date.fromisoformat(args.date) if args.date else today())
    else:
        cmd_render(args.edition)


if __name__ == "__main__":
    main()
