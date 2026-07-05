# Document Triage Agent Brief

Goal: decide which permit documents are worth downloading next for finish/floor-plan
label growth.

This is not a permanent delete/pass decision. `pass_now` means "do not spend
download/render/label budget on this in the current wave."

## Why We Are Doing This

Most permit document rows are not useful for the current training goal. We need
more diverse floor plans, finish plans, and finish schedules across many
permits. Downloading every PDF wastes time on receipts, certificates, letters,
trade sheets, civil/site/survey docs, structural-only docs, MEP-only docs, and
other files that do not help the current model.

Act like an estimator doing fast document-room triage before takeoff:

1. Open/download the likely architectural/interior/finish plan documents first.
2. Skip obvious admin and specialty documents for now.
3. Mark vague but promising files for review instead of pretending certainty.

## Decisions

Permit-level decision:

- `target_now`: this permit likely has useful floor-plan/finish-plan training data.
- `maybe_later`: plausible, but filenames/scope are too ambiguous for this wave.
- `pass_now`: unlikely to help the current finish/floor-plan dataset.

Document-level decision:

- `download_now`: strong evidence this PDF should be downloaded/rendered next.
- `maybe_download`: unclear; needs a human/second-agent check or should wait until
  after better docs in the same permit are reviewed.
- `pass_now`: do not download in the current wave.

## Download Now Signals

Prioritize filenames/scope like:

- Architectural set: `ARCH`, `Architectural`, `Architecture`, `A-###`, `A###`
- Interior design set: `Interior Design`, `Interiors`, `Interior Scope`,
  `ID-###`, `ID###`
- Finish-specific: `Finish Plan`, `Finishes`, `Finish Schedule`,
  `Room Finish`, `Material Schedule`, `Floor Finish`
- Floor/layout-specific: `Floor Plan`, `Overall Layout`, `Enlarged Layout`
- Full plan sets: `Permit Set`, `Construction Documents`, `CD Set`,
  `Issued for Permit`, `Approved Plans`, `Stamped Plans`

If a permit has both an architectural set and an interior-design/finish set,
select both. Cap the first wave to about 1-3 documents per permit unless the
filenames clearly represent split parts of the same architectural/interior set.

## Pass Now Signals

Usually pass:

- Admin: receipt, invoice, fee, application, permit certificate, certificate of
  occupancy, license, forms, contracts, letters, emails, plan-review comments
- Civil/site: civil, site plan, survey, stormwater, drainage, grading, ROW,
  landscape, tree, irrigation
- Structural: structural, foundation, framing, pile, shoring, slab, beam
- Trade-only: MEP, mechanical, electrical, plumbing, HVAC, sprinkler, fire
  alarm, fire protection, riser, COMcheck, lighting-only
- Exterior-only: roof/re-roof, gutters, exterior violation work, fence, sign,
  solar, window-only
- Photos/media/reports unless the filename also clearly says plan set

Exceptions are allowed, but explain them. For example, a combined
`ARCH MEP.pdf` may be worth downloading if it is the only architectural-looking
set in an interior renovation permit. A `foundation permit set` is usually not.

## Vague Filename Handling

For names like `Volume 6.pdf`, `Drawings.pdf`, `Stamped.pdf`, or
`Compiled Part 3.pdf`, use the permit scope and neighboring filenames.

- If other clearer architectural/interior docs exist, mark vague docs
  `maybe_download` or `pass_now`.
- If the vague file is the only plausible plan set for a strong interior/retail/
  restaurant/hotel/classroom/office renovation, mark `maybe_download`.
- If the vague file appears to be a trade/admin/specialty file, mark `pass_now`.

## Required Output

Return one JSON object per permit:

```json
{
  "permit_num": "25-12345-RNVS",
  "permit_decision": "target_now",
  "permit_reason": "Interior restaurant renovation; filenames include architectural and finish plans.",
  "documents": [
    {
      "doc_id": 123,
      "decision": "download_now",
      "reason": "Architectural set likely contains floor plans."
    }
  ],
  "confidence": "high"
}
```

Use `confidence` values: `high`, `medium`, `low`.

If you are unsure, do not overstate. Use `maybe_later`/`maybe_download` and
explain the uncertainty.
