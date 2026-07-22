# Model and station training plan V1

- Date: 2026-07-17
- Status: architecture and training proposal
- Process dependency: `FULL_PROCESS_V5_DRAFT.md`, approved for lock in Codex round 5

## 1. Core decision

We are not training one model to ingest every permit document and produce a final flooring estimate.

Each station has a bounded responsibility. Models propose where perception or language understanding is needed. Deterministic software performs exact transforms, measurement, topology, policy application, and audit history. Qualified humans establish truth.

The primary RunPod-trained geometry model will propose **physical floor-surface masks**, not one polygon per room identity.

## 2. Station map

| Station | Responsibility | Initial implementation | Train our own model? |
|---|---|---|---|
| S1 Pages | Route pages by type/phase/level | Rules, OCR, rented vision | Yes: Model 1 |
| S1.5 Plan-set map | Revisions, levels, viewports, relationships | Rules + structured AI | Later, only where useful |
| S1.7 Scale | Verified scale/transforms | Deterministic + reviewer | No primary ML model |
| S2 Roster | Identities, schedules, anchors, conflicts | PDF text + rules + AI extraction | Later structured extractor |
| S3 Evidence | Multi-scale packets | Deterministic rendering | No |
| S4 Draft | Propose physical surface | Rented vision, then trained segmenter | Yes: main geometry model |
| S5 Criticize | Independent edge criticism | Separate vision model | Possibly later; remains independent |
| S5.2 Surface model | Open zones, stairs, unsupported splits | Vision + topology/rules | Hybrid |
| S5.5 Measure | Confirmed reference and deviations | Vector/raster geometry + reviewer | Candidate nomination may learn later |
| S7 Topology | Overlap, gaps, duplicates, adjacency | Deterministic geometry | No |
| S8 Human gate | Product and truth decision | Qualified reviewer | No |
| S10 Estimate | Policy, products, waste, pricing, export | Versioned business rules | No core model initially |

## 3. Model 1: page-routing model

### Task

Given a page image plus extracted text and document metadata, predict routing information such as:

- floor plan;
- finish plan;
- room/finish schedule;
- enlarged plan/detail;
- proposed versus existing/demo;
- floor level;
- other/administrative;
- uncertain.

Model 1 never deletes a page. It creates reversible routing suggestions.

### Data

- All preserved pages.
- Human-verified labels.
- Project/document grouping.
- Phase and level evidence.
- Explicit uncertain labels.

### Evaluation

Split by whole project. The primary risk is a false negative on a page needed downstream. Report recall/false-negative rates separately for floor plans, finish plans, schedules, and enlarged references. Precision matters, but sending an extra page to review is safer than hiding a necessary page.

### Architecture

Begin with a simple baseline using OCR/text features, document metadata, and page-image embeddings. Compare it with rented multimodal classification. Only add a larger trained page model if held-out project performance justifies it. This task may need only brief/small GPU runs.

## 4. Main geometry model: physical-surface segmentation

### Task

The initial geometry model answers:

> Given a floor-plan image and one or more anchors associated with a candidate physical surface, which pixels belong to that floor surface?

### Input

- scale-derived room/surface crop;
- full-floor context or context features;
- one or more room-label anchors;
- optional surface-type prompt;
- immutable coordinate transform metadata.

The model never receives printed square footage as a shape selector.

### Target

- one reviewed mask per `physical_surface_region`;
- surface type, such as interior/open/deck/specialty;
- room and finish identities stored as memberships, not separate masks;
- ignored/unresolved pixels where truth is not established.

Example:

```text
physical_surface_region surface_3f_open_01
├── target mask: one continuous reviewed floor surface
├── membership: room 305
├── membership: room 306
└── membership: room 307
```

### Production output

The neural model produces a mask proposal. The downstream process remains:

```text
mask proposal
  -> polygon extraction
  -> boundary-type assignment
  -> PDF/raster reference nomination
  -> reviewer confirmation
  -> vector snap or reviewed redraw
  -> measured gate
  -> floor topology
  -> human decision
```

The model does not create training truth by itself.

## 5. Candidate geometry architectures

### Candidate A: anchor-prompted SAM decoder fine-tune

