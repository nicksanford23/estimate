# Geometry reboot v1

> **Superseded for current geometry execution on 2026-07-21 by
> `GEOMETRY_RESET_V2_FIRST_PRINCIPLES.md`.** This document remains historical
> evidence for the segmentation/SAM experiments and portfolio rules. No mask,
> polygon, or colored edge-gate output described here is qualified truth.

Locked 2026-07-14 after complete-project testing on `24-06748-RNVS`.

## Decision

Stop treating the current v4 rules engine or `wall_model_v2` as a candidate for
approval. They are proposal generators only. On the complete four-level pilot,
v4 produced 2/36 accurate numbered rooms and the model produced 0/36. Dual did
not improve the accurate-room count.

The current model answers too narrow a question: “does this PDF segment look
like a wall?” The product needs a different answer: “what exact quantity zone
belongs to this scheduled space, and is its boundary a wall, finish transition,
exterior limit, open-zone split, or unresolved?” Decks, open areas, garages,
and finish-only divisions make those tasks materially different.

## Replacement architecture

The new pipeline is hybrid but room/zone-first:

1. Assemble the complete plan set, schedule roster, levels, and quantity
   viewports deterministically.
2. Rasterize each confirmed viewport at a fixed physical resolution while
   retaining the PDF transform and vector primitives as auxiliary channels.
3. Use every room-label location as a positive point prompt. Run a promptable
   segmentation baseline to propose one or more masks for every scheduled room,
   including rooms the wall polygonizer missed.
4. Train an in-domain instance/semantic segmentation model on corrected masks
   with explicit classes for room interior, finish zone, exterior/deck zone,
   wall/obstruction, and ignore/annotation. Do not train from printed SF alone.
5. Convert accepted masks back to PDF polygons; deterministic code performs
   regularization, snapping, scale conversion, area arithmetic, and audits.
6. Join finish/material evidence after geometry, with open/finish zones kept as
   first-class product outcomes.

SAM 2 is a useful zero-shot/few-shot proposal experiment because it accepts
point/box prompts, but it is not assumed to be the final model. A supervised
Mask2Former-style instance/semantic model is the main training candidate once
in-domain corrected masks exist. CubiCasa5K and FloorPlanCAD are useful for
pretraining/augmentation experiments, not as proof on construction permit sets:
their domains and label objectives differ from our quantity-zone task.

RoomFormer is not the primary candidate here: its published input is a density
map derived from 3D scans, not a cluttered 2D construction PDF.

Primary references:

- Meta SAM 2: https://ai.meta.com/research/sam2/
- Mask2Former code/paper: https://github.com/facebookresearch/Mask2Former
- CubiCasa5K dataset/model: https://github.com/CubiCasa/CubiCasa5k
- FloorPlanCAD paper: https://openaccess.thecvf.com/content/ICCV2021/html/Fan_FloorPlanCAD_A_Large-Scale_CAD_Drawing_Dataset_for_Panoptic_Symbol_Spotting_ICCV_2021_paper.html
- RoomFormer code/paper: https://github.com/ywyue/RoomFormer

## What SAM does — and does not do

SAM is a promptable image-segmentation model. For this product, it receives a
rendered plan viewport plus a positive point at a room label (and optionally
negative points or a rough box), then returns one or more pixel masks. It does
not understand flooring scope, select the plan revision, establish scale,
calculate square footage, or attach material.

The responsibility split is binding:

```text
project packet + room roster -> choose the right plan and prompt
SAM / later segmentation model -> propose a room or quantity-zone mask
vector + deterministic geometry -> sharpen edges and convert mask to PDF polygon
scale + arithmetic -> calculate square footage
schedule join -> attach material and reference area
reviewer/editor -> correct or reject the proposal
```

The current `wall_model_v2` is paused as a production candidate. Vector PDF
work is not discarded: it remains useful for text coordinates, clean CAD
layers, scale, snapping, exact polygons, and audits. The architecture is
segmentation for understanding plus vectors/code for precision.

## Data contract before GPU spend

Run:

```bash
python scripts/build_geometry_annotation_packet.py --permit 24-06748-RNVS
```

The output contains one required task for each of the 36 schedule spaces. A
task is complete only when a human supplies an explicit outcome and boundary
type. Missing rooms remain tasks. Machine proposals stay separate from human
geometry. The schedule area may check a polygon after drawing but cannot create
the polygon or serve as training truth by itself.

The internal Geometry Review surface currently records verdicts but cannot edit
full vector rings. Therefore the next UI milestone is a viewport polygon/mask
editor that reads and writes this contract (or a temporary CVAT/Label Studio
adapter using the same contract). Verdict-only review is insufficient for
training a replacement model.

## First SAM test — one complete project

`24-06748-RNVS` is sufficient to test the machinery and whether SAM is useful
as an annotation assistant. It is not sufficient to train or claim a general
production model.

The local, zero-GPU preparation step produces four clean viewport images, the
PDF-to-image transforms, and exactly 36 room prompt tasks. For every room, the
GPU test runs at least these prompt variants:

1. room-label point only;
2. room-label point plus other nearby room labels as negative points; and
3. room-label point plus a rough search box.

Every candidate mask and model score is saved. The evaluator must not choose a
candidate merely because its area is closest to the printed schedule value;
that would use the answer to select the prediction and would not work on
schedules without area. Schedule area is applied only after prediction as a
diagnostic check. Corrected geometry is required to judge boundary overlap.

