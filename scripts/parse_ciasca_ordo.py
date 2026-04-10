#!/usr/bin/env python3
"""
Parse Ciasca 1888 "ORDO DIATESSARI IN VERSIONE ARABICA" (PDF pages 122-129)
into structured data mapping each Caput (chapter I-LV) to canonical gospel verses.

Pipeline:
  1. Extract PDF pages 122-129 as high-res images via PyMuPDF
  2. Run Tesseract OCR (Latin/English mode) on each page
  3. Parse OCR text to extract chapter→verse mappings
  4. Save as TSV and JSON

Usage:
  uv run scripts/parse_ciasca_ordo.py
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_ROOT / "data" / "diatessaron_arabic_ocr" / "Ciasca 1888_Tatiani Evangeliorum Harmoniae....pdf"
OUT_DIR = PROJECT_ROOT / "data" / "diatessaron_ciasca"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# PDF pages 122-129 (0-indexed: 121-128)
PAGE_RANGE = range(121, 129)

# ── Gospel abbreviation normalization ──────────────────────────────────────
# Ciasca uses Latin abbreviations: Matth., Marc., Luc., Joan.
# OCR may produce variants; we normalize to standard short forms.
GOSPEL_MAP = {
    "matth": "Matt",
    "matt": "Matt",
    "marc": "Mark",
    "luc": "Luke",
    "joan": "John",
    "joa": "John",
    "ion": "John",   # OCR misread of Joan
    "ioan": "John",  # alternate spelling
}


def normalize_gospel(raw: str) -> str | None:
    """Map an OCR'd gospel abbreviation to a standard name."""
    cleaned = raw.strip().rstrip(".").lower()
    for prefix, standard in GOSPEL_MAP.items():
        if cleaned.startswith(prefix):
            return standard
    return None


def extract_pages_as_images(pdf_path: Path, page_indices, dpi: int = 300) -> list[Path]:
    """Render PDF pages to temporary PNG files at given DPI."""
    doc = fitz.open(str(pdf_path))
    image_paths = []
    zoom = dpi / 72  # default PDF resolution is 72 dpi
    mat = fitz.Matrix(zoom, zoom)
    for idx in page_indices:
        page = doc[idx]
        pix = page.get_pixmap(matrix=mat)
        tmp = tempfile.NamedTemporaryFile(suffix=f"_p{idx+1}.png", delete=False)
        pix.save(tmp.name)
        image_paths.append(Path(tmp.name))
        print(f"  Extracted page {idx+1} → {tmp.name}")
    doc.close()
    return image_paths


def run_tesseract(image_path: Path) -> str:
    """Run Tesseract OCR on an image and return the text."""
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", "eng", "--psm", "6"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  WARNING: Tesseract error on {image_path}: {result.stderr[:200]}")
    return result.stdout


