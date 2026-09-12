## Phase 2 — Image Prompt Generation

**Goal:** Automatically expand each of the 30 chapter beats from the Story
Bible into a full, detailed image-generation prompt, ready for Phase 3.

### Method
- Wrote `generate_image_prompts.py`, reading `story_bible.json` from Phase 1.
- Chapters are processed in **batches** (5 per API call) rather than one
  call per chapter, to fit within tight free-tier daily request quotas.
- Each batch prompt includes the full verbatim character descriptions
  (with scale anchors), art style, and setting, plus an explicit
  instruction not to invent new characters/props and to state the 9:16
  aspect ratio in every prompt.
- Script is resumable: progress saves after every batch, and a rerun skips
  already-completed days.

### Issues encountered
- `gemini-3.6-flash`'s free tier was limited to 20 requests/day on the
  account, which is incompatible with 30 individual per-chapter calls.
  Switching to batched requests (6 calls instead of 30 for a full story)
  resolved this.
- Also switched the model to `gemini-3.5-flash-lite`, a separate model
  with its own independent daily quota, isolating Phase 2 usage from
  Phase 1's quota.

### Results
- All 30 image prompts generated successfully in a single run, no failures.
- Automated validation confirmed: 30 sequential entries, every prompt
  explicitly states 9:16 aspect ratio, no empty/failed prompts.
- Manual review confirmed characters appear/don't appear correctly
  according to each chapter's actual beat (e.g. solo scenes before
  companions are introduced, full trio present for the climax) —
  indicating the model tracked story state correctly across batches, not
  just pattern-matching character mentions.

### Conclusion
Batching solved the free-tier quota constraint without any loss in output
quality — even a "lite" tier model produced correctly-scoped, detailed
prompts across all 30 chapters. Phase 2 is complete and ready to feed
Phase 3 (image generation).

### Learnings for later phases
- Minor text artifacts from Phase 1 (e.g. a duplicated word in `setting`)
  propagate forward into every downstream prompt that includes that field
  verbatim — worth a quick proofread of the story bible before generating
  images, since fixing it once in Phase 1's output is cheaper than
  fixing it 30 times downstream.
- Different Gemini models track separate daily quotas — using a different
  model per phase is a legitimate way to spread usage across independent
  free-tier budgets, not just a fallback for deprecations.