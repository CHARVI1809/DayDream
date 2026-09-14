"""
Phase 2 — Image Prompt Generation

Reads the Story Bible + 30-chapter outline (from Phase 1) and expands each
chapter's one-sentence "beat" into a full, detailed image-generation prompt,
using the Gemini API. Character descriptions, art style, and setting are
injected verbatim into every prompt to preserve consistency (per the Phase 0
finding: full re-description works better than shorthand references).

Chapters are processed in BATCHES (multiple chapters per API call), not one
call per chapter. Free-tier daily request quotas are tight (as low as ~20
requests/day depending on model/account) — batching keeps a 30-chapter story
well within that budget instead of requiring 30 separate calls.

Resumable: progress is saved to the output file after every batch. If the
script is interrupted, hits a quota limit, or a batch fails, rerunning the
script will skip every day that already succeeded and only generate the
missing/failed ones. Use --force to ignore existing progress and regenerate
everything.

If the daily request quota is exhausted, the script stops immediately
(rather than burning through remaining batches on guaranteed failures) and
tells you to either wait for the quota to reset or reduce BATCH_SIZE isn't
the fix here — increasing it is, since fewer, larger batches use less quota.

Usage:
    python generate_image_prompts.py
    python generate_image_prompts.py --input output/story_bible.json --output output/image_prompts.json
    python generate_image_prompts.py --force
    python generate_image_prompts.py --batch-size 10

Requires:
    pip install google-genai python-dotenv
    A .env file with GEMINI_API_KEY=your_key_here
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path(__file__).parent / "output" / "story_bible.json"
DEFAULT_OUTPUT = Path(__file__).parent / "output" / "image_prompts.json"

# Google's Gemini lineup deprecates models frequently — if this model name
# stops working, the error message from the API will name the current
# replacement. Just swap the string below; nothing else needs to change.
MODEL_NAME = "gemini-3.5-flash-lite"

# How many chapters to ask for in a single API call. Higher = fewer total
# requests = safer against tight free-tier daily quotas, at the cost of a
# larger single prompt/response. 5 keeps each call's output small and
# reliable to parse while cutting 30 chapters down to 6 requests.
DEFAULT_BATCH_SIZE = 5

# Small delay between calls to stay comfortably inside free-tier per-minute
# rate limits (separate from the daily request quota).
REQUEST_DELAY_SECONDS = 3

BATCH_PROMPT_TEMPLATE = """Using this exact cast of characters:
{characters_block}

Using this exact art style: {art_style}

Using this exact world setting: {setting}

Write a detailed image-generation prompt for EACH of the following {count} chapters. Each chapter continues directly from the one before it — keep scenes consistent with that continuity.

Chapters:
{chapters_block}

Rules:
- Every image must be a vertical mobile wallpaper composition, 9:16 aspect ratio. State this explicitly in every prompt.
- Include the FULL character description(s) verbatim for every character who appears in each scene, exactly as given above. Do not shorten, summarize, or refer to characters by name only.
- Do not invent new characters, props, or outfit details not present in the descriptions above.
- Keep each scene grounded in the setting and its beat.
- Specify a distinct CAMERA FRAMING/SHOT TYPE for each prompt (e.g. close-up on a face mid-reaction, wide establishing shot, low angle emphasizing scale, dynamic action shot mid-motion, over-the-shoulder). Avoid defaulting every scene to the same "characters standing in a row facing the camera" composition — that reads as repetitive and static across a sequence. Vary framing across consecutive chapters even when the underlying beat is similar.
- Favor depicting characters mid-action (reaching, moving, reacting) over posed/static standing, unless the beat specifically calls for a calm, still moment.

Output ONLY a JSON array, no markdown fences, no commentary, in this exact structure:
[
  {{"day": <int>, "image_prompt": "..."}},
  ...
]
One entry per chapter listed above, in the same order.
"""


def build_characters_block(characters: list) -> str:
    return "\n".join(f"- {c['name']}: {c['description']}" for c in characters)


def build_chapters_block(batch: list) -> str:
    return "\n".join(f"- Day {entry['day']}: {entry['beat']}" for entry in batch)


def build_batch_prompt(story_bible: dict, batch: list) -> str:
    return BATCH_PROMPT_TEMPLATE.format(
        characters_block=build_characters_block(story_bible["characters"]),
        art_style=story_bible["art_style"],
        setting=story_bible["setting"],
        count=len(batch),
        chapters_block=build_chapters_block(batch),
    )


def clean_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip().rstrip("`").strip()


class QuotaExhaustedError(Exception):
    """Raised when the daily request quota is used up — retrying now won't help."""
    pass


def call_gemini_batch(client: "genai.Client", prompt: str) -> list:
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    except genai_errors.ClientError as e:
        message = str(e)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            raise QuotaExhaustedError(message) from e
        raise

    cleaned = clean_json_text(response.text)
    return json.loads(cleaned)