def parse_ordo_text(all_text: str) -> list[dict]:
    """
    Parse the combined OCR text of the ORDO table.

    Key challenge: the original PDF has 3 columns, so Tesseract linearizes
    them into single lines where CAP headers and gospel references from
    different columns appear on the same line.

    Strategy:
      1. Join all text into one stream
      2. Find CAP markers and gospel references by position
      3. A gospel reference = gospel name + everything until next gospel/CAP
      4. Assign each reference to the most recently seen CAP

    Returns a list of dicts with chapter number and entries.
    """
    # Clean the text: remove noise lines
    cleaned_lines = []
    for line in all_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[-—]+\s*\d+\s*[-—]+$", line):
            continue
        if "ORDO" in line.upper() and "DIATESS" in line.upper():
            continue
        if "digitized" in line.lower() or "google" in line.lower():
            continue
        if "IMPRIMATUR" in line.upper():
            continue
        if "Raphael" in line or "Julius Lenti" in line:
            continue
        cleaned_lines.append(line)

    text = " ".join(cleaned_lines)

    # Tokens: (position, type, value)
    tokens = []

    # ── CAP markers ──
    # OCR variants: Car, Cap, CAP, Gar, Carp, Cay, etc.
    # Match "Car. XXXV." or "Cap. XIV." etc.
    # Handle OCR garbling: "Il" for "III", "Vil" for "VII",
    #   "XXKV" for "XXXV", etc.
    cap_re = re.compile(
        r"\b(?:C[Aa][PpRrYy]|GAP|Gar|Carp)\s*[.,:]?\s*"
        r"([IVXLC][IVXLCKl]*)\b",  # K→X, l→I in OCR
        re.IGNORECASE
    )
    for m in cap_re.finditer(text):
        # Normalize OCR errors in roman numerals
        roman_str = m.group(1).upper()
        roman_str = roman_str.replace("K", "X")
        # "Il" at end → likely "III" (Tesseract reads III as Il)
        # But be careful: "Il" could also be "II"
        # We handle this by trying both interpretations later
        try:
            num = roman_to_int(roman_str)
            if 1 <= num <= 55:
                tokens.append((m.start(), "cap", num))
        except Exception:
            pass

    # Special handling for known OCR garbling of roman numerals.
    # Tesseract frequently misreads:
    #   III → "Il" (lowercase L looks like I)
    #   VII → "Vil" (V+I+I → V+i+l)
    #   XXXVIII → "XXXVI" (losing trailing "II")
    # We manually correct these based on observed OCR output.
    special_caps = [
        (r"\bCar\.\s*Il\b", 3),          # "Car. Il" → III
        (r"\bCar\.\s*Vil\b", 7),          # "Car. Vil" → VII
        (r"\bCar,\s*XXXVI\b", 38),        # "Car, XXXVI" → XXXVIII
    ]
    for pat, num in special_caps:
        for m in re.finditer(pat, text, re.IGNORECASE):
            tokens.append((m.start(), "cap", num))

    # Fix duplicate chapter numbers: when OCR produces the same number
    # twice (e.g., two "XXXII"), the second is likely the next chapter
    # (XXXIII). We detect this after sorting and correct.
    # This is handled in post-processing below.

    # ── Gospel references ──
    # Match gospel name followed by everything up to the next gospel/CAP/end.
    # Gospel names in OCR: Matth, Matt, Nath, Marc, Mare, Luc, Lue, Joan, Ioan
    # The reference text after the name contains chapter (roman, often garbled)
    # and verse numbers.
    gospel_re = re.compile(
        r"\b(Matth?|Nath|Marc|Mare|Luc|Lue|Joan|Ioan)\b",
        re.IGNORECASE
    )
    # Boundary pattern: next gospel name, or CAP marker, or end of string
    boundary_re = re.compile(
        r"\b(?:Matth?|Nath|Marc|Mare|Luc|Lue|Joan|Ioan"
        r"|C[Aa][PpRrYy]|GAP|Gar|Carp)\b",
        re.IGNORECASE
    )

    gospel_positions = list(gospel_re.finditer(text))
    for i, m in enumerate(gospel_positions):
        gospel_raw = m.group(1)
        start = m.end()
        # Find where this reference ends (next gospel or CAP marker)
        rest = text[start:]
        boundary_match = boundary_re.search(rest)
        if boundary_match:
            ref_text = rest[:boundary_match.start()]
        else:
            ref_text = rest

        # Clean the reference text
        ref_text = ref_text.strip().strip(".,;:*°>< ").strip()
        # Remove leading punctuation like ". " or ", "
        ref_text = re.sub(r"^[.,;:\s]+", "", ref_text)

        if not ref_text or len(ref_text) < 3:
            continue

        gospel = normalize_gospel(gospel_raw)
        if gospel is None:
            gospel = f"?{gospel_raw}"

        tokens.append((m.start(), "ref", (gospel, ref_text)))

    # Sort all tokens by position
    tokens.sort(key=lambda x: x[0])

    # Remove duplicate CAP entries at same/nearby positions.
    # Special patterns (appended later) should override general patterns,
    # so we process in reverse order and keep the LAST token at each position
    # (which is the special/corrected one).
    seen_cap_ranges: dict[int, int] = {}  # position → index in deduped
    deduped = []
    for pos, ttype, value in tokens:
        if ttype == "cap":
            # Check if there's already a cap within 5 chars of this position
            replaced = False
            for existing_pos, existing_idx in list(seen_cap_ranges.items()):
                if abs(pos - existing_pos) < 10:
                    # Replace with this one (later entries = special patterns = better)
                    deduped[existing_idx] = (pos, ttype, value)
                    replaced = True
                    break
            if not replaced:
                seen_cap_ranges[pos] = len(deduped)
                deduped.append((pos, ttype, value))
        else:
            deduped.append((pos, ttype, value))
    tokens = deduped

    # Post-process: fix duplicate chapter numbers.
    # When OCR produces the same CAP number twice, the second occurrence
    # is likely N+1 (e.g., two "XXXII" means the second is XXXIII).
    # Similarly for any duplicated number where N+1 is missing.
    cap_tokens = [(i, pos, val) for i, (pos, ttype, val) in enumerate(tokens) if ttype == "cap"]
    seen_caps = set()
    for idx, (token_idx, pos, val) in enumerate(cap_tokens):
        if val in seen_caps:
            # This is a duplicate — try N+1
            new_val = val + 1
            if new_val not in seen_caps and new_val <= 55:
                tokens[token_idx] = (pos, "cap", new_val)
                seen_caps.add(new_val)
            else:
                # Try N+2 if N+1 also taken
                new_val = val + 2
                if new_val not in seen_caps and new_val <= 55:
                    tokens[token_idx] = (pos, "cap", new_val)
                    seen_caps.add(new_val)
        else:
            seen_caps.add(val)

    # Build chapters by assigning refs to the most recent cap
    chapters_dict: dict[int, list[dict]] = {}
    current_cap = None

    for pos, ttype, value in tokens:
        if ttype == "cap":
            current_cap = value
            if current_cap not in chapters_dict:
                chapters_dict[current_cap] = []
        elif ttype == "ref" and current_cap is not None:
            gospel, reference = value
            chapters_dict[current_cap].append({
                "gospel": gospel,
                "reference": reference
            })

    # Convert to sorted list
    chapters = []
    for cap_num in sorted(chapters_dict.keys()):
        chapters.append({
            "chapter": cap_num,
            "entries": chapters_dict[cap_num]
        })

    return chapters


