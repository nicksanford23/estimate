# takeoff.py — the standing takeoff runner

**Date:** 2026-07-09
**Script:** `scripts/takeoff.py` (imports probe2_sf, probe2b_sf, probe7_layer_walls,
page_select, exp_p0 unchanged; no logic copy-pasted)
**Data:** `data/takeoff/<permit>/{run.json,overlay_*.jpg,takeoff_*.md}`,
`data/takeoff/scoreboard.csv`, `data/takeoff/vision_cache/{scale,anchor}/`

This is the composition pass: turn probes 2/2b/7/22/23/24 + page_select + exp_p0
into one repeatable `run` / `grade` / `scoreboard` command. Every module is
imported, not reimplemented. Two real bugs surfaced during composition (below)
were fixed because they'd have silently produced wrong numbers otherwise — not
invented scope.

## Interface

```
python3 scripts/takeoff.py run PERMIT [--doc D] [--pages P1,P2]
python3 scripts/takeoff.py grade PERMIT
python3 scripts/takeoff.py scoreboard
```

`run` resolves pages from Neon (read-only), routes geometry (layer vs rules),
anchors rooms to text labels, joins material from `data/triage/truth_area/` or
`data/triage/materials/` when present, and writes `run.json` + an overlay JPG +
a markdown table. `grade` matches a permit's `run.json` against its truth_area
JSON by room number and reports per-room error + coverage. `scoreboard` prints
the append-only run log.

## Acceptance tests

### 1. 14-11290-NEWC (bank) — layer path — PASSED, exact geometric match

`run` with no page hint resolved doc 1494156 page 3 ("A-1.1 PARTIAL FLOOR PLAN
- BRANCH") automatically — the same page probes 4/7/22/23 used, picked by "most
named-wall-layer segments among the doc's labeled floor_plan candidates" (486
vs 443/343/132 on the other 3 candidate pages). Routed to the **layer** path.

Result: **13 auto_quantity rooms, 1178 SF enclosed, 2 open_zone_split groups**
(926 SF front-of-house, 614 SF copy/mortgage core).

Cross-check: re-ran `probe22_bank_validated.py` live in the same session.
**Enclosed geom sum: 1178 SF — identical to takeoff.py's total, and every
per-room area matches to the same rounding** (e.g. 108→213/213, 104→164/164,
109→125/124.9). The two open-zone groups match probe11/23's own documented
open-plan finding (front-of-house 102/103/105 and copy/mortgage 110/111 have
no dividing wall — confirmed independently three times now).

