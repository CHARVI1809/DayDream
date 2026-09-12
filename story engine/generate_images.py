"""
Phase 3 — Wallpaper Image Generation (Cloudflare Workers AI)

Reads the image prompts (from Phase 2) and generates an actual wallpaper
image for each of the 30 chapters, using Cloudflare Workers AI's free tier.
Saves each as output/images/day_NN.png.

Model: @cf/black-forest-labs/flux-2-klein-9b — chosen specifically because
it supports explicit width/height parameters (unlike flux-1-schnell, which
is square-only), letting us generate true 9:16 vertical wallpapers directly
instead of cropping a square image down afterward.

Resumable: a day is skipped if its image file already exists on disk. Use
--force to regenerate everything from scratch.

Setup required before running:
    1. Create a free Cloudflare account: https://dash.cloudflare.com/sign-up
    2. Enable Workers AI in the dashboard (no credit card required)
    3. Get your Account ID (dashboard sidebar) and create an API Token
       with Workers AI permissions
    4. Add both to your .env file:
         CLOUDFLARE_ACCOUNT_ID=your_account_id
         CLOUDFLARE_API_TOKEN=your_api_token

Usage:
    python generate_images.py
    python generate_images.py --force
    python generate_images.py --input output/image_prompts.json --output-dir output/images

Requires:
    pip install requests python-dotenv
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path(__file__).parent / "output" / "image_prompts.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output" / "images"

# Cloudflare deprecates/renames models occasionally too — if this stops
# working, check the current model catalog at:
# https://developers.cloudflare.com/workers-ai/models/
MODEL_NAME = "@cf/black-forest-labs/flux-2-klein-9b"

# 896x1592 is a close approximation of 9:16 (0.5628 vs 0.5625), within the
# model's supported 256-1920 range.
IMAGE_WIDTH = 896
IMAGE_HEIGHT = 1592

# Small delay between calls to be a good citizen on the free tier.
REQUEST_DELAY_SECONDS = 3

# Retry a transient failure a couple of times before giving up on a day.
MAX_RETRIES_PER_DAY = 2
RETRY_BACKOFF_SECONDS = 10


def call_cloudflare_image(account_id: str, api_token: str, prompt: str) -> bytes:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{MODEL_NAME}"
    headers = {"Authorization": f"Bearer {api_token}"}

    # This model requires multipart/form-data, even for plain text fields —
    # using `files=` with (None, value) tuples forces requests to encode it
    # that way instead of the default x-www-form-urlencoded.
    fields = {
        "prompt": (None, prompt),
        "width": (None, str(IMAGE_WIDTH)),
        "height": (None, str(IMAGE_HEIGHT)),
    }

    response = requests.post(url, headers=headers, files=fields, timeout=120)

    if response.status_code == 429:
        raise RuntimeError(f"Rate limited (429): {response.text}")
    if not response.ok:
        raise RuntimeError(f"Cloudflare API error {response.status_code}: {response.text}")

    data = response.json()
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare API reported failure: {data}")

    image_b64 = data["result"]["image"]
    return base64.b64decode(image_b64)


def day_filename(output_dir: Path, day: int) -> Path:
    return output_dir / f"day_{day:02d}.png"


def generate_all_images(prompts: list, account_id: str, api_token: str,
                         output_dir: Path, force: bool) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(prompts)
    status = {}

    for entry in prompts:
        day = entry["day"]
        image_prompt = entry.get("image_prompt")
        out_path = day_filename(output_dir, day)

        if not image_prompt:
            print(f"  Day {day:02d}/{total}: SKIPPED — no prompt available (Phase 2 failed for this day).")
            status[day] = "no_prompt"
            continue

        if out_path.exists() and not force:
            print(f"  Day {day:02d}/{total}: already generated, skipping.")
            status[day] = "done"
            continue

        print(f"  Day {day:02d}/{total}: generating image...")

        image_bytes = None
        last_error = None
        for attempt in range(1, MAX_RETRIES_PER_DAY + 1):
            try:
                image_bytes = call_cloudflare_image(account_id, api_token, image_prompt)
                break
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES_PER_DAY:
                    print(f"    Attempt {attempt} failed ({e}), retrying in {RETRY_BACKOFF_SECONDS}s...")
                    time.sleep(RETRY_BACKOFF_SECONDS)

        if image_bytes is None:
            print(f"    WARNING: generation failed for day {day} after {MAX_RETRIES_PER_DAY} attempts: {last_error}")
            status[day] = "failed"
            continue

        with open(out_path, "wb") as f:
            f.write(image_bytes)
        status[day] = "done"

        time.sleep(REQUEST_DELAY_SECONDS)

    return status


def validate_images(status: dict, expected_count: int, output_dir: Path) -> None:
    done = [day for day, s in status.items() if s == "done"]
    missing = [day for day, s in status.items() if s != "done"]

    print(f"\n{len(done)}/{expected_count} images generated successfully.")
    if missing:
        print(f"WARNING: incomplete/failed days: {sorted(missing)}. Rerun the script to retry these (it will skip completed days).")

    tiny_files = []
    for day in done:
        path = day_filename(output_dir, day)
        if path.exists() and path.stat().st_size < 5000:
            tiny_files.append(day)
    if tiny_files:
        print(f"WARNING: these files are suspiciously small (<5KB), worth opening to check: {sorted(tiny_files)}")


def main():
    parser = argparse.ArgumentParser(description="Generate DayDream wallpaper images via Cloudflare Workers AI.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to image_prompts.json from Phase 2")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to save generated images")
    parser.add_argument("--force", action="store_true", help="Regenerate every image even if it already exists")
    args = parser.parse_args()

    load_dotenv()

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        sys.exit("ERROR: CLOUDFLARE_ACCOUNT_ID and/or CLOUDFLARE_API_TOKEN not found. Add both to your .env file.")

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"ERROR: {input_path} not found. Run generate_image_prompts.py (Phase 2) first.")

    with open(input_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    output_dir = Path(args.output_dir)

    print(f"Generating {len(prompts)} images via Cloudflare Workers AI (model: {MODEL_NAME})...")
    print(f"Target size: {IMAGE_WIDTH}x{IMAGE_HEIGHT} (~9:16)\n")

    status = generate_all_images(prompts, account_id, api_token, output_dir, args.force)

    validate_images(status, expected_count=len(prompts), output_dir=output_dir)


if __name__ == "__main__":
    main()
