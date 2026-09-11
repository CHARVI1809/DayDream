## Phase 1 — Automated Story Bible Generation

**Goal:** Build a repeatable script that generates a Story Bible (title,
characters, setting, world rules, ending, art style) plus a 30-chapter
outline via the Gemini API, replacing the manual Phase 0 process.

### Method
- Wrote `generate_story_bible.py`, taking `--genre` and `--mood` as CLI args.
- Prompt template incorporates the two fixes learned in Phase 0: explicit
  scale/size anchors in character descriptions, and an explicit vertical
  9:16 art style instruction.
- Script validates output automatically: checks all required Story Bible
  fields are present, checks exactly 30 chapters were generated, checks
  day numbers are sequential.
- Output saved as `output/story_bible.json` for Phase 2 to consume.

### Issues encountered
- Initial implementation used the `google-generativeai` package and
  `gemini-2.5-pro` — both were deprecated/unavailable to new API users at
  time of testing.
- Migrated to the new `google-genai` SDK (`genai.Client()` pattern instead
  of `genai.configure()` + `GenerativeModel()`).
- Switched model to `gemini-2.5-flash`, which was also unavailable to new
  users by the time of testing.
- Settled on `gemini-3.6-flash`, which worked successfully. The Gemini
  model lineup is moving quickly; the model name is isolated to a single
  constant in the script for easy future swaps.

### Results
- Successfully generated a complete, valid Fantasy story bible ("The
  Sunstone Cartographer") with a 3-character cast, full 30-chapter outline,
  and all automated validation checks passing:
  - 30 chapters, numbered sequentially 1–30
  - Every character description includes an explicit scale anchor
  - `art_style` explicitly specifies vertical 9:16 composition
- Chapter outline has genuine narrative structure (setup, companion-bonding,
  rising obstacles, climax, resolution) rather than repetitive beats.

### Conclusion
The automated Phase 1 script reliably reproduces (and validates) the
quality achieved manually in Phase 0. The core AI generation pipeline for
story structure is working end-to-end. Google's frequent model deprecations
are a real, recurring operational risk for this project and should be
expected to recur — not treated as a one-off issue.

### Learnings for later phases
- Isolate model names behind a single constant/config value in every script
  that calls the Gemini API — deprecations are frequent enough that this
  needs to be a one-line fix, not a rewrite, each time.
- Minor text artifacts (e.g. a duplicated word in `setting`) can appear in
  model output — harmless for internal use (image prompt generation), but
  worth a light validation/cleanup pass if this text is ever shown directly
  to users.
- Worth running the script across a few more genre/mood combinations to
  confirm output quality is consistent, not just structurally valid, before
  committing to one story for the rest of the pipeline.