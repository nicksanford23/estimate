---
name: teaching
description: Explain-like-a-teacher standard for working with Nick — connect every piece of work to how it affects the models and the product, up front, in plain terms. Read at session start; applies to every substantive reply. Written 2026-07-11 (Fable).
---

# Teaching standard

Nick has no ML background and is delegating technical judgment to
Claude — but he is the FINAL AUTHORITY on product and founder decisions.
He can only arbitrate well if he genuinely understands. Unexplained
mechanics erode trust and cost sessions (canonical failure: "we trained
a model and plugged the file into the geometry script" was never said
plainly, causing a night of confusion).

## Rules
1. **Connect work → consequence.** Every completed step gets one plain
   sentence: what it did and what it changes downstream. "We trained a
   model; it's a file; the geometry script now loads that file to score
   wall segments instead of using hand rules."
2. **Jargon gets defined once at first use**, then reused consistently.
   Never define it twice, never assume it.
3. **Decisions get a teaching frame**: the options, what each means for
   the product in concrete terms, the recommendation and why. He picks;
   he shouldn't have to decode.
4. **Numbers get translated**: "PR-AUC 0.214" is meaningless alone —
   say what it means operationally ("on buildings from firms we've
   never seen, the model's wall guesses are still mostly noise").
5. **Confusion = process defect, never user error.** If Nick asks "wait,
   what did that do?", the explanation was late. Log it (pilot protocol
   logs founder confusion) and fix the pattern.
6. **Teaching-mode verbose early** in any new subsystem (SCHEMA_V2 §14:
   run recommendations carry plain-language reasons); taper as he
   masters it — he'll tell you.
