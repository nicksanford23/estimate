#!/usr/bin/env python3
"""Probe NOLA One Stop permit pages for document metadata only.

This script samples commercial permit strata, visits each permit record with a
fresh cookie jar, extracts inline document metadata from the permit view page,
and writes resumable probe results plus a stratum-level yield summary.
"""

from __future__ import annotations

import argparse
import csv
import html
import http.cookiejar
import multiprocessing
import os
import random
import re
import signal
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


INPUT_CSV = Path("data/nola_permits_commercial.csv")
OUTPUT_CSV = Path("data/probe_results.csv")
SUMMARY_MD = Path("data/probe_summary.md")
SAMPLE_SIZE = 15
SEED = 42
REQUEST_INTERVAL_SECONDS = 10.0
REQUEST_TIMEOUT_SECONDS = 90
PERMIT_TIMEOUT_SECONDS = 600
MAX_RETRIES = 2
RATE_LIMIT_BACKOFF_SECONDS = 60
MAX_CONSECUTIVE_429 = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

RESULT_FIELDS = [
    "permitNum",
    "stratum",
    "status",
    "docCount",
    "pdfCount",
    "planLikeCount",
    "planLikeFilenames",
    "allDocIDs",
    "docPairs",
    "itemID",
    "notes",
]

ITEM_ID_RE = re.compile(
    r"Redirect\.aspx\?module=permits&ItemID=(\d+)&view=true",
    re.IGNORECASE,
)
DOC_REDIRECT_RE = re.compile(r"DocRedirect\((\d+)\)", re.IGNORECASE)
DOC_FILENAME_RE = re.compile(
    r"([^<>\r\n]{1,300}?\.[A-Za-z0-9]{2,5})\s*"
    r"\(\s*\d{1,2}/\d{1,2}/\d{4}\s*\)",
    re.IGNORECASE,
)
TENANT_RE = re.compile(r"tenant|build-?out|suite|interior", re.IGNORECASE)
SHEET_NUMBER_RE = re.compile(r"\bA[-.]?\d", re.IGNORECASE)
SITE_PLAN_RE = re.compile(r"\bsite[-\s]+plans?\b", re.IGNORECASE)
CAPTCHA_RE = re.compile(
    r"captcha|recaptcha|hcaptcha|verify\s+you\s+are\s+human|"
    r"checking\s+your\s+browser|cloudflare|cf-chl|access\s+denied",
    re.IGNORECASE,
)

PLAN_KEYWORDS = [
    "arch",
    "floor",
    "plan",
    "drawing",
    "dwg",
    "cd set",
    "cd drawings",
    "construction doc",
    "layout",
    "elevation",
    "interior",
    "permit set",
    "issued for",
]


class StopRun(RuntimeError):
    """Raised when politeness/safety rules require the probe to stop."""


