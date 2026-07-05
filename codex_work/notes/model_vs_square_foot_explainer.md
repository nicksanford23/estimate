# Model Vs Square Foot Explainer

Date: 2026-07-05

## Short Answer

There is no problem with working on the model too.

The model and square-foot extraction are two different parts of the same project.

The model helps us find the useful pages.

The square-foot system tries to measure quantities from those useful pages.

## Model Track

The model track is about page/document understanding.

Examples:

- Is this page a floor plan?
- Is this page a finish schedule?
- Is this page a demo plan?
- Is this page admin junk that should be hidden?
- Is this permit worth labeling?

This matters because permit sets have a lot of junk:

- receipts
- applications
- review comments
- letters
- certificates
- trade-only pages
- random admin PDFs

The model helps sort the mess so an estimator, Claude, or another pipeline step only looks at useful pages.

## Square-Foot Track

The square-foot track is about measurement/takeoff.

Once we know a page is a floor plan, the next question is:

Can we measure area from it?

Examples:

- floor square footage
- wall square footage
- ceiling square footage
- room-by-room area
- demo area
- finish area

This is more geometry than normal labeling.

## Why Both Matter

A likely product flow is:

1. The model finds useful pages.
2. Floor plan pages go to square-foot extraction.
3. Finish schedules/spec pages tell us materials if they exist.
4. If materials do not exist, we still output quantities first.
5. The estimator applies materials, allowances, or assumptions later.

So the model is still important even if we care about square feet.

The model finds the floor plans.

The square-foot system measures them.

## What "SF Without Materials" Means

`SF` means square feet.

The findings said the product must support a "quantities-first workflow."

That means the system should still be useful even when the permit set does not include finish materials.

Example:

The permit may not say whether the floor is tile, LVT, carpet, or polished concrete.

But if we can calculate:

- 2,400 SF of floor area
- 1,800 SF of ceiling area
- 3,500 SF of wall area

Then the estimator can still price the job using allowances or their own assumptions.

So the system should not fail just because finish docs are missing.

## How Square Feet Is Calculated

At the basic level:

Area = width x length

Example:

- Room is 16 feet wide.
- Room is 20 feet long.
- Area is 16 x 20 = 320 SF.

On a PDF plan, the hard part is converting drawing size into real-world size.

Plans usually have a scale like:

- `1/8" = 1'-0"`
- `1/4" = 1'-0"`
- `3/16" = 1'-0"`

If the scale is `1/8" = 1'-0"`, then:

- 1/8 inch on the drawing equals 1 real foot.
- 1 inch on the drawing equals 8 real feet.
- 2 inches on the drawing equals 16 real feet.

So if a room measures 2 drawing inches by 2.5 drawing inches:

- 2 inches = 16 real feet
- 2.5 inches = 20 real feet
- 16 x 20 = 320 SF

Software does this with PDF coordinates instead of a ruler.

The general process is:

1. Read the plan page.
2. Find the drawing scale.
3. Detect walls or room boundaries.
4. Convert PDF distances into real feet.
5. Build room or floor polygons.
6. Calculate polygon area.
7. Output square feet.

## Why Vector PDFs Matter

Some PDFs contain real drawing lines.

These are called vector PDFs.

In a vector PDF, the software can read lines, rectangles, curves, and text objects from the file.

That is useful because walls and room boundaries may be directly available as geometry.

Other PDFs are just flat scans/images.

Those are harder because the software cannot directly read the wall lines. It has to use image/computer-vision methods instead.

The latest finding said 5 of 6 tested floor plan pages had real vector geometry.

That is good.

It means the square-foot route is worth testing more.

## What Is Not Solved Yet

Square-foot extraction is not solved yet.

The first probe only showed that the approach is viable.

Problems found:

### 1. Rotated Plans

Some plans are not perfectly horizontal/vertical on the page.

They may be rotated 8-10 degrees or even 45 degrees.

A simple wall detector looking only for horizontal and vertical lines can miss those walls.

Fix:

Detect the dominant drawing angle first, then measure walls relative to that angle.

### 2. Hatch Noise

Some drawings use hatch marks to show existing walls or materials.

Those hatch marks can look like many tiny wall lines.

The software may incorrectly think they are hundreds of walls.

Fix:

Detect repeating hatch patterns and suppress them.

### 3. Scanned Plans

Some PDFs are just images.

These are harder to measure from automatically.

They may require computer vision or manual calibration.

## My Recommendation

Keep the model/data pipeline as the main track.

Also run small square-foot probes in parallel on known-good floor plans.

Do not treat square-foot extraction as solved yet.

The model helps us find the right pages.

Then the square-foot system tries to measure those pages.

Both tracks support each other.

