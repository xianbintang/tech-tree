"""Blog / tech-report fetchers: RSS/Atom feeds and link-scraped listing pages."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html import unescape

import feedparser

from functools import lru_cache

from .common import UA, Scorer, fetch_url, log

TAG = re.compile(r"<[^>]+>")


def post_key(url: str) -> str:
    return "post:" + hashlib.sha1(url.strip().rstrip("/").encode()).hexdigest()[:12]


def _clean(html: str, limit: int = 1500) -> str:
    return " ".join(unescape(TAG.sub(" ", html or "")).split())[:limit]


def _post(url: str, title: str, summary: str, feed: dict, when: str, scorer: Scorer) -> dict:
    key = post_key(url)
    base = scorer.score(title, summary)
    return {
        "key": key,
        "type": "post",
        "id": key.split(":", 1)[1],
        "url": url,
        "title": title,
        "abstract": summary,
        "date": when,
        "source": feed["name"],
        "score": base if base < 0 else base + feed.get("weight", 0),
    }


def _keep(feed: dict, title: str) -> bool:
    """Optional per-feed title regex, for noisy corporate blogs."""
    pat = feed.get("title_filter")
    return not pat or re.search(pat, title, re.I) is not None


def _slug_title(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    return slug.replace("-", " ").replace("_", " ").strip().capitalize()


@lru_cache(maxsize=32)
def _cached(url: str) -> str:
    # Several sources may share one sitemap (e.g. Anthropic engineering/research/news).
    return fetch_url(url)


def fetch_rss(feed: dict, since: date, scorer: Scorer) -> list[dict]:
    parsed = feedparser.parse(feed["url"], agent=UA)
    if parsed.bozo and not parsed.entries:
        log(f"  [WARN] feed failed {feed['name']}: {parsed.get('bozo_exception')}")
        return []
    out = []
    for e in parsed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        if not t:
            continue
        when = datetime(*t[:6], tzinfo=timezone.utc).date()
        if when < since:
            continue
        link = e.get("link", "")
        if not link:
            continue
        title = " ".join(e.get("title", "").split())
        if not _keep(feed, title):
            continue
        summary = _clean(e.get("summary") or (e.get("content") or [{}])[0].get("value", ""))
        out.append(_post(link, title, summary, feed, when.isoformat(), scorer))
    return out


def fetch_html_links(feed: dict, seen: set[str], scorer: Scorer) -> tuple[list[dict], list[str]]:
    """Returns (new posts, keys to silently mark seen).

    Listing pages have no dates, so "new" means "not seen before". On the very first
    run for a source every link is unseen; we record them all as seen without emitting
    to avoid dumping a site's whole archive into one day's inbox.
    """
    html = _cached(feed["url"])
    if not html:
        return [], []
    urls = []
    for m in re.finditer(feed["pattern"], html):
        u = feed.get("base", "") + m.group(1)
        if u not in urls:
            urls.append(u)
    keys = {u: post_key(u) for u in urls}
    unseen = [u for u in urls if keys[u] not in seen]
    if len(unseen) == len(urls) and len(urls) > 3:
        log(f"  {feed['name']}: first run, bootstrapping {len(urls)} links as seen")
        return [], list(keys.values())
    posts = [_post(u, _slug_title(u), "", feed, "", scorer) for u in unseen if _keep(feed, _slug_title(u))]
    return posts, []


def fetch_sitemap(feed: dict, since: date, seen: set[str], scorer: Scorer) -> tuple[list[dict], list[str]]:
    """Sitemap: filter <loc> by regex; "new" = not seen before (like html_links).

    <lastmod> is only a secondary filter — some sites (OpenAI) bump every page's
    lastmod on each rebuild, so it can't be trusted alone. First run for a source
    records every matching URL as seen instead of dumping the archive.
    """
    xml_text = _cached(feed["url"])
    if not xml_text:
        return [], []
    try:
        root = ET.fromstring(xml_text.encode())
    except ET.ParseError as e:
        log(f"  [WARN] sitemap parse {feed['name']}: {e}")
        return [], []
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    pat = re.compile(feed["pattern"])
    entries = []
    for url in root.findall("s:url", ns):
        loc = (url.findtext("s:loc", "", ns) or "").strip()
        if pat.search(loc):
            entries.append((loc, post_key(loc), (url.findtext("s:lastmod", "", ns) or "")[:10]))
    unseen = [e for e in entries if e[1] not in seen]
    if len(unseen) == len(entries) and len(entries) > 3:
        log(f"  {feed['name']}: first run, bootstrapping {len(entries)} links as seen")
        return [], [k for _, k, _ in entries]
    posts = []
    for loc, _, lastmod in unseen:
        if lastmod and date.fromisoformat(lastmod) < since:
            continue
        title = _slug_title(loc)
        if _keep(feed, title):
            posts.append(_post(loc, title, "", feed, lastmod, scorer))
    return posts, []


QUANT = re.compile(r"(?i)(gguf|awq|gptq|fp8|fp4|int4|int8|w4a16|mlx|bnb|4bit|8bit|eagle|mtp|draft|onnx)")
VARIANT = re.compile(r"(?i)-(base|instruct|chat|thinking|preview|it)$")


def fetch_hf_models(feed: dict, since: date, scorer: Scorer) -> list[dict]:
    """New model repos from a HuggingFace org — the reliable release signal for labs
    whose own sites are JS-rendered (Kimi, Qwen, Hunyuan…). Quantized builds are dropped
    and Base/Instruct/Thinking siblings released together collapse into one item."""
    raw = fetch_url(
        f"https://huggingface.co/api/models?author={feed['org']}&sort=createdAt&direction=-1&limit=40"
    )
    try:
        models = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []
    groups: dict[str, list[str]] = {}
    when: dict[str, str] = {}
    for m in models:
        mid, created = m.get("id", ""), (m.get("createdAt") or "")[:10]
        name = mid.split("/", 1)[-1]
        if not created or date.fromisoformat(created) < since or QUANT.search(name):
            continue
        if not _keep(feed, name):
            continue
        stem = VARIANT.sub("", name)
        groups.setdefault(stem, []).append(mid)
        when[stem] = created
    out = []
    for stem, ids in groups.items():
        url = f"https://huggingface.co/{feed['org']}/{stem}" if len(ids) > 1 else f"https://huggingface.co/{ids[0]}"
        title = f"{feed['name']} 发布模型 {stem}"
        summary = "HuggingFace 新模型：" + ", ".join(ids)
        out.append(_post(url, title, summary, feed, when[stem], scorer))
    return out


def fetch_posts(target: date, cfg: dict, seen: set[str], scorer: Scorer) -> tuple[list[dict], list[str]]:
    since = target - timedelta(days=cfg.get("window_days", 2))
    out, bootstrap = [], []
    for feed in cfg.get("feeds", []):
        kind = feed.get("type", "rss")
        try:
            if kind == "rss":
                items = fetch_rss(feed, since, scorer)
            elif kind == "html_links":
                items, boot = fetch_html_links(feed, seen, scorer)
                bootstrap += boot
            elif kind == "sitemap":
                items, boot = fetch_sitemap(feed, since, seen, scorer)
                bootstrap += boot
            elif kind == "hf_models":
                items = fetch_hf_models(feed, since, scorer)
            else:
                log(f"  [WARN] unknown feed type {kind} for {feed['name']}")
                continue
        except Exception as e:  # one broken feed must not break the day
            log(f"  [WARN] {feed['name']}: {e}")
            continue
        log(f"  {feed['name']}: {len(items)} recent")
        out += items
    return out, bootstrap
