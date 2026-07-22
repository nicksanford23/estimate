# V2 Product Rebuild Plan v1

Status: **APPROVED PRODUCT DIRECTION — implementation not started**  
Written: 2026-07-17  
Primary screenshot reviewed:
`docs/pilot/Plan-Sets-—-NOLA-commercial-permits-07-17-2026_01_21_PM.png`

This document is the build brief for replacing the current V2 research-tool
navigation with one understandable estimating workflow. It incorporates the
Geometry Label Book V2 direction and the agreed Claude-proposes / Codex-checks
/ Claude-repairs / human-approves outline workflow.

The builder should treat the present V2 interface as disposable where needed.
Preserve its useful data and backend capabilities, but do not preserve confusing
information architecture merely because code already exists.

---

## 1. Product outcome

V2 should feel like one project moving through a clear sequence:

```text
Project
  -> select and confirm the plan set
  -> confirm the room/finish roster
  -> review physical floor areas
  -> apply estimating policy
  -> produce an estimate
```

It must not feel like several unrelated ML experiments taped together.

The normal user should not need to understand:

- page-label pilots;
- geometry-engine bake-offs;
- training packets;
- database identifiers;
- model run numbers;
- evidence-governance terminology;
- internal permit-path names.

Those concepts may remain available in an internal diagnostics area.

---

## 2. Binding product decisions

1. A project is displayed by an editable project name or address, never
   primarily by permit number.
2. Each project appears once on the V2 landing page.
3. The page-label and geometry experiments are not separate project cards.
4. `Pages` and `Documents` are combined into the user-facing `Plan Set` area.
5. `Rooms & Finishes` remains a product stage, with clearer source evidence.
6. The existing `Outline Rooms` interface is replaced.
7. The existing `Geometry Review` interface is removed from normal navigation.
8. One new `Floor Areas` workspace owns proposal, inspection, correction, and
   human approval.
9. Schedule-area proximity never approves geometry.
10. A green state means human-approved geometry, not “close to schedule SF.”
11. Existing V1 annotation rows remain provisional proposals and cannot be
    described as locked or training truth.
12. Old routes/data are preserved until migration is verified, but hidden from
    normal product navigation.

---

## 3. Why the current V2 feels incoherent

The current `/v2` landing page exposes two parallel sections:

- `Outline Rooms — training data pipeline`, keyed primarily by permit number;
- `Page-label pilot`, keyed primarily by address and split into artificial
  geometry/schedule paths.

The same underlying project can therefore appear twice with two identities and
two unrelated progress systems.

The current project navigation also exposes:

```text
Pages | Rooms & Finishes | Outline Rooms | Geometry Review | Documents
```

This mixes source management, product stages, an obsolete geometry diagnostic,
and a V1 polygon editor. `Outline Rooms` and `Geometry Review` appear to be two
versions of the same task but actually use different data and truth rules.

The current `Geometry Review` also centers schedule-area agreement. That is not
a safe verification method: a wrong shape can have the right area, and two edge
errors can numerically cancel each other.

This is a structural problem, not a styling problem.

---

## 4. Project identity

### 4.1 Display-name priority

Resolve the visible title in this order:

1. `user_project_name`, if a user has set one;
2. normalized property address;
3. short project/development description;
4. permit number only as a last-resort fallback.

Example:

```text
600 Baronne / 840 Lafayette Renovation
New Orleans, Louisiana
Permit 24-06748-RNVS
```

The title should be editable from the project Overview. Changing it changes
only display identity, never internal permit/document keys.

### 4.2 Internal keys

The application may continue using permit number in URLs and database joins.
That implementation detail should appear only as subdued metadata.

It is acceptable to retain `/v2/b/[permit]` during the rebuild if changing the
route would create unnecessary migration risk.

---

## 5. V2 landing page: Projects

Rename `Buildings` to `Projects`.

Show one card per project, ordered by recently active first. Do not create
separate cards for page labeling, schedules, geometry, or annotation packets.

### 5.1 Project card

```text
┌──────────────────────────────────────────────────────────┐
│ 600 Baronne / 840 Lafayette Renovation                   │
│ New Orleans, Louisiana                                   │
│                                                          │
│ Current step: Floor-area review                          │
│ 35 proposed · 0 approved · 1 unresolved                  │
│                                                          │
│ [Continue review]                         24-06748-RNVS   │
└──────────────────────────────────────────────────────────┘
```

