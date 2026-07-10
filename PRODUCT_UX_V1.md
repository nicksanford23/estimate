# Product UX v1 — the estimator's flow

*Proposal (2026-07-10, Fable). Mapping only — nothing here is built yet
except the static guide pages it evolves from. The design is grounded in
what the pipeline already produces: product actions (auto_quantity /
geometry_review / open_zone_split / redraw), per-room SF + materials,
confidence, and evidence. One UX law inherited from the pipeline: NEVER
show a confident number we can't defend — every figure traceable, every
doubt visible.*

## Who it's for, and the one number that matters

Commercial flooring estimators. Today: receive an invite-to-bid with a
100-300 page plan set, hunt for the flooring-relevant sheets, measure every
room by hand (Bluebeam/OST/paper), join materials from the finish schedule,
apply waste, produce quantities. Hours per bid; bids lost to slow turnaround.

North-star metric: **time-per-trusted-takeoff** (upload → numbers the
estimator will actually bid). Secondary: corrections-per-room (drives both
UX polish and the training flywheel).

## The flow — three screens

### 1. Upload & processing (sets expectations, earns trust early)
- Drag in the whole bid set (one PDF or many; no page-picking required —
  that's Model 1's job).
- Staged progress, in plain language, as the pipeline runs:
  "Kept 14 of 220 pages (3 floor plans, 1 finish schedule, 1 demo plan)" →
  "Scale found on all 3 plans" → "Measured 34 rooms; 6 need your eyes."
- The kept/discarded pages show as a filmstrip the user can expand; they
  can pull a page back in or toss one out. (Every such click is a Model-1
  training label — the flywheel starts on screen 1.)

### 2. Review screen — THE product
Split view. Left: the floor plan. Right: the takeoff.

**Left — plan canvas.** Room polygons colored by state:
- GREEN auto-quantity: confident, evidence attached. Default-accepted.
- YELLOW review: "check me" (geometry_review; suspicious size vs label,
  door-gap uncertainty, REVIEW_KILLED rescues).
- BLUE open zone: one space, multiple finish areas (open_zone_split) —
  needs a boundary drawn or confirmation it's one material.
- RED/GREY: redraw/unmeasured (fragment cases; missing plans).
Floor tabs across the top for multi-level sets.

**Right — living takeoff table.** Rooms grouped by material; SF totals
update live as rooms are confirmed/corrected. Two-line header: "Verified
X SF / Estimated Y SF" — the split IS the trust story.

**Interactions (keyboard-first; estimators do volume):**
- Click a room → evidence card: computed SF, the schedule row it matched,
  printed dimension cross-check when found, why flagged (in words).
- Enter = confirm; arrows = next flagged room (inbox-triage rhythm — the
  happy path through a clean building is: skim greens, hit Enter a few
  times, done).
- Drag a wall/vertex to fix a boundary; polygon re-closes and re-areas live.
- Draw-a-room for the redraw cases (assisted: edges snap to detected walls).
- Open zones: draw the finish boundary (follow-the-carpet-edge), or
  one-click "single material" to accept the blob whole.
- Material dropdown per room, pre-filled from the finish schedule; bulk
  reassign by selection.
- EVERY correction is captured as a training label on exactly the file
  type the model is weakest on. Corrections are the moat.

### 3. Output — the bid sheet
- Per-material summary: SF, waste-factor knob (user's trade rules, saved
  as defaults), base LF, totals.
- Per-room detail table (the guide-page table, matured).
- Auto-drafted assumptions & exclusions block: rooms excluded and why,
  areas estimated vs verified, missing-plan disclosures ("Buildings A/D/F
  priced from schedule only; no drawn plan filed"). Estimators live and
  die by qualification language — generating it honestly is a feature no
  competitor leads with.
- Export: PDF (print-ready), CSV (into their bid software), share link.

## Trust mechanics (the differentiator, product-wide)
1. No silent numbers: every SF traces to a page, a schedule row, or a
   drawn correction — one click shows the source.
2. Doubt is a first-class state: flagged rooms are the FIRST thing the
   review screen focuses, not buried.
3. The verified/estimated split is always visible on the total.
4. When we can't measure (missing plans, true scans pre-ML), we say so
   plainly and still deliver what the schedule alone supports —
   quantities-first workflow, never a fabricated plan.

## What gets built first (when we build — not yet)
1. **v0.5 — interactive guide page** (days, one agent): upgrade the
   existing /permits/[id]/guide pages from static images to an SVG overlay
   with clickable rooms, evidence cards, confirm buttons, and the live
   table — powered by takeoff.py run.json outputs. Use the bank,
   26-10321, and one TRUTH_AREA schedule permit as the three demo
   buildings (covers all room states).
2. **v1 review screen prototype** — the real canvas interactions (drag
   wall, draw room, split zone) on the same data. Fake the upload;
   clickable end-to-end.
3. **Customer-discovery demo** — put the prototype in front of 2-3
   estimators Nick knows. Watch where they hesitate. Their reactions
   reprioritize everything below this line.
4. Only after that: real upload path wiring the actual pipeline, then
   accounts/billing/scale — deliberately last, after the engine and the
   demo have proven the core loop.

## Open questions for Nick (trade knowledge, not tech)
1. First thing you check on a takeoff you didn't do yourself — total SF,
   flagged rooms, or material breakdown? (Decides the review screen's
   default focus.)
2. Waste factors: per material? per room shape? house rules per company?
3. Base/cove: always quoted with flooring, or separate line?
4. What would make you TRUST a number enough to bid it — seeing the
   dimension math, the schedule row, or the plan overlay?
5. Output format your bid software wants (CSV columns? Excel? specific
   template?).