The first experiment answers: “Does a SAM proposal reduce correction effort
compared with drawing a mask from scratch?” It does not answer: “Is SAM ready
to produce bid quantities automatically?” Useful-but-imperfect masks make SAM
an editor accelerator. Poor masks end the SAM branch without invalidating the
editor or the corrected dataset.

The per-room artifact includes the original crop, prompt points, all masks,
scores, image and PDF polygons, calculated SF, schedule comparison, AI-review
flags, and the final human outcome. Independent agent review can prioritize
problems, but agent agreement remains machine evidence until human review or
the applicable audit gate.

## Cross-project development and evaluation ladder

Floors from one plan set share an architect, symbols, line styles, and export
process. Four floors are therefore still one project for leakage and
generalization purposes.

The first credible experiment uses this staged portfolio:

1. **one smoke project:** `24-06748-RNVS`, 36 rooms across four levels, to
   prove prompt preparation, inference, editing, transforms, and scoring;
2. **three to four complete development projects:** deliberately different
   architects and conditions, including clean named-layer vector, flattened
   vector, open/finish zones, exterior/deck limits, and scans if scans are in
   product scope; and
3. **two untouched evaluation projects:** no training, prompt tuning, threshold
   adjustment, or page selection after their results are seen.

`14-11290-NEWC` is useful as a development case for finish/material joins
without printed room areas. It is not a sealed SF answer key unless a human
creates and qualifies its geometry.

A practical first training portfolio is roughly 150-300 corrected room or
quantity-zone masks across those complete projects, but diversity matters more
than the raw count. Hundreds of rooms from one drawing family do not replace
project-held-out evidence. Train/validation/evaluation manifests split by
project and plan revision, never by random pages or crops.

One project is enough to start; multiple diverse projects are required before
training and production claims. The portfolio expands further if the two
held-out projects expose a missing drawing condition.

## GPU experiment ladder

No cloud GPU is rented until the exact input bundle, container digest,
checkpoint, command, output path, max runtime, and budget cap are recorded.

### G0 — CPU/data integrity

- Four confirmed viewports and 36 explicit annotation tasks.
- Source PDF-to-raster and raster-to-PDF transforms round-trip within tolerance.
- Project-level split manifest prevents pages from one building appearing in
  both train and evaluation.

### G1 — promptable baseline, no training

- Run SAM 2.1 Small on all prompt variants for all 36 tasks; compare Large only
  after the container and result path work end to end.
- Save every candidate mask and score; never overwrite human geometry.
- Measure proposal coverage, other-room contamination, boundary correction
  effort, calculated area, missing rooms, and confident-wrong output.
- SAM passes the **annotation-assistant** gate only if its proposals measurably
  reduce correction effort. It cannot pass the production gate from this
  project, even if several masks are excellent.

### G2 — supervised segmentation fine-tune

- After the development portfolio exists, compare adapting SAM with training a
  compact dedicated instance/semantic model. Do not assume SAM is the final
  production model.
- Use raster plan content plus derived vector/text/hatch channels where useful.
- Select checkpoints by project-held-out metrics, not random image crops.
- Stop early if held-out project performance does not beat deterministic v4
  and the promptable baseline on the same frozen grader.

### G3 — vector graph experiment, only if justified

- If raster masks fail mainly at exact boundary placement, test a vector graph
  model initialized/augmented with FloorPlanCAD-style line semantics.
- Do not start here: it is more specialized, and the current evidence says the
  missing signal includes finish/exterior zone semantics, not just wall lines.

## Promotion gates

A replacement may become a candidate only when it:

- runs every required viewport of a complete held-out project;
- improves scheduled-identity coverage, exact-area count, and missing-room
  count over v4, with no level hidden or dropped;
- has zero high-confidence quantity polygons outside the accepted tolerance;
- records explicit review actions for open, finish, exterior, and unresolved
  zones;
- preserves scale/transform/provenance audits; and
- passes a second complete-project canary unchanged.

The eventual product gate remains at least 70% auto-proposed rooms, median area
error below 2%, and zero confident-but-wrong bid quantities. “Looks cleaner”
and “one floor improved” are not promotion criteria.

## RunPod lifecycle and secret handling

The current Codespace prepares data and application code but has no GPU,
PyTorch, or SAM installation. SAM inference and later training run in a pinned,
reproducible GPU container.

No RunPod account credit or API key is needed during local preparation. Once
the 36-task input bundle, container, result schema, timeout, and cleanup path
are verified:

1. add a small prepaid balance with auto-pay disabled for the smoke test;
2. start one temporary on-demand Pod;
3. run the 36-room Small checkpoint test and, if healthy, the Large comparison;
4. copy all results back and verify them locally; and
5. terminate the Pod rather than leaving GPU or persistent storage idle.

Production, if volume is intermittent, should use a Serverless Flex worker that
scales to zero and accepts a cold start. An always-active worker is a later
latency/business decision, not a development default.

API keys are passwords. They are never pasted into chat, committed, printed in
logs, or stored in an artifact. If automation is needed, create a dedicated
minimum-permission key and expose it as the `RUNPOD_API_KEY` Codespaces secret.
The first interactive smoke can also be launched manually, avoiding an API key
until the container has proved useful.

Current official operational references:

- SAM 2 installation/checkpoints: https://github.com/facebookresearch/sam2
- SAM 2 custom training: https://github.com/facebookresearch/sam2/blob/main/training/README.md
- RunPod Pod lifecycle: https://docs.runpod.io/pods/manage-pods
- RunPod Serverless worker modes: https://docs.runpod.io/serverless/workers/overview
- RunPod API-key safety: https://docs.runpod.io/get-started/api-keys
