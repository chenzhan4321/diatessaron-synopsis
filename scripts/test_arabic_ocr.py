"""
Test Arabic OCR models on the Marmardji 1935 Diatessaron edition.

We test three engines:
  1. Tesseract (ara language pack)
  2. EasyOCR (Arabic support)
  3. Kraken (with Arabic model)

The Marmardji edition has French main text with Arabic critical apparatus
in footnotes. We test on full pages and on cropped footnote regions.
"""

import os
import sys
import json
import time
from pathlib import Path
from PIL import Image

# Paths
DATA_DIR = Path("/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_arabic_ocr")
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Test pages that have substantial Arabic footnotes
TEST_PAGES = ["page_n200.jpg", "page_n260.jpg", "page_n300.jpg", "page_n400.jpg", "page_n450.jpg"]


def crop_footnote_region(img_path: str, output_path: str) -> str:
    """
    Crop the bottom portion of a page where footnotes with Arabic text appear.
    Typically the bottom ~30% of the page contains the critical apparatus.
    """
    img = Image.open(img_path)
    w, h = img.size
    # Footnotes are roughly in the bottom 30% of the page
    cropped = img.crop((0, int(h * 0.70), w, h))
    cropped.save(output_path)
    return output_path


def test_tesseract(img_path: str, lang: str = "ara+fra") -> dict:
    """Run Tesseract OCR on an image with Arabic + French language support."""
    import subprocess
    start = time.time()
    try:
        result = subprocess.run(
            ["tesseract", img_path, "stdout", "-l", lang, "--psm", "6"],
            capture_output=True, text=True, timeout=60
        )
        elapsed = time.time() - start
        text = result.stdout.strip()
        return {
            "engine": f"tesseract ({lang})",
            "text": text,
            "time_sec": round(elapsed, 2),
            "error": result.stderr.strip() if result.returncode != 0 else None
        }
    except Exception as e:
        return {"engine": f"tesseract ({lang})", "text": "", "time_sec": 0, "error": str(e)}


def test_tesseract_arabic_only(img_path: str) -> dict:
    """Run Tesseract with Arabic-only mode for footnote crops."""
    import subprocess
    start = time.time()
    try:
        result = subprocess.run(
            ["tesseract", img_path, "stdout", "-l", "ara", "--psm", "6"],
            capture_output=True, text=True, timeout=60
        )
        elapsed = time.time() - start
        text = result.stdout.strip()
        return {
            "engine": "tesseract (ara only)",
            "text": text,
            "time_sec": round(elapsed, 2),
            "error": result.stderr.strip() if result.returncode != 0 else None
        }
    except Exception as e:
        return {"engine": "tesseract (ara only)", "text": "", "time_sec": 0, "error": str(e)}


def test_easyocr(img_path: str) -> dict:
    """Run EasyOCR with Arabic + French support."""
    import easyocr
    start = time.time()
    try:
        # Initialize reader (will download models on first run)
        reader = easyocr.Reader(['ar', 'fr'], gpu=False, verbose=False)
        results = reader.readtext(img_path)
        elapsed = time.time() - start
        # Combine detected text blocks
        lines = []
        for (bbox, text, conf) in results:
            lines.append(f"[{conf:.2f}] {text}")
        full_text = "\n".join(lines)
        avg_conf = sum(r[2] for r in results) / len(results) if results else 0
        return {
            "engine": "easyocr (ar+fr)",
            "text": full_text,
            "time_sec": round(elapsed, 2),
            "num_blocks": len(results),
            "avg_confidence": round(avg_conf, 3),
            "error": None
        }
    except Exception as e:
        return {"engine": "easyocr (ar+fr)", "text": "", "time_sec": 0, "error": str(e)}


