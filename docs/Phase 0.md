## Phase 0 — Art Style & Consistency Validation

**Goal:** Determine whether a consistent character, art style, and world could be
maintained across multiple AI-generated images using text-only prompting, before
committing to a full automated pipeline.

### Method
- Generated a Story Bible (title, characters, setting, world rules, ending,
  30-chapter outline) for a fantasy genre story ("The Cartographer of Falling
  Stars") using Gemini.
- Manually constructed image prompts for Days 1–3 by combining the chapter beat
  with the exact character description, art style, and setting text from the
  Story Bible.
- Generated all three images in the same chat session (to allow the model visual
  context from prior generations, not just text).
- Compared the three images for character, art style, and world consistency.
- Generated one additional full-body pose of the secondary character (Corvus) to
  verify whether an initial apparent inconsistency was real drift or just
  pose variation.

### Results
- **Main character (Lyra):** consistent across all three images — face, hair,
  coat design, and color palette all held up well using text-only
  re-description.
- **Secondary character (Corvus, mechanical fox):** design (head shape, ear
  shape, eye color, tail shape/tip) held up consistently across both perched
  and full-body poses — confirmed via a follow-up full-body generation.
  However, **scale was not respected**: the spec describes Corvus as ~45cm
  (fox-sized), but the full-body render depicted him as much larger relative
  to surrounding objects and the human character.
- **Art style / world:** consistent painterly fantasy style and color palette
  across all scenes.

### Conclusion
Text-only prompting (re-describing the character/style/setting verbatim in
every prompt) is sufficient to hold shape, color, and design consistency for
both primary and secondary characters across scenes and poses. This validates
moving forward with a template-based prompt assembly approach for Phase 1–2,
without requiring heavier consistency tooling (e.g. IP-Adapter, reference-image
conditioning) for v1. Scale consistency needs a specific prompt-level fix (see
below) rather than a tooling change.

### Learnings for later phases
- Prompt templates must explicitly repeat full character descriptions every
  time — no shorthand references.
- Character descriptions should include an explicit **scale/size anchor**
  (e.g. "fox-sized, no taller than knee-height on an adult human") rather than
  relying on a numeric measurement alone ("45cm") — numbers alone were not
  reliably respected by the model.
- File naming discipline matters early: mismatched day-numbering in generated
  assets will silently break Phase 6's date-gated reveal logic.
- Generating a character in a different pose than initially tested is a good
  sanity check before concluding a design is "inconsistent" — what first looked
  like drift turned out to be a design that reads differently at different
  poses, not an actual inconsistency.