Show only progress that is honest and actionable.

Do not show:

- `13 locked / 36 rooms` for V1 outcomes;
- `Geometry path`;
- `Schedule path`;
- `Page-label pilot`;
- `training data pipeline`;
- model agreement as human completion.

### 5.2 Suggested card states

- Plan set needs confirmation
- Room roster needs review
- Floor-area proposals running
- Floor-area review ready
- Specialist decisions required
- Ready for quantity policy
- Estimate ready

Machine work and human approval counts must be shown separately.

---

## 6. Project navigation

The permanent product navigation is:

```text
Overview | Plan Set | Rooms & Finishes | Floor Areas | Estimate
```

Hide `Estimate` until it performs a real end-to-end quantity function. Do not
ship a decorative or fake-working tab.

### 6.1 Overview

Shows:

- editable project name;
- address and permit metadata;
- active plan-set revision;
- current stage and next action;
- progress across the real stages;
- unresolved and specialist-review counts;
- most recent activity.

Suggested stage display:

```text
1 Plan set      Confirmed
2 Room roster   36 rooms confirmed
3 Floor areas   18 ready · 12 need repair · 5 special/unresolved
4 Policy        Waiting for flooring decisions
5 Estimate      Not ready
```

### 6.2 Plan Set

Combines the useful parts of current `Pages` and `Documents`.

It should allow the user to:

- see every filed document;
- identify the active architectural plan set;
- see revision/date/source;
- inspect sheets in that plan set;
- confirm proposed floor-plan viewports;
- locate room schedules and finish plans;
- replace the active plan set without deleting history.

Page-category labeling remains useful internally, but the product should use
plain actions such as “Use as proposed floor plan” or “Use as room schedule.”

The current detailed page-label review board can move to an internal route.

### 6.3 Rooms & Finishes

Keep the core purpose:

- show the source room/finish schedule;
- show extracted room code, name, floor material, base, and reference area;
- link every extracted value back to its source row;
- let the user correct values;
- show missing, duplicate, or contradictory rows;
- establish the complete room/member roster for Floor Areas.

Do not call the printed schedule area an answer key. It is reference evidence
and a later diagnostic, not geometry truth.

### 6.4 Floor Areas

This replaces both `Outline Rooms` and `Geometry Review`.

It owns:

- Claude outline proposals;
- Codex/second-agent edge inspection;
- Claude repair proposals;
- deterministic validation;
- manual correction;
- human approval or unresolved decisions;
- room/open-zone membership;
- specialty surfaces and scope flags;
- measured square footage after geometry review.

### 6.5 Estimate

Eventually applies versioned estimating policy to approved observable geometry:

- materials;
- included/excluded scope;
- cabinet/fixture treatment;
- obstruction deductions;
- stair measurement;
- waste;
- rounding and order quantities;
- pricing.

This stage must not mutate the approved physical geometry.

---

## 7. Floor Areas workspace

### 7.1 Desktop layout

```text
┌──────────────────┬────────────────────────────────┬──────────────────────┐
│ Area queue       │ Plan canvas                    │ Review               │
│                  │                                │                      │
│ 102 RR1       ✓  │ [Room] [Full floor] [Edges]   │ Room 206 — Laundry   │
│ 103 Mop       ✓  │                                │                      │
│ 104 Entry     !  │     large high-resolution      │ AI inspection        │
│ 105 Stair     ⚠  │     plan + outline             │ Top: pass            │
│ 106 Elevator  ⚠  │                                │ Right: pass          │
│ 206 Laundry   →  │                                │ Bottom: pass         │
│                  │                                │ Left: needs repair   │
│                  │                                │                      │
│                  │                                │ [Repair with AI]     │
│                  │                                │ [Edit manually]      │
│                  │                                │ [Cannot determine]   │
└──────────────────┴────────────────────────────────┴──────────────────────┘
```

The plan canvas receives the most screen space. The current small/awkward
canvas and control-heavy sidebar should not be reused as the visual baseline.

### 7.2 Default view behavior