def test_easyocr_arabic_only(img_path: str) -> dict:
    """Run EasyOCR with Arabic only."""
    import easyocr
    start = time.time()
    try:
        reader = easyocr.Reader(['ar'], gpu=False, verbose=False)
        results = reader.readtext(img_path)
        elapsed = time.time() - start
        lines = []
        for (bbox, text, conf) in results:
            lines.append(f"[{conf:.2f}] {text}")
        full_text = "\n".join(lines)
        avg_conf = sum(r[2] for r in results) / len(results) if results else 0
        return {
            "engine": "easyocr (ar only)",
            "text": full_text,
            "time_sec": round(elapsed, 2),
            "num_blocks": len(results),
            "avg_confidence": round(avg_conf, 3),
            "error": None
        }
    except Exception as e:
        return {"engine": "easyocr (ar only)", "text": "", "time_sec": 0, "error": str(e)}


def test_kraken(img_path: str) -> dict:
    """
    Run Kraken OCR. First we need to download an Arabic model.
    We use the default segmentation + an Arabic recognition model.
    """
    start = time.time()
    try:
        from kraken import blla, rpred
        from kraken.lib import models
        from PIL import Image as PILImage

        img = PILImage.open(img_path)

        # Try to get an Arabic model
        # First check if we have one cached
        model_dir = DATA_DIR / "kraken_models"
        model_dir.mkdir(exist_ok=True)

        # Use kraken's model download facility
        from kraken import repo
        try:
            # Try to list and download Arabic model
            model_path = str(model_dir / "arabic_generalized.mlmodel")
            if not os.path.exists(model_path):
                print("  Downloading Kraken Arabic model...")
                # Download the Arabic-Persian generalized model
                model_id = repo.get_model("10.5281/zenodo.6657809", str(model_dir), model_path)
                print(f"  Downloaded model to {model_path}")
        except Exception as e:
            print(f"  Model download failed: {e}")
            # Try alternative: use default model
            model_path = None

        if model_path and os.path.exists(model_path):
            rec_model = models.load_any(model_path)
        else:
            # Fallback: try to use whatever default model is available
            print("  No Arabic model available, skipping Kraken test")
            return {"engine": "kraken", "text": "", "time_sec": 0,
                    "error": "No Arabic model available"}

        # Segment the image
        seg_result = blla.segment(img)

        # Run recognition
        pred_gen = rpred.rpred(rec_model, img, seg_result)
        lines = []
        for record in pred_gen:
            lines.append(record.prediction)

        elapsed = time.time() - start
        full_text = "\n".join(lines)
        return {
            "engine": "kraken (arabic_generalized)",
            "text": full_text,
            "time_sec": round(elapsed, 2),
            "num_lines": len(lines),
            "error": None
        }
    except Exception as e:
        import traceback
        return {
            "engine": "kraken",
            "text": "",
            "time_sec": round(time.time() - start, 2),
            "error": f"{str(e)}\n{traceback.format_exc()}"
        }


def count_arabic_chars(text: str) -> int:
    """Count Arabic Unicode characters in the text."""
    return sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F'
               or '\u08A0' <= c <= '\u08FF' or '\uFB50' <= c <= '\uFDFF'
               or '\uFE70' <= c <= '\uFEFF')


def analyze_result(result: dict, page_name: str, region: str) -> dict:
    """Add analysis metrics to a result."""
    text = result.get("text", "")
    result["page"] = page_name
    result["region"] = region
    result["total_chars"] = len(text)
    result["arabic_chars"] = count_arabic_chars(text)
    result["arabic_ratio"] = round(result["arabic_chars"] / max(1, result["total_chars"]), 3)
    return result


