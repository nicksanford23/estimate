"""Sheet classification taxonomy for commercial plan sets.

Categories are chosen around what a flooring estimator needs: the sheets that
feed the takeoff (floor plans, finish plans, finish schedules) get their own
classes; everything else is bucketed coarsely.
"""

CATEGORIES = [
    "floor_plan",          # dimensioned architectural floor plan
    "finish_plan",         # floor finish plan (hatches/tags showing flooring)
    "finish_schedule",     # room finish schedule table
    "demo_plan",           # demolition plan
    "reflected_ceiling",   # RCP
    "furniture_plan",      # furniture/equipment layout
    "site_plan",           # site/civil
    "elevation_section",   # elevations, building/wall sections
    "detail",              # detail sheets, enlarged plans of assemblies
    "schedule_other",      # door/window/hardware/other schedules
    "structural",          # S-series
    "mep",                 # mechanical / electrical / plumbing / fire
    "cover_index",         # cover sheet, sheet index, general notes
    "specs_notes",         # specification or notes-only pages
    "other",
]

# Sheets that feed the takeoff pipeline directly.
TAKEOFF_RELEVANT = {"floor_plan", "finish_plan", "finish_schedule", "demo_plan"}

# Claude labels at or above this confidence are used as training data;
# anything below is queued for human review.
TRAIN_CONFIDENCE_THRESHOLD = 0.8
