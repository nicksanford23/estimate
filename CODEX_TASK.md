# Task: Stratified document-availability probe of NOLA One Stop permits

## Context

We're building a commercial flooring estimating tool and need construction plan
PDFs as training data. We have a local CSV of 23,230 commercial permits
(`data/nola_permits_commercial.csv`) scraped from a Supabase mirror of New
Orleans permit data. Each row has a `link` column pointing to the permit's
record on One Stop (onestopapp.nola.gov), where submitted plan PDFs are
publicly downloadable.

Before bulk-downloading anything, we need a **yield table**: what fraction of
permits in each stratum actually has plan documents attached. This task is
that probe. **Do NOT download any PDFs — metadata only.**

A 3-permit pilot already validated the access pattern end to end (results in
`data/probe_pilot.csv`). Your job is the full stratified probe.

## Input

`data/nola_permits_commercial.csv` — relevant columns:
- `permitNum`, `permitType` (NEWC | RNVS | RNVN), `permitClass`,
  `estProjectCost`, `totalSqFt`, `issueDate`, `description`, `link`

## Sampling plan

Sample **15 permits per stratum**, 12 strata = 180 permits total.
Strata = permitType × cost band × era:

| # | permitType | estProjectCost | issueDate |
|---|---|---|---|
| 1 | NEWC | >= $10M | any |
| 2 | NEWC | $1M-10M | >= 2022 |
| 3 | NEWC | $1M-10M | < 2022 (but non-empty) |
| 4 | RNVS | $1M-10M | >= 2022 |
| 5 | RNVS | $1M-10M | < 2022 (non-empty) |
| 6 | RNVS | $250k-1M | >= 2022 |
| 7 | RNVN | $1M-10M | >= 2022 |
| 8 | RNVN | $250k-1M | >= 2022 |
| 9 | RNVN | $250k-1M | < 2022 (non-empty) |
| 10 | RNVN | $50k-250k | >= 2022 |
| 11 | any | any cost | issueDate empty ("applied only") |
| 12 | RNVN | $250k-1M, description matches /tenant|build-?out|suite|interior/i | any |

Within each stratum: random sample with a fixed seed (e.g. 42) so the run is
reproducible. If a stratum has fewer than 15 rows, take all of them. A permit
may satisfy multiple strata; sample without replacement globally (skip rows
already sampled by an earlier stratum, top up from the remainder).

## Verified access pattern (per permit — 3 requests)

All requests: HTTPS, browser User-Agent
(`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36`),
**fresh cookie jar per permit**, and **sleep 10 seconds between every request**.
(A first run at 3s spacing got rate-limited to death — 167/180 permits errored
with 429s/timeouts. 10s is the verified-safe pace. On any 429, back off 60s;
after 3 consecutive 429s, stop and report.)

1. `GET <link from CSV, upgraded to https>` with cookie jar (`curl -c jar`).
   Returns 302 and sets an ASP.NET session cookie. Do not follow the redirect.
2. `GET https://onestopapp.nola.gov/Search.aspx` with the jar (`-b jar`).
   The HTML contains `Redirect.aspx?module=permits&ItemID=<n>&view=true`.
   ⚠️ The `&` appears as a literal `&amp;` in the HTML — unescape before use.
   If no ItemID link is present, record status `not_found` and move on.
3. `GET https://onestopapp.nola.gov/Redirect.aspx?module=permits&ItemID=<n>&view=true`
   with the jar and `-L`. Lands on `PrmtView.aspx?ref=...`. The Documents tab
   is inline in this HTML.

### Parsing the documents list (gotchas found in the pilot)

- Each document appears inside an `<li>` as plain-text
  `FILENAME.pdf (M/D/YYYY)` followed (up to ~400 chars later) by an anchor
  `onclick='DocRedirect(<DocID>)'`.
- Extract pairs by iterating `DocRedirect\((\d+)\)` matches and scanning
  **backwards** from each for the last `text (date)` pattern — the naive
  "closest preceding text" undercounts.
- Run `html.unescape()` on filenames (they contain `&amp;` etc.).
- Attachment lists mix in `.doc`, `.msg`, invoices, emails. Count everything,
  but classify separately (see output columns).
- HTML is on very long lines — parse with Python `re`, not line-based grep.

### Plan-likeness classifier (filename heuristic)

`is_plan_like` if the filename (case-insensitive) matches any of:
`arch`, `floor`, `plan`, `drawing`, `dwg`, `cd set`, `cd drawings`,
`construction doc`, `layout`, `elevation`, `interior`, `permit set`,
`issued for`, or a sheet-number pattern like `\bA[-.]?\d`.
Exclude matches on `site plan` only if nothing else matches (site plans are
low value for flooring but still drawings — flag as `site_only`).

## Output

Write `data/probe_results.csv`, one row per probed permit:

```
permitNum, stratum, status, docCount, pdfCount, planLikeCount,
planLikeFilenames (;-joined), allDocIDs (;-joined), itemID, notes
```

`status` ∈ `ok | not_found | error`. Properly CSV-quote (filenames contain
commas). Flush after every row so the run is resumable; on restart, skip
permitNums whose existing row has status `ok` or `not_found` — **re-try rows
whose status is `error`** (rewrite the file without them at startup, then
re-probe). The current probe_results.csv has 167 error rows from the
rate-limited first run; those are the work queue.

Also print/write a summary table at the end (`data/probe_summary.md`):
per stratum — n probed, % with any docs, % with ≥1 plan-like PDF, median
pdfCount. This yield table is the deliverable.

## Politeness / safety rules (non-negotiable)

- 10-second sleep between ALL requests. ~500 remaining requests ≈ 90 min runtime.
- Max 2 retries per request, exponential backoff, then record `error` and move on.
- **No PDF downloads. No GetDocument.aspx requests.** Metadata only.
- If you start seeing 403s or CAPTCHA-looking responses, STOP the run and
  report — do not push through.
- Keep scratch HTML in /tmp, not the repo.

## Done criteria

- `data/probe_results.csv` with ~180 rows
- `data/probe_summary.md` with the per-stratum yield table
- The probe script saved as `scripts/probe_onestop.py` (single file, stdlib
  only — urllib/csv/re/html/time/random — no pip installs needed)
