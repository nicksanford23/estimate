# Probe 8 — Layers as FREE multi-class training data

**Date:** 2026-07-08
**Scripts:** `scripts/probe8_layer_classes.py` (ontology), `probe8_visual.py`
(the side-by-side artifact), `probe8_coverage.py` (rich-signal coverage).
**Follows:** Probe 7 (layer walls) + the coverage reality check (~16% keep layers).

## Idea
A layered CAD PDF pre-sorts every line by what it is. Map each layer NAME to an
estimator-relevant class (wall / door / fixture / furniture / structure / finish
/ annotation). Then: render the FLATTENED page (all black — what the 82% of files
that lost their layers look like) as the INPUT, and the per-line class as the
TARGET. That's a fully-labeled training example generated with zero human effort.

## The artifact — `data/probe8/semantic_labels.jpg`
Left = flattened plan (all black). Right = same lines auto-colored by class.
Walls (red) cleanly trace every room boundary INCLUDING the service core that
broke the rules pipeline; furniture/equipment (gray) = the clutter that split
those rooms; doors blue; plumbing teal; text/tags faded gray.

14-11290 branch plan, per-class element counts:
annotation 116,097 · furniture 6,507 · wall 4,964 · door 1,457 · structure 1,229
· fixture 920 · finish 826.

**Key point:** the clutter that beat the rules pipeline is trivially separable
from walls once you have the layers — so the layered files can TEACH that
separation to a model that works on the flattened files.

## Rich-signal coverage (of the ~8 layered projects among 51 labeled permits)
| class | coverage | note |
|---|---|---|
| doors | 7/8 | nearly universal |
| finish (floor material) | 4/8 | substantial where present (10k–16k elems) — a free per-room MATERIAL mask for those firms |
| furniture (clutter) | 5/8 | separable in most |
| fixtures | 5/8 | restroom wet-areas |
| structure/grid | 1/8 | rare |

Caveats: `13-44083`/`13-44130` are a byte-identical duplicate prototype plan;
`26-11301` (walls=19), `24-22310` (150), `19-00670` (386) barely trip the wall
filter. So the genuinely-layered set is ~5 distinct projects, not 8.

## Conclusion
The free training data is MULTI-CLASS (not just walls) for most layered files —
exactly what teaches wall-vs-clutter separation. The finish-mask (material)
signal is real but firm-dependent (some hatch floors, some only tag them).

**Binding constraint is now sample size, not signal richness.** ~5 solid layered
projects proves the pipeline, not a generalizing model. Next: widen the scan from
the 51 labeled floor plans to all 2,329 downloaded PDFs — most layered files we
own were never labeled — to learn whether the free-data well is 5 deep or 50.