def roman_to_int(s: str) -> int:
    """Convert a Roman numeral string to integer."""
    roman_values = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000
    }
    total = 0
    prev = 0
    for ch in reversed(s.upper()):
        val = roman_values.get(ch, 0)
        if val < prev:
            total -= val
        else:
            total += val
        prev = val
    return total


def save_tsv(chapters: list[dict], path: Path):
    """Save as TSV: chapter_number, gospel, reference."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("chapter\tgospel\treference\n")
        for ch in chapters:
            for entry in ch["entries"]:
                f.write(f"{ch['chapter']}\t{entry['gospel']}\t{entry['reference']}\n")
    print(f"Saved TSV → {path}")


def save_json(chapters: list[dict], path: Path):
    """Save as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON → {path}")


def main():
    print("=" * 60)
    print("Parsing Ciasca 1888 ORDO DIATESSARI IN VERSIONE ARABICA")
    print("=" * 60)

    # Step 1: Extract pages as images
    print(f"\n[1/4] Extracting PDF pages {PAGE_RANGE.start+1}-{PAGE_RANGE.stop} as images (300 DPI)...")
    image_paths = extract_pages_as_images(PDF_PATH, PAGE_RANGE, dpi=300)

    # Step 2: Run OCR on each page
    print(f"\n[2/4] Running Tesseract OCR on {len(image_paths)} pages...")
    all_text = ""
    for img in image_paths:
        print(f"  OCR: {img.name}")
        text = run_tesseract(img)
        all_text += text + "\n"

    # Save raw OCR output for debugging
    raw_path = OUT_DIR / "ciasca_ordo_raw_ocr.txt"
    raw_path.write_text(all_text, encoding="utf-8")
    print(f"  Raw OCR saved → {raw_path}")

    # Step 3: Parse structured data
    print(f"\n[3/4] Parsing chapter→verse mappings...")
    chapters = parse_ordo_text(all_text)
    print(f"  Found {len(chapters)} chapters")
    for ch in chapters:
        print(f"    CAP. {ch['chapter']:>3}: {len(ch['entries'])} entries")

    # Step 4: Save outputs
    print(f"\n[4/4] Saving results...")
    save_tsv(chapters, OUT_DIR / "ciasca_ordo.tsv")
    save_json(chapters, OUT_DIR / "ciasca_ordo.json")

    # Summary
    total_entries = sum(len(ch["entries"]) for ch in chapters)
    gospels_seen = set()
    unknown_count = 0
    for ch in chapters:
        for e in ch["entries"]:
            if e["gospel"].startswith("?"):
                unknown_count += 1
            else:
                gospels_seen.add(e["gospel"])

    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Chapters parsed:  {len(chapters)} / 55 expected")
    print(f"  Total entries:    {total_entries}")
    print(f"  Gospels found:    {', '.join(sorted(gospels_seen))}")
    if unknown_count:
        print(f"  Unrecognized:     {unknown_count} (marked with '?' prefix)")
    if len(chapters) < 55:
        print(f"  WARNING: Expected 55 chapters but only found {len(chapters)}.")
        print(f"           OCR quality may have caused some CAP headers to be missed.")
    print(f"{'=' * 60}")

    # Cleanup temp images
    for img in image_paths:
        img.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
