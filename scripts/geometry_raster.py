#!/usr/bin/env python3
"""Shared polygon <-> mask geometry helpers for the G2 room-segmenter harness.

Pure-stdlib + numpy + PIL only (all present in this Codespace; no torch/cv2).
Used by:
  * scripts/build_training_manifest.py  (area sanity, px<-pdf conversion)
  * scripts/train_room_segmenter.py     (polygon -> mask rasterization for GT)
  * offline tests                       (polygon -> mask -> area round-trip)

Coordinate convention: polygons are ordered [[x,y], ...] in CROP-IMAGE PIXELS
(origin top-left, x right, y down) unless a function name says _pdf.
"""
import numpy as np

try:
    from PIL import Image, ImageDraw
    _HAVE_PIL = True
except Exception:  # pragma: no cover - PIL is present here, but guard anyway
    _HAVE_PIL = False


def shoelace_area(polygon):
    """Signed-magnitude polygon area (px^2) by the shoelace formula.

    polygon: iterable of [x, y]. Returns a non-negative float. Handles an
    optionally-closed ring (first == last point) correctly.
    """
    pts = np.asarray(polygon, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[0] < 3:
        return 0.0
    # drop an explicit closing duplicate if present
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    x = pts[:, 0]
    y = pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def polygon_to_mask(polygon, width, height):
    """Rasterize a pixel-space polygon to a uint8 {0,1} mask of (height,width).

    Uses PIL's even-odd scan fill. Boundary-pixel inclusion makes the raster
    area differ from the exact shoelace area by an O(perimeter) term; for the
    room crops here (areas of 10^4-10^5 px^2) that is well under 2%.
    """
    if not _HAVE_PIL:
        raise RuntimeError("PIL not available; cannot rasterize polygon")
    pts = np.asarray(polygon, dtype=np.float64)
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    img = Image.new("L", (int(width), int(height)), 0)
    ImageDraw.Draw(img).polygon([(float(x), float(y)) for x, y in pts],
                                outline=1, fill=1)
    return np.asarray(img, dtype=np.uint8)


def apply_affine(polygon, affine):
    """Apply a forward_affine {'px_x':[a,b,c], 'px_y':[d,e,f]} to a polygon.

    Matches the bundle transforms.json contract:
        px_x = a*pdf_x + b*pdf_y + c
        px_y = d*pdf_x + e*pdf_y + f
    Used to convert human polygon_pdf outcomes into crop-pixel space.
    """
    ax, bx, cx = affine["px_x"]
    ay, by, cy = affine["px_y"]
    out = []
    for x, y in polygon:
        out.append([ax * x + bx * y + cx, ay * x + by * y + cy])
    return out


def mask_iou(a, b):
    """IoU of two {0,1} masks (numpy arrays, same shape)."""
    a = a.astype(bool)
    b = b.astype(bool)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter) / float(union) if union else 1.0


def boundary_f1(pred, gt, tol_px=2):
    """Boundary F1 between two {0,1} masks at a pixel tolerance.

    Boundary pixels = mask XOR its 1-px erosion. Precision/recall computed by
    dilating the opposing boundary by tol_px. scipy is used if present; a
    numpy-only 4-neighbour fallback keeps this importable everywhere.
    """
    def edges(m):
        m = m.astype(bool)
        e = np.zeros_like(m)
        e[:-1, :] |= m[:-1, :] ^ m[1:, :]
        e[1:, :] |= m[:-1, :] ^ m[1:, :]
        e[:, :-1] |= m[:, :-1] ^ m[:, 1:]
        e[:, 1:] |= m[:, :-1] ^ m[:, 1:]
        return e & m

    pe = edges(pred)
    ge = edges(gt)
    if pe.sum() == 0 and ge.sum() == 0:
        return 1.0
    if pe.sum() == 0 or ge.sum() == 0:
        return 0.0
    try:
        from scipy.ndimage import binary_dilation
        struct = np.ones((2 * tol_px + 1, 2 * tol_px + 1), dtype=bool)
        ge_d = binary_dilation(ge, structure=struct)
        pe_d = binary_dilation(pe, structure=struct)
    except Exception:
        ge_d, pe_d = ge, pe
    prec = (pe & ge_d).sum() / pe.sum()
    rec = (ge & pe_d).sum() / ge.sum()
    if prec + rec == 0:
        return 0.0
    return float(2 * prec * rec / (prec + rec))