When a user opens a room:

1. fit the selected room to the available canvas;
2. show enough neighboring context to understand walls and openings;
3. show the latest reviewed proposal, not necessarily the first machine draft;
4. keep one-click toggles for full-floor and edge-close-up context;
5. preserve the current zoom/pan position when switching overlays.

### 7.3 Canvas interactions

Required:

- normal mouse-wheel/trackpad/pinch zoom;
- click-and-drag pan;
- double-click or button to fit selected room;
- one-click fit full floor;
- high-resolution image at useful zoom;
- toggle initial proposal, repaired proposal, and approved geometry;
- click an edge to open its close-up and evidence;
- drag an entire straight edge;
- drag/add/delete vertices where needed;
- visible threshold and non-wall edge types;
- undo/redo during an edit session;
- clear save/cancel behavior;
- keyboard accessibility for primary actions.

Avoid requiring the user to manipulate tiny individual points for every normal
wall adjustment.

### 7.4 Mobile/tablet behavior

Use the full screen for the plan. The queue and review panel become drawers or
bottom sheets. Pinch zoom and pan must behave naturally. Do not reproduce the
three-column layout at unreadable widths.

---

## 8. AI proposal and inspection loop

The user should not be asked to approve an unchecked one-shot proposal.

```text
Claude proposal v1
        -> independent Codex/vision edge inspection
        -> Claude repair of rejected edges
        -> deterministic geometry checks
        -> independent final visual inspection
        -> human review
```

### 8.1 Proposal pass

Claude receives:

- immutable source-plan reference;
- full proposed-floor viewport;
- selected room crop;
- room/member identity;
- visible neighboring identities;
- Geometry Label Book version;
- no schedule area during boundary selection.

Claude returns:

- V2 surface geometry;
- one record per edge;
- boundary type;
- source-evidence reference;
- uncertainty/reason;
- obstruction observations;
- proposal provenance.

### 8.2 Edge-inspection pass

The reviewer receives the original high-resolution source plus the rendered
proposal. Inspect every edge individually, preferably with generated edge
close-ups.

Each edge verdict is one of:

- correct;
- offset inward;
- offset outward;
- follows wrong line;
- unsupported boundary;
- clipped by crop;
- cannot determine.

The reviewer must name the visible evidence and suggested correction. A
room-level “looks good” statement without edge verdicts is insufficient.

Room 206 Laundry is a required regression example: the process must detect
that its left proposal edge runs through the exterior wall instead of the
floor-facing inside wall.

### 8.3 Repair pass

Claude receives:

- the source image;
- original proposal;
- edge-level critique;
- any deterministic snap candidates.

It must preserve passed edges and replace only failed geometry unless a
topology change is required. Save proposal v1, critique, repair v2, and all
later versions separately.

Allow at most two automatic repair cycles. If evidence remains insufficient,
route to `unresolved`; do not loop until agents agree.

### 8.4 Final inspection

Render the repaired outline again. Re-run edge inspection on the repaired
version. Agent agreement is supporting evidence, never a human decision.

---

## 9. Deterministic checks

Before human approval, run checks that do not require trade judgment:

- source document/revision and viewport identity are present;
- transform round-trips to the immutable PDF;
- geometry is closed, valid, and non-self-intersecting;
- holes and multipart pieces are represented explicitly;
- edge count matches ring segment count;
- every edge has type and evidence;
- no crop boundary is used as a wall without matching source evidence;
- room identity is linked by contained label or reviewed leader/tag evidence;
- no unexplained overlap with neighboring surface regions;
- no unexplained coverage gap;
- no duplicate individual polygons for one unsupported open-zone split;
- only true no-floor voids are holes;
- schedule area did not select or reshape the polygon;
- applicable precision checks pass against independently reviewed geometry.

These checks do not grant eligibility or approve the label.

---

## 10. Human review actions

Use plain language:

- **Approve shape**
- **Repair with AI**
- **Edit manually**
- **Cannot determine**
- **Specialist review required**

For an ordinary room, show the edge review before action:

```text
Room 206 — Laundry

AI inspection
✓ Top edge
✓ Right edge
✓ Bottom threshold
! Left edge runs through exterior wall

Suggested repair
Move the left edge to the room-facing wall line.
```

