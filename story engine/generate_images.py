"""
Phase 3 — Wallpaper Image Generation (Cloudflare Workers AI, flux-1-schnell)

Reads the image prompts (from Phase 2) and generates an actual wallpaper
image for each chapter, using Cloudflare Workers AI's flux-1-schnell model.
Saves each as output/images/day_NN.png.

flux-1-schnell is square-only (no width/height parameters, unlike
flux-2-klein-9b) but costs far less per image — chosen specifically to fit
comfortably within the free daily neuron allocation. Since the output is
square and your wallpapers need to be vertical (9:16), each image is
post-processed locally:

  1. The square image is resized to fill the canvas width.
  2. The remaining top/bottom space is filled with a blurred, stretched
     copy of the same image (not plain black bars) — this keeps the full
     scene visible with no cropping, and looks like a deliberate design
     choice rather than an obvious letterbox.

Use --crop instead if you'd rather crop to fill the frame completely
(loses the top/bottom of each scene, but no blur/bars at all).

Resumable: a day is skipped if its image file already exists on disk. Use
--force to regenerate everything from scratch.

Setup required before running (same Cloudflare account as before):
    CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in your .env file

Usage:
    python generate_images.py
    python generate_images.py --crop
    python generate_images.py --force

Requires:
    pip install requests python-dotenv pillow
"""

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image, ImageFilter

DEFAULT_INPUT = Path(__file__).parent / "output" / "image_prompts.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output" / "images"

MODEL_NAME = "@cf/black-forest-labs/flux-1-schnell"

TARGET_WIDTH = 896
TARGET_HEIGHT = 1592

REQUEST_DELAY_SECONDS = 2  # schnell is cheap and fast; free tier headroom is generous
MAX_RETRIES_PER_DAY = 2
RETRY_BACKOFF_SECONDS = 10


def call_cloudflare_image(account_id: str, api_token: str, prompt: str) -> bytes:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{MODEL_NAME}"
    headers = {"Authorization": f"Bearer {api_token}"}

    response = requests.post(url, headers=headers, json={"prompt": prompt}, timeout=120)

    if response.status_code == 429:
        raise RuntimeError(f"Rate limited (429): {response.text}")
    if not response.ok:
        raise RuntimeError(f"Cloudflare API error {response.status_code}: {response.text}")

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        if not data.get("success"):
            raise RuntimeError(f"Cloudflare API reported failure: {data}")
        return base64.b64decode(data["result"]["image"])
    else:
        # Some Workers AI image models return raw binary directly rather
        # than JSON-wrapped base64 — handle both response shapes.
        return response.content