Use the existing room-label anchor as a point prompt. Start with the repository's SAM 2.1 small-encoder harness, freeze the encoder, and fine-tune the mask decoder.

Why it is the first candidate:

- strong pretrained image representation;
- works naturally with an anchor prompt;
- suitable for hundreds rather than thousands of initial masks;
- fits a single 24 GB GPU;
- existing training plumbing is available.

This is the first contestant, not the predetermined production winner.

### Candidate B: Mask2Former-style supervised segmentation

Compare a promptless/whole-view segmentation model when:

- anchors are frequently unavailable;
- whole-floor prediction becomes important;
- surface classes need stronger explicit modeling;
- the labeled dataset becomes larger and more diverse;
- the prompted candidate plateaus.

### Candidate C: vector-graph/refinement system

If a segmentation model consistently finds the correct approximate surface but misses exact wall faces, use PDF vector structure rather than assuming a larger image model will fix precision.

Candidate capabilities:

- wall-pair identification;
- room-facing side selection;
- junction/corner graph construction;
- door-jamb and threshold detection;
- curve/sloped-wall following;
- shared-edge consistency.

This may remain a hybrid of learned nomination and deterministic constrained geometry.

## 6. Training eligibility

A real geometry training run requires:

- locked label book;
- at least 150 training-eligible `physical_surface_regions`;
- multiple projects and architect/design families;
- complete S8 evidence chain;
- per-edge confirmed references;
- measured and topology gates;
- project-disjoint training/validation splits;
- machine proposals excluded from truth.

The 150-surface threshold permits an exploratory run only. It does not authorize production replacement.

The current 35 Baronne proposals are not eligible merely because they exist. They must pass the locked workflow and human gate.

## 7. RunPod usage

### Diagnostic run

Purpose:

- prove pod creation;
- upload/download flow;
- dependency installation;
- training loop;
- loss and checkpoint plumbing;
- guaranteed pod termination.

Diagnostic metrics must never appear in model-quality or sales claims.

### Real exploratory run

When eligibility is met:

1. create an immutable dataset manifest;
2. upload data/checkpoint with short-lived transfer URLs;
3. start one 24 GB GPU;
4. train Candidate A under a hard budget/time cap;
5. download checkpoints and metrics;
6. terminate the pod;
7. evaluate locally/on held-out projects;
8. repeat for approved bakeoff candidates.

RunPod is burst infrastructure. It should not run continuously while idle.

## 8. Evaluation and promotion

### Model-level metrics

- mask IoU;
- boundary F1;
- maximum/p95 boundary deviation after scale conversion;
- coverage rate;
- confident-wrong rate;
- performance by surface type;
- performance by project and architect family.

Area error is measured only against qualified reference geometry, never a printed schedule.

### Workflow-level metrics

The winning model is not necessarily the model with the highest IoU. Measure:

- percentage of surfaces passing without redraw;
- reviewer minutes per surface/project;
- repair rounds;
- critical omissions;
- total project turnaround;
- variable compute/review cost.

### Promotion gate

A model may replace the rented S4 proposer only when it:

- beats the declared rented-AI/vector baseline on held-out projects;
- introduces no unacceptable confident-wrong behavior;
- passes a second-project canary;
- has defined rollback criteria;
- preserves the independent S5 critic;
- does not use sealed exam projects for tuning.

## 9. Independence requirement

The proposer and critic must be separate invocations with fresh context and no access to each other's rationale. During calibration, use cross-vendor review on failures/disputes and sampled passes. A later trained critic cannot silently approve outputs from the same checkpoint without an independently validated protocol.

## 10. Required runbook update

Before any real RunPod training, update `data/training/TRAIN_RUNBOOK.md` and its manifest builder to:

- use `physical_surface_region`, not room, as the canonical sample;
- require the V5 S8 eligibility chain;
- reference the locked label book/schema;
- retain memberships without duplicating masks;
- split by project and architect family;
- store dataset/model/code versions;
- report boundary and workflow metrics;
- run a model-agnostic bakeoff rather than assuming SAM wins.

Until then, the existing runbook is valid only as historical plumbing guidance and for a clearly marked diagnostic smoke.
