## Phase 4 — Package the Story for the Android App

**Goal:** Combine the Story Bible, image prompts, and generated images
into a single, self-contained bundle the Android app can consume directly
— no live API calls, no story-engine dependencies at runtime.

### Method
- Wrote `package_story.py`, which:
  - Loads `story_bible.json` and `image_prompts.json`
  - Validates completeness: every chapter has a prompt AND a generated
    image file on disk, and flags any suspiciously small (<5KB, likely
    broken) image files before packaging
  - Builds a single `story_package.json` containing only what the app
    needs per chapter -- `day`, `title`, `beat`, `image_file` -- dropping
    the verbose image-generation prompts, which were internal plumbing
  - Copies all chapter images into `output/story_package/images/`,
    consistently renamed as `day_01.png` ... `day_NN.png`

### Results
- Clean validation pass -- all 15 chapters had both a prompt and a valid
  generated image.
- Output: a single `output/story_package/` folder, ready to be copied
  directly into the Android project's assets directory.

### Conclusion
This is the handoff point between the Python story-engine (Phases 0-3)
and the Android app (Phase 5 onward). Everything upstream of this point --
model choice, API calls, prompt engineering, quota management -- is now
irrelevant to the app itself; it only needs to read one JSON file and a
folder of images.

### Learnings for later phases
- Keeping the app-facing data format (`story_package.json`) minimal and
  decoupled from the generation pipeline's internal formats
  (`image_prompts.json`, with its verbose prompts) makes the Android side
  simpler and avoids exposing generation implementation details to the
  app layer.
