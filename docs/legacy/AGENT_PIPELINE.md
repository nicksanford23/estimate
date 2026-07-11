# v0 labeling pipeline — agent task spec

Read this top to bottom before doing anything. This spec drives the local v0
data pipeline for the flooring-estimator sheet classifier. The database is
SQLite at `data/estimate.db` (schema in `schema.sql` — initialize it first if
the file doesn't exist: `sqlite3 data/estimate.db < schema.sql`).

Everything is designed to be **idempotent and resumable**: every job claims
work by querying a status, and every write flips a status. Re-running a job
never duplicates work. Multiple agents can run different jobs concurrently.

Prerequisite artifacts already in the repo:
- `data/nola_permits_commercial.csv` — 23,230 commercial permits
- `data/probe_results.csv` + `data/probe_summary.md` — per-stratum doc
  availability (produced by CODEX_TASK.md; if missing, run that task first)
- `CODEX_TASK.md` — the probe spec, including the verified One Stop access
  pattern and its parsing gotchas. Job 1 reuses that access pattern.

---

## Job 1 — Acquire (download plan PDFs)

**Goal:** download every `document` row with status 'pending' into
`data/pdfs/`. The database IS the queue — no separate pull list, no cap.
(320 pending DocIDs are already loaded from the probe results; many have an
empty `filename` because the probe couldn't pair filenames to IDs.)

Per document (status 'pending', ordered by permit_num):
1. Download `https://onestopapp.nola.gov/GetDocument.aspx?DocID=<onestop_doc_id>`
   with the browser UA from CODEX_TASK.md. **Sleep 5 seconds between
   downloads** — these are large files; be polite. Max 2 retries. On a 429
   back off 60s; after three consecutive 429s stop and report. Note: time to
   first byte can exceed 20s on big files — use a generous timeout (120s+
   connect-to-first-byte, no total cap).
2. If the row's `filename` is empty, take it from the response
   Content-Disposition header; if absent, sniff the type from magic bytes
   (`%PDF`) and name it `<docid>.pdf` / `<docid>.bin`.
3. Non-PDF payloads (.msg, .doc, invoices, HTML error pages): delete the file
   and set status 'error' with a note like 'not a pdf: <content-type>'. Do NOT
   keep non-PDFs. Filenames matching
   /struct|mep|mech|elec|plumb|civil|fire|survey|receipt|invoice|contract|license|letter|approval|extension/i
   are also 'error' ('skipped: <reason>') — delete after identifying.
4. On success: write filename, sha256, bytes,
   storage_path (`data/pdfs/<docid>_<safe-filename>`), status 'downloaded',
   downloaded_at.
5. If any response looks like a block page (HTML instead of PDF, 403,
   captcha), STOP the job and report.

## Job 2 — Render (PDF -> page PNGs)

**Goal:** every `document` with status 'downloaded' becomes `page` rows.

Use PyMuPDF (`pip install pymupdf` if needed — the only allowed install).
Per document:
1. Render each page at zoom so the long edge ≈ 1568 px -> PNG at
   `data/pages/<docid>/page_<n:04d>.png`.
2. INSERT a `page` row per page: page_index (0-based), image_path, width_px,
   height_px, has_vector_text (1 if `page.get_text()` yields > 50 chars).
3. Set document.page_count and status 'rendered'.
4. Documents that fail to open: status 'error', move on.

## Job 3 — Label (the v0 classifier IS you, the agent)

**Goal:** a `page_label` row for every `page` with status 'rendered'.

You (the coding agent) are the v0 labeler: **open each page image, look at
it, classify it.** No API calls, no external services — read the image
directly and judge.

Categories (exact strings): floor_plan, finish_plan, finish_schedule,
demo_plan, reflected_ceiling, furniture_plan, site_plan, elevation_section,
detail, schedule_other, structural, mep, cover_index, specs_notes, other.

`keep` = 1 iff category ∈ {floor_plan, finish_plan, finish_schedule, demo_plan}.

Guidance:
- floor_plan: dimensioned architectural plan of building interior
- finish_plan: flooring/finish materials shown via hatches, tags, legend
- finish_schedule: the room-finish table (room -> floor/base/wall)
- Title block (bottom/right edge) usually names the sheet: A-101 = floor
  plan territory; A6xx/ID-xxx often finishes; S = structural; M/E/P = mep.
- Report honest confidence 0..1. Ambiguous or illegible -> low confidence,
  never a confident guess.

Mechanics:
1. Work in batches (e.g. 25 pages). Claim: pages with status 'rendered' and
   no page_label row.
2. INSERT into page_label: source = 'claude-code' or 'codex' (whichever you
   are), category, keep, confidence.
3. UPDATE page.status = 'labeled'.
4. Log progress every batch (labeled count / remaining).

## Job 4 — Review queue (for the human, not you)

Produce/refresh `data/review_queue.csv` after labeling: pages whose best
label confidence < 0.8, columns page_id, image_path, category, confidence.
The human's corrections get inserted as page_label rows with source='human'
(never UPDATE existing rows).

---

## Ground rules (all jobs)

- Append-only labels. Never UPDATE or DELETE page_label rows.
- No PDF/PNG files in git (data/ is gitignored). DB stays in data/.
- Politeness on anything hitting onestopapp.nola.gov: sleeps as specified,
  stop on 403/captcha.
- When done with a job, print a one-paragraph summary: rows written, errors,
  and the exact SQL to see the results.

## Definition of done for v0

- ~40 documents downloaded and rendered (expect roughly 1,500-4,000 pages)
- Every page labeled with category + confidence
- review_queue.csv generated
- Summary stats: pages per category, keep ratio, mean confidence

After that, the training step (CLIP embed + linear probe on `v_page_truth`)
turns this into the v1 model — separate task, don't start it.