After geometry is approved, reveal the diagnostic:

```text
Measured approved geometry: 57.8 SF
Schedule reference: 59 SF
Difference: -2%

The schedule comparison did not approve or reshape this outline.
```

---

## 11. Status and color language

### 11.1 Overlay colors

- Pink/magenta: original Claude proposal
- Orange: AI-repaired proposal awaiting human review
- Red: rejected, unsupported, or unresolved edge
- Green: human-approved geometry only
- Neutral gray/blue: source/evidence aids

Never use green merely because measured SF is close to schedule SF.

### 11.2 Queue states

- Proposal running
- AI inspection running
- Repair prepared
- Ready for human review
- Needs manual correction
- Cannot determine
- Specialist review required
- Human approved
- Superseded

Keep `machine`, `human decision`, and `evidence eligibility` distinct in data
even if the product summarizes them more simply.

---

## 12. Special cases

The following never auto-pass during the pilot:

- stairs;
- elevators/shafts;
- decks/balconies/exterior surfaces;
- open zones with multiple room identities;
- missing or clipped boundaries;
- unsupported schedule-only splits;
- multipart regions or holes;
- contradictory plan revisions;
- unresolved phase/scope;
- large overlap/gap conflicts.

Examples from `24-06748-RNVS`:

- rooms 305/306/307 are one visible open surface until a defensible split is
  established;
- rooms 404/405 are one continuous deck surface absent a visible division;
- room 210 remains unresolved because no reliable anchor/boundary was found;
- stairs 105/201/301/401 are specialty surfaces, not ordinary room-SF truth;
- elevator geometry and flooring scope are different decisions.

---

## 13. Area-comparison rule

Schedule area is hidden during proposal, critique, and repair.

It appears only after the geometry review step as a diagnostic. It may trigger
additional inspection but cannot:

- choose between candidate masks;
- move an edge;
- create an open split;
- approve a room;
- mark an engine run verified;
- grant training/evaluation eligibility.

Primary geometry-quality measures are:

- edge pass/correction rate;
- manual vertices/edges moved;
- correction time;
- overlap and gap rate;
- unresolved rate;
- project-held-out performance.

---

## 14. What to preserve

Preserve and reuse where sound:

- project/building records;
- document inventory;
- PDF retrieval and page rendering;
- active-plan-set source records;
- extracted room schedules;
- room and finish references;
- Claude proposal artifacts;
- PDF/pixel transforms;
- append-only decision history;
- Geometry Label Book V2 schema and validator;
- existing V1 rows as provisional proposal history;
- internal diagnostic engine runs.

Do not silently convert existing V1 rows into V2 truth.

---

## 15. Routes and legacy interfaces

Current normal-product routes include:

- `/v2`
- `/v2/b/[permit]`
- `/v2/b/[permit]/rooms`
- `/v2/annotate/[permit]`
- `/v2/b/[permit]/geometry`
- `/v2/b/[permit]/docs`

Recommended approach:

1. Reuse `/v2` for the new Projects page.
2. Reuse `/v2/b/[permit]` for Overview.
3. Add or repurpose one project route for Plan Set.
4. Keep the rooms route for Rooms & Finishes.
5. Add a single Floor Areas route.
6. Remove old Outline/Geometry links from `V2Tabs`.
7. Move old annotation/geometry screens under an internal/legacy route or
   leave them directly accessible while migration is verified.
8. Redirect old normal links only after the new Floor Areas route works.

Do not delete legacy data as part of the navigation cleanup.

---

## 16. Build sequence

### Phase 1 — information architecture and honest project identity

- rebuild `/v2` as one Projects list;
- display project name/address first and permit second;
- remove duplicate pilot sections;
- remove misleading V1 `locked` language;
- rebuild project header and tabs;
- create Overview using real status data;
- hide internal page-label/geometry experiments from normal navigation.

### Phase 2 — Plan Set consolidation

- combine document inventory and relevant sheet review;
- clearly show active plan set/revision;
- expose proposed-plan and schedule source confirmation;
- retain full source links.

### Phase 3 — Floor Areas review shell

