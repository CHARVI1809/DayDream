"""
Phase 1 — Story Bible Generation

Calls the Gemini API to generate a complete Story Bible (title, characters,
setting, world rules, ending, art style) plus a chapter outline for a
DayDream story, and saves it as JSON for Phase 2 to consume.

Usage:
    python generate_story_bible.py --genre Fantasy --mood Adventure
    python generate_story_bible.py --genre Fantasy --mood Adventure --chapters 15

Requires:
    pip install google-genai python-dotenv
    A .env file with GEMINI_API_KEY=your_key_here

Note: this uses the new `google-genai` SDK (the old `google-generativeai`
package is deprecated). If you installed the old package earlier, uninstall
it first: pip uninstall google-generativeai
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "story_bible.json"

# Google's Gemini lineup deprecates models frequently — if this model name
# stops working, the error message from the API will name the current
# replacement. Just swap the string below; nothing else needs to change.
MODEL_NAME = "gemini-3.6-flash"

PROMPT_TEMPLATE = """You are a creative writer designing a {chapters}-day visual novel story for an app called DayDream, where each day the user sees one new AI-generated image continuing the story.

Genre: {genre}
Mood/theme: {mood}

Generate a Story Bible in JSON format with this exact structure:

{{
  "title": "...",
  "characters": [
    {{"name": "...", "description": "physical appearance, clothing, distinguishing features, and an explicit SCALE/SIZE anchor relative to a human (e.g. 'fox-sized, no taller than knee-height on an adult'). Be very specific and consistent — this will be reused verbatim in every image prompt across all {chapters} days."}}
  ],
  "setting": "a detailed description of the world/location, consistent visual elements, time period",
  "world_rules": "any magic systems, technology rules, or constraints that must stay consistent",
  "ending": "how the story concludes",
  "art_style": "a consistent visual style description for a VERTICAL 9:16 mobile wallpaper composition (do not describe it as 16:9 or landscape)",
  "chapter_outline": [
    {{"day": 1, "beat": "one sentence describing what happens this chapter"}}
  ]
}}

Requirements:
- chapter_outline must contain exactly {chapters} entries, day 1 through day {chapters}.
- Pace the story as a genuinely complete arc within {chapters} chapters — proper setup, rising complications, a real climax, and a resolution. Do not simply compress a longer story; plan the beats for this exact length so day {chapters} is a true ending, not a midpoint.
- Character descriptions must include an explicit scale anchor, not just a numeric measurement alone.
- art_style must specify a vertical 9:16 composition, never landscape/16:9.
- Only output the JSON object. No markdown code fences, no commentary, no preamble.
"""


def build_prompt(genre: str, mood: str, chapters: int) -> str:
    return PROMPT_TEMPLATE.format(genre=genre, mood=mood, chapters=chapters)


def call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("ERROR: GEMINI_API_KEY not found. Add it to a .env file in this folder.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text


def clean_json_text(raw_text: str) -> str:
    """Strip markdown code fences if the model added them despite instructions."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip().rstrip("`").strip()


def validate_story_bible(data: dict, expected_chapters: int) -> None:
    required_keys = {"title", "characters", "setting", "world_rules", "ending", "art_style", "chapter_outline"}
    missing = required_keys - data.keys()
    if missing:
        sys.exit(f"ERROR: Story Bible is missing required keys: {missing}")

    outline = data["chapter_outline"]
    if len(outline) != expected_chapters:
        print(f"WARNING: Expected {expected_chapters} chapters, got {len(outline)}. Continuing anyway.")

    days = [entry.get("day") for entry in outline]
    expected_days = list(range(1, len(outline) + 1))
    if days != expected_days:
        print(f"WARNING: Chapter day numbers are not sequential 1..N: {days}")


def main():
    parser = argparse.ArgumentParser(description="Generate a DayDream Story Bible + 30-chapter outline.")
    parser.add_argument("--genre", required=True, help="e.g. Fantasy, Cyberpunk, Sci-Fi, Nature, Mystery, Anime")
    parser.add_argument("--mood", required=True, help="e.g. Adventure, Hope, Romance, Survival, Exploration")
    parser.add_argument("--chapters", type=int, default=30, help="Number of chapters/days in the story (default: 30)")
    args = parser.parse_args()

    load_dotenv()

    print(f"Generating Story Bible — genre: {args.genre}, mood: {args.mood}, chapters: {args.chapters}")
    prompt = build_prompt(args.genre, args.mood, args.chapters)
    raw_response = call_gemini(prompt)

    cleaned = clean_json_text(raw_response)
    try:
        story_bible = json.loads(cleaned)
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: Model output was not valid JSON: {e}\n\nRaw output:\n{raw_response}")

    validate_story_bible(story_bible, args.chapters)

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(story_bible, f, indent=2, ensure_ascii=False)

    print(f"\nStory Bible saved to: {OUTPUT_FILE}")
    print(f"Title: {story_bible['title']}")
    print(f"Characters: {[c['name'] for c in story_bible['characters']]}")
    print(f"Chapters generated: {len(story_bible['chapter_outline'])}")


if __name__ == "__main__":
    main()
