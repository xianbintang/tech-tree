"""Push a short message to Feishu / Slack / Telegram.

    python -m pipeline.notify --title "..." --text "..." [--url https://...]

Channels are toggled in config/notify.yaml; credentials come from env vars.
Missing credentials → channel skipped silently. Failures are logged, never fatal.
"""
from __future__ import annotations

import argparse
import json
import os
from urllib.request import Request, urlopen

from .common import load_config, log


def _post_json(url: str, payload: dict) -> None:
    req = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as resp:
        resp.read()


def send(title: str, text: str, url: str = "") -> None:
    channels = load_config("notify")["channels"]
    full = f"{title}\n\n{text}" + (f"\n\n{url}" if url else "")

    feishu = channels.get("feishu", {})
    if feishu.get("enabled") and os.environ.get(feishu["env"]):
        content = [[{"tag": "text", "text": text}]]
        if url:
            content.append([{"tag": "a", "text": "打开 PR / Issue", "href": url}])
        payload = {"msg_type": "post", "content": {"post": {"zh_cn": {"title": title, "content": content}}}}
        _try("feishu", lambda: _post_json(os.environ[feishu["env"]], payload))

    slack = channels.get("slack", {})
    if slack.get("enabled") and os.environ.get(slack["env"]):
        _try("slack", lambda: _post_json(os.environ[slack["env"]], {"text": full}))

    tg = channels.get("telegram", {})
    token, chat = os.environ.get(tg.get("env_token", "")), os.environ.get(tg.get("env_chat", ""))
    if tg.get("enabled") and token and chat:
        _try("telegram", lambda: _post_json(
            f"https://api.telegram.org/bot{token}/sendMessage",
            {"chat_id": chat, "text": full, "disable_web_page_preview": True},
        ))


def _try(name: str, fn) -> None:
    try:
        fn()
        log(f"  notified {name}")
    except Exception as e:
        log(f"  [WARN] notify {name} failed: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file")
    ap.add_argument("--url", default="")
    a = ap.parse_args()
    text = open(a.text_file).read() if a.text_file else a.text
    send(a.title, text[:3000], a.url)


if __name__ == "__main__":
    main()
