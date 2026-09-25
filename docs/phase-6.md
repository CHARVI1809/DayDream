## Phase 6 — Date-Gated Reveal Logic

**Goal:** Make the app show the chapter matching the real current date
(Day 1 on first launch, Day 2 the next calendar day, and so on) instead
of always hardcoding Day 1, capping at the story's final day once
complete.

### Method
- Used `SharedPreferences` to persist a single value: the story's start
  date, saved as midnight (epoch milliseconds) the very first time the
  app is ever opened. Every later launch reads this same stored value
  rather than resetting it.
- Computed the currently-unlocked day as:
  `daysSinceStart = (today_midnight - start_midnight) / ms_per_day + 1`,
  clamped between 1 and the story's total day count.
- Used plain millisecond math via `Calendar` rather than `java.time`,
  specifically to avoid needing `coreLibraryDesugaring` in Gradle for
  older minSdk levels — one less moving part to configure at this stage.
- Updated the UI to show "Day X of Y" for progress visibility, and a
  "The story is complete." message once the final day is reached.

### Results
- On first launch, the app correctly shows Day 1 (as expected, since the
  install date and start date are the same day).
- Full day-to-day progression not yet manually verified (would require
  either waiting real days or changing the device's system clock) — this
  is expected to be tested via clock manipulation or a future debug
  override rather than real-time waiting.

### Conclusion
The app now has real date-driven behavior rather than a hardcoded
single day, which is the core mechanic the whole product depends on.
This unlocks the two remaining core features: setting the day's image as
the actual lock screen wallpaper (Phase 7), and eventually a gallery of
all unlocked chapters (Phase 8).

### Learnings for later phases
- Date-gated logic is inherently hard to test quickly during
  development, since real progress requires real days to pass. Plan for
  either temporary system-clock changes or a debug-only start-date
  override before relying on manual day-by-day testing.
