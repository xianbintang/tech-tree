"""Shared helpers: paths, config, HTTP, scoring."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
TZ = ZoneInfo(os.environ.get("TECH_TREE_TZ", "Asia/Shanghai"))
UA = "tech-tree-bot/1.0 (+https://github.com/xianbintang/tech-tree)"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_config(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / f"{name}.yaml").read_text())


def today() -> date:
    return datetime.now(TZ).date()


def fetch_url(url: str, timeout: int = 30) -> str:
    try:
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:  # network errors must never kill the whole run
        log(f"  [WARN] fetch failed {url}: {e}")
        return ""


def read_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text())
    return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class Scorer:
    """Keyword scoring ported from dailypaper-skills fetch_and_score.py."""

    def __init__(self, interests: dict):
        s = interests["scoring"]
        self.keywords = [k.lower() for k in s["keywords"]]
        self.negative = [k.lower() for k in s["negative_keywords"]]
        self.boost = [k.lower() for k in s["domain_boost_keywords"]]

    def score(self, title: str, text: str, hf_upvotes: int | None = None) -> int:
        title_l = title.lower()
        text_l = f"{title} {text}".lower()
        if any(neg in text_l for neg in self.negative):
            return -999

        score = 0
        hits = 0
        for kw in self.keywords:
            if kw in title_l:
                score += 3
                hits += 1
            elif kw in text_l:
                score += 1
                hits += 1

        domain_hits = sum(1 for kw in self.boost if kw in text_l)
        score += min(domain_hits, 2)

        # Trending boost only when the paper is on-topic, so popular but
        # irrelevant papers don't flood the list.
        if hf_upvotes is not None:
            up = hf_upvotes or 0
            if hits or domain_hits:
                score += 3 if up >= 10 else 2 if up >= 5 else 1 if up >= 2 else 0
            elif up >= 20:
                score += 1
        return score
