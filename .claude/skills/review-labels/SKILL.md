---
name: review-labels
description: Blind second-opinion review of page labels — re-judge the image first, then compare with the first-pass label. Used by label-reviewer agents.
---

# Reviewing page labels (blind-then-compare)

You are the independent checker. The first labeler's answer is hidden from
you on purpose until step 2. Anchoring on it would make you worthless.

Per assigned page:
1. **Blind pass:** Read the page image and classify it yourself using the
   full label-pages skill (same 15 categories, same observation fields).
   Commit to your answer.
2. **Compare:** only now fetch the first-pass row (database is Neon Postgres
   via `./scripts/db.sh "SQL"` — never data/estimate.db):
   `./scripts/db.sh "SELECT category, confidence, sheet_title FROM page_label
    WHERE page_id=<id> AND source='claude-code' ORDER BY id DESC LIMIT 1"`
3. **Write your row** (append-only, source='claude-code-review') with YOUR
   judgment from step 1 — never switch to match the first pass. If you
   genuinely reconsider after comparing, that's allowed, but say why in
   `evidence` and cap confidence at 0.7.
4. Agreement = same category. Disagreements are expected and fine — the
   adjudicator settles them; your job is an honest independent opinion.

Same mechanics as label-pages (batches of 10, ≤80 pages/run, honest
confidence, site plans never keep=1). Report: pages reviewed, agree/disagree
counts, disagreement page_ids.
