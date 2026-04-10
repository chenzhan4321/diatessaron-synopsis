#!/usr/bin/env python3
"""
Test Arabic OCR on Ciasca 1888 PDF pages 133-136.

These pages contain clear Arabic printing with decorative borders.
We test Tesseract OCR with Arabic language using multiple PSM modes
(3, 4, 6) and compare output quality.

Usage:
  uv run scripts/test_arabic_ocr_ciasca.py
"""

import subprocess
import tempfile
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_ROOT / "data" / "diatessaron_arabic_ocr" / "Ciasca 1888_Tatiani Evangeliorum Harmoniae....pdf"
OUT_DIR = PROJECT_ROOT / "data" / "diatessaron_arabic_ocr" / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# PDF pages 133-136 (0-indexed: 132-135)
PAGE_RANGE = range(132, 136)
PSM_MODES = [3, 4, 6]  # different page segmentation modes to test


def extract_pages_as_images(pdf_path: Path, page_indices, dpi: int = 400) -> list[Path]:
    """Render PDF pages to PNG files at given DPI. Higher DPI helps Arabic OCR."""
    doc = fitz.open(str(pdf_path))
    image_paths = []
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    for idx in page_indices:
        page = doc[idx]
        pix = page.get_pixmap(matrix=mat)
        out_path = OUT_DIR / f"page_{idx+1}.png"
        pix.save(str(out_path))
        image_paths.append(out_path)
        print(f"  Extracted page {idx+1} → {out_path}")
    doc.close()
    return image_paths


def run_tesseract(image_path: Path, psm: int = 6) -> str:
    """Run Tesseract OCR with Arabic language on an image."""
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", "ara", "--psm", str(psm)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  WARNING: Tesseract error (psm={psm}): {result.stderr[:200]}")
    return result.stdout


def analyze_arabic_quality(text: str) -> dict:
    """
    Analyze the quality of Arabic OCR output.

    Checks:
    - Total character count
    - Arabic character count and percentage
    - Number of lines
    - Common Arabic words detected
    - Presence of typical Diatessaron references (verse numbers, gospel names)
    """
    total_chars = len(text)
    arabic_chars = sum(1 for c in text if unicodedata.category(c).startswith("Lo")
                       and "ARABIC" in unicodedata.name(c, ""))
    # Also count Arabic marks (diacritics, etc.)
    arabic_marks = sum(1 for c in text if "ARABIC" in unicodedata.name(c, ""))
    lines = [l for l in text.splitlines() if l.strip()]
    non_space_chars = sum(1 for c in text if not c.isspace())

    # Common Arabic words that should appear in the Diatessaron
    common_words = {
        "يسوع": "Jesus",
        "الله": "God",
        "قال": "said",
        "الذي": "who/which",
        "من": "from",
        "في": "in",
        "على": "on",
        "هذا": "this",
        "ان": "that",
        "لهم": "to them",
        "متى": "Matthew (متى)",
        "مرقس": "Mark (مرقس)",
        "لوقا": "Luke (لوقا)",
        "يوحنا": "John (يوحنا)",
    }
    found_words = {}
    for arabic, english in common_words.items():
        count = text.count(arabic)
        if count > 0:
            found_words[english] = count

    return {
        "total_chars": total_chars,
        "non_space_chars": non_space_chars,
        "arabic_chars": arabic_marks,
        "arabic_pct": (arabic_marks / non_space_chars * 100) if non_space_chars else 0,
        "lines": len(lines),
        "found_words": found_words,
    }


