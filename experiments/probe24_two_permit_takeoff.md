# Probe 24 — Two-permit takeoff pass + the "layered ≠ usable" finding

**Date:** 2026-07-08
**Scripts:** `scripts/probe24_takeoff.py`, ad-hoc montage/diagnostic runs (this session)
**Web guides:** `/permits/26-10321-RNVN/guide`, `/permits/25-33341-NEWC/guide`
**Images:** `data/probe24/*` (web copies under `web/public/guide/<permit>/`)
**For:** Fable review — recommendations on process adjustment + go-deeper vs go-wider.

This is the second and third buildings after the bank (14-11290). Goal: run the
full **extract → debug → repeat** takeoff on the two READY permits that segmented
as LAYERED, and record honestly what worked, what didn't, and what it means for
the plan.

---

## TL;DR for the reviewer

1. **26-10321 (office reno) — the method works end-to-end.** Vision scale →
   layer geometry → vision room-anchoring → finish material. 15 private rooms
   auto-quantified (2,323 SF, Carpet 1,365 + LVT 958). Open-plan core merges
   (known, honest limit). This is a real per-room takeoff on a second building.
2. **25-33341 (Newlab lab/maker building) — geometry fails despite being
   "layered."** The wall layer is a **3D solid** (`A - Walls - Exterior.3D`),
   16,264 fragmented segments; the polygonizer only closes small core rooms
   (~2,055 SF of a ~10k+ SF building). No parameter tuning fixes it.
3. **The finding that changes the plan:** *"layered" is not the same as
   "geometry-usable."* `segment_ready.py` counted wall segments, not wall
   quality. Of the 2 LAYERED READY permits, **only 1 is actually usable.** The
   layered-supply bottleneck is worse than the 2/23 count implied.
4. **Decision on the table (needs your call):** finish hand-working all 25
   (go-deeper) vs download more layered permits with a quality gate (go-wider).
   My lean: **go-wider**, because the binding constraint is geometry-usable
   layered supply + the ML wall-model, and hand-finishing flattened permits
   produces no takeoff without that model.

---

## Permit A — 26-10321-RNVN (Veteran's Benefits Administration, office reno)

Doc 9058456 · 42 pages · "100 CD_ARCH 04-06-26.pdf" · multi-floor office reno,
EXIST/NEW WALL layers + A5.x finish plans. Near-GOLD (layers + finish, aligned).

**Pipeline run (Floor 9, A2.4 = p18, finish A5.4 = p33):**

| step | how | result |
|---|---|---|
| scale | **vision** off trimmed sheet (regex missed it) | `1/8" = 1'-0"` → fpp 0.111 |
| geometry | `NEW WALL`/`EXIST WALL` layer → snap → polygonize | 63 polygons, 18,462 SF total |
| room anchor | **vision** — outlined-crop montage, one read | 15 rooms named on a **vectorized** plan (only 98 text tokens on page) |
| material | A5.4 finish plan hex tags + legend | Carpet C1 (offices), LVT (service/wet) |

**Anchored takeoff — 15 rooms, 2,323 SF:**
Offices 901/902/903/905/907/918/943/944 + Conference 941 = **Carpet C1, 1,365 SF**.
Wellness 916, Breakroom 923, Waiting 931, Workroom 933, Supply 934, File Room 937
= **LVT, 958 SF**. Material split fell out exactly as the finish key predicts
(offices carpet, service/wet LVT) — an independent sanity check that the anchoring
is right.

**Honest coverage:** the 2,323 SF is the *hard-walled private rooms*. Not included:
open-office + corridor blobs (~7,400 SF, floored carpet but not room-splittable —
no enclosing walls, only furniture) and restroom/core/chase (correctly excluded).
Full-floor flooring ≈ 2,323 anchored + ~7,400 open-office ≈ **~9,700 SF**.

