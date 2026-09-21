## Phase 5 — Android UI Shell

**Goal:** Build a minimal Kotlin + Jetpack Compose app that reads the
Phase 4 story_package (bundled as assets) and displays a chapter on
screen — proving the app-side data pipeline works before adding any
date logic or wallpaper integration.

### Method
- Created an Empty Activity (Compose) project in Android Studio.
- Copied Phase 4's `story_package/` folder (JSON + images) directly into
  `app/src/main/assets/`.
- Wrote `MainActivity.kt`:
  - Parses `story_package.json` using Android's built-in `org.json`
    (no extra JSON library dependency needed).
  - Loads a chapter's image as a Bitmap directly from assets via
    `BitmapFactory`.
  - Displays story title, chapter title, image, and beat text in a
    simple scrollable Compose screen.
  - Hardcoded to always show Day 1 for this phase — no date logic yet.

### Issues encountered
- `ClassNotFoundException` on first run: the file was moved into a `ui`
  subpackage (`com.example.daydream.ui.MainActivity`) but
  `AndroidManifest.xml` still pointed to the old path (`.MainActivity`).
  Fixed by updating the manifest's `android:name` to `.ui.MainActivity`.
  A useful general lesson: in Kotlin/Android, a file's `package` line and
  its actual folder location must match exactly, and the manifest's
  activity path must in turn match the package.
- A black screen on first launch turned out to be the emulator itself
  still powered off/booting, not an app-side bug — worth checking device
  state before assuming a crash.

### Results
- App builds and runs successfully on an emulator, correctly displaying
  Day 1: story title, "Day 1: The Falling Star Fragment" heading, Lyra's
  Day 1 image, and the beat text — confirmed working end to end from the
  Python-generated story through to the Android UI.

### Conclusion
The full pipeline is now proven end to end: story generation (Phases
0-2) → image generation (Phase 3) → packaging (Phase 4) → Android
rendering (Phase 5). Remaining phases build on this working foundation
rather than introducing new architectural risk.

### Learnings for later phases
- Reading bundled JSON + image assets works reliably with just the
  Android SDK's built-in tools — no need for extra JSON or image-loading
  libraries at this scale.
- Project folder location matters for later git/repo setup — worth
  consolidating the Android project and the Python story-engine under
  one shared root folder before initializing version control, rather
  than after.
