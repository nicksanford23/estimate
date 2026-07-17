# Codex blind outline audit — 24-06748-RNVS

- Date: 2026-07-17
- Scope: current-best outline for each of the 35 supplied room codes
- Rules applied: `GEOMETRY_LABEL_BOOK_V2_DRAFT.md`, Layer A

## Method and result

I inspected every whole-room overlay and every polygon edge against the drawing, using enlarged edge strips where page-scale review was not conclusive. I did not use printed square footage or area agreement. Repaired proposals were used for 101, 104, 204, 206, and 208. This section was completed before opening the prior inspector's JSON or either prior narrative audit.

The result is **1 perfect and 34 wrong**. This is not a claim that 34 rooms are unusable for every downstream purpose. It means those 34 current polygons do not meet the label-book boundary standard closely enough to be accepted as reviewed geometry.

## Per-room verdicts

| Code | Verdict | Edge-level findings and required correction |
|---|---|---|
| 100 | perfect | Edges 0, 2, and 3 follow the visible room-facing/storefront boundary; edge 1 is a defensible straight threshold between jambs. No correction observed. |
| 101 | wrong | Edge 1 floats vertically through the white-box floor instead of following the restroom/room boundary. Edge 4 is also detached from the visible storefront boundary. Redraw the actual bounded 101 floor region; do not preserve the unsupported notch merely to close a polygon. |
| 102 | wrong | Edges 0 and 2 run within the thick wall bands rather than on the room-facing wall faces. Move both to the white-floor/finished-wall interfaces; retain edges 1 and 3 only after endpoint snapping at the corrected corners. |
| 103 | wrong | Edge 2 is materially inset from the bottom room-facing wall face. Move edge 2 to that face and re-intersect edges 1 and 3 with it. |
| 104 | wrong | Repaired edges 1 and 2 cross open floor with no visible physical or threshold boundary; edge 3 also does not establish a defensible closing boundary. Reconstruct the actual circulation/open-zone geometry or mark it unresolved instead of forcing this rectangle. |
| 105 | wrong | Edges 0–3 enclose a broad elevator/stair/general area, not the observable stair surface footprint; the left/internal closures are unsupported. Trace the actual stair specialty surface and label it as such. |
| 106 | wrong | Edges 0–3 lie predominantly within the elevator wall bands instead of on the cab/floor-facing interior faces and doorway threshold. Move wall edges to the white-floor interfaces and make the opening edge a jamb-to-jamb threshold. |
| 107 | wrong | Edges 0, 1, and 2 are visibly inset or located within wall construction rather than on the room-facing perimeter. Refit those edges to the finished faces and recompute the corners; verify edge 3 after that refit. |
| 201 | wrong | Edges 0, 1, and 2 cut across open/interior floor and do not describe the stair footprint; edge 3 does not rescue the unsupported closure. Replace the rectangle with the observable stair specialty-surface footprint. |
| 202 | wrong | Edges 0–3 are drawn in the surrounding wall mass rather than consistently on the elevator floor-facing faces/door threshold. Refit all four sides using the interior face convention. |
| 203 | wrong | Edges 0 and 1 are unsupported diagonals across open circulation; edge 2 is an invented vertical split through open floor; edge 4 is detached from the left room-facing wall. Redraw from physical walls and jamb-to-jamb thresholds, or represent the open circulation boundary as unresolved. |
| 204 | wrong | Repaired edge 0 crosses multiple wall/opening conditions without threshold vertices. Edges 2 and 4 are materially inset from the sloped room-facing wall; edge 3 needs a jamb-to-jamb threshold check. Move the sloped edges to the finished face and segment every door opening at its jambs. |
| 205 | wrong | Edge 0 invents a horizontal split across open floor; edge 1 sits outside the sloped room-facing boundary; edge 2 is horizontal although the visible lower wall is sloped. Redraw the observable closet/alcove boundary or mark the individual-room split unresolved. |
| 206 | wrong | Repaired edge 0 is substantially below the top room-facing wall, and edge 1 floats well left of the right boundary. Refit those sides to the finished faces and recheck edges 2 and 3 after corner reconstruction. This is visibly not flush even though a whole-room view can look plausible. |
| 207 | wrong | Edge 1 is materially left of the right wall face; edge 2 lies below/in the bottom wall; edge 3 uses the wrong side of the left divider. Move each to the room-facing surface and rebuild the vertices. |
| 208 | wrong | Repaired edge 1 is materially inset from the right exterior boundary, while edge 2 follows the far/outside side of the bottom wall/window assembly rather than the deck/room-facing physical edge. Correct those two faces and re-intersect edges 0 and 3. |
| 209 | wrong | Edge 1 is vertical and detached from the visible sloped right wall; edge 2 runs through wall construction rather than the room-facing face. Follow the wall angle and move the bottom edge to the finished interface. |
| 209A | wrong | Edge 1 is an unsupported vertical closure in open space instead of the visible sloped boundary. Edge 3 follows a wall center/far line; edges 0 and 2 also need wall-versus-threshold segmentation. Rebuild the polygon from the sloped face and actual jambs. |
| 211 | wrong | Edge 1 remains vertical while the adjacent wall is sloped; edge 2 sits inside the bottom wall band; edge 3 floats within the room instead of following a wall or threshold. Redraw those three sides from visible evidence. |
| 212 | wrong | Edge 1 ignores the sloped wall; edge 2 invents a horizontal split across the open closet/circulation area; edge 3 follows an exterior wall center/far line. Trace the room-facing/exterior faces and leave the open split unresolved unless another sheet supports it. |
| 301 | wrong | Edges 0–3 form a broad rectangular closure rather than the stair surface. In particular, edge 2 cuts straight through room 304 and ignores its curved wall. Replace the polygon with the observable stair specialty-surface footprint. |
| 302 | wrong | Edge 0 is deeply inset from the top elevator face; edges 1 and 3 are also inside the cab/floor rather than consistently on its finished boundary, and edge 2 does not establish a correct doorway threshold. Refit all sides to interior faces and jambs. |
| 303 | wrong | Edges 0–3 float in open corridor/floor area without a supporting wall, finish break, or jamb-to-jamb closure. Do not accept the rectangle; derive a supported circulation zone or record an unresolved boundary. |
| 304 | wrong | Founder concern confirmed. Edge 0 lies in wall mass; curved edges 1 and 2 run within the curved wall band rather than along its inner floor-facing curve; edges 3 and 4 cut diagonally across the room/toilet area with no boundary; edge 5 uses an exterior wall line; edge 6 is not consistently on the correct face. This needs a full redraw following the inner curved wall and true doorway/adjacent-room boundaries, not a local nudge. |
| 305 | wrong | Edges 0–3 assign a separate polygon to part of the continuous kitchen/dining/living floor with no visible physical or finish boundary supporting the split. Remove the duplicate room polygon and use one open surface with 305/306/307 identity memberships. |
| 306 | wrong | Edges 0–3 repeat the same unsupported individual-room treatment in the continuous open plan. Merge the surface with 305 and 307 while preserving 306 as an identity membership, unless independent finish-boundary evidence exists. |
| 307 | wrong | Edges 0–3 close another overlapping/open-plan room without an observable split. Use the shared 305/306/307 open-zone geometry and keep 307 as membership metadata. |
| 308 | wrong | Edge 0 is in the top wall band; edge 1 floats at the closet/opening; edge 2 is detached from the partition; edge 3 is far left of the bath wall; edge 4 is not a jamb-aligned threshold; edge 5 follows a wall center/far line. Rebuild all sides using finished faces and explicit doorway vertices. |
| 308A | wrong | Edge 1 follows the far side of the right exterior wall instead of the room-facing/exterior deck edge; edge 2 lies within the bottom wall; edge 3 extends through the open doorway/room rather than stopping at a jamb-to-jamb threshold. Correct those edges; retain edge 0 only after new endpoint intersections. |
| 309 | wrong | Edge 0 runs through the top wall band; edge 1 follows the far exterior face; edge 2 stays horizontal and cuts across the floor instead of following the sloped bottom wall; edge 3 is outside the left room-facing wall. Redraw all four sides from the visible finished/exterior faces. |
| 401 | wrong | Edges 0–3 create a room-like rectangle around/through the stair rather than tracing its actual specialty-surface footprint. Edge 2 also spans mixed wall and cased-opening conditions. Trace the stair surface and segment any threshold at its jambs. |
| 402 | wrong | Edges 0, 1, and 3 are materially inset into the elevator floor; edge 2 crosses the doorway above the actual jamb-to-jamb threshold. Move wall sides to the interior faces and place the opening edge between jambs. |
| 403 | wrong | Edge 0 combines a cased opening and wall without vertices; edge 1 follows the far exterior side; edge 2 crosses the millwork/edge condition without a defensible room-facing boundary; edge 3 cuts through the open doorway/floor. Reconstruct the kitchen floor boundary with explicit obstruction and threshold handling. |
| 404 | wrong | Edge 2 is an invented horizontal division across a visibly continuous deck, and edges 0, 1, and 3 use inconsistent exterior/guard lines. Remove the separate 404 surface and make 404/405 memberships of one continuous deck surface unless another source proves a physical finish split. |
| 405 | wrong | Edge 0 duplicates the unsupported 404/405 split; edges 1–3 need one consistent deck physical-edge convention. Merge with 404 as one deck surface, and separately record/verify the central deck-mounted skylight or no-floor footprint as an obstruction/hole rather than silently flooring through it. |

