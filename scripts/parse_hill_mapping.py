"""
Parse Hill 1894 English translation of the Arabic Diatessaron.

The OCR text has a two-margin system:
  Left margin:  Diatessaron section (1-55) and verse number
  Right margin: Canonical gospel reference (Mt./Mk./Lu./Jn. chapter verse)

Format rules (from examining the printed book):
  - When a new SECTION begins, the line starts with "section_num verse_num"
    e.g., "4 1 Christ. No man hath seen God..." means section 4, verse 1
  - Within a section, subsequent verses start with just the verse number
    e.g., "2 And this is the witness..." means verse 2 (same section)
  - Right margin shows gospel reference: "Jn. 1 18" or „ 19 (ditto = same gospel)
  - The section number only appears on the FIRST verse of each new section

Key OCR artifacts:
  - „ = ditto mark (same gospel book as previous line)
  - Page headers like "THE DIATESSARON. 55" or "56 THE DIATESSARON."
  - Footnote markers (^ or superscript numbers)
  - Jn/ = Jn. (OCR confusion of period and slash)
"""

import re
import json
import csv
from pathlib import Path
from collections import Counter

# Paths
BASE = Path("/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian")
RAW_FILE = BASE / "data" / "diatessaron_hill" / "hill_1894_raw_ocr.txt"
TSV_FILE = BASE / "data" / "diatessaron_hill" / "hill_mapping.tsv"
JSON_FILE = BASE / "data" / "diatessaron_hill" / "hill_mapping.json"


def load_raw_text():
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        return f.readlines()


def is_page_header(line):
    """Detect page headers like 'THE DIATESSARON. 55' or '56 THE DIATESSARON.'"""
    stripped = line.strip()
    if re.match(r"^\d+\s+THE\s+DIATESSARO", stripped):
        return True
    if re.match(r"^THE\s+DIATESSARO[NK][\.,]?\s*\d*$", stripped):
        return True
    return False


def is_skip_line(line):
    """Check if a line should be skipped (footnotes, page headers, etc.)."""
    stripped = line.strip()
    if not stripped:
        return True
    if is_page_header(line):
        return True
    # Footnote lines
    if re.match(r"^\^", stripped):
        return True
    # Standalone page numbers
    if re.match(r"^['']?\s*\d{1,3}\s*$", stripped):
        return True
    # Footnote explanations: "1 Or, ..." "2 Lit. ..." etc.
    if re.match(r"^\d\s+(Or,|Lit\.|Omitting|Repeated|Arabic|Kepeated|cf\.|The clause|Throughout)", stripped):
        return True
    # Lines that are just footnote references
    if re.match(r"^['']$", stripped):
        return True
    return False


def normalize_gospel(abbrev):
    """Normalize gospel abbreviation."""
    abbrev = abbrev.strip().rstrip("./,;:^'*")
    mapping = {
        "mt": "Matt", "mt.": "Matt",
        "mk": "Mark", "mk.": "Mark",
        "lu": "Luke", "lu.": "Luke",
        "jn": "John", "jn.": "John", "jn/": "John",
    }
    return mapping.get(abbrev.lower(), abbrev)


def parse_verse_number(s):
    """Parse a verse number (arabic or roman numeral from OCR)."""
    s = s.strip().rstrip("^'\".,;:*")
    try:
        return int(s)
    except ValueError:
        pass
    roman = {
        "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
        "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
    }
    return roman.get(s.lower().strip(), None)


def find_text_boundaries(lines):
    """Find start and end line indices of the Diatessaron text."""
    start = None
    end = None
    for i, line in enumerate(lines):
        if "In the beginning was the Word" in line and start is None:
            if i > 2000:  # Skip intro
                start = i
        if "contain the books that must be written" in line:
            end = i
    return start, end


# Regex to match gospel references at end of line
# Captures: gospel_abbrev, chapter, verse
# Handles trailing OCR artifacts like ^, ', *, t-, etc.
GOSPEL_REF_RE = re.compile(
    r"\s+(Mt\.?|Mk\.?\*?|Lu\.?|Jn\.?[/]?)\s+(\d+)\s+(\d+|[ivx]+)\s*[\^'\"*]*\s*[a-z\-]*\s*$"
)

# Ditto reference at end of line: „ verse_num
DITTO_REF_RE = re.compile(
    r"\s+„\s+(\d+|[ivx]+)\s*[\^'\"*]*\s*$"
)

# Ditto with chapter change: „ chapter verse
DITTO_CHAP_RE = re.compile(
    r"\s+„\s+(\d+)\s+(\d+|[ivx]+)\s*[\^'\"*]*\s*$"
)

# Section + verse at start: captures section_num and verse_num
# Section only appears at the FIRST verse of a new section
SECTION_VERSE_RE = re.compile(r"^(\d{1,2})\s+(\d{1,3})\s+")