def main():
    all_results = []

    # Select pages to test
    available_pages = [p for p in TEST_PAGES if (DATA_DIR / p).exists()]
    if not available_pages:
        print("ERROR: No test pages found. Download them first.")
        sys.exit(1)

    print(f"Found {len(available_pages)} test pages: {available_pages}")
    print("=" * 70)

    # We'll do detailed tests on 2 pages to keep runtime reasonable
    test_subset = available_pages[:3]

    for page_name in test_subset:
        img_path = str(DATA_DIR / page_name)
        print(f"\n{'='*70}")
        print(f"Processing: {page_name}")
        print(f"{'='*70}")

        # Crop footnote region
        footnote_path = str(DATA_DIR / f"footnote_{page_name}")
        crop_footnote_region(img_path, footnote_path)
        print(f"  Cropped footnote region saved to {footnote_path}")

        # --- Test on full page ---
        print(f"\n  [Full Page Tests]")

        # Tesseract (ara+fra)
        print("  Running Tesseract (ara+fra) on full page...")
        r = test_tesseract(img_path, "ara+fra")
        r = analyze_result(r, page_name, "full_page")
        all_results.append(r)
        print(f"    -> {r['total_chars']} chars, {r['arabic_chars']} Arabic, {r['time_sec']}s")

        # EasyOCR (ar+fr)
        print("  Running EasyOCR (ar+fr) on full page...")
        r = test_easyocr(img_path)
        r = analyze_result(r, page_name, "full_page")
        all_results.append(r)
        print(f"    -> {r['total_chars']} chars, {r['arabic_chars']} Arabic, {r['time_sec']}s")

        # --- Test on footnote crop ---
        print(f"\n  [Footnote Region Tests]")

        # Tesseract (ara only on footnotes)
        print("  Running Tesseract (ara) on footnote region...")
        r = test_tesseract_arabic_only(footnote_path)
        r = analyze_result(r, page_name, "footnote")
        all_results.append(r)
        print(f"    -> {r['total_chars']} chars, {r['arabic_chars']} Arabic, {r['time_sec']}s")

        # Tesseract (ara+fra on footnotes)
        print("  Running Tesseract (ara+fra) on footnote region...")
        r = test_tesseract(footnote_path, "ara+fra")
        r = analyze_result(r, page_name, "footnote")
        all_results.append(r)
        print(f"    -> {r['total_chars']} chars, {r['arabic_chars']} Arabic, {r['time_sec']}s")

        # EasyOCR (ar only on footnotes)
        print("  Running EasyOCR (ar) on footnote region...")
        r = test_easyocr_arabic_only(footnote_path)
        r = analyze_result(r, page_name, "footnote")
        all_results.append(r)
        print(f"    -> {r['total_chars']} chars, {r['arabic_chars']} Arabic, {r['time_sec']}s")

    # --- Kraken test on one page ---
    print(f"\n{'='*70}")
    print("Testing Kraken OCR...")
    print(f"{'='*70}")
    footnote_path = str(DATA_DIR / f"footnote_{test_subset[0]}")
    r = test_kraken(footnote_path)
    r = analyze_result(r, test_subset[0], "footnote")
    all_results.append(r)
    print(f"  -> {r['total_chars']} chars, {r['arabic_chars']} Arabic, {r['time_sec']}s")
    if r.get("error"):
        print(f"  Error: {r['error'][:200]}")

    # Save all results
    results_file = RESULTS_DIR / "ocr_comparison_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {results_file}")

    # Save text outputs for manual inspection
    for r in all_results:
        if r["text"]:
            safe_name = f"{r['page']}_{r['region']}_{r['engine'].replace(' ', '_').replace('(', '').replace(')', '').replace('+', '_')}.txt"
            with open(RESULTS_DIR / safe_name, "w", encoding="utf-8") as f:
                f.write(r["text"])

    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Engine':<30} {'Region':<12} {'Page':<16} {'Total':<8} {'Arabic':<8} {'Ratio':<8} {'Time':<6}")
    print("-" * 90)
    for r in all_results:
        print(f"{r['engine']:<30} {r['region']:<12} {r['page']:<16} {r['total_chars']:<8} {r['arabic_chars']:<8} {r['arabic_ratio']:<8} {r['time_sec']:<6}")

    print(f"\nAll text outputs saved in: {RESULTS_DIR}")
    print("Inspect the .txt files to evaluate OCR quality manually.")


if __name__ == "__main__":
    main()