## Systemic holes

### 1. The wall-face convention is not actually enforced

The dominant failure is not room recognition. It is boundary placement. Many red edges sit on wall centerlines, within thick wall bands, on far/exterior faces, or noticeably inside the floor. This affects ordinary rooms, elevators, sloped walls, curved walls, and exterior/deck conditions. A polygon should not enter reviewed state until each edge has an explicit boundary type and passes a scaled distance check against the selected room-facing physical edge.

### 2. Whole-room review produces false confidence

Several outlines look persuasive when reduced to a whole crop but fail immediately in enlarged edge strips. Room 206 is the clearest example: a broadly plausible pink box still has a top and right side visibly detached from their boundaries. The workflow needs a mandatory edge-by-edge second review; page-scale appearance and area proximity are not acceptance evidence.

### 3. Door openings are being absorbed into long unsplit edges

Long edges repeatedly cross walls, cased openings, and doors without vertices at the jambs. A boundary segment must change type at each opening: wall-face segment, then a straight jamb-to-jamb threshold, then wall-face segment. The editor and saved geometry should retain those types and the supporting image evidence.

### 4. Open zones are being forced into unsupported individual rooms

The 305/306/307 open plan and 404/405 deck demonstrate a project-level modeling error: schedule identities are being converted into separate surfaces even when the drawing shows one continuous surface. This creates overlap, double counting, and invented splits. The data model needs one physical surface with multiple identity memberships and an explicit unresolved state when a split cannot be observed.

