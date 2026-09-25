"""arXiv + HuggingFace paper fetchers."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from .common import Scorer, fetch_url, log

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})")


def _paper(arxiv_id: str, **kw) -> dict:
    return {
        "key": f"arxiv:{arxiv_id}",
        "type": "paper",
        "id": arxiv_id,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
        **kw,
    }


def fetch_hf(target: date, cfg: dict, scorer: Scorer) -> list[dict]:
    endpoints = []
    if cfg.get("daily", True):
        # HF lists by announcement date; include yesterday to cover timezone skew.
        for d in (target - timedelta(days=1), target):
            endpoints.append(("hf-daily", f"https://huggingface.co/api/daily_papers?date={d.isoformat()}&limit=100"))
    if cfg.get("trending", True):
        endpoints.append(("hf-trending", "https://huggingface.co/api/daily_papers?sort=trending&limit=50"))

    out = []
    for source, url in endpoints:
        log(f"  fetching {source}: {url}")
        raw = fetch_url(url)
        try:
            items = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            log(f"  [WARN] bad JSON from {source}")
            continue
        for item in items:
            p = item.get("paper", {})
            aid = p.get("id", "")
            if not ARXIV_ID.fullmatch(aid or ""):
                continue
            authors = ", ".join(a.get("name", "") for a in p.get("authors", []) if isinstance(a, dict))
            title = " ".join((p.get("title") or "").split())
            abstract = " ".join((p.get("summary") or "").split())
            up = p.get("upvotes", 0) or 0
            out.append(_paper(
                aid, title=title, authors=authors, abstract=abstract,
                date=(p.get("publishedAt") or "")[:10], source=source, hf_upvotes=up,
                score=scorer.score(title, abstract, hf_upvotes=up),
            ))
    log(f"  HF: {len(out)} raw entries")
    return out


def fetch_arxiv(cfg: dict, scorer: Scorer) -> list[dict]:
    cats = "+OR+".join(f"cat:{c}" for c in cfg["categories"])
    n = cfg.get("max_results_per_day", 400)
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query=({cats})&sortBy=submittedDate&sortOrder=descending&max_results={n}"
    )
    log(f"  fetching arXiv (max_results={n})")
    xml_text = fetch_url(url, timeout=120)
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log(f"  [WARN] arXiv XML parse error: {e}")
        return []

    out = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title_el = entry.find("atom:title", ATOM_NS)
        summary_el = entry.find("atom:summary", ATOM_NS)
        id_el = entry.find("atom:id", ATOM_NS)
        if title_el is None or summary_el is None or id_el is None:
            continue
        m = ARXIV_ID.search(id_el.text or "")
        if not m:
            continue
        title = " ".join(title_el.text.split())
        abstract = " ".join(summary_el.text.split())
        names = [a.findtext("atom:name", "", ATOM_NS).strip() for a in entry.findall("atom:author", ATOM_NS)]
        cat_el = entry.find("arxiv:primary_category", ATOM_NS)
        published = entry.findtext("atom:published", "", ATOM_NS)[:10]
        out.append(_paper(
            m.group(1), title=title, authors=", ".join(n for n in names if n), abstract=abstract,
            date=published, source="arxiv", category=cat_el.get("term", "") if cat_el is not None else "",
            score=scorer.score(title, abstract),
        ))
    log(f"  arXiv: {len(out)} raw entries")
    return out


def fetch_papers(target: date, cfg: dict, scorer: Scorer) -> list[dict]:
    by_id: dict[str, dict] = {}
    for p in fetch_hf(target, cfg.get("huggingface", {}), scorer) + fetch_arxiv(cfg["arxiv"], scorer):
        prev = by_id.get(p["id"])
        if prev is None or p["score"] > prev["score"]:
            if prev and prev.get("hf_upvotes") and not p.get("hf_upvotes"):
                p["hf_upvotes"] = prev["hf_upvotes"]
            by_id[p["id"]] = p
    return list(by_id.values())
