# Primary Plan Labeling Addendum

This addendum is for the current primary-plan wave: 67 downloaded/rendered PDFs,
49 permits, and 1,864 rendered pages.

## Purpose Of This Wave

Label the primary architectural, interior, and finish plan documents first. These
are the documents most likely to contain useful floor plans, finish plans, and
finish schedules for the current training goal.

Do not treat this as final review of every document in each permit. After the
primary plan documents are labeled, the remaining documents in those same permits
can be revisited in a second pass for trade sheets, admin documents, alternates,
supplements, revisions, or unclear companion PDFs.

## Keep The Existing Taxonomy

Keep the current core page categories. Do not invent broad new page categories
for this wave.

Use the added fields below to capture primary-plan status, sheet titles, scale
quality, grouping, review state, and uncertainty. These fields should augment the
existing labels, not replace them.

## Fields To Add Or Check

Use these fields wherever the labeling format allows them:

- `primary_plan_doc`: `true` when the document is one of the primary
  architectural/interior/finish plan documents for the permit; `false` when it
  is clearly a secondary, trade-only, admin, or unrelated document.
- `sheet_title`: the visible sheet title or best concise transcription from the
  title block/header. Use the title shown on the page, not the filename, unless
  the page itself is missing a title.
- `scale_visible`: `true` when a scale note, graphic scale, or title-block scale
  is visible on the page; otherwise `false`.
- `usable_scale`: `true` only when the page has a usable plan scale for measuring
  or relating dimensions on the plan view. Use `false` for NTS-only pages,
  detail-only scales that do not apply to the floor/finish plan, illegible scales,
  or pages where the visible scale is clearly not tied to the main plan.
- `floor_finish_group_id`: stable grouping ID for pages that belong together,
  such as one floor plan and the matching finish plan/schedule for the same
  floor or area. Keep it simple and human-readable, for example
  `permit123-level01`, `permit123-suite200`, or `permit123-public-restrooms`.
- `applies_to_area`: the floor, suite, room group, building area, phase, or other
  scope shown on the page. Prefer the page's own wording when visible.
- `applies_to_floor`: the floor/level if explicit. Leave blank or `unknown` when
  the page does not identify one.
- `review_status`: use `reviewed`, `needs_second_pass`, or `blocked_unclear`.
- `confidence`: use `high`, `medium`, or `low` for the page-level judgment.
- `notes`: short reason or caveat. Record why something is uncertain, why a page
  was grouped, or what should be checked later.

## Category Edge Cases

Use the existing category labels, but apply these interpretations consistently:

- `finish_schedule`: a tabular or keyed schedule listing room finishes, material
  codes, floor/base/wall/ceiling finishes, product tags, or finish legends. It
  may not show a plan view. If it only defines finish codes but is needed to read
  a finish plan, group it with the related plan using `floor_finish_group_id`.
- `finish_plan`: a plan view that places finish tags, material zones, floor
  patterns, finish transitions, room finish references, or keyed finish areas on
  the drawing. A finish plan may include a small legend or schedule on the same
  sheet; still treat the page as a finish plan when the plan view is the main
  content.
- `floor_plan`: a plan view showing layout, rooms, walls, doors, fixtures,
  furniture, dimensions, or general architectural arrangement. If the same page
  has finish tags but the primary purpose is layout, keep the floor-plan category
  and note the finish content in `notes` or related fields if needed.

When a page reasonably fits more than one existing category, do not create a new
hybrid category. Use the strongest existing category and explain the secondary
content in `notes`.

## Scale Handling

Separate visible scale from usable scale:

- Mark `scale_visible=true` when any scale information is visible, including
  `NTS`, `Not To Scale`, a detail scale, a title-block scale, or a graphic scale.
- Mark `usable_scale=true` only when the scale can be applied to the main
  floor/finish/architectural plan on the page.
- Mark `usable_scale=false` when the only visible scale is `NTS`, when a scale
  belongs to an enlarged detail/elevation/section instead of the main plan, when
  the page is a schedule-only sheet, or when the scale is too blurry/cropped to
  rely on.
- If the title block says one scale but the plan view says another, use `notes`
  to record the conflict and set confidence accordingly.

Details, sections, elevations, and enlarged callouts can have valid scales, but
those are not usable plan scales unless the main labeled content for this wave is
itself that plan area.

## Duplicates, Stamps, And Revisions

Plan sets often include stamped, reviewed, corrected, or revised copies of the
same sheet.

- If two pages are visually the same sheet and one is a permit-stamped or
  approval-stamped copy, prefer the stamped/reviewed page as the primary labeled
  instance when it is readable.
- If a stamped copy is less readable than an unstamped copy, label the clearer
  page and note that a stamped duplicate exists.
- If two pages have the same sheet number/title but different revision dates,
  clouds, deltas, or changed content, treat the latest/revised page as primary
  when the revision date is clear. Note older duplicates as superseded or
  duplicate in `notes`.
- If pages are exact duplicates across separate PDFs in the same permit, mark
  only the clearest/current one as the primary source and use
  `review_status=needs_second_pass` plus `notes` on the duplicate if it may need
  later reconciliation.
- Do not discard information from a duplicate if it is the only readable copy of
  a title, scale, legend, or schedule. Record that reason in `notes`.

## Floor/Finish Pairing And Grouping

Use `floor_finish_group_id` to connect sheets that should be interpreted
together:

- Floor plan plus finish plan for the same floor, suite, wing, tenant area, or
  phase.
- Finish plan plus finish schedule or finish legend needed to decode its tags.
- Enlarged room/area plan plus the overall plan that locates that room/area.

Use the most specific stable area name visible on the sheets. If the relationship
is probable but not certain, still group them when useful, set `confidence` to
`medium` or `low`, and explain the uncertainty in `notes`.

## Review Status

Use review status to make later passes easy:

- `reviewed`: page was reviewed and the primary fields/category judgment are
  good enough for this wave.
- `needs_second_pass`: page is not the current priority, is a duplicate/revision
  question, references another document, or needs comparison with other PDFs in
  the same permit.
- `blocked_unclear`: page cannot be labeled reliably because it is unreadable,
  missing context, badly cropped, incorrectly rendered, or ambiguous even after
  checking nearby pages.

Keep `confidence` separate from `review_status`. A reviewed page can still have
`medium` confidence if the sheet is readable but the category boundary is fuzzy.

## Second-Pass Questions For Same-Permit Documents

Leave practical second-pass questions in `notes` instead of expanding the
taxonomy. Phrase them as checks another labeler can act on later.

Examples:

- `Second pass: compare with doc_id 123 stamped set; same A2.01 sheet may be newer.`
- `Second pass: finish tags reference schedule not found in this PDF. Check other same-permit docs.`
- `Second pass: trade sheet only, but may contain reflected ceiling finishes for lobby.`
- `Second pass: unclear whether Level 2 plan belongs to Phase 1 or Phase 2.`

For this wave, the priority is to get the primary plan documents labeled
consistently and to leave enough breadcrumbs for the later permit-level revisit.