def main():
    print("=" * 60)
    print("Testing Arabic OCR on Ciasca 1888 (pages 133-136)")
    print("=" * 60)

    # Step 1: Extract pages as high-resolution images
    print(f"\n[1/3] Extracting PDF pages as 400 DPI images...")
    image_paths = extract_pages_as_images(PDF_PATH, PAGE_RANGE, dpi=400)

    # Step 2: Run Tesseract with different PSM modes
    print(f"\n[2/3] Running Tesseract OCR (Arabic) with PSM modes {PSM_MODES}...")

    results = {}  # (page, psm) → text

    for psm in PSM_MODES:
        print(f"\n  --- PSM {psm} ---")
        for img_path in image_paths:
            page_num = int(img_path.stem.split("_")[1])
            print(f"    OCR page {page_num} (psm={psm})...")
            text = run_tesseract(img_path, psm=psm)
            results[(page_num, psm)] = text

            # Save each result
            out_file = OUT_DIR / f"ocr_p{page_num}_psm{psm}.txt"
            out_file.write_text(text, encoding="utf-8")

    # Step 3: Analyze and compare quality
    print(f"\n[3/3] Analyzing OCR quality...")
    print(f"\n{'='*70}")
    print(f"{'Page':>6} {'PSM':>4} {'Lines':>6} {'Chars':>7} {'Arabic%':>8} {'Key Words':>10}")
    print(f"{'-'*70}")

    best_by_page = {}  # page → (psm, score)

    for psm in PSM_MODES:
        for img_path in image_paths:
            page_num = int(img_path.stem.split("_")[1])
            text = results[(page_num, psm)]
            stats = analyze_arabic_quality(text)
            word_count = sum(stats["found_words"].values())

            print(f"{page_num:>6} {psm:>4} {stats['lines']:>6} "
                  f"{stats['non_space_chars']:>7} {stats['arabic_pct']:>7.1f}% "
                  f"{word_count:>10}")

            # Score: combine Arabic percentage and word detection
            score = stats["arabic_pct"] * 0.5 + word_count * 2
            if page_num not in best_by_page or score > best_by_page[page_num][1]:
                best_by_page[page_num] = (psm, score)

    print(f"{'='*70}")

    # Report best PSM per page
    print(f"\nBest PSM mode per page:")
    best_psm_overall = {}
    for page_num in sorted(best_by_page):
        psm, score = best_by_page[page_num]
        print(f"  Page {page_num}: PSM {psm} (score={score:.1f})")
        best_psm_overall[psm] = best_psm_overall.get(psm, 0) + 1

    most_common_psm = max(best_psm_overall, key=best_psm_overall.get)
    print(f"\n  Overall best PSM: {most_common_psm}")

    # Show detected words for best configuration
    print(f"\nDetected Arabic words (best PSM per page):")
    for page_num in sorted(best_by_page):
        psm, _ = best_by_page[page_num]
        text = results[(page_num, psm)]
        stats = analyze_arabic_quality(text)
        if stats["found_words"]:
            print(f"  Page {page_num} (PSM {psm}):")
            for word, count in sorted(stats["found_words"].items(),
                                       key=lambda x: -x[1]):
                print(f"    {word}: {count}")

    # Save combined best output
    print(f"\nSaving combined best output...")
    combined = []
    for page_num in sorted(best_by_page):
        psm, _ = best_by_page[page_num]
        text = results[(page_num, psm)]
        combined.append(f"=== Page {page_num} (PSM {psm}) ===\n{text}")

    combined_path = OUT_DIR / "arabic_ocr_best_combined.txt"
    combined_path.write_text("\n".join(combined), encoding="utf-8")
    print(f"  → {combined_path}")

    # Show sample of best output for first page
    first_page = sorted(best_by_page)[0]
    psm, _ = best_by_page[first_page]
    text = results[(first_page, psm)]
    sample_lines = text.splitlines()[:15]
    print(f"\nSample output (page {first_page}, PSM {psm}, first 15 lines):")
    print("-" * 50)
    for line in sample_lines:
        print(f"  {line}")
    print("-" * 50)

    # Quality assessment
    print(f"\n{'='*60}")
    print("QUALITY ASSESSMENT")
    print(f"{'='*60}")

    all_arabic_pcts = []
    all_word_counts = []
    for page_num in sorted(best_by_page):
        psm, _ = best_by_page[page_num]
        text = results[(page_num, psm)]
        stats = analyze_arabic_quality(text)
        all_arabic_pcts.append(stats["arabic_pct"])
        all_word_counts.append(sum(stats["found_words"].values()))

    avg_arabic = sum(all_arabic_pcts) / len(all_arabic_pcts) if all_arabic_pcts else 0
    avg_words = sum(all_word_counts) / len(all_word_counts) if all_word_counts else 0

    print(f"  Average Arabic char percentage: {avg_arabic:.1f}%")
    print(f"  Average key words detected:     {avg_words:.1f} per page")

    if avg_arabic > 70:
        quality = "GOOD - Most characters are Arabic"
    elif avg_arabic > 50:
        quality = "MODERATE - Majority of characters are Arabic"
    elif avg_arabic > 30:
        quality = "FAIR - Significant Arabic content detected"
    else:
        quality = "POOR - Most characters not recognized as Arabic"

    print(f"  Overall quality:                {quality}")
    print(f"\n  Note: The OCR captures character shapes but Arabic script")
    print(f"  recognition accuracy (correct words vs. garbled) requires")
    print(f"  manual inspection of the output files in {OUT_DIR}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
