#!/usr/bin/env python3
"""Discover One Stop document metadata (doc_id + filename) for permits we have
NOT yet enumerated — the "identify" step, not the "download" step.

For each target permit it runs the proven probe flow:
  1. GET the permit link (sets a session cookie)
  2. GET Search.aspx and extract the ItemID
  3. GET Redirect.aspx?module=permits&ItemID=..&view=true and extract every
     DocRedirect(<doc_id>) call plus its nearby filename.

Requests are spread across a pool of HTTP proxies (webshare), one dedicated
cookie jar + politeness clock per proxy, so we parallelise without hammering a
single exit IP. Output is append-only and resumable.

Nothing is written to Neon (read-only for us). Discovered pairs land in
data/discovered_docs.csv. No PDFs are downloaded here.
"""
from __future__ import annotations

import argparse
import csv
import html
import http.cookiejar
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

ITEM_ID_RE = re.compile(
    r"Redirect\.aspx\?module=permits&ItemID=(\d+)&view=true", re.IGNORECASE
)
DOC_REDIRECT_RE = re.compile(r"DocRedirect\((\d+)\)", re.IGNORECASE)
DOC_FILENAME_RE = re.compile(
    r"([^<>\r\n]{1,300}?\.[A-Za-z0-9]{2,5})\s*\(\s*\d{1,2}/\d{1,2}/\d{4}\s*\)",
    re.IGNORECASE,
)
CAPTCHA_RE = re.compile(
    r"captcha|recaptcha|hcaptcha|verify\s+you\s+are\s+human|"
    r"checking\s+your\s+browser|cloudflare|cf-chl|access\s+denied",
    re.IGNORECASE,
)

RESULT_FIELDS = ["permitNum", "status", "itemID", "docCount", "docPairs", "notes"]


class BlockedProxy(RuntimeError):
    """The proxy's exit IP got throttled/blocked — cool it down and retry."""


@dataclass
class Proxy:
    ip: str
    port: str
    user: str
    pw: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_at: float = 0.0
    cooldown_until: float = 0.0

    @property
    def url(self) -> str:
        return f"http://{self.user}:{self.pw}@{self.ip}:{self.port}"


def load_proxies(path: Path) -> list[Proxy]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) != 4:
            continue
        out.append(Proxy(*parts))
    if not out:
        raise SystemExit(f"no proxies parsed from {path}")
    return out


