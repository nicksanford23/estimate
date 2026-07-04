"""Label rendered pages with Claude (the teacher model).

Every label is stored in data/labels/labels.jsonl — this file IS the training
set for the distilled classifier. Re-running skips already-labeled pages.

Usage:
    python -m estimate.label --manifest data/pages/manifest.jsonl
"""

import argparse
import base64
import json
import pathlib

import anthropic
from tqdm import tqdm

from estimate.taxonomy import CATEGORIES

MODEL = "claude-opus-4-8"

LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "confidence": {
            "type": "number",
            "description": "0-1 confidence in the category assignment",
        },
        "sheet_number": {
            "type": ["string", "null"],
            "description": "Sheet number from the title block, e.g. A-101, if legible",
        },
        "sheet_title": {"type": ["string", "null"]},
    },
    "required": ["category", "confidence", "sheet_number", "sheet_title"],
    "additionalProperties": False,
}

PROMPT = """You are classifying one page of a commercial construction plan set \
for a flooring estimating pipeline. Look at the drawing content and the title \
block. Classify the page into exactly one category:

- floor_plan: dimensioned architectural floor plan of building interior
- finish_plan: floor finish plan — flooring materials shown via hatches/tags/legend
- finish_schedule: room finish schedule table (room -> floor/base/wall finishes)
- demo_plan: demolition plan
- reflected_ceiling: reflected ceiling plan
- furniture_plan: furniture/equipment layout
- site_plan: site or civil drawing
- elevation_section: elevations or building/wall sections
- detail: detail sheets or enlarged assembly plans
- schedule_other: non-finish schedules (door, window, hardware, fixtures)
- structural: structural drawings (S-series)
- mep: mechanical, electrical, plumbing, fire protection
- cover_index: cover sheet, sheet index, general notes/symbols
- specs_notes: specification text or notes-only pages
- other: anything else

Report your true confidence — if the page is ambiguous or illegible, say so \
with a low confidence rather than guessing high."""


def label_page(client: anthropic.Anthropic, png_path: str) -> dict:
    data = base64.standard_b64encode(pathlib.Path(png_path).read_bytes()).decode()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": LABEL_SCHEMA},
        },
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=pathlib.Path, default=pathlib.Path("data/pages/manifest.jsonl"))
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/labels/labels.jsonl"))
    ap.add_argument("--limit", type=int, default=None, help="Max pages to label this run")
    args = ap.parse_args()

    with open(args.manifest) as f:
        pages = [json.loads(line) for line in f]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.out.exists():
        with open(args.out) as f:
            done = {json.loads(line)["page_id"] for line in f}

    todo = [p for p in pages if p["page_id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} pages to label ({len(done)} already done)")

    client = anthropic.Anthropic()
    with open(args.out, "a") as out:
        for page in tqdm(todo):
            try:
                result = label_page(client, page["png"])
            except anthropic.APIStatusError as e:
                print(f"skip {page['page_id']}: {e.status_code} {e.message}")
                continue
            result["page_id"] = page["page_id"]
            result["png"] = page["png"]
            result["labeler"] = MODEL
            out.write(json.dumps(result) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
