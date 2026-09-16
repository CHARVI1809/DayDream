"""
Phase 4 — Package the Story for the Android App

Combines the Story Bible (Phase 1), image prompts (Phase 2), and generated
images (Phase 3) into a single, self-contained "story package" that the
Android app can read directly — no live API calls needed at runtime.

Output structure:
    output/story_package/
        story_package.json   <- all metadata: title, characters, chapters
                                 (day, title, beat, image filename)
        images/
            day_01.png
            day_02.png
            ...

This is the ONLY thing Phase 5 (the Android app) needs to consume. It can
be bundled directly into the app's assets folder.

Usage:
    python package_story.py

Requires: no extra dependencies (stdlib only)
"""

import json
import shutil
import sys
from pathlib import Path

STORY_BIBLE_PATH = Path(__file__).parent / "output" / "story_bible.json"
IMAGE_PROMPTS_PATH = Path(__file__).parent / "output" / "image_prompts.json"
IMAGES_DIR = Path(__file__).parent / "output" / "images"

PACKAGE_DIR = Path(__file__).parent / "output" / "story_package"
PACKAGE_IMAGES_DIR = PACKAGE_DIR / "images"
PACKAGE_JSON_PATH = PACKAGE_DIR / "story_package.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run the earlier phase scripts first.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_completeness(story_bible: dict, image_prompts: list) -> list:
    """Returns a list of problems found. Empty list = all good."""
    problems = []

    expected_days = {entry["day"] for entry in story_bible["chapter_outline"]}
    prompt_days = {entry["day"] for entry in image_prompts}

    missing_prompts = expected_days - prompt_days
    if missing_prompts:
        problems.append(f"Days missing from image_prompts.json: {sorted(missing_prompts)}")

    for day in sorted(expected_days):
        image_path = IMAGES_DIR / f"day_{day:02d}.png"
        if not image_path.exists():
            problems.append(f"Day {day}: no generated image found at {image_path}")
        elif image_path.stat().st_size < 5000:
            problems.append(f"Day {day}: image file is suspiciously small (<5KB) at {image_path}")

    return problems


def build_package(story_bible: dict, image_prompts: list) -> dict:
    prompts_by_day = {entry["day"]: entry for entry in image_prompts}

    chapters = []
    for entry in story_bible["chapter_outline"]:
        day = entry["day"]
        prompt_entry = prompts_by_day.get(day, {})
        chapters.append({
            "day": day,
            "title": entry.get("title") or prompt_entry.get("title") or f"Day {day}",
            "beat": entry["beat"],
            "image_file": f"day_{day:02d}.png",
        })

    return {
        "title": story_bible["title"],
        "characters": story_bible["characters"],
        "setting": story_bible["setting"],
        "ending": story_bible["ending"],
        "total_days": len(chapters),
        "chapters": chapters,
    }


def copy_images(expected_days: list) -> None:
    PACKAGE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for day in expected_days:
        filename = f"day_{day:02d}.png"
        src = IMAGES_DIR / filename
        dst = PACKAGE_IMAGES_DIR / filename
        if src.exists():
            shutil.copy2(src, dst)


def main():
    print("Loading Phase 1-3 outputs...")
    story_bible = load_json(STORY_BIBLE_PATH)
    image_prompts = load_json(IMAGE_PROMPTS_PATH)

    print("Validating completeness...")
    problems = validate_completeness(story_bible, image_prompts)
    if problems:
        print("\nPROBLEMS FOUND — package will still be built, but review these before shipping:")
        for p in problems:
            print(f"  - {p}")
        print()
    else:
        print("  All chapters have prompts and valid images.\n")

    print("Building package...")
    package = build_package(story_bible, image_prompts)

    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(PACKAGE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2, ensure_ascii=False)

    expected_days = [entry["day"] for entry in story_bible["chapter_outline"]]
    copy_images(expected_days)

    print(f"\nPackage complete: {PACKAGE_DIR}")
    print(f"  - {PACKAGE_JSON_PATH.name}: {len(package['chapters'])} chapters")
    print(f"  - {PACKAGE_IMAGES_DIR}: {len(list(PACKAGE_IMAGES_DIR.glob('*.png')))} images")
    print(f"\nCopy this whole '{PACKAGE_DIR.name}' folder into your Android project's assets directory for Phase 5.")


if __name__ == "__main__":
    main()