Where takeoff.py's count (13) differs from probe22's headline ("10
validated"): probe22 additionally cross-checked each room against a
**vision-read printed dimension** (a manual VDIM dict, a different data
source outside this mission's scope — `run` only joins `truth_area`/
`materials` JSON, and the bank has neither). Rooms 109 and 114 are within
15-27% of their dimension read (probe22 called them "check", not wrong) and
101 is a genuine storefront/vestibule fragment (probe22 called it "redraw").
takeoff.py correctly reports all three as **closed, single-anchored, real
polygons** — which they are — just without the extra dimension-based
downgrade that isn't part of this pipeline's inputs. Not a discrepancy in the
geometry; a difference in available cross-checks. `grade` correctly reports
"no truth_area JSON — nothing to grade against" (bank has none).

### 2. 26-10321-RNVN doc 9058456 — layer path — PASSED, reproduces probe24 exactly

`run` with no page hint resolved page 18 ("A2.4 ARCHITECTURAL PLAN FLOOR 9")
automatically — the same page probe24_takeoff.py picked (788 wall-layer
segments, highest of the 5 floor candidates). Routed to the **layer** path.

Scale: unresolvable by regex (pagetext and live text both have zero `SCALE_RE`
matches on this sheet — confirmed independently). `needs_vision_scale` would
fire; instead `vision_cache/scale/9058456_18.json` was seeded with the value
probe24_takeoff.py already established by reading the A2.4 title block
(1/8"=1'-0", fpp=0.1111) — reusing an established fact, not guessing.

Anchoring: this page's real PDF text has only 4 digit-like tokens total, 0 of
which land in any room polygon — `needs_vision_anchor` fired correctly. Rather
than re-deriving from scratch, I read `data/probe24/anchor_montage3.png`
(already generated in the prior session) myself this session, cross-checked
idx↔poly correspondence against `data/probe24/anchor_meta.json`, and cached
the result to `vision_cache/anchor/9058456_18.json` — this is the mission's
own instruction ("its vision anchors are in anchor_meta.json — reuse"), made
concrete as the actual cache-consumption mechanism `run` will use for any
future permit that hits this same flag.

Result: **16 auto_quantity rooms, 2394 SF** — 901,902,903,905,907,918,943,944
(offices), 941 (Conference), 916 (Wellness), 923 (Breakroom), 931 (Waiting),
933 (Workroom), 934 (Supply), 937 (File Room), plus 911 (Fire Suppression, a
mechanical closet, not a flooring line item). **Excluding 911: 15 rooms, 2323
SF — an exact match to probe24_two_permit_takeoff.md's reported "15 rooms,
2,323 SF."** That exact match is the verification that the vision read and the
cache wiring are both correct. 2 open_zone_split groups reproduce the same
merges probe24 found (913 OT Supply + 914 Training; 924/925 Office pair).
45 polygons remain `geometry_review` (real rooms the montage read didn't
confidently resolve, plus several mechanical/hatched chases) — an honest
gap, not hidden.

### 3. 24-06748-RNVS doc 7372349 p6 — rules path — baseline, as expected

`run` with no page hint resolved page 6 ("A102 2ND FLOOR") automatically —
same page probe3 used, picked by rules-path wall-candidate count (1753 vs
1243/1723/1584/589 on the other 4 floor pages; page 10 "A201 ENLARGED PLANS,"
which `page_select.py`'s title heuristic alone would have picked, was
correctly passed over). No named wall layers exist on any candidate page
(`has_named_layer=False` for all 5, confirmed against `closeability.csv`), so
this correctly routed to the **rules** path (probe2b two-tier, unchanged).

Result: **0 auto_quantity, 9 geometry_review, 0 SF.** This reproduces
`probe3_sf.py`'s own recorded verdict for this exact page — `BLOB`, 9
room-sized polygons total, only 1 real (46 SF fragment) after clustering.
Nothing new went wrong; the rules path is known-weak on dense interiors
(probe3: 61% BLOB across 18 permits) and this permit's floor plan has none of
the named CAD wall layers that make the layer path work. This is the honest
baseline the mission asked for.

`grade 24-06748-RNVS` against `data/triage/truth_area/24-06748-RNVS.json` (36
rooms, 5,055 SF, spanning levels 01-04) produces a coherent table: all 36
truth rooms printed, 0/36 matched (0% coverage, since only the 2nd-floor page
was processed and the rules path closed nothing usable there), `median |err|:
n/a (no matches)`. Coherent and correct, not fabricated — this is what "the
grade subcommand must produce a coherent table" requires even when the
underlying takeoff has nothing to show.

## Two real bugs found and fixed during composition (not scope creep)

1. **Shared PDF temp dir race.** `probe2_sf.download_pdf()` writes to a
   process-global `data/probe2/_pdf_tmp/<doc_id>.pdf`. Other concurrent jobs
   on this shared box (`harvest_layered_full.py`, `scan_closeability_full.py`,
   confirmed running via `ps aux` during this session) import the same
   module and can delete a same-doc_id PDF mid-run. First `run` attempt hit
   exactly this (`FileNotFoundError` deep in `extract_wall_layer_segments`).
   Fix: retarget `probe2_sf.PDF_TMP_DIR` to `data/takeoff/_pdf_tmp/` at
   import time — the same pattern `probe3_sf.py` already uses for the
   identical reason.
2. **The routing gate's placeholder scale silently misroutes good pages.**
   The mission's own spec for the layer/rules gate ("probe7 extraction + a
   quick polygonize sanity, >=5 room-band polygons") is naturally scale-free
   before a page's real scale is known — `scan_closeability.py` hardcodes
   `feet_per_pt=0.1` for exactly that reason, fine for its batch-triage use
   case. But `feet_per_pt` also sets the door-gap-closing radius
   (`door_pt = door_ft / feet_per_pt`), so a wrong placeholder changes
   *topology*, not just units. Verified on 14-11290 p3: real scale is
   1/4"=1'-0" (fpp=0.0556); the 0.1 placeholder makes the gap-closing radius
   ~45% too small, under-closes the wall graph, and reports `n_mid=4`
   (misroutes a clean, layer-usable page to the much weaker rules path,
   which is what happened on the first `run` attempt: 43 review / 6 auto).
   `takeoff.py`'s pipeline order has already resolved the page's *real* scale
   by the time it needs to route (step 2 before step 3), so it reuses that
   value in its own copy of the gate (`routing_gate_real_scale`, same
   metric/thresholds as `scan_closeability.score_page`, real fpp instead of
   the placeholder) rather than calling that function directly. Fixed, this
   produced the exact probe22 reproduction above.

## Known gaps / flags (honest, not silently patched)

- **Multi-floor page selection is single-page by default.** `resolve_pages()`
  picks the single richest page per doc (by wall-segment count) when several
  floor_plan pages are labeled for one permit — correct for the bank (four
  *alternate views of one tenant space*) and 26-10321 (picks Floor 9 by
  segment count, with no external signal telling it *which* floor to
  prefer), but a genuine multi-story building (24-06748 has 4 real floors)
  only gets ONE floor processed by default. Use `--pages` to target other
  floors explicitly; this is why `--doc`/`--pages` exist in the interface.
  Not fixed generically — would need scope-matching floor plan sheets to
  their corresponding finish/schedule sheets by title, which is a bigger
  design question than this composition pass, flagged for next session.
- **Text-anchor false positives on dense sheets.** Real-PDF-text room-number
  anchoring (`^\d{3,4}[A-Za-z]?$`, tightened from exp_p0/page_select's
  `^\d{2,4}[A-Za-z]?$` after verifying 1-2 digit tokens on the bank page were
  door/keynote tags, not rooms) still occasionally catches door/partition/
  keynote tags that happen to be 3-4 digits (e.g. bank open-zone group
  members "300", "225", "120" alongside the real merged room numbers). When
  a `truth_area`/`materials` JSON exists, `run` whitelists anchors to that
  schedule's own room-number list, which mostly eliminates this (used for
  24-06748). No such whitelist is possible for permits without a schedule
  (bank, 26-10321) — flagged in each `run`'s output rather than hidden; it
  changes which polygons get swept into an `open_zone_split` group's member
  list, not which polygons get a *wrong* SF number.
