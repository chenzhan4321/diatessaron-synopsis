"""
Test Kraken OCR with the Arabic generalized model on Diatessaron footnotes.
"""
import os
import sys
import time
from pathlib import Path
from PIL import Image

DATA_DIR = Path("/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_arabic_ocr")
RESULTS_DIR = DATA_DIR / "results"
MODEL_PATH = DATA_DIR / "kraken_models" / "arabic_generalized.mlmodel"

# Test on footnote crops
test_files = sorted(DATA_DIR.glob("footnote_*.jpg"))

if not MODEL_PATH.exists():
    print(f"ERROR: Model not found at {MODEL_PATH}")
    sys.exit(1)

print(f"Loading Kraken Arabic model from {MODEL_PATH}")

from kraken import blla, rpred
from kraken.lib import models

rec_model = models.load_any(str(MODEL_PATH))
print(f"Model loaded successfully")

for img_file in test_files:
    print(f"\n{'='*60}")
    print(f"Processing: {img_file.name}")
    print(f"{'='*60}")

    img = Image.open(img_file)
    start = time.time()

    try:
        # Segment the image
        seg_result = blla.segment(img)
        print(f"  Segmentation found {len(seg_result.lines)} lines")

        # Run recognition
        pred_gen = rpred.rpred(rec_model, img, seg_result)
        lines = []
        for record in pred_gen:
            lines.append(record.prediction)
            print(f"  Line: {record.prediction}")

        elapsed = time.time() - start
        full_text = "\n".join(lines)
        print(f"\n  Total time: {elapsed:.2f}s")
        print(f"  Total lines: {len(lines)}")

        # Save output
        out_file = RESULTS_DIR / f"{img_file.stem}_kraken_arabic.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"  Saved to {out_file}")

    except Exception as e:
        import traceback
        print(f"  ERROR: {e}")
        traceback.print_exc()