# Verse only at start
VERSE_RE = re.compile(r"^(\d{1,3})\s+")


def extract_right_margin(line):
    """
    Extract gospel reference from right margin.
    Returns (gospel, chapter, verse, text_before_ref) or None.
    """
    stripped = line.strip()

    # Try full gospel reference
    m = GOSPEL_REF_RE.search(stripped)
    if m:
        gospel = normalize_gospel(m.group(1))
        chapter = int(m.group(2))
        verse = parse_verse_number(m.group(3))
        text = stripped[:m.start()].strip()
        return gospel, chapter, verse, text

    # Try ditto with chapter: „ chapter verse
    m = DITTO_CHAP_RE.search(stripped)
    if m:
        chapter = int(m.group(1))
        verse = parse_verse_number(m.group(2))
        text = stripped[:m.start()].strip()
        return None, chapter, verse, text  # None = use previous gospel

    # Try simple ditto: „ verse
    m = DITTO_REF_RE.search(stripped)
    if m:
        verse = parse_verse_number(m.group(1))
        text = stripped[:m.start()].strip()
        return None, None, verse, text  # None = use previous gospel+chapter

    return None


def extract_left_margin(line):
    """
    Extract section and verse from left margin.
    Returns (section, verse, remainder) or (None, verse, remainder) or None.
    """
    stripped = line.strip()

    # Try section + verse (new section beginning)
    m = SECTION_VERSE_RE.match(stripped)
    if m:
        sect = int(m.group(1))
        verse = int(m.group(2))
        remainder = stripped[m.end():]
        if 1 <= sect <= 55:
            return sect, verse, remainder

    # Try verse only
    m = VERSE_RE.match(stripped)
    if m:
        verse = int(m.group(1))
        remainder = stripped[m.end():]
        if 1 <= verse <= 80:
            return None, verse, remainder

    return None


def parse_diatessaron(lines, start, end):
    """Parse the Diatessaron text and extract section-verse to gospel mappings."""

    entries = []
    current_section = 0
    current_gospel = ""
    current_chapter = 0

    # State for accumulating text for current verse
    current_verse = 0
    current_gospel_verse = 0
    current_text_parts = []

    def flush():
        """Save current verse entry."""
        nonlocal current_text_parts
        if current_section > 0 and current_verse > 0 and current_gospel:
            text = " ".join(current_text_parts)
            text = re.sub(r"\s+", " ", text).strip()
            # Clean footnote markers
            text = re.sub(r"[\^]+\d*", "", text)
            text = re.sub(r"['']+", "", text)
            text = text.strip()
            if text:
                entries.append({
                    "diatessaron_section": current_section,
                    "diatessaron_verse": current_verse,
                    "gospel_book": current_gospel,
                    "gospel_chapter": current_chapter,
                    "gospel_verse": current_gospel_verse,
                    "text_snippet": text[:200],
                })
        current_text_parts = []

    i = start
    while i <= end:
        line = lines[i].rstrip("\n")
        i += 1

        if is_skip_line(line):
            continue

        stripped = line.strip()

        # --- Parse left margin (section / verse number) ---
        left = extract_left_margin(stripped)
        new_section = None
        new_verse = None
        text_after_left = stripped

        if left is not None:
            sect, verse, remainder = left
            if sect is not None:
                # This looks like section+verse. Validate the section number.
                # Section should advance sequentially (or be same section with
                # a multi-digit verse). Key insight: if sect is close to
                # current_section, it's likely a section marker.
                if (sect == current_section + 1 or
                    (current_section == 0 and sect == 1) or
                    (sect == current_section and verse == 1)):
                    # Genuine section transition
                    new_section = sect
                    new_verse = verse
                    text_after_left = remainder
                elif sect == current_section:
                    # Same section, sect+verse at start (OCR sometimes repeats section)
                    new_verse = verse
                    text_after_left = remainder
                else:
                    # The "section" number might actually be a verse number
                    # e.g., "44 And great wonder..." where 44 is a verse
                    if 1 <= sect <= 80 and current_section > 0:
                        new_verse = sect
                        # The second number might be start of text
                        text_after_left = str(verse) + " " + remainder
                    # Otherwise skip this interpretation
            else:
                # Just a verse number
                new_verse = verse
                text_after_left = remainder

        # --- Parse right margin (gospel reference) ---
        right = extract_right_margin(text_after_left if left else stripped)

        # Extract text content from the right margin parse
        text_content = ""
        new_gospel = None
        new_chapter = None
        new_gospel_verse = None
        if right is not None:
            gospel, chapter, verse_r, text_before = right
            new_gospel = gospel
            new_chapter = chapter
            new_gospel_verse = verse_r
            text_content = text_before
        else:
            # No gospel ref on this line — it's continuation text
            text_content = text_after_left if left else stripped

        # --- Flush BEFORE updating gospel state, when starting a new verse ---
        if new_section is not None:
            flush()
            current_section = new_section
            current_verse = new_verse
            # Update gospel state AFTER flush
            if new_gospel is not None:
                current_gospel = new_gospel
            if new_chapter is not None:
                current_chapter = new_chapter
            if new_gospel_verse is not None:
                current_gospel_verse = new_gospel_verse
            current_text_parts = [text_content] if text_content else []
        elif new_verse is not None and new_verse != current_verse:
            flush()
            current_verse = new_verse
            # Update gospel state AFTER flush
            if new_gospel is not None:
                current_gospel = new_gospel
            if new_chapter is not None:
                current_chapter = new_chapter
            if new_gospel_verse is not None:
                current_gospel_verse = new_gospel_verse
            current_text_parts = [text_content] if text_content else []
        else:
            # Continuation line — update gospel state immediately
            if new_gospel is not None:
                current_gospel = new_gospel
            if new_chapter is not None:
                current_chapter = new_chapter
            if new_gospel_verse is not None:
                current_gospel_verse = new_gospel_verse
            if text_content:
                current_text_parts.append(text_content)

    # Flush the last entry
    flush()

    return entries