- **`needs_vision_scale` / `needs_vision_anchor` are real, exercised
  mechanisms**, not stubs: 26-10321 exercised both flags live this session
  (scale had zero regex matches; anchor text had 0/63 real hits). The crop
  and outline-only anchor montage (`render_anchor_montage`, the "probe24
  anchor_montage pattern" made into a reusable function, since it never
  existed as one before — the prior montages were ad hoc, per
  `experiments/probe24_two_permit_takeoff.md`'s own adjustment #4 request)
  both write to the run dir and are consumed by `vision_cache/`; a future
  agent reading a flagged crop/montage just needs to write the matching
  cache JSON for the next `run` to pick up automatically — no code change.
- **No polygon cap on the rules path.** The mission warns rules-path dense
  plans can produce "thousands of polygons." The existing 15-8000 sqft
  filter (unchanged from probe2/2b/3) already keeps this bounded in
  practice (9 on 24-06748, worst case observed); no additional cap was
  added since none of the acceptance tests needed one — flagged for
  whoever hits a permit where it isn't enough.
- **Anchor montage tile sizing is not robust to extreme aspect-ratio
  polygons** (a thin sliver from a BLOB rules-path run produces one absurdly
  tall crop, seen on 24-06748's montage). Cosmetic; the montage still shows
  every polygon.
- **Material step is a join + a todo flag, not extraction.** Per spec:
  `run` joins `floor_material_bucket`/`material`/`floor_code` from
  `truth_area`/`materials` JSON by room number when the file exists (used on
  24-06748); otherwise, if a finish_plan/finish_schedule page is labeled, it
  flags `material_todo` naming that page (bank, 26-10321) rather than
  attempting to parse finish-plan hex tags/legends automatically — that
  parse was manual in probe24 and was never scripted; out of scope here.

## Scoreboard (original session, clean, --engine v1)

```
permit            path    auto  rev  open  art  total_sf
14-11290-NEWC     layer     13    0     2    0   1178.4
26-10321-RNVN     layer     16   45     2    0   2393.9
24-06748-RNVS     rules      0    9     0    0      0.0
```

## Probe 29 Task B -- engine ladder wired in, default flipped v1 -> v4

`run` now accepts `--engine {v1,v2,v3,v4}` (rules path only; the layer path has
no engine ladder of its own and ignores the flag entirely). `v1` is this file's
original two-tier + admit_minor + `snap_and_close(feet_per_pt=None)` composition,
unchanged. `v2`/`v3`/`v4` delegate to `geometry_v2.run_geometry_engine_v2` /
`geometry_v3.run_geometry_engine_v3` / `geometry_v4.run_geometry_engine_v4`
(probes 27/28/29's density-gated gap closer + cavity/hatch filter, then the
anchor-cluster membership filter, then the directional proximity-reconnection
fix -- see `experiments/probe27_closure_fix.md` / `probe28_anchor_filters.md`
/ `probe29_continuity_fix.md`). v3/v4 need room-code text anchors computed
*before* geometry runs (the anchor-cluster filter judges cluster membership by
them); `rules_path_geometry` reuses `real_text_anchors()` (the same function
ANCHOR/step 4 already used) one step earlier for this, whitelisted to the
permit's own truth schedule when one exists.

### Re-ran all 3 acceptance tests with `--engine v4`

**1. 14-11290-NEWC (bank), layer path -- IDENTICAL, as expected.**
`--engine v4` (and `v1`/no flag) all resolve to the same layer-path run: 13
auto_quantity rooms, 1,178.4 SF, 2 open_zone_split groups -- byte-identical to
the original acceptance run. Confirms the mission's own prediction: rules-path
engine choice cannot touch a permit that routes to the layer path.

**2. 26-10321-RNVN, layer path -- IDENTICAL, as expected.**
`--engine v4`: 16 auto_quantity rooms, 2,393.9 SF, 2 open_zone_split groups --
byte-identical to the original acceptance run, same reasoning as above.

**3. 24-06748-RNVS, rules path -- MATERIALLY BETTER, the acceptance bar this
probe was actually testing.**

| engine | auto | review | total_sf | truth rooms matched | coverage | median \|err\| |
|---|---:|---:|---:|---:|---:|---:|
| v1 (original baseline, BLOB) | 0 | 9 | 0.0 | 0/36 | 0% | n/a (no matches) |
| v2 | 5 | 20 | 480.0 | 5/36 | 14% | 56.3% |
| **v4 (new default)** | **5** | **6** | **480.0** | **5/36** | **14%** | **56.3%** |

**Diagnosis, so the improvement isn't miscredited:** the actual unlock is v2's
density-gated gap closer + cavity/hatch filter (it alone produces the identical
5/36 matched, 480 SF, 56.3% median-err result) -- v3/v4's anchor-cluster filter
doesn't add newly-matched rooms here (it only removes/reclassifies polygons that
carry zero room anchors), but it materially cleans up the `geometry_review` pool
a human/vision reviewer would have to sift through afterward: 20 review polygons
under v2 shrink to 6 under v4, with the same 5 matched rooms retained and zero
coverage lost. Matched rooms: `201` (+12.2%), `202` (+16.9%), `205` (+403.3%,
bad), `206` (-56.3%), `208` (-60.7%) -- a real, coherent, non-fabricated grading
table (2 of 5 within 20% error, 3 clearly wrong but visibly so, not silently
wrong), a large step up from v1's "nothing to grade at all."

### Decision: default flipped v1 -> v4

No regression on either layer-path acceptance test (both byte-identical); a
material improvement on the rules-path acceptance test (0/36 -> 5/36 truth
rooms matched, 0% -> 14% coverage, 0 -> 480 SF, review-polygon noise cut 70%
with zero coverage loss). `DEFAULT_RULES_ENGINE` in `scripts/takeoff.py` is now
`"v4"`; `--engine v1` still works for anyone who wants the original baseline.

### Scoreboard (this session, `--engine v4` runs, reproducing the acceptance table)

```
permit            path    auto  rev  open  art  total_sf
14-11290-NEWC     layer     13    0     2    0   1178.4
26-10321-RNVN     layer     16   45     2    0   2393.9
24-06748-RNVS     rules      5    6     0    0    480.0
```

(`scoreboard.csv`'s `flags` column now also carries `rules_engine=vN` per run
for traceability -- the CSV schema itself was left unchanged rather than adding
a new column, since the file is append-only and already has runs under the old
header.)

## Probe 30 follow-up -- model + dual engines wired in; dual quality-gated; default NOT flipped

**Date:** 2026-07-10. Implements the CONDITIONAL PROMOTE decision from
`experiments/probe30_wall_model_v2.md` plus a mid-task coordinator amendment
(external review): wall_model_v2 ships as an ADDITIONAL candidate engine in
the rules path, never a silent replacement, and the dual arbitration is
quality-gated so an over-detecting engine can't win on raw anchor count.

### Engine section (updated interface)

`run --engine {v1,v2,v3,v4,model,dual}` (rules path only; the layer path has
no engine ladder and ignores the flag entirely -- `model`/`dual` never even
load the classifier for a layer-routed permit; the joblib load is a lazy
singleton behind `get_wall_model()`).

- **`model`** -- `geometry_model.run_geometry_engine_model`: wall_model_v2
  (probe30's trained segment classifier, threshold 0.80) picks wall
  candidates; everything downstream (v2 gap-close/cavity filter ->
  polygonize -> v4 anchor-cluster proximity reconnection) is the same code
  the rules engines use.
- **`dual`** -- runs v4 AND model on the same page, then
  `reconcile_dual_engines()` per page:
  1. Each engine's rooms are matched to room-label anchors; an anchored
     room only COUNTS toward the winner-election score if its polygon
     passes the QUALITY GATES (amendment): 40-5,000 SF size band, centroid
     inside the principal drawing region (padded bbox of the room-label
     text cluster), bbox aspect < 12:1, and no contradiction of the printed
     dimensions physically inside the polygon by >30% (one agreeing dim is
     enough to pass).
  2. Winner = more quality-passing anchored rooms (tie -> v4). The winner's
     quality-FAILING anchored rooms are demoted to `geometry_review` with
     the failed gate named.
  3. Rooms the loser anchored that the winner missed ENTIRELY are appended
     as `geometry_review` candidates (deduped by loser polygon -- a merged
     blob anchoring several loser-only tokens is added once), never auto.
  4. Rooms BOTH engines anchor via uniquely-anchored polygons whose areas
     disagree >15% are demoted to `geometry_review` ("engines disagree").
     Multi-token merged blobs are excluded from this comparison (a blob is
     not a per-room measurement; merges are judged by the open-zone
     machinery instead).
  5. If BOTH engines fail quality on >50% of their anchored rooms, the
     whole page demotes to review.

Provenance: every rules-path room row in `run.json` now carries
`engine: v4|model|both`; the run summary carries `engine_provenance` counts
and the scoreboard row carries them in `flags`
(`engine_provenance=both:1,model:1,v4:10`). Layer-path runs carry NO engine
key anywhere -- byte-identity below depends on that. `scoreboard.csv` gained
a `green_precision` column (of rooms marked auto_quantity, fraction within
15% of truth; graded permits only) -- the header migrates in place, old rows
backfill blank, content stays append-only.

### Acceptance battery (all runs this session)

**1-2. Layer path, byte-identical -- PASS.** `run 14-11290-NEWC` and
`run 26-10321-RNVN` with `--engine dual` (and with the model/dual code
merely present): `run.json` byte-identical to the prior v4-session outputs
except `generated_at` + the `rules_engine=` label. 13 auto / 1,178.4 SF and
16 auto / 2,393.9 SF reproduced exactly. The flag does not leak into the
layer path.

**3. 24-06748-RNVS (rules path), takeoff grader vs truth_area:**

| engine | auto | review | total_sf | truth matched | coverage | med err | green_precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| v4 | 5 | 6 | 480.0 | 5/36 | 14% | 56.3% | 1/5 = 20% |
| model | 0 | 6 (+1 open) | 0.0 | 0/36 | 0% | n/a | n/a |
| dual | 3 | 9 | 435.5 | 3/36 | 8% | 60.7% | 1/3 = 33% |

Dual = v4's page win with the amendment's gates applied: rooms 202 (18.7sf,
truth 16sf -- CORRECT but under the 40 SF floor) and 206 (25.8sf, truth 59sf
-- confidently WRONG, -56%) demoted to review by the size gate; model's
3-token blob (204/206/207, 161sf) rescued once as review. **The strict bar
"dual >= max(v4, model) on matched rooms" FAILS on auto count (3 < 5); no
geometry is lost** (all 5 v4 polygons persist, 2 as flagged review), and
green_precision improves 20% -> 33% (the demoted 206 was exactly the
confident-garbage class the amendment targets; the demoted 202 is the
amendment's floor discarding a real 16sf closet).

**4. TRUTH_AREA product test (probe26-29 grader, fixes 3-6 verbatim,
`scripts/probe30_product_test_dual.py`, results in
`data/probe30/product_test/{results_dual,scorecard_dual}.json`):**

| permit | v4: m/le30/cw/miss% | model: m/le30/cw/miss% | dual: m/le30/cw/miss% (+review) |
|---|---|---|---|
| 24-06233-RNVS | 2/0/2/38.2 | 6/5/2/23.5 | 5/5/**1**/5.9 (+9) |
| 20-29653-RNVS | 6/3/7/15.9 | 20/11/7/18.2 | 9/6/**0**/9.1 (+21) |
| 24-06748-RNVS | 3/2/8/30.6 | 2/1/8/50.0 | 1/1/**5**/27.8 (+7) |
| 26-05332-NEWC | 3/2/13/44.1 | 22/12/22/20.6 | 15/2/**9**/10.3 (+25) |
| **TOTAL (182 addr)** | 14/7/30/33.5 | 50/29/39/26.4 | 30/14/**15**/12.6 (+62) |

(m = matched, le30 = matched<=30% err, cw = confident_wrong, miss% =
missed-no-polygon %; +review = rows routed to DUAL_REVIEW, surfaced not
lost. One page -- 20-29653 doc 4941401 -- tripped the both-engines->50%-fail
page demote, correctly: dual posts 0 confident-wrong on that permit.)

Dual DOMINATES v4 on every aggregate column, posts the lowest missed% and
roughly HALF either single engine's confident-wrong -- but **FAILS the
"dominate or tie both on matched<=30%" bar vs model (14 vs 29)**, and
confident-wrong is 15, not the bar's 0 (no engine has ever hit 0 on this
grader; the disagree->review guard only fires when both engines cleanly
anchor the same room). Root cause of both shortfalls, measured: the
amendment's 40 SF floor. These multifamily permits' truth keys are full of
real 16-39sf rooms (23 winner rooms demoted on 26-05332's page alone, most
of which model had matched within 30%).

**5. Canaries (bank p3 / hotel p9, `scripts/probe30_canary_dual.py`,
results in `data/probe30/canary/canary_dual_results.json`) -- PASS.** No
crash, sane bounds, v4 wins both pages (bank 12-vs-1 quality-passing
anchors, hotel 15-vs-?), ZERO v4 polygons lost: dual only flags review on
top (bank: 1 poly, the 36sf room-108 poly under the size floor; hotel: 4
polys -- 3 size-floor + 1 all-dims-contradicted + 2 engines-disagree
demotions land on those). No regression vs the probe29 v4 canary numbers.

### Decision: default NOT flipped -- stays v4; dual ships opt-in

Two of the four battery bars fail as literally specced (3 above, 4 vs
model), and both failures trace to a single parameter: the amendment's
40 SF plausibility floor demoting genuinely-sub-40sf truth rooms. Per the
mission's own rule ("default changed to dual yes/no per the acceptance
outcome"), `DEFAULT_RULES_ENGINE` stays `"v4"`; `--engine dual` (and
`--engine model`) are fully wired, provenance-tracked, and acceptance-
documented. Recommended follow-up before a second promotion attempt:
re-derive the size floor from the truth_area room-size distribution
(MIN_SQFT=15 is the pipeline-wide floor; ~40% of demoted-but-correct rooms
sit in 15-40sf) and re-run ONLY battery items 3-4 -- everything else
already passes.

### Scoreboard (this session's rows)

```
permit            path    engine  auto  rev  open  total_sf  matched  green_prec
14-11290-NEWC     layer   (dual)    13    0     2    1178.4  no-truth       --
26-10321-RNVN     layer   (dual)    16   45     2    2393.9  no-truth       --
24-06748-RNVS     rules   v4         5    6     0     480.0     5/36      0.20
24-06748-RNVS     rules   model      0    6     1       0.0     0/36        --
24-06748-RNVS     rules   dual       3    9     0     435.5     3/36      0.333
```
