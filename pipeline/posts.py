"""Blog / tech-report fetchers: RSS/Atom feeds and link-scraped listing pages."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from html import unescape

import feedparser

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
        summary = _clean(e.get("summary") or (e.get("content") or [{}])[0].get("value", ""))
        out.append(_post(link, " ".join(e.get("title", "").split()), summary, feed, when.isoformat(), scorer))
    return out


def fetch_html_links(feed: dict, seen: set[str], scorer: Scorer) -> tuple[list[dict], list[str]]:
    """Returns (new posts, keys to silently mark seen).

    Listing pages have no dates, so "new" means "not seen before". On the very first
    run for a source every link is unseen; we record them all as seen without emitting
    to avoid dumping a site's whole archive into one day's inbox.
    """
    html = fetch_url(feed["url"])
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
    posts = []
    for u in unseen:
        slug = u.rstrip("/").rsplit("/", 1)[-1]
        title = slug.replace("-", " ").capitalize()
        posts.append(_post(u, title, "", feed, "", scorer))
    return posts, []


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
            else:
                log(f"  [WARN] unknown feed type {kind} for {feed['name']}")
                continue
        except Exception as e:  # one broken feed must not break the day
            log(f"  [WARN] {feed['name']}: {e}")
            continue
        log(f"  {feed['name']}: {len(items)} recent")
        out += items
    return out, bootstrap