def make_opener(proxy: Proxy) -> urllib.request.OpenerDirector:
    """Fresh cookie jar per call so each permit visit is a clean session."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy.url, "https": proxy.url}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )


def upgraded_https(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def clean_filename(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.lstrip("> ").strip()


def extract_documents(permit_html: str) -> list[tuple[str, str]]:
    text = html.unescape(permit_html)
    docs = []
    for m in DOC_REDIRECT_RE.finditer(text):
        window = text[max(0, m.start() - 1200): m.start()]
        cand = DOC_FILENAME_RE.findall(window)
        docs.append((m.group(1), clean_filename(cand[-1]) if cand else ""))
    return docs


def probe_permit(permit_num: str, link: str, proxy: Proxy, req_interval: float,
                 timeout: int) -> dict:
    opener = make_opener(proxy)

    def get(url: str) -> tuple[int, str]:
        with proxy.lock:
            wait = req_interval - (time.monotonic() - proxy.last_at)
            if proxy.last_at and wait > 0:
                time.sleep(wait)
            proxy.last_at = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                status = resp.getcode()
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        if status in (403, 429) or (body and CAPTCHA_RE.search(body)):
            raise BlockedProxy(f"HTTP {status} at {url}")
        return status, body

    get(upgraded_https(link))
    _, shtml = get("https://onestopapp.nola.gov/Search.aspx")
    m = ITEM_ID_RE.search(html.unescape(shtml))
    if not m:
        return {"permitNum": permit_num, "status": "not_found", "itemID": "",
                "docCount": "0", "docPairs": "", "notes": "no ItemID"}
    item_id = m.group(1)
    _, vhtml = get(
        "https://onestopapp.nola.gov/Redirect.aspx?"
        f"module=permits&ItemID={item_id}&view=true"
    )
    docs = extract_documents(vhtml)
    return {
        "permitNum": permit_num,
        "status": "ok",
        "itemID": item_id,
        "docCount": str(len(docs)),
        "docPairs": ";".join(
            f"{d}|{f.replace(';', ',').replace('|', '/')}" for d, f in docs
        ),
        "notes": "",
    }


def load_targets(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="") as f:
        return [(r["permitNum"], r["link"]) for r in csv.DictReader(f)]


def done_permits(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()
    with path.open(newline="") as f:
        # settled = ok / not_found; error rows get retried on the next run
        return {r["permitNum"] for r in csv.DictReader(f)
                if r.get("status") in {"ok", "not_found"}}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--targets", type=Path, default=ROOT / "data" / "discover_targets.csv")
    p.add_argument("--proxies", type=Path, required=True,
                   help="webshare list file: ip:port:user:pass per line")
    p.add_argument("--out", type=Path, default=ROOT / "data" / "discovered_docs.csv")
    p.add_argument("--limit", type=int, default=0, help="max permits (0 = all)")
    p.add_argument("--req-interval", type=float, default=1.5,
                   help="min seconds between requests PER proxy")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--cooldown", type=float, default=45.0,
                   help="seconds to bench a proxy after a block")
    p.add_argument("--max-attempts", type=int, default=4,
                   help="per-permit retries across proxies before giving up")
    p.add_argument("--breaker-window", type=int, default=40,
                   help="recent requests to judge the global block rate over")
    p.add_argument("--breaker-threshold", type=float, default=0.5,
                   help="halt the whole run if block rate over the window exceeds this")
    args = p.parse_args()

    proxies = load_proxies(args.proxies)
    targets = load_targets(args.targets)
    done = done_permits(args.out)
    todo = [(pn, lk) for pn, lk in targets if pn not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"proxies={len(proxies)} targets={len(targets)} done={len(done)} "
          f"todo={len(todo)}", flush=True)
    if not todo:
        return 0

    work: queue.Queue = queue.Queue()
    for item in todo:
        work.put((item[0], item[1], 0))

    write_lock = threading.Lock()
    write_header = not args.out.exists() or args.out.stat().st_size == 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_f = args.out.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_f, fieldnames=RESULT_FIELDS)
    if write_header:
        writer.writeheader(); out_f.flush()

    stats = {"ok": 0, "not_found": 0, "error": 0, "docs": 0}
    stats_lock = threading.Lock()
    total = len(todo)

    # Global circuit-breaker: if blocks dominate a sliding window of recent
    # requests, everyone is getting throttled — stop rather than burn IPs.
    stop_all = threading.Event()
    recent: list[bool] = []  # True = blocked
    recent_lock = threading.Lock()

    def note_outcome(blocked: bool) -> None:
        with recent_lock:
            recent.append(blocked)
            if len(recent) > args.breaker_window:
                del recent[0]
            if (len(recent) >= args.breaker_window
                    and sum(recent) / len(recent) > args.breaker_threshold):
                if not stop_all.is_set():
                    print(f"CIRCUIT-BREAKER: block rate "
                          f"{sum(recent)}/{len(recent)} over window — halting. "
                          f"Rerun later to resume.", flush=True)
                stop_all.set()

    def emit(row: dict) -> None:
        with write_lock:
            writer.writerow(row); out_f.flush()
        with stats_lock:
            stats[row["status"]] = stats.get(row["status"], 0) + 1
            stats["docs"] += int(row.get("docCount") or 0)
            n = stats["ok"] + stats["not_found"] + stats["error"]
            if n % 25 == 0 or n == total:
                print(f"[{n}/{total}] ok={stats['ok']} nf={stats['not_found']} "
                      f"err={stats['error']} docs={stats['docs']}", flush=True)

    def worker(proxy: Proxy) -> None:
        while not stop_all.is_set():
            try:
                permit_num, link, attempts = work.get_nowait()
            except queue.Empty:
                return
            now = time.monotonic()
            if proxy.cooldown_until > now:
                time.sleep(min(proxy.cooldown_until - now, 5))
            try:
                emit(probe_permit(permit_num, link, proxy,
                                  args.req_interval, args.timeout))
                note_outcome(False)
            except BlockedProxy:
                note_outcome(True)
                proxy.cooldown_until = time.monotonic() + args.cooldown
                if attempts + 1 < args.max_attempts:
                    work.put((permit_num, link, attempts + 1))  # let another proxy try
                else:
                    emit({"permitNum": permit_num, "status": "error", "itemID": "",
                          "docCount": "0", "docPairs": "", "notes": "blocked"})
            except Exception as exc:  # noqa: BLE001 - network is messy; log and move on
                if attempts + 1 < args.max_attempts:
                    work.put((permit_num, link, attempts + 1))
                else:
                    emit({"permitNum": permit_num, "status": "error", "itemID": "",
                          "docCount": "0", "docPairs": "",
                          "notes": f"{type(exc).__name__}: {exc}"[:200]})
            finally:
                work.task_done()

    threads = [threading.Thread(target=worker, args=(px,), daemon=True) for px in proxies]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out_f.close()
    dt = time.monotonic() - t0
    print(f"DONE in {dt:.0f}s  ok={stats['ok']} not_found={stats['not_found']} "
          f"error={stats['error']} docs_discovered={stats['docs']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
