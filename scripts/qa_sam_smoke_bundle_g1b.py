#!/usr/bin/env python3
"""QA overlays for the G1b per-room crop bundle (local, no GPU/network).

For every OK task draws, over the crop image:
  * green filled dot  = the room anchor (positive prompt point)
  * orange rectangle  = the point_plus_box geometry box (transformed to crop px)
  * blue hollow dots  = negatives (other rooms' anchors that fell in the crop)
  * caption strip     = code, name, sheet, ppf, crop px size

Writes data/sam_smoke/24-06748-RNVS/qa_g1b/prompts_<code>.png. Purely a visual
check that each anchor sits on its room tag and the crop contains the room.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
SMOKE = os.path.join(ROOT, "data", "sam_smoke", PERMIT)
BUNDLE = os.path.join(SMOKE, "bundle_g1b")
QA_DIR = os.path.join(SMOKE, "qa_g1b")

GREEN = (0, 210, 0)
ORANGE = (255, 140, 0)
BLUE = (40, 120, 255)


def font(size=17):
    for c in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            pass
    return ImageFont.load_default()


def main():
    os.makedirs(QA_DIR, exist_ok=True)
    doc = json.load(open(os.path.join(BUNDLE, "tasks.json")))
    f = font()
    n = 0
    for t in doc["tasks"]:
        if t["status"] != "ok":
            continue
        img = Image.open(os.path.join(BUNDLE, t["image"])).convert("RGB")
        d = ImageDraw.Draw(img)
        pv = t["prompt_variants"]
        # orange box
        bx = pv["point_plus_box"]["box_px"]
        if bx:
            d.rectangle(bx, outline=ORANGE, width=3)
        # blue negatives
        for (nx, ny) in pv["point_plus_negatives"]["negative_points_px"]:
            d.ellipse([nx - 6, ny - 6, nx + 6, ny + 6], outline=BLUE, width=3)
        # green anchor
        ax, ay = t["anchor_px"]
        d.ellipse([ax - 7, ay - 7, ax + 7, ay + 7], fill=GREEN, outline=(0, 80, 0), width=2)

        tr = t["transform"]
        cap = [f"{t['code']}  {t['space_name']}  [{t['sheet_number']} p{t['page_index']}]",
               f"ppf={tr['px_per_foot']}  crop={tr['size'][0]}x{tr['size'][1]}px  "
               f"negs={len(pv['point_plus_negatives']['negative_points_px'])}  "
               f"prov={t['anchor_provenance']}"]
        out = Image.new("RGB", (img.width, img.height + 46), (18, 18, 18))
        out.paste(img, (0, 0))
        cd = ImageDraw.Draw(out)
        y = img.height + 4
        for line in cap:
            cd.text((6, y), line, fill=(238, 238, 238), font=f)
            y += 20
        out.save(os.path.join(QA_DIR, f"prompts_{t['code']}.png"))
        n += 1
    print(f"wrote {n} QA overlays -> {QA_DIR}", flush=True)


if __name__ == "__main__":
    main()
