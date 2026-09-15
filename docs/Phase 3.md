## Phase 3 — Wallpaper Image Generation

**Goal:** Generate an actual vertical wallpaper image for every chapter of
the committed story, using a free-tier image generation API.

### Method
- Evaluated multiple free image generation options before committing:
  - **Gemini (Nano Banana family)** — ruled out: the account had 0/0 free
    API quota for all image models, despite having a Gemini Pro app
    subscription (consumer app access ≠ API billing).
  - **Cloudflare Workers AI (flux-2-klein-9b)** — worked, good consistency,
    but ~500 neurons/image capped generation at ~20 images/day on the free
    10,000 neurons/day allocation.
  - **Pollinations.ai** — no signup required, but full-length prompts
    (~1000-1850 chars) got silently truncated, dropping character detail
    entirely and producing generic scenery. A purpose-written short prompt
    (~300 chars) rendered correctly, confirming prompt length as the cause.
    Even after building content-aware trimming (prioritizing sentences that
    mention a character name) and testing purpose-written short prompts,
    results remained unreliable. Ruled out.
  - **Cloudflare Workers AI (flux-1-schnell)** — chosen as the final model:
    far cheaper per image (fits well within free daily quota), though
    square-only (no width/height control).
- Since flux-1-schnell only outputs square images, wrote local
  post-processing to convert to 9:16 vertical:
  - Tried letterboxing (blurred, stretched background fill) first — had
    visible hard seams and blotchy artifacts even after adding feathered
    alpha blending.
  - Compared directly against simple center-cropping — cropping looked
    cleaner with no artifacts. Made crop the default, letterbox optional.
- Script is resumable (skips days with an existing image file) and stops
  cleanly on quota exhaustion rather than burning through guaranteed
  failures.
- Added a `--days` flag to spot-check specific chapters before committing
  full daily quota to a complete run.

### Issues encountered
- Hit Cloudflare's daily free neuron allocation mid-run more than once.
  One occurrence involved the dashboard showing "0/10k used today" while
  the API still rejected requests as quota-exhausted — most likely a
  propagation delay between Cloudflare's billing/analytics display and
  live rate-limit enforcement at the edge. Resolved itself after waiting;
  no billing was enabled.
- A real bug was found and fixed in the Pollinations trimming logic: it
  matched on a character's full name as it appears in the story bible
  (e.g. "Lyra Vane") rather than individual name parts, meaning sentences
  that only said "Lyra" weren't recognized as character mentions at all.

### Results
- Final story ("The Sun-Forge Arcana") generated successfully across all
  15 chapters using Cloudflare + flux-1-schnell + crop post-processing.
- Spot-check of a leap/action shot, a character-reveal shot, and a pure
  environmental establishing shot confirmed genuinely varied, distinct
  compositions — not just different scenes in the same static pose.

### Learnings for later phases
- Free-tier image generation quotas are consistently the tightest
  constraint in this pipeline — tighter than text generation by a wide
  margin. Model choice for images matters far more for cost/quota than
  for text.
- A model good at following character-description instructions in text
  form is not automatically good at rendering unusual/secondary character
  designs accurately (see Bramble in an earlier test run, and Pip's design
  here) — this is a recurring, not one-off, limitation worth flagging in
  the final report as a known constraint of free-tier image models.
- When post-processing generated images (aspect ratio conversion, etc.),
  test the actual visual result before committing — the first letterbox
  implementation looked reasonable in code but produced visibly broken
  output in practice.