def letterbox_to_vertical(square_bytes: bytes, target_w: int, target_h: int) -> bytes:
    """Fit a square image into a vertical canvas by scaling it to fill the
    width, then filling the remaining top/bottom space with a blurred,
    stretched copy of the same image — blended with a soft gradient at the
    seam rather than a hard cut, so it reads as an intentional background
    extension instead of an obvious patch."""
    img = Image.open(io.BytesIO(square_bytes)).convert("RGB")

    # Sharp foreground: scaled to fill the target width, full square visible.
    scale = target_w / img.width
    fg_w, fg_h = target_w, int(img.height * scale)
    foreground = img.resize((fg_w, fg_h), Image.LANCZOS)

    # Blurred background: scaled to COVER the whole canvas (may crop), then
    # blurred. A moderate radius (not too heavy) avoids blotchy artifacts.
    cover_scale = max(target_w / img.width, target_h / img.height)
    bg_w, bg_h = int(img.width * cover_scale), int(img.height * cover_scale)
    background = img.resize((bg_w, bg_h), Image.LANCZOS)
    left = (bg_w - target_w) // 2
    top = (bg_h - target_h) // 2
    background = background.crop((left, top, left + target_w, top + target_h))
    background = background.filter(ImageFilter.GaussianBlur(radius=18))
    # Darken slightly so the background doesn't compete visually with the
    # sharp foreground — makes the transition read as intentional depth.
    background = Image.eval(background, lambda p: int(p * 0.75))

    canvas = background.copy()
    paste_y = (target_h - fg_h) // 2

    # Soft feathered blend at the seam: build an alpha mask for the
    # foreground that fades in/out over a band at its top and bottom edges,
    # instead of a hard paste boundary. Built via a thin gradient strip
    # resized to full width (fast) rather than a per-pixel loop.
    feather = min(120, fg_h // 6)
    mask = Image.new("L", (fg_w, fg_h), 255)
    if feather > 0:
        top_strip = Image.new("L", (1, feather))
        for y in range(feather):
            top_strip.putpixel((0, y), int(255 * (y / feather)))
        top_strip = top_strip.resize((fg_w, feather))
        mask.paste(top_strip, (0, 0))

        bottom_strip = top_strip.transpose(Image.FLIP_TOP_BOTTOM)
        mask.paste(bottom_strip, (0, fg_h - feather))

    canvas.paste(foreground, (0, paste_y), mask)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def crop_to_vertical(square_bytes: bytes, target_w: int, target_h: int) -> bytes:
    """Alternative: crop the square image to fill the vertical frame
    completely. Loses the top/bottom of the scene, no blur/bars."""
    img = Image.open(io.BytesIO(square_bytes)).convert("RGB")
    scale = max(target_w / img.width, target_h / img.height)
    new_w, new_h = int(img.width * scale), int(img.height * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    cropped = resized.crop((left, top, left + target_w, top + target_h))

    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    return buffer.getvalue()


def day_filename(output_dir: Path, day: int) -> Path:
    return output_dir / f"day_{day:02d}.png"


def generate_all_images(prompts: list, account_id: str, api_token: str,
                         output_dir: Path, force: bool, use_letterbox: bool) -> dict:
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

        square_bytes = None
        last_error = None
        for attempt in range(1, MAX_RETRIES_PER_DAY + 1):
            try:
                square_bytes = call_cloudflare_image(account_id, api_token, image_prompt)
                break
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES_PER_DAY:
                    print(f"    Attempt {attempt} failed ({e}), retrying in {RETRY_BACKOFF_SECONDS}s...")
                    time.sleep(RETRY_BACKOFF_SECONDS)

        if square_bytes is None:
            print(f"    WARNING: generation failed for day {day} after {MAX_RETRIES_PER_DAY} attempts: {last_error}")
            status[day] = "failed"
            continue

        try:
            if use_letterbox:
                final_bytes = letterbox_to_vertical(square_bytes, TARGET_WIDTH, TARGET_HEIGHT)
            else:
                final_bytes = crop_to_vertical(square_bytes, TARGET_WIDTH, TARGET_HEIGHT)
        except Exception as e:
            print(f"    WARNING: post-processing failed for day {day}: {e}")
            status[day] = "failed"
            continue

        with open(out_path, "wb") as f:
            f.write(final_bytes)
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
    parser = argparse.ArgumentParser(description="Generate DayDream wallpaper images via Cloudflare Workers AI (flux-1-schnell).")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to image_prompts.json from Phase 2")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to save generated images")
    parser.add_argument("--force", action="store_true", help="Regenerate every image even if it already exists")
    parser.add_argument("--letterbox", action="store_true", help="Use blurred-background letterboxing instead of cropping (crop is now the default — letterboxing had visible seam/blur artifacts in testing)")
    parser.add_argument("--days", type=int, nargs="+", default=None, help="Only generate specific day numbers, e.g. --days 1 6 14 (for spot-checking before committing full quota)")
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

    if args.days:
        prompts = [p for p in prompts if p["day"] in args.days]
        if not prompts:
            sys.exit(f"ERROR: none of the requested days {args.days} were found in {input_path}.")

    output_dir = Path(args.output_dir)
    mode = "letterbox (blurred background fill)" if args.letterbox else "crop"

    print(f"Generating {len(prompts)} images via Cloudflare Workers AI (model: {MODEL_NAME})...")
    print(f"Square output -> {TARGET_WIDTH}x{TARGET_HEIGHT} vertical, mode: {mode}\n")

    status = generate_all_images(prompts, account_id, api_token, output_dir, args.force, args.letterbox)

    validate_images(status, expected_count=len(prompts), output_dir=output_dir)


if __name__ == "__main__":
    main()