- build the new queue/canvas/review layout;
- load the existing 35 Claude proposals and room 210 unresolved state;
- implement fit-to-room, full-floor, edge view, pan, and zoom;
- show machine provenance honestly;
- do not claim edge inspection exists until real inspection data is present;
- preserve V1 rows as provisional history.

### Phase 4 — edge inspection and repair workflow

- define append-only proposal/critique/repair artifacts;
- generate edge close-ups;
- implement Codex/second-agent edge critique;
- implement Claude repair using critique;
- render before/after overlays;
- run deterministic checks;
- add the human actions and histories.

### Phase 5 — V2 geometry editing and decisions

- support multipart geometry and holes;
- support edge-level types/evidence;
- support open-zone memberships;
- support observed obstructions;
- support specialty surfaces;
- save complete V2 records;
- store human decisions and evidence eligibility separately;
- add project-level overlap/gap validation.

### Phase 6 — estimating policy and quantity

- obtain qualified flooring-estimator decisions for policy B1-B7;
- apply policy to approved geometry;
- introduce Estimate only when it works with real project data.

---

## 17. First implementation slice

The first faster Codex build should focus on Phase 1 plus the Floor Areas
visual shell. It should not attempt model training or the entire V2 editor in
one pass.

Required first-slice result:

1. `/v2` shows one card per project, address/name first.
2. Project header uses name/address and demotes permit number.
3. Navigation becomes Overview, Plan Set, Rooms & Finishes, Floor Areas.
4. Existing Geometry Review and Outline Rooms disappear from normal tabs.
5. Floor Areas opens with a room queue, a large useful canvas, and review
   panel using real existing proposal data.
6. Room 206 can be opened at a useful default zoom.
7. The original magenta proposal can be inspected edge by edge.
8. The interface labels all current data as machine/provisional.
9. No save action can describe V1 data as approved V2 truth.

The agentic critique/repair backend may follow in the next slice, but the UI
must reserve real states for it rather than hard-code fake reviews.

---

## 18. Acceptance criteria

### Projects page

- One card per project.
- Project name/address is the dominant text.
- Permit is secondary metadata.
- No duplicate geometry/schedule/page-pilot cards.
- No `locked` count derived from V1 provisional rows.
- A user can identify the project without knowing its permit number.

### Project navigation

- Normal navigation has no old Geometry Review tab.
- Normal navigation has no separate old Outline Rooms tab.
- Plan Set includes document/sheet source functions.
- Floor Areas is the single geometry-review destination.
- No unfinished Estimate tab appears functional.

### Floor Areas

- Selected room fills the useful canvas area by default.
- Pan/zoom works naturally with mouse and trackpad.
- Full-floor context is one action away.
- Edge close-ups are one action away.
- Proposal, repair, and human-approved states are visually distinct.
- Human approval cannot be inferred from SF difference.
- Schedule comparison is hidden until geometry review is complete.
- Crop-edge closures, unsupported splits, and special cases cannot auto-pass.
- Existing proposal/history data is preserved.

### Truth and safety

- V1 rows remain explicitly provisional.
- Machine proposals remain separate from final geometry.
- Human decisions are append-only.
- Eligibility remains a separate event.
- No old engine run is promoted because it matches schedule area.
- No project data is deleted during the UI migration.

---

## 19. Explicit non-goals

The rebuild does not authorize:

- starting RunPod training;
- treating Claude/Codex agreement as truth;
- deleting old diagnostic artifacts;
- rewriting schedule area as geometry truth;
- inventing estimating-policy answers;
- bulk-approving rooms from percentage agreement;
- shipping fake controls or placeholder product stages;
- expanding beyond project-first processing;
- polishing the old geometry editor instead of building the new workflow.

---

## 20. Related contracts

- `docs/pilot/GEOMETRY_LABEL_BOOK_V2_DRAFT.md`
- `docs/pilot/schema/geometry_annotation_v2.schema.json`
- `docs/pilot/GEOMETRY_REBOOT_V1.md`
- `docs/pilot/PROJECT_FIRST_EXECUTION_V1.md`
- `SCHEMA_V2.md`
- `STATE.md`

If this product brief conflicts with the Geometry Label Book V2 truth model,
the truth model controls data qualification. If the current application
conflicts with this product brief, this brief controls the rebuild direction.