**Method note (3 montage iterations to get room-anchoring right):** no-fill crop =
ambiguous (multiple bubbles, can't tell which polygon); solid-fill = hides the
bubble; **outline-only = works.** Worth locking into a reusable script.

Images: `takeoff-final.jpg` (colored by material), `all-polygons.jpg` (shows the
open-plan merge), `room-anchoring.jpg` (the montage method).

---

## Permit B — 25-33341-NEWC (Newlab, 4480 Dauphine, new construction lab/maker)

Doc 8640130 · 36 pages · new construction, hard-walled labs (Wet Lab, Foam Labs
1–4, Shop Fab, Project Area, Event). Has a **real finish schedule table** (A-603,
p35) — but **no area column** (MATERIAL_ONLY, not TRUTH_AREA). Floors are almost
all **CN-1 = floated sealed concrete**; tile in wet rooms. Flooring scope here is
concrete sealing/polishing, not carpet/resilient install.

**Scale (vision):** `3/32" = 1'-0"` → fpp 0.1481 (not a 1/N scale — good it was
read visually, regex would mis-parse).

**Geometry — the failure:**

| signal | value |
|---|---|
| wall layer | `A - Walls - Exterior.3D` (single layer, **`.3D` = 3D solid edges**) |
| raw segments | 16,264 (→ 1,250 after length filter) |
| longest segments | 87–88 ft (exterior walls ARE captured) |
| largest polygon | **only 263 SF** (all filters off) |
| rooms closed | ~18 small core rooms, **2,055 SF** of a ~10k+ SF building |

**Parameter sweep (all failed to close the labs):** snap_tol 0.0025→0.005,
door 4.5→6 ft, self-snap 1–2 ft. Self-snap *collapsed* the network (0 rooms).

**Root cause:** the long exterior wall faces don't node together at corners —
the corner/junction geometry lives in the thousands of tiny sub-segments the
length filter drops, and interior partitions meet the *mid-span* of exterior
walls with no shared vertex. So cycles never form for the big rooms; only the
tightly-drawn small rooms (restrooms, jan, mech) close. This is a bad wall
*representation*, not a bad tolerance.

Image: `geometry-fail.jpg` (only small core rooms fill green; labs stay open).

---

## The cross-cutting finding: "layered" ≠ "geometry-usable"

`segment_ready.py` tiered permits LAYERED vs FLATTENED by **wall-segment count**
(≥200). That's necessary but not sufficient:

- 26-10321: clean 2D `NEW WALL` centerlines → geometry closes rooms. **Usable.**
- 25-33341: `.3D` solid, 16k fragments → geometry closes almost nothing. **Not
  usable**, despite 1,250+ "wall segments."

So of the 2 LAYERED READY permits, **only 1 is actually geometry-usable.** The
count over-reports usable supply.

### Proposed adjustment 1 — polygonize-quality gate

Replace the segment-count test in `segment_ready.py` with a **closeability** test:
run the actual snap→polygonize and score on the *output*, e.g.
`largest_room_SF ≥ 150` AND `count(rooms 40–2000 SF) ≥ 3`. A `.3D` solid that
yields a 263 SF max polygon fails; a clean centerline layer passes. Re-score all
23 READY permits — the LAYERED pile likely shrinks. (Cheap: it's the same geometry
we already run.)

### Proposed adjustment 2 — re-tier 25-33341 → MODEL_TARGET

It's not TRAIN_LAYERED (layer unusable) and not TRUTH_AREA (schedule has no area
column). It's a MATERIAL_ONLY + MODEL_TARGET permit: good finish materials, needs
the ML wall-model for area.

### Proposed adjustment 3 — the ML wall-model matters *more*, not less

Clean-2D layered files are rarer than the raw layered count suggested. That
strengthens the case for the vector-first wall classifier that learns walls from
*any* representation (clean centerlines, `.3D` solids, flattened) rather than
depending on tidy named layers. Layered files remain the free training labels —
but need the quality gate before they're trusted as labels.

### Proposed adjustment 4 — lock in the room-anchoring method

The outlined-crop montage (vision reads room numbers off vectorized plans, one
pass) worked on 26-10321. Make it a reusable `scripts/takeoff.py` step so every
geometry-usable permit runs the same path.

---

## The decision: go-deeper (finish 25) vs go-wider (get more layered)

**Go-deeper** (hand-work the remaining ~23 permits): produces Model-1 page labels
and material reads, but **no square-footage takeoffs** for the 21 FLATTENED ones —
they have no usable walls, so there's nothing for geometry to measure until the
ML model exists. We'd be producing material-only guides.

**Go-wider** (download more permits, apply the quality gate, grow the
geometry-usable + layered-training piles): directly attacks the binding
constraint. More clean-2D layered permits = more buildings we can take off *today*
(like 26-10321) **and** more training labels for the wall-model.

**My recommendation: go-wider**, with the quality gate in place so we're scoring
by closeability, not segment count. Keep hand-finishing only the permits that pass
the gate (real takeoffs) + any TRUTH_AREA permits (grading data). Park the rest as
MODEL_TARGET.

*(This is the open question for Fable — the above is a lean, not a settled call.)*

---

## Status vs the bank (14-11290)

| | bank 14-11290 | 26-10321 | 25-33341 |
|---|---|---|---|
| walls | clean centerlines | clean `NEW/EXIST WALL` | `.3D` solid (**unusable**) |
| geometry | 10 auto / 2 review / open split | 15 private auto / open core merges | ~18 core rooms only |
| room anchor | dimensions cross-check | **vision montage** (vectorized) | blocked (no geometry) |
| finish | schedule w/ materials | finish plan hex tags | schedule table, **no area col** |
| area truth | none (net-vs-gross) | none | none |
| verdict | partial | partial | not_suitable (geometry) |

None of the three has a per-room **area schedule** to grade against — that
TRUTH_AREA permit is still the missing piece for hard validation.