class RequestFailed(RuntimeError):
    """Raised when a request exhausts retry attempts."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RequestAlarm:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.old_handler = None

    def __enter__(self) -> None:
        self.old_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self._handle_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)

    def __exit__(self, exc_type, exc, tb) -> None:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.old_handler)

    @staticmethod
    def _handle_timeout(signum, frame) -> None:
        raise TimeoutError("request timed out")


@dataclass(frozen=True)
class Stratum:
    label: str
    predicate: object


class OneStopClient:
    def __init__(self) -> None:
        self.cookie_jar = http.cookiejar.CookieJar()
        cookie_handler = urllib.request.HTTPCookieProcessor(self.cookie_jar)
        self.follow_opener = urllib.request.build_opener(cookie_handler)
        self.no_redirect_opener = urllib.request.build_opener(cookie_handler, NoRedirect)
        self.last_request_at = 0.0
        self.consecutive_429 = 0

    def get(self, url: str, *, follow_redirects: bool = True) -> tuple[int, str, str]:
        opener = self.follow_opener if follow_redirects else self.no_redirect_opener
        last_error = ""

        for attempt in range(MAX_RETRIES + 1):
            self._wait_for_slot()
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            self.last_request_at = time.monotonic()

            try:
                with RequestAlarm(REQUEST_TIMEOUT_SECONDS):
                    with opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                        status = response.getcode()
                        final_url = response.geturl()
                        body = response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                status = exc.code
                final_url = exc.geturl()
                body = exc.read().decode("utf-8", errors="replace")
                if not follow_redirects and 300 <= status < 400:
                    self._check_safety(status, body, url)
                    return status, final_url, body
                last_error = f"HTTP {status} for {url}"
                if status == 403:
                    raise StopRun(f"403 response from {url}")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                status = 0
                body = ""
                last_error = f"{type(exc).__name__}: {exc}"

            self._check_safety(status, body, url)
            if status and 200 <= status < 400:
                self.consecutive_429 = 0
                return status, final_url, body

            if status == 429:
                self.consecutive_429 += 1
                if self.consecutive_429 >= MAX_CONSECUTIVE_429:
                    raise StopRun(f"{MAX_CONSECUTIVE_429} consecutive 429s at {url}")
                time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            elif attempt < MAX_RETRIES:
                time.sleep(REQUEST_INTERVAL_SECONDS * (2 ** attempt))

        raise RequestFailed(last_error or f"request failed for {url}")

    def _wait_for_slot(self) -> None:
        elapsed = time.monotonic() - self.last_request_at
        remaining = REQUEST_INTERVAL_SECONDS - elapsed
        if self.last_request_at and remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _check_safety(status: int, body: str, url: str) -> None:
        if status == 403:
            raise StopRun(f"403 response from {url}")
        if body and CAPTCHA_RE.search(body):
            raise StopRun(f"CAPTCHA/access-check response from {url}")


def parse_money(value: str) -> float | None:
    value = (value or "").strip().replace("$", "").replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def issue_year(row: dict[str, str]) -> int | None:
    value = (row.get("issueDate") or "").strip()
    if not value:
        return None
    match = re.match(r"(\d{4})", value)
    return int(match.group(1)) if match else None


def cost_between(row: dict[str, str], low: float, high: float | None = None) -> bool:
    cost = parse_money(row.get("estProjectCost", ""))
    if cost is None or cost < low:
        return False
    return high is None or cost < high


def issue_from(row: dict[str, str], year: int) -> bool:
    row_year = issue_year(row)
    return row_year is not None and row_year >= year


def issue_before(row: dict[str, str], year: int) -> bool:
    row_year = issue_year(row)
    return row_year is not None and row_year < year


def empty_issue_date(row: dict[str, str]) -> bool:
    return not (row.get("issueDate") or "").strip()


def build_strata() -> list[Stratum]:
    return [
        Stratum(
            "01 NEWC >=10M any era",
            lambda r: r.get("permitType") == "NEWC" and cost_between(r, 10_000_000),
        ),
        Stratum(
            "02 NEWC 1M-10M >=2022",
            lambda r: r.get("permitType") == "NEWC"
            and cost_between(r, 1_000_000, 10_000_000)
            and issue_from(r, 2022),
        ),
        Stratum(
            "03 NEWC 1M-10M <2022",
            lambda r: r.get("permitType") == "NEWC"
            and cost_between(r, 1_000_000, 10_000_000)
            and issue_before(r, 2022),
        ),
        Stratum(
            "04 RNVS 1M-10M >=2022",
            lambda r: r.get("permitType") == "RNVS"
            and cost_between(r, 1_000_000, 10_000_000)
            and issue_from(r, 2022),
        ),
        Stratum(
            "05 RNVS 1M-10M <2022",
            lambda r: r.get("permitType") == "RNVS"
            and cost_between(r, 1_000_000, 10_000_000)
            and issue_before(r, 2022),
        ),
        Stratum(
            "06 RNVS 250k-1M >=2022",
            lambda r: r.get("permitType") == "RNVS"
            and cost_between(r, 250_000, 1_000_000)
            and issue_from(r, 2022),
        ),
        Stratum(
            "07 RNVN 1M-10M >=2022",
            lambda r: r.get("permitType") == "RNVN"
            and cost_between(r, 1_000_000, 10_000_000)
            and issue_from(r, 2022),
        ),
        Stratum(
            "08 RNVN 250k-1M >=2022",
            lambda r: r.get("permitType") == "RNVN"
            and cost_between(r, 250_000, 1_000_000)
            and issue_from(r, 2022),
        ),
        Stratum(
            "09 RNVN 250k-1M <2022",
            lambda r: r.get("permitType") == "RNVN"
            and cost_between(r, 250_000, 1_000_000)
            and issue_before(r, 2022),
        ),
        Stratum(
            "10 RNVN 50k-250k >=2022",
            lambda r: r.get("permitType") == "RNVN"
            and cost_between(r, 50_000, 250_000)
            and issue_from(r, 2022),
        ),
        Stratum(
            "11 any cost applied only",
            lambda r: empty_issue_date(r),
        ),
        Stratum(
            "12 RNVN 250k-1M tenant/buildout any era",
            lambda r: r.get("permitType") == "RNVN"
            and cost_between(r, 250_000, 1_000_000)
            and bool(TENANT_RE.search(r.get("description") or "")),
        ),
    ]


def load_permits(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sample_permits(rows: list[dict[str, str]], seed: int = SEED) -> list[dict[str, str]]:
    rng = random.Random(seed)
    selected: set[str] = set()
    sampled: list[dict[str, str]] = []

    for stratum in build_strata():
        eligible = [
            row
            for row in rows
            if row.get("permitNum") not in selected and stratum.predicate(row)
        ]
        picked = rng.sample(eligible, SAMPLE_SIZE) if len(eligible) > SAMPLE_SIZE else eligible
        for row in picked:
            copied = dict(row)
            copied["_stratum"] = stratum.label
            sampled.append(copied)
            selected.add(row.get("permitNum", ""))

    return sampled


def existing_results(path: Path) -> set[str]:
    """Permits already settled (ok/not_found). Error rows are dropped from the
    file so they get re-probed on this run."""
    if not path.exists() or path.stat().st_size == 0:
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keep = []
    seen_permits = set()
    for row in rows:
        permit_num = row.get("permitNum")
        if row.get("status") not in {"ok", "not_found"} or permit_num in seen_permits:
            continue
        if row.get("status") == "ok" and row.get("allDocIDs") and not row.get("docPairs"):
            # Pre-docPairs row: re-probe so we capture DocID<->filename pairs.
            continue
        keep.append(row)
        seen_permits.add(permit_num)
    if len(keep) != len(rows):
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=RESULT_FIELDS, restval="", extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(keep)
            f.flush()
            os.fsync(f.fileno())
        print(f"Dropped {len(rows) - len(keep)} rows for re-probe (errors or missing docPairs).")
    return {row["permitNum"] for row in keep if row.get("permitNum")}


def upgraded_https(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def extract_item_id(search_html: str) -> str | None:
    text = html.unescape(search_html)
    match = ITEM_ID_RE.search(text)
    return match.group(1) if match else None


def clean_filename(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    value = value.lstrip("> ").strip()
    return value


def extract_documents(permit_html: str) -> list[tuple[str, str]]:
    text = html.unescape(permit_html)
    documents: list[tuple[str, str]] = []

    for match in DOC_REDIRECT_RE.finditer(text):
        doc_id = match.group(1)
        window = text[max(0, match.start() - 1200) : match.start()]
        candidates = DOC_FILENAME_RE.findall(window)
        filename = clean_filename(candidates[-1]) if candidates else ""
        documents.append((doc_id, filename))

    return documents


def classify_plan_like(filename: str) -> tuple[bool, bool]:
    lower = filename.lower()
    keyword_hits = [keyword for keyword in PLAN_KEYWORDS if keyword in lower]
    sheet_hit = bool(SHEET_NUMBER_RE.search(filename))
    site_only = bool(SITE_PLAN_RE.search(filename)) and not sheet_hit

    non_site_hits = [hit for hit in keyword_hits if hit != "plan"]
    if site_only and not non_site_hits:
        return False, True
    return bool(keyword_hits or sheet_hit), False


def probe_permit(row: dict[str, str]) -> dict[str, str]:
    permit_num = row.get("permitNum", "")
    stratum = row.get("_stratum", "")
    link = upgraded_https(row.get("link", ""))

    if not link:
        return error_row(permit_num, stratum, "missing link")

    client = OneStopClient()
    try:
        client.get(link, follow_redirects=False)
        _, _, search_html = client.get("https://onestopapp.nola.gov/Search.aspx")
        item_id = extract_item_id(search_html)
        if not item_id:
            return {
                "permitNum": permit_num,
                "stratum": stratum,
                "status": "not_found",
                "docCount": "0",
                "pdfCount": "0",
                "planLikeCount": "0",
                "planLikeFilenames": "",
                "allDocIDs": "",
                "docPairs": "",
                "itemID": "",
                "notes": "ItemID link not found in Search.aspx",
            }

        view_url = (
            "https://onestopapp.nola.gov/Redirect.aspx?"
            f"module=permits&ItemID={item_id}&view=true"
        )
        _, _, permit_html = client.get(view_url, follow_redirects=True)
    except RequestFailed as exc:
        return error_row(permit_num, stratum, str(exc))

    documents = extract_documents(permit_html)
    pdfs = [filename for _, filename in documents if filename.lower().endswith(".pdf")]
    plan_like = []
    site_only = []
    for _, filename in documents:
        is_plan, is_site_only = classify_plan_like(filename)
        if is_site_only:
            site_only.append(filename)
        if is_plan and filename.lower().endswith(".pdf"):
            plan_like.append(filename)

    notes = ""
    if site_only:
        notes = f"site_only={len(site_only)}"

    return {
        "permitNum": permit_num,
        "stratum": stratum,
        "status": "ok",
        "docCount": str(len(documents)),
        "pdfCount": str(len(pdfs)),
        "planLikeCount": str(len(plan_like)),
        "planLikeFilenames": ";".join(plan_like),
        "allDocIDs": ";".join(doc_id for doc_id, _ in documents),
        "docPairs": ";".join(
            f"{doc_id}|{filename.replace(';', ',').replace('|', '/')}"
            for doc_id, filename in documents
        ),
        "itemID": item_id,
        "notes": notes,
    }


def probe_worker(row: dict[str, str], queue: multiprocessing.Queue) -> None:
    try:
        queue.put(probe_permit(row))
    except StopRun as exc:
        queue.put({"_stop": str(exc)})
    except BaseException as exc:
        queue.put(error_row(row.get("permitNum", ""), row.get("_stratum", ""), repr(exc)))


def probe_permit_with_hard_timeout(row: dict[str, str]) -> dict[str, str]:
    queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
    process = multiprocessing.Process(target=probe_worker, args=(row, queue))
    process.start()
    process.join(PERMIT_TIMEOUT_SECONDS)

    if process.is_alive():
        process.terminate()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join()
        return error_row(
            row.get("permitNum", ""),
            row.get("_stratum", ""),
            f"permit probe timed out after {PERMIT_TIMEOUT_SECONDS}s",
        )

    if not queue.empty():
        result = queue.get()
        if "_stop" in result:
            raise StopRun(result["_stop"])
        return result

    if process.exitcode:
        return error_row(
            row.get("permitNum", ""),
            row.get("_stratum", ""),
            f"probe worker exited with code {process.exitcode}",
        )

    return error_row(row.get("permitNum", ""), row.get("_stratum", ""), "no worker result")


def error_row(permit_num: str, stratum: str, notes: str) -> dict[str, str]:
    return {
        "permitNum": permit_num,
        "stratum": stratum,
        "status": "error",
        "docCount": "0",
        "pdfCount": "0",
        "planLikeCount": "0",
        "planLikeFilenames": "",
        "allDocIDs": "",
        "docPairs": "",
        "itemID": "",
        "notes": notes[:500],
    }


def append_results(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        if write_header:
            writer.writeheader()
            f.flush()
        for result in rows:
            writer.writerow(result)
            f.flush()


def result_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return f"{(100.0 * numerator / denominator):.1f}%"


def int_value(row: dict[str, str], key: str) -> int:
    try:
        return int(row.get(key, "0") or "0")
    except ValueError:
        return 0


def write_summary(results_path: Path, summary_path: Path) -> None:
    rows = []
    seen_permits = set()
    for row in result_rows(results_path):
        permit_num = row.get("permitNum")
        if permit_num in seen_permits:
            continue
        rows.append(row)
        seen_permits.add(permit_num)
    by_stratum: dict[str, list[dict[str, str]]] = {
        stratum.label: [] for stratum in build_strata()
    }
    for row in rows:
        by_stratum.setdefault(row.get("stratum", ""), []).append(row)

    lines = [
        "# NOLA One Stop document availability probe",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "| Stratum | n probed | % with any docs | % with >=1 plan-like PDF | median pdfCount |",
        "|---|---:|---:|---:|---:|",
    ]

    for label, stratum_rows in by_stratum.items():
        n = len(stratum_rows)
        any_docs = sum(1 for row in stratum_rows if int_value(row, "docCount") > 0)
        any_plan = sum(1 for row in stratum_rows if int_value(row, "planLikeCount") > 0)
        pdf_counts = [int_value(row, "pdfCount") for row in stratum_rows]
        median_pdf = statistics.median(pdf_counts) if pdf_counts else ""
        lines.append(
            f"| {label} | {n} | {pct(any_docs, n)} | {pct(any_plan, n)} | {median_pdf} |"
        )

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--summary", type=Path, default=SUMMARY_MD)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Print the sampled permit list without making network requests.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Regenerate the summary from the existing results CSV.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.summary_only:
        write_summary(args.output, args.summary)
        print(f"Wrote {args.summary}")
        return 0

    rows = load_permits(args.input)
    sampled = sample_permits(rows, seed=args.seed)

    if args.sample_only:
        writer = csv.DictWriter(sys.stdout, fieldnames=["permitNum", "stratum", "link"])
        writer.writeheader()
        for row in sampled:
            writer.writerow(
                {
                    "permitNum": row.get("permitNum", ""),
                    "stratum": row.get("_stratum", ""),
                    "link": upgraded_https(row.get("link", "")),
                }
            )
        return 0

    done = existing_results(args.output)
    remaining = [row for row in sampled if row.get("permitNum") not in done]
    print(
        f"Sampled {len(sampled)} permits; {len(done)} already done; "
        f"{len(remaining)} remaining."
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_header = not args.output.exists() or args.output.stat().st_size == 0
    try:
        with args.output.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
            if write_header:
                writer.writeheader()
                f.flush()
                os.fsync(f.fileno())

            for index, row in enumerate(remaining, start=1):
                permit_num = row.get("permitNum", "")
                stratum = row.get("_stratum", "")
                print(f"[{index}/{len(remaining)}] {permit_num} {stratum}", flush=True)
                result = probe_permit_with_hard_timeout(row)
                writer.writerow(result)
                f.flush()
                os.fsync(f.fileno())
    except StopRun as exc:
        write_summary(args.output, args.summary)
        print(f"STOPPED: {exc}", file=sys.stderr)
        print(f"Partial summary written to {args.summary}", file=sys.stderr)
        return 2

    write_summary(args.output, args.summary)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
