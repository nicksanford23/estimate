# From free layer-labels → an ML model → a better product

**Date:** 2026-07-08
**Context:** SF (square-footage) extraction — "Model 2." Follows probes 2–10.
**One-line thesis:** Layered CAD PDFs hand us free answer keys; we train a model
to reproduce those answers on files that have *no* layers; that model replaces the
brittle rules that were failing; more rooms auto-measure; the estimator confirms
instead of draws.

---

## Where the one permit (14-11290 Liberty Bank) actually stands

We've been grinding on this single project. Honest status **today**, no ML yet:

| Method | Result on the 18 branch rooms |
|---|---|
| Rules geometry (Route A) | ~8–11 close cleanly; **dense service core fails** (proven, not tunable) |
| **Its own CAD layers (Probe 7)** | **12 closed · 1 fragment · 5 merged · 0 no-polygon** |

So even on the one file with *beautiful* layers, we get **~12 of 18 truly clean**,
not 18/18. The remaining 5 are **merges** — two adjacent rooms whose shared wall
didn't fully split them, so they polygonized into one blob. That's a **closure**
problem, not a wall-detection problem.

**Bottom line:** perfect-automatic is NOT here, even on the best-case file.
- Layers took us from *"half, core impossible"* → *"most, a few merges."*
- What IS essentially here: **assisted** takeoff — a human confirms the 5–6 hard
  rooms instead of drawing all 18.
- The ML model below is what raises the auto-fraction; it is not trained/run yet.

---

## Stage 1 — Turn layers into training pairs (the free part)

The side-by-side artifact (`data/probe8/semantic_labels.jpg`) *is* one training
example. For every layered floor-plan page:

- **Input X:** render the page FLATTENED — all black linework, layer info stripped.
  Deliberately identical to what the 82%-of-files (no usable layers) look like.
- **Answer Y:** render the same page colored by class from the layers
  (wall / door / furniture / fixture / finish). That colored image is a
  **segmentation mask** — for every pixel, "what is this."

One layered page → one `(flat image → labeled mask)` pair. Across the confirmed
layered permits, every floor-plan page, then augment (rotate / scale / crop into
tiles) → thousands of labeled tiles. **Zero human labeling.** (Hand-drawing a wall
mask is ~20–40 min/page; we generate it in milliseconds.)

**Hard rule (same as Model 1):** split train/test **by permit, never by page** —
else the model memorizes a firm's style and we fool ourselves.

## Stage 2 — Train the model

Standard tool: a **U-Net** (image-in, per-pixel-class-out segmentation network).
Not invented here — the floor-plan-parsing literature (CubiCasa5K, Raster-to-Vector)
already does wall/room segmentation from plan images. The twist that makes *ours*
work is **domain match**: those datasets are residential apartments; **our labels
are commercial construction plans**, which is what we actually estimate.

- It learns: "this arrangement of black pixels is a *wall*; this cluster is
  *furniture*; this is *text*" — the exact sort the layers did for free.
- Model-quality metric: **wall IoU** (predicted-vs-true wall overlap) on
  **held-out permits**.

## Stage 3 — Run it on the flattened 82%

```
flat plan → [U-Net] → wall mask → vectorize (trace to segments)
          → snap_and_close → polygonize_rooms → rooms → × scale → SF
```

The second half we **already built** (probes 2–7). The model only replaces the
fragile step that was failing — the rules-based "which lines are walls" (angle/
width heuristics that couldn't tell a wall from a dimension tick or furniture).
The learned detector *did* learn to ignore furniture, because training showed it
furniture-separated-from-walls thousands of times.

## Stage 4 — Why the PRODUCT gets better

| | Today (rules) | With the model |
|---|---|---|
| Clean rectangular rooms | ✅ close | ✅ close |
| Cluttered service core | ❌ fails | ✅ model ignores learned clutter |
| Estimator's job | draw **every** room | confirm the few hard ones |
| Material per room | manual | pre-filled from finish layers |

Product shape: **assisted takeoff** — app pre-draws boundaries + SF + likely
material; estimator nudges the handful the model is unsure of. **Time-per-takeoff**
is the number that drops — the sellable outcome.

Judge two things separately: **wall IoU** (is the model good) vs **room-closure /
SF accuracy vs real measured SF** (is the *product* good). Pixels can look great
while a 2-px gap stops a room closing — so we grade on rooms, not pixels.

## Stage 5 — The flywheel (why it compounds)

- Layered files solve the **cold start** — a working model before any customer.
- Every estimator **correction** (drag a wall, fix a room) is a *new labeled
  example* — and it's on a **flattened file**, exactly our weakest distribution.
- Free layer-labels bootstrap → real usage fixes the long tail. More use → better,
  on the files that matter.

---

## Honest risks (state them first)

1. **Raster → vector is lossy.** Thin walls vanish at low DPI; tile at high DPI →
   more compute.
2. **~30–44 permits proves it, doesn't fully generalize.** Firms draw differently.
   Fix is known & cheap — download more (≈3,000 addressable permits) — but data
   *quantity* is the real risk, not the method.
3. **Commercial plans are messier** than research datasets — our own labels close
   that gap, which is why an off-the-shelf model won't do.
4. **The model finds walls; SF still needs correct closure + scale.** We have
   scale detection; closure is the existing (imperfect) pipeline. The model raises
   the ceiling, not to 100%.

## The data behind this (probes 7–10)

- Only **~16%** of labeled floor plans kept named CAD layers; **82%** flattened to
  one blank layer (layer names destroyed at export). The trick is real but not
  universal → its best use is *training data*, not runtime.
- Full corpus (2,329 downloaded PDFs = **150 unique permits**): **44 permits (29%)
  carry wall-named layers.** Of those, ~80–86% also carry door/furniture/finish
  layers → genuinely multi-class free labels.
- Name-match is an upper bound; geometry-confirmed count: **_(verification pass
  pending — will insert)_**.
- Scaling headline: we've downloaded **150 of 12,106 permits**. At a 29% rate, the
  addressable free-training well is **~3,000+ permits** — constraint is download +
  verify, not availability.

## Tie-back to Model 1 (the page classifier)

The same layer signal feeds Model 1: a page with wall layers is almost certainly a
floor plan → **free weak-labels** for the classifier currently stuck at ~0.27
finish recall. **Both models share one free data source.**
