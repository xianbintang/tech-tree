"""Download a paper PDF and extract its text for the deep-read agent.

    python -m pipeline.fetch_paper <url> --id <note-id>
      → .cache/papers/<id>.txt   (PDF itself stays in .cache; nothing goes into git)

Accepts arXiv abs/pdf links, USENIX presentation pages, ACM/other DOIs, and direct PDF
URLs. Landing pages are resolved via <meta name="citation_pdf_url"> or USENIX's
/system/files/*.pdf link.

Exit codes: 0 ok · 2 not a paper PDF (read it as a web page) · 3 blocked / failed
(on 3 the last stdout line names the PDF URL to retry with firecrawl_scrape parsers=["pdf"]).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from urllib.request import Request, urlopen

from .common import CACHE, log

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
PAPERS = CACHE / "papers"


def get(url: str) -> tuple[int, str, bytes]:
    req = Request(url, headers={"User-Agent": BROWSER_UA, "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8"})
    try:
        with urlopen(req, timeout=60) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except Exception as e:  # HTTPError carries a code; others (timeouts) don't
        return getattr(e, "code", 0) or 0, "", b""


def candidates(url: str) -> list[str]:
    """PDF URLs to try, most direct first."""
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", url)
    if m:
        return [f"https://arxiv.org/pdf/{m.group(1)}"]
    m = re.search(r"doi\.org/(10\.1145/[^\s?#]+)", url)
    if m:  # ACM DL is open access, but often bot-blocked → firecrawl fallback
        return [f"https://dl.acm.org/doi/pdf/{m.group(1)}"]
    if url.lower().endswith(".pdf"):
        return [url]
    status, ctype, data = get(url)
    if "pdf" in ctype or data[:4] == b"%PDF":
        return [url]
    html = data.decode("utf-8", "replace")
    found = re.findall(r'<meta[^>]+name="citation_pdf_url"[^>]+content="([^"]+)"', html)
    found += re.findall(r'href="(https?://www\.usenix\.org/system/files/[^"]+\.pdf)"', html)
    found += [("https://www.usenix.org" + p) for p in re.findall(r'href="(/system/files/[^"]+\.pdf)"', html)]
    return list(dict.fromkeys(found))  # dedupe, keep order


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--id", required=True)
    a = ap.parse_args()
    PAPERS.mkdir(parents=True, exist_ok=True)
    txt = PAPERS / f"{a.id}.txt"
    if txt.exists() and txt.stat().st_size > 2000:
        print(txt)
        return

    urls = candidates(a.url)
    if not urls:
        log(f"no PDF found behind {a.url}; read it as a web page (WebFetch)")
        sys.exit(2)

    last = urls[0]
    for pdf_url in urls:
        last = pdf_url
        status, ctype, data = get(pdf_url)
        if data[:4] != b"%PDF":
            log(f"  {pdf_url}: HTTP {status} {ctype or ''} (not a PDF)")
            continue
        pdf = PAPERS / f"{a.id}.pdf"
        pdf.write_bytes(data)
        if not shutil.which("pdftotext"):
            log("pdftotext not installed (brew install poppler)")
            sys.exit(3)
        subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), str(txt)], check=True)
        pages = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
        n = re.search(r"Pages:\s+(\d+)", pages)
        log(f"  {pdf_url} → {txt} ({n.group(1) if n else '?'} pages, {txt.stat().st_size // 1024} KB)")
        print(txt)
        return

    log(f"could not download a PDF (blocked?). Retry with firecrawl_scrape parsers=[\"pdf\"] on:")
    print(last)
    sys.exit(3)


if __name__ == "__main__":
    main()