def post_process(entries):
    """Clean up and validate entries."""
    # Remove entries where text snippet is empty or very short (OCR artifacts)
    entries = [e for e in entries if len(e["text_snippet"]) > 5]

    # Remove genuine duplicate (same section+verse, keep first)
    seen = {}
    unique = []
    for e in entries:
        key = (e["diatessaron_section"], e["diatessaron_verse"])
        if key not in seen:
            seen[key] = True
            unique.append(e)
    entries = unique

    # Sort by section, then verse
    entries.sort(key=lambda e: (e["diatessaron_section"], e["diatessaron_verse"]))

    return entries


def report(entries):
    """Print summary statistics."""
    sections = sorted(set(e["diatessaron_section"] for e in entries))
    gospels = sorted(set(e["gospel_book"] for e in entries))
    section_counts = Counter(e["diatessaron_section"] for e in entries)

    print(f"Total entries: {len(entries)}")
    print(f"Sections found: {len(sections)} / 55")
    if len(sections) < 55:
        missing = sorted(set(range(1, 56)) - set(sections))
        print(f"Missing sections: {missing}")
    else:
        print("All 55 sections found!")
    print(f"Gospels found: {gospels}")

    print(f"\nVerses per section:")
    for s in sections:
        print(f"  Section {s:2d}: {section_counts[s]:3d} verses")

    print(f"\nFirst 10 entries:")
    for e in entries[:10]:
        print(f"  {e['diatessaron_section']:2d}:{e['diatessaron_verse']:2d} -> "
              f"{e['gospel_book']:5s} {e['gospel_chapter']:2d}:{e['gospel_verse']:2d} "
              f"| {e['text_snippet'][:70]}")

    print(f"\nLast 10 entries:")
    for e in entries[-10:]:
        print(f"  {e['diatessaron_section']:2d}:{e['diatessaron_verse']:2d} -> "
              f"{e['gospel_book']:5s} {e['gospel_chapter']:2d}:{e['gospel_verse']:2d} "
              f"| {e['text_snippet'][:70]}")


def save_tsv(entries, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow([
            "diatessaron_section", "diatessaron_verse",
            "gospel_book", "gospel_chapter", "gospel_verse",
            "text_snippet"
        ])
        for e in entries:
            writer.writerow([
                e["diatessaron_section"], e["diatessaron_verse"],
                e["gospel_book"], e["gospel_chapter"], e["gospel_verse"],
                e["text_snippet"],
            ])
    print(f"Saved TSV: {path} ({len(entries)} rows)")


def save_json(entries, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {path} ({len(entries)} entries)")


def main():
    print("=" * 60)
    print("Parsing Hill 1894 Diatessaron OCR text")
    print("=" * 60)

    lines = load_raw_text()
    print(f"Loaded {len(lines)} lines from {RAW_FILE}")

    start, end = find_text_boundaries(lines)
    print(f"Text boundaries: lines {start}-{end}")

    if start is None or end is None:
        print("ERROR: Could not find text boundaries!")
        return

    entries = parse_diatessaron(lines, start, end)
    print(f"Raw entries: {len(entries)}")

    entries = post_process(entries)
    print(f"After cleanup: {len(entries)}")

    print()
    report(entries)

    print()
    save_tsv(entries, TSV_FILE)
    save_json(entries, JSON_FILE)
    print("\nDone!")


if __name__ == "__main__":
    main()
