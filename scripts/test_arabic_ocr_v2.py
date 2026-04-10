"""
Extended OCR tests on Diatessaron Arabic text.

We focus on Tesseract (best performer so far) with different settings,
and also try using the Archive.org pre-existing ABBYY/full-text OCR data.

Key finding from v1: The Marmardji 1935 edition has Arabic primarily in
the critical apparatus (footnotes), mixed with Syriac and French text.
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

DATA_DIR = Path("/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_arabic_ocr")
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def preprocess_image(img_path: str, output_path: str, method: str = "default") -> str:
    """
    Preprocess image to improve OCR quality.
    Historical book scans benefit from contrast enhancement and binarization.
    """
    img = Image.open(img_path)

    if method == "sharpen_contrast":
        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

    elif method == "binarize":
        # Convert to grayscale then binarize (Otsu-like)
        img = img.convert('L')
        # Simple threshold
        threshold = 128
        img = img.point(lambda x: 255 if x > threshold else 0, '1')

    elif method == "grayscale_sharp":
        img = img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)

    img.save(output_path)
    return output_path


def run_tesseract(img_path: str, lang: str, psm: int = 6, extra_args: list = None) -> dict:
    """Run Tesseract with specific settings."""
    cmd = ["tesseract", img_path, "stdout", "-l", lang, "--psm", str(psm)]
    if extra_args:
        cmd.extend(extra_args)
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        elapsed = time.time() - start
        return {
            "engine": f"tesseract (lang={lang}, psm={psm})",
            "text": result.stdout.strip(),
            "time_sec": round(elapsed, 2),
            "error": result.stderr.strip() if result.returncode != 0 else None
        }
    except Exception as e:
        return {"engine": f"tesseract (lang={lang}, psm={psm})", "text": "", "time_sec": 0, "error": str(e)}


def count_arabic_chars(text: str) -> int:
    """Count Arabic script characters."""
    return sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F'
               or '\u08A0' <= c <= '\u08FF' or '\uFB50' <= c <= '\uFDFF'
               or '\uFE70' <= c <= '\uFEFF')


def count_french_chars(text: str) -> int:
    """Count Latin characters (proxy for French)."""
    return sum(1 for c in text if c.isalpha() and ord(c) < 256)


def main():
    # Use page n300 footnote as primary test (good mix of Arabic + French + Syriac)
    footnote_path = str(DATA_DIR / "footnote_page_n300.jpg")
    full_page_path = str(DATA_DIR / "page_n300.jpg")
    page_400_fn = str(DATA_DIR / "footnote_page_n400.jpg")

    # Create footnote crop for page 400 if not exists
    if not os.path.exists(page_400_fn):
        img = Image.open(str(DATA_DIR / "page_n400.jpg"))
        w, h = img.size
        cropped = img.crop((0, int(h * 0.70), w, h))
        cropped.save(page_400_fn)

    results = []

    print("=" * 70)
    print("PART 1: Tesseract with different language combinations")
    print("=" * 70)

    # Test different language settings on footnote
    lang_combos = [
        "ara",
        "ara+fra",
        "fra+ara",
        "ara+syr",       # Arabic + Syriac if available
        "ara+fra+syr",   # All three if available
    ]

    for lang in lang_combos:
        print(f"\n  Testing: {lang}")
        r = run_tesseract(footnote_path, lang)
        if r.get("error") and "Failed loading language" in str(r["error"]):
            print(f"    SKIPPED (language not available)")
            continue
        arabic = count_arabic_chars(r["text"])
        french = count_french_chars(r["text"])
        print(f"    {len(r['text'])} chars total, {arabic} Arabic, {french} French, {r['time_sec']}s")
        r["arabic_chars"] = arabic
        r["french_chars"] = french
        results.append(r)

    print("\n" + "=" * 70)
    print("PART 2: Tesseract with different PSM modes")
    print("=" * 70)

    # PSM modes relevant for our mixed-script pages:
    # 3 = Fully automatic page segmentation, but no OSD
    # 4 = Assume a single column of text of variable sizes
    # 6 = Assume a single uniform block of text (default for api)
    # 11 = Sparse text. Find as much text as possible in no particular order
    # 12 = Sparse text with OSD
    for psm in [3, 4, 6, 11]:
        print(f"\n  Testing: PSM {psm}")
        r = run_tesseract(footnote_path, "ara+fra", psm=psm)
        arabic = count_arabic_chars(r["text"])
        french = count_french_chars(r["text"])
        print(f"    {len(r['text'])} chars total, {arabic} Arabic, {french} French, {r['time_sec']}s")
        r["arabic_chars"] = arabic
        r["french_chars"] = french
        results.append(r)

    print("\n" + "=" * 70)
    print("PART 3: Image preprocessing effects")
    print("=" * 70)

    for method in ["sharpen_contrast", "binarize", "grayscale_sharp"]:
        preprocessed_path = str(DATA_DIR / f"preprocessed_{method}_footnote.jpg")
        preprocess_image(footnote_path, preprocessed_path, method)
        print(f"\n  Testing: {method}")
        r = run_tesseract(preprocessed_path, "ara+fra")
        arabic = count_arabic_chars(r["text"])
        french = count_french_chars(r["text"])
        print(f"    {len(r['text'])} chars total, {arabic} Arabic, {french} French, {r['time_sec']}s")
        r["engine"] += f" [{method}]"
        r["arabic_chars"] = arabic
        r["french_chars"] = french
        results.append(r)

    print("\n" + "=" * 70)
    print("PART 4: Best configuration on multiple pages")
    print("=" * 70)

    # Based on above tests, use best config on all footnote pages
    best_lang = "ara+fra"
    best_psm = 6  # Will update based on Part 2 results

    footnote_files = sorted(DATA_DIR.glob("footnote_page_*.jpg"))
    for fn_file in footnote_files:
        print(f"\n  Processing: {fn_file.name}")
        r = run_tesseract(str(fn_file), best_lang, psm=best_psm)
        arabic = count_arabic_chars(r["text"])
        french = count_french_chars(r["text"])
        print(f"    {len(r['text'])} chars total, {arabic} Arabic, {french} French")
        # Save individual output
        out_file = RESULTS_DIR / f"{fn_file.stem}_best_tesseract.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(r["text"])

    # Save all results
    results_file = RESULTS_DIR / "ocr_extended_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n\nResults saved to {results_file}")

    # Now also check if Archive.org has pre-existing OCR data
    print("\n" + "=" * 70)
    print("PART 5: Checking Archive.org pre-existing OCR")
    print("=" * 70)
    print("  Attempting to download full text from Archive.org...")
    import urllib.request
    try:
        url = "https://archive.org/download/diatessarondetat0000tati/diatessarondetat0000tati_djvu.txt"
        txt_path = str(DATA_DIR / "archive_org_fulltext.txt")
        if not os.path.exists(txt_path):
            urllib.request.urlretrieve(url, txt_path)
            print(f"  Downloaded full text to {txt_path}")
        else:
            print(f"  Full text already exists at {txt_path}")

        with open(txt_path, "r", encoding="utf-8") as f:
            full_text = f.read()
        total_len = len(full_text)
        arabic = count_arabic_chars(full_text)
        french = count_french_chars(full_text)
        print(f"  Full text: {total_len} chars, {arabic} Arabic ({arabic*100/max(1,total_len):.1f}%), {french} French ({french*100/max(1,total_len):.1f}%)")

        # Extract a sample of the Arabic text
        # Look for lines with high Arabic content
        arabic_lines = []
        for line in full_text.split('\n'):
            ar_count = count_arabic_chars(line)
            if ar_count > 5:
                arabic_lines.append((ar_count, line))

        arabic_lines.sort(key=lambda x: -x[0])
        print(f"\n  Top 10 lines with most Arabic characters:")
        for count, line in arabic_lines[:10]:
            print(f"    [{count} ar chars] {line[:100]}")

        # Save sample
        sample_path = RESULTS_DIR / "archive_org_arabic_sample.txt"
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write("# Arabic text lines from Archive.org OCR\n")
            f.write(f"# Total: {len(arabic_lines)} lines with Arabic characters\n\n")
            for count, line in arabic_lines[:100]:
                f.write(f"[{count}] {line}\n")
        print(f"\n  Arabic sample saved to {sample_path}")

    except Exception as e:
        print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