### 5. Stairs are treated as conventional rooms

Rooms 105, 201, 301, and 401 are closed with broad rectangular room polygons rather than traced as specialty surfaces. Stair recognition and stair surface geometry need a separate proposal/review path; a room rectangle is not an acceptable fallback.

### 6. Curves and slopes are being regularized away

The method frequently substitutes horizontal or vertical edges for visible sloped or curved walls (204, 205, 208, 209, 209A, 211, 212, 304, and 309). Geometry generation must preserve polyline/curve evidence at source resolution and should never snap to orthogonal simply because a rectangle is easier to produce.

### 7. Per-room crops hide topology

A crop often hides the adjacent room, the full doorway, the continuation of an open zone, or whether a candidate line is only the crop border. Review packets should include: the whole floor with all current surfaces, the local room crop, every enlarged edge strip, and neighboring-room polygons. Crop borders must be marked visually and prohibited as boundary evidence.

### 8. There is no decisive project-level topology gate

The duplicate open-zone/deck surfaces should have been caught without vision review. Before acceptance, run deterministic checks for overlap, gaps between expected adjacent floor surfaces, self-intersection, duplicate/near-duplicate polygons, shared-edge disagreement, and unmapped schedule memberships. A room can be locally plausible and still be globally impossible.

### 9. Obstructions and no-floor holes lack an explicit evidence pass

