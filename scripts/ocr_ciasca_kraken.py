"""
Kraken OCR on all Arabic pages of Ciasca 1888.
Uses the all_arabic_scripts model on pages 0133–0348 (216 pages).
Kraken CLI: kraken -i input.png output.txt segment -bl ocr -m <model>
"""

import subprocess
import time
from pathlib import Path

# Paths
PROJECT = Path(__file__).resolve().parent.parent
PAGES_DIR = PROJECT / "data" / "diatessaron_arabic_ocr" / "ciasca_pages"
OUT_DIR = PROJECT / "data" / "diatessaron_arabic_ocr" / "results" / "ciasca_kraken"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Kraken model path (all_arabic_scripts, DOI 10.5281/zenodo.7050270)
MODEL = Path.home() / "Library" / "Application Support" / "htrmopo" / "230a3928-733e-5524-baa5-f89ba9b9eb70" / "all_arabic_scripts.mlmodel"
assert MODEL.exists(), f"Model not found: {MODEL}"

# Collect all page images
pages = sorted(PAGES_DIR.glob("page_*.png"))
print(f"Found {len(pages)} pages to OCR with Kraken")

t0 = time.time()
combined_lines = []
errors = 0

for i, page_path in enumerate(pages):
    page_num = page_path.stem.replace("page_", "")  # e.g. "0133"
    out_file = OUT_DIR / f"page_{page_num}_kraken.txt"

    # kraken -i input output segment -bl ocr -m model
    cmd = [
        "kraken",
        "-i", str(page_path), str(out_file),
        "segment", "-bl",
        "ocr", "-m", str(MODEL),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  [ERROR] page {page_num}: {result.stderr.strip()[:200]}")
        errors += 1
    elif out_file.exists():
        text = out_file.read_text(encoding="utf-8")
        combined_lines.append(f"===== PAGE {page_num} =====")
        combined_lines.append(text)

    # Progress every 10 pages
    if (i + 1) % 10 == 0 or (i + 1) == len(pages):
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed
        remaining = (len(pages) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i+1}/{len(pages)}] elapsed {elapsed:.0f}s, ~{remaining:.0f}s remaining")

# Save combined output
combined_path = OUT_DIR / "ciasca_arabic_kraken_combined.txt"
combined_path.write_text("\n".join(combined_lines), encoding="utf-8")
print(f"\nDone! Combined output: {combined_path}")
print(f"Total time: {time.time() - t0:.1f}s, errors: {errors}/{len(pages)}")
