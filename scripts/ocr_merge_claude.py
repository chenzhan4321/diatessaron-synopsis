"""
OCR Merge & Correction Pipeline — "4th Version"

Takes 3 OCR outputs (QARI, Tesseract, Kraken) for each page of Ciasca 1888
Arabic Diatessaron, and uses Claude API to produce a corrected 4th version.

Claude sees all 3 versions + the page image, and outputs the best possible
Arabic text by:
  - Cross-referencing the 3 versions to resolve ambiguities
  - Using its Arabic language knowledge to fix grammar/spelling
  - Using Diatessaron content knowledge to resolve uncertain words
  - Preserving verse numbers and gospel references (متى، مرقس، لوقا، يوحنا)

Usage:
  uv run python scripts/ocr_merge_claude.py [--start PAGE] [--end PAGE]
"""

import anthropic
import base64
import json
import os
import sys
import time
from pathlib import Path

# --- Paths ---
PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data" / "diatessaron_arabic_ocr"
IMAGE_DIR = DATA / "ciasca_pages"
RESULTS = DATA / "results"

QARI_DIR = RESULTS / "ciasca_qari"       # from Forge
TESS_DIR = RESULTS / "ciasca_tesseract"   # local Tesseract
KRAK_DIR = RESULTS / "ciasca_kraken"      # local Kraken
OUT_DIR  = RESULTS / "ciasca_merged"      # 4th version output

# Page range for Arabic text in Ciasca 1888
FIRST_PAGE = 133
LAST_PAGE  = 348

SYSTEM_PROMPT = """You are an expert in Classical Arabic and early Christian texts,
specifically Tatian's Diatessaron (the Arabic translation by Ibn al-Tayyib).

You will receive a scanned page image from Ciasca's 1888 edition of the Arabic
Diatessaron, along with 3 OCR transcriptions of that page (from different engines).
Each OCR version has different strengths and errors.

Your task: produce the CORRECT Arabic text of this page by:
1. Cross-referencing the 3 OCR versions to find consensus
2. Where versions disagree, use the page image + your Arabic knowledge to determine
   the correct reading
3. Fix obvious OCR errors (e.g. مقس → مرقس, letter confusions like ب↔ن↔ت↔ث)
4. Preserve the original structure: verse numbers in parentheses, gospel references
   (متى، مرقس، لوقا، يوحنا), section markers (الاصحاح), and the ※ symbols
5. Do NOT add any text that isn't on the page — only correct what's there
6. Do NOT translate — output Arabic text only
7. Ignore the footnotes/critical apparatus at the bottom (Latin+Arabic mixed text)
   — only transcribe the main Arabic body text

Output ONLY the corrected Arabic text, nothing else."""


def load_ocr_version(page_num: int, engine: str, directory: Path) -> str:
    """Load OCR text for a specific page and engine."""
    patterns = [
        directory / f"page_{page_num:04d}_{engine}.txt",
        directory / f"page_{page_num:04d}.txt",
    ]
    for p in patterns:
        if p.exists() and p.stat().st_size > 30:
            return p.read_text(encoding="utf-8").strip()
    return ""


def load_page_image_b64(page_num: int) -> str:
    """Load page image as base64 for Claude API."""
    img_path = IMAGE_DIR / f"page_{page_num:04d}.png"
    if not img_path.exists():
        return ""
    with open(img_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def merge_page(client: anthropic.Anthropic, page_num: int) -> str:
    """Send 3 OCR versions + image to Claude, get corrected text."""
    # Load OCR versions
    qari = load_ocr_version(page_num, "qari", QARI_DIR)
    tess = load_ocr_version(page_num, "tesseract", TESS_DIR)
    krak = load_ocr_version(page_num, "kraken", KRAK_DIR)

    # Check if we have at least 1 version
    versions = []
    if qari:
        versions.append(f"=== QARI-OCR (VLM-based, usually best) ===\n{qari}")
    if tess:
        versions.append(f"=== Tesseract (traditional OCR) ===\n{tess}")
    if krak:
        versions.append(f"=== Kraken (classical Arabic specialist) ===\n{krak}")

    if not versions:
        return ""

    # Load image
    img_b64 = load_page_image_b64(page_num)

    # Build message content
    content = []

    # Add image if available
    if img_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64,
            },
        })

    # Add OCR versions as text
    ocr_text = "\n\n".join(versions)
    content.append({
        "type": "text",
        "text": f"Here are 3 OCR transcriptions of this page (page {page_num} of Ciasca 1888 Arabic Diatessaron):\n\n{ocr_text}\n\nPlease produce the corrected Arabic text."
    })

    # Call Claude
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    return response.content[0].text


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=FIRST_PAGE)
    parser.add_argument("--end", type=int, default=LAST_PAGE)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

    total = 0
    skipped = 0

    for page_num in range(args.start, args.end + 1):
        out_path = OUT_DIR / f"page_{page_num:04d}_merged.txt"

        # Skip if already done
        if out_path.exists() and out_path.stat().st_size > 50:
            skipped += 1
            continue

        # Check if image exists (skip blank/non-Arabic pages)
        img_path = IMAGE_DIR / f"page_{page_num:04d}.png"
        if not img_path.exists():
            continue

        print(f"[Page {page_num}] Merging...", end=" ", flush=True)
        t0 = time.time()

        try:
            result = merge_page(client, page_num)
            if result:
                out_path.write_text(result, encoding="utf-8")
                total += 1
                print(f"{len(result)} chars in {time.time()-t0:.1f}s")
            else:
                print("NO OCR DATA")
        except Exception as e:
            print(f"ERROR: {e}")
            # Rate limit — wait and retry once
            if "rate" in str(e).lower():
                time.sleep(30)
                try:
                    result = merge_page(client, page_num)
                    if result:
                        out_path.write_text(result, encoding="utf-8")
                        total += 1
                        print(f"  RETRY OK: {len(result)} chars")
                except Exception as e2:
                    print(f"  RETRY FAILED: {e2}")

    # Combine all pages
    combined = OUT_DIR / "ciasca_arabic_merged_combined.txt"
    with open(combined, "w", encoding="utf-8") as f:
        for page_num in range(args.start, args.end + 1):
            p = OUT_DIR / f"page_{page_num:04d}_merged.txt"
            if p.exists():
                f.write(f"\n=== Page {page_num} ===\n")
                f.write(p.read_text(encoding="utf-8"))
                f.write("\n")

    print(f"\nDone! {total} pages merged ({skipped} skipped)")
    print(f"Combined: {combined}")


if __name__ == "__main__":
    main()