The deck skylight condition shows the risk of using only an outer shell. The reviewer needs a separate obstruction/hole layer with `observed`, `uncertain`, or `not present` evidence status. Policy about whether flooring goes beneath an item comes later; geometry review should not silently infer it.

### 10. Repair is still a one-shot relocation of error

All five repaired proposals (101, 104, 204, 206, and 208) still fail Layer A. A repair result cannot inherit trust from the fact that it was repaired. The required loop is: initial trace, independent edge criticism, targeted redraw, then a fresh independent edge check with overlap/gap validation. If the evidence remains ambiguous, save `needs_founder`/structured unresolved rather than manufacturing closure.

## Blind verdict lock

The per-room verdicts and systemic findings above are the locked independent audit. The prior inspector comparison below was intentionally left unwritten until after this lock.

## Comparison with prior edge inspector

Comparison source opened only after the blind verdict lock: `data/sam_smoke/24-06748-RNVS/inspection/edge_inspection.json`. For repaired rooms, I compared against its after-repair verdict. Its `pass` maps to this audit's `perfect`; its `unresolved` is kept distinct from `wrong`.

| Rooms | Prior inspector | Codex | Agreement | Why the result differs |
|---|---|---|---|---|
| 100 | pass | perfect | agree | Both inspections found all four edges supported by the visible physical boundary/threshold. |
| 101, 102, 103, 106, 107, 202, 206, 207, 208, 209, 209A, 211, 212, 302, 308, 308A, 309, 402 | pass | wrong | disagree | Enlarged strips show one or more edges materially inset, inside wall mass, on the far face, or detached from a sloped wall. The prior pass appears to rely too heavily on whole-room plausibility or an inconsistent wall-face convention. |
| 104, 205, 303 | pass | wrong | disagree | These polygons contain closures through open floor without a physical edge, finish break, or jamb-supported threshold. Closing cleanly as a rectangle does not make the boundary observable. |
| 105, 201, 301, 401 | pass | wrong | disagree | The current outlines are broad room/enclosure rectangles, not defensible traces of the actual stair specialty surfaces required by A6. |
| 204, 304 | pass | wrong | disagree | The current edges regularize or cut across visible sloped/curved walls. Room 304 is a major disagreement: multiple edges run through wall bands or across the toilet room rather than following its inner curved face. |
| 403 | pass | wrong | disagree | Its four long edges combine wall, cased-opening, exterior, millwork, and open-floor conditions without the required boundary-type changes and threshold vertices. |
| 404, 405 | pass | wrong | disagree | The drawing shows one continuous deck, while the two polygons preserve an unsupported internal split and overlapping identity/surface treatment; the obstruction/hole condition is also not represented. |
| 203 | unresolved | wrong | disagree on category; agree it must not pass | The prior inspector found one unsupported edge but left the room unresolved. The enlarged review shows several unsupported open-floor closures, so the current polygon itself is decisively wrong even if the correct replacement still needs broader context. |
| 305, 306, 307 | unresolved | wrong | disagree on category; agree they must not pass | Cropping may make the prior reviewer uncertain, but the project-level relationship is enough to reject the three separate polygons: they model one continuous open surface as independent overlapping rooms. The replacement should be one surface with three identity memberships. |

The unusually large disagreement is itself actionable evidence. It indicates that the current inspection method can mark an edge `correct` without proving which side of the wall is room-facing, and can mark a room `pass` without checking cross-room topology or whether a stair/open-zone polygon represents the correct kind of surface.
