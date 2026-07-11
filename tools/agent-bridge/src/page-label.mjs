import { z } from "zod";

export const PAGE_LABEL_RUBRIC_VERSION = "pilot-page-label-v1";

export const PAGE_CATEGORIES = Object.freeze([
  "floor_plan",
  "finish_plan",
  "finish_schedule",
  "demo_plan",
  "reflected_ceiling",
  "furniture_plan",
  "site_plan",
  "elevation_section",
  "detail",
  "schedule_other",
  "structural",
  "mep",
  "life_safety",
  "cover_index",
  "specs_notes",
  "other",
]);

export const PAGE_FLAGS = Object.freeze([
  "multiple_viewports",
  "contains_area_table",
  "scale_visible",
  "finish_codes_visible",
  "table_present",
  "room_labels_visible",
  "dimensions_visible",
  "possible_duplicate",
]);

export const PAGE_LABEL_JSON_SCHEMA = Object.freeze({
  type: "object",
  additionalProperties: false,
  properties: {
    category: { type: "string", enum: PAGE_CATEGORIES },
    flags: {
      type: "array",
      items: { type: "string", enum: PAGE_FLAGS },
      uniqueItems: true,
    },
    sheet_number: { type: "string" },
    sheet_title: { type: "string" },
    confidence: { type: "number", minimum: 0, maximum: 1 },
    evidence: { type: "string", minLength: 1 },
    uncertainty: { type: "string" },
    image_inspected: { type: "boolean", const: true },
  },
  required: [
    "category",
    "flags",
    "sheet_number",
    "sheet_title",
    "confidence",
    "evidence",
    "uncertainty",
    "image_inspected",
  ],
});

export const PageLabelSchema = z
  .object({
    category: z.enum(PAGE_CATEGORIES),
    flags: z.array(z.enum(PAGE_FLAGS)),
    sheet_number: z.string(),
    sheet_title: z.string(),
    confidence: z.number().min(0).max(1),
    evidence: z.string().min(1),
    uncertainty: z.string(),
    image_inspected: z.literal(true),
  })
  .strict()
  .transform((label) => ({
    ...label,
    flags: [...new Set(label.flags)].sort(),
  }));

const CATEGORY_GUIDE = {
  floor_plan: "dimensioned architectural interior plan; rooms, walls, and doors are the subject",
  finish_plan: "floor or finish materials, finish tags, or finish hatches are the subject",
  finish_schedule: "room-finish table mapping rooms to floor, base, or wall materials",
  demo_plan: "demolition plan showing existing work or removals",
  reflected_ceiling: "ceiling grid, lighting, or reflected ceiling plan",
  furniture_plan: "furniture or equipment layout is the subject",
  site_plan: "exterior site, parking, landscape, or property layout",
  elevation_section: "building elevation, interior elevation, or section",
  detail: "enlarged construction detail, assembly, or callout",
  schedule_other: "non-finish schedule such as doors, windows, or hardware",
  structural: "foundation, framing, structural, or reinforcement drawing",
  mep: "mechanical, electrical, plumbing, fire, technology, or other engineering drawing",
  life_safety: "egress, occupant load, code, or life-safety plan",
  cover_index: "cover sheet, drawing index, or general project-information sheet",
  specs_notes: "dense specifications, notes, legends, abbreviations, or code text",
  other: "none of the categories above, illegible, photo, form, or map",
};

export function buildPageLabelPrompt(imageFilename) {
  const categories = PAGE_CATEGORIES.map(
    (category) => `- ${category}: ${CATEGORY_GUIDE[category]}`,
  ).join("\n");
  const flags = PAGE_FLAGS.map((flag) => `- ${flag}`).join("\n");

  return `You are independently labeling one rendered construction-plan page for a flooring estimator.

You MUST inspect the actual image file named ${imageFilename}. Do not classify from a filename, extracted text file, prior label, database row, or another worker's output. Set image_inspected=true only after successfully viewing the image. If the image cannot be viewed, do not guess; fail the task instead.

Choose exactly one primary category:
${categories}

Choose every visibly supported independent flag, and no others:
${flags}

Rules:
- Drawing content decides; a title block is only supporting evidence.
- For a mixed page, choose the dominant drawing type, except visible flooring or finish content should not be hidden by a generic floor-plan category.
- Flags are independent visible claims; category agreement never implies flag agreement.
- Use empty strings when sheet number or title is unreadable.
- Evidence must name visible image content supporting the category.
- Uncertainty must name any ambiguity, illegibility, mixed content, or failed flag check; otherwise it may be an empty string.
- Return only the required structured object.`;
}

export function comparePageLabels(claudeLabel, codexLabel) {
  const claims = [
    {
      claim: "page_category",
      key: "category",
      claude: claudeLabel.category,
      codex: codexLabel.category,
      agrees: claudeLabel.category === codexLabel.category,
    },
    ...PAGE_FLAGS.map((flag) => {
      const claude = claudeLabel.flags.includes(flag);
      const codex = codexLabel.flags.includes(flag);
      return {
        claim: "page_flag",
        key: flag,
        claude,
        codex,
        agrees: claude === codex,
      };
    }),
  ];
  const disagreements = claims.filter((claim) => !claim.agrees);

  return {
    state: disagreements.length === 0 ? "machine_cross_verified" : "machine_disagreement",
    all_claims_agree: disagreements.length === 0,
    human_truth: false,
    requires_human_review: disagreements.length > 0,
    claims,
    disagreement_keys: disagreements.map((claim) => claim.key),
  };
}
