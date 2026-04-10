"""
Tesseract OCR on all Arabic pages of Ciasca 1888.
Runs tesseract with -l ara --psm 6 on pages 0133–0348 (216 pages).
"""

import subprocess
import time
from pathlib import Path

# Paths
PROJECT = Path(__file__).resolve().parent.parent
PAGES_DIR = PROJECT / "data" / "diatessaron_arabic_ocr" / "ciasca_pages"
OUT_DIR = PROJECT / "data" / "diatessaron_arabic_ocr" / "results" / "ciasca_tesseract"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TESSERACT = "/opt/homebrew/bin/tesseract"
TESSDATA = "/opt/homebrew/share/tessdata/"

# Collect all page images (page_0133.png .. page_0348.png)
pages = sorted(PAGES_DIR.glob("page_*.png"))
print(f"Found {len(pages)} pages to OCR with Tesseract")

t0 = time.time()
combined_lines = []

for i, page_path in enumerate(pages):
    page_num = page_path.stem.replace("page_", "")  # e.g. "0133"
    out_base = OUT_DIR / f"page_{page_num}_tesseract"  # tesseract appends .txt

    # Run tesseract: output base (no .txt extension), language=ara, psm=6 (uniform block)
    cmd = [
        TESSERACT, str(page_path), str(out_base),
        "-l", "ara",
        "--psm", "6",
        "--tessdata-dir", TESSDATA,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    out_file = Path(str(out_base) + ".txt")
    if result.returncode != 0:
        print(f"  [ERROR] page {page_num}: {result.stderr.strip()}")
    elif out_file.exists():
        text = out_file.read_text(encoding="utf-8")
        # Add page header for combined output
        combined_lines.append(f"===== PAGE {page_num} =====")
        combined_lines.append(text)

    # Progress every 10 pages
    if (i + 1) % 10 == 0 or (i + 1) == len(pages):
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed
        remaining = (len(pages) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i+1}/{len(pages)}] elapsed {elapsed:.0f}s, ~{remaining:.0f}s remaining")

# Save combined output
combined_path = OUT_DIR / "ciasca_arabic_tesseract_combined.txt"
combined_path.write_text("\n".join(combined_lines), encoding="utf-8")
print(f"\nDone! Combined output: {combined_path}")
print(f"Total time: {time.time() - t0:.1f}s")