def load_existing_results(output_path: Path) -> dict:
    if not output_path.exists():
        return {}
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        return {r["day"]: r for r in existing if r.get("image_prompt")}
    except (json.JSONDecodeError, KeyError, TypeError):
        print(f"  NOTE: couldn't parse existing {output_path}, ignoring it and starting fresh.")
        return {}


def save_results(results: dict, output_path: Path) -> None:
    output_path.parent.mkdir(exist_ok=True)
    ordered = sorted(results.values(), key=lambda r: r["day"])
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2, ensure_ascii=False)


def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]


def generate_all_prompts(story_bible: dict, client: "genai.Client", output_path: Path,
                          force: bool, batch_size: int) -> dict:
    outline = story_bible["chapter_outline"]
    total = len(outline)

    results = {} if force else load_existing_results(output_path)
    if results:
        print(f"  Resuming: {len(results)}/{total} chapters already completed, skipping those.\n")

    pending = [entry for entry in outline if entry["day"] not in results]
    if not pending:
        print("  All chapters already completed.")
        return results

    batches = chunk(pending, batch_size)
    print(f"  {len(pending)} chapters remaining, grouped into {len(batches)} batch(es) of up to {batch_size}.\n")

    for i, batch in enumerate(batches, start=1):
        days_in_batch = [entry["day"] for entry in batch]
        print(f"  Batch {i}/{len(batches)}: days {days_in_batch}...")

        prompt = build_batch_prompt(story_bible, batch)

        try:
            batch_output = call_gemini_batch(client, prompt)
        except QuotaExhaustedError:
            print(f"\n  STOPPED: daily request quota exhausted after {i - 1} successful batch(es).")
            print("  Retrying immediately will not help — this is a per-day limit, not a transient error.")
            print("  Options: (1) wait for the quota to reset (check the reset time in your AI Studio")
            print("  console — it's usually daily, but confirm there), or (2) increase --batch-size so")
            print("  fewer requests are needed next time. Progress so far is saved — just rerun this")
            print("  same command later and it will resume from here.")
            break
        except (json.JSONDecodeError, KeyError) as e:
            print(f"    WARNING: batch {i} returned unparseable output, skipping this batch: {e}")
            continue
        except Exception as e:
            print(f"    WARNING: batch {i} failed: {e}")
            continue

        by_day = {entry["day"]: entry for entry in batch}
        for item in batch_output:
            day = item.get("day")
            if day not in by_day:
                print(f"    WARNING: response included unexpected day {day}, ignoring it.")
                continue
            results[day] = {
                "day": day,
                "title": by_day[day].get("title"),
                "beat": by_day[day]["beat"],
                "image_prompt": item.get("image_prompt"),
            }

        missing = set(by_day) - {item.get("day") for item in batch_output}
        for day in missing:
            print(f"    WARNING: batch response was missing day {day}.")
            results[day] = {"day": day, "title": by_day[day].get("title"), "beat": by_day[day]["beat"], "image_prompt": None}

        save_results(results, output_path)
        time.sleep(REQUEST_DELAY_SECONDS)

    return results


def validate_prompts(results: dict, expected_count: int) -> None:
    if len(results) != expected_count:
        print(f"\nWARNING: Expected {expected_count} prompts, have {len(results)} tracked so far.")

    failed_days = [day for day, r in results.items() if not r.get("image_prompt")]
    if failed_days:
        print(f"WARNING: Missing/failed prompts for days: {sorted(failed_days)}. Rerun the script to retry — it will resume and only retry these.")

    missing_aspect_ratio = [
        day for day, r in results.items()
        if r.get("image_prompt") and "9:16" not in r["image_prompt"]
    ]
    if missing_aspect_ratio:
        print(f"WARNING: These days' prompts don't mention 9:16 explicitly: {sorted(missing_aspect_ratio)}")


def main():
    parser = argparse.ArgumentParser(description="Generate DayDream image prompts from a Story Bible.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to story_bible.json from Phase 1")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to write image_prompts.json")
    parser.add_argument("--force", action="store_true", help="Ignore existing progress and regenerate every chapter from scratch")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Chapters per API call (fewer total requests = safer against daily quotas)")
    args = parser.parse_args()

    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("ERROR: GEMINI_API_KEY not found. Add it to a .env file in this folder.")

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"ERROR: {input_path} not found. Run generate_story_bible.py (Phase 1) first.")

    with open(input_path, "r", encoding="utf-8") as f:
        story_bible = json.load(f)

    output_path = Path(args.output)

    print(f"Loaded story bible: {story_bible['title']}")
    print(f"Generating image prompts for {len(story_bible['chapter_outline'])} chapters...\n")

    client = genai.Client(api_key=api_key)
    results = generate_all_prompts(story_bible, client, output_path, args.force, args.batch_size)

    validate_prompts(results, expected_count=len(story_bible["chapter_outline"]))

    succeeded = sum(1 for r in results.values() if r.get("image_prompt"))
    print(f"\nSaved {succeeded}/{len(results)} image prompts to: {output_path}")


if __name__ == "__main__":
    main()
