"""
Segment the Ciasca 1888 Arabic Diatessaron into 55 sections (الاصحاح).

Uses an explicit lookup table of all 55 section phrases (with OCR variants)
rather than trying to parse ordinals generically. This is more robust against
OCR errors like المشرون→العشرون.

The book is RTL-bound: Section 1 is near the END of the PDF (highest page
numbers), Section 55 is near the START (lowest). We scan pages in reading
order (highest→lowest page) to build sections in order 1→55.

Missing sections (due to OCR errors in the section header) are reported
but the script doesn't abort — the preceding section just absorbs the
following text until the next recognized marker.

Output:
  data/diatessaron_arabic/arabic_sections.json
"""

import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MERGED_DIR = PROJECT / "data" / "diatessaron_arabic_ocr" / "results" / "ciasca_merged"
OUT_DIR = PROJECT / "data" / "diatessaron_arabic"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Lookup table: section number -> list of recognized phrases
# Includes OCR variants (العشرون / المشرون, الثلاثون / الثلثون, etc.)
SECTION_PHRASES = {
    1:  ["الاول", "الأول"],
    2:  ["الثاني", "الثانى"],
    3:  ["الثالث"],
    4:  ["الرابع"],
    5:  ["الخامس"],
    6:  ["السادس"],
    7:  ["السابع"],
    8:  ["الثامن"],
    9:  ["التاسع"],
    10: ["العاشر"],
    11: ["الحادي عشر", "الحادى عشر"],
    12: ["الثاني عشر", "الثانى عشر"],
    13: ["الثالث عشر"],
    14: ["الرابع عشر"],
    15: ["الخامس عشر"],
    16: ["السادس عشر"],
    17: ["السابع عشر"],
    18: ["الثامن عشر"],
    19: ["التاسع عشر"],
    20: ["العشرون", "المشرون", "العشرين"],
    21: ["الحادي والعشرون", "الحادى والعشرون", "الاحد والعشرون"],
    22: ["الثاني والعشرون", "الثانى والعشرون"],
    23: ["الثالث والعشرون"],
    24: ["الرابع والعشرون"],
    25: ["الخامس والعشرون"],
    26: ["السادس والعشرون"],
    27: ["السابع والعشرون"],
    28: ["الثامن والعشرون"],
    29: ["التاسع والعشرون"],
    30: ["الثلاثون", "الثلثون"],
    31: ["الحادي والثلاثون", "الحادي والثلثون", "الحادى والثلاثون"],
    32: ["الثاني والثلاثون", "الثاني والثلثون", "الثانى والثلاثون", "الثانى والثلثون"],
    33: ["الثالث والثلاثون", "الثالث والثلثون"],
    34: ["الرابع والثلاثون", "الرابع والثلثون"],
    35: ["الخامس والثلاثون", "الخامس والثلثون"],
    36: ["السادس والثلاثون", "السادس والثلثون"],
    37: ["السابع والثلاثون", "السابع والثلثون"],
    38: ["الثامن والثلاثون", "الثامن والثلثون"],
    39: ["التاسع والثلاثون", "التاسع والثلثون"],
    40: ["الاربعون", "الأربعون"],
    41: ["الحادي والاربعون", "الحادى والاربعون", "الحادي والأربعون"],
    42: ["الثاني والاربعون", "الثانى والاربعون"],
    43: ["الثالث والاربعون"],
    44: ["الرابع والاربعون"],
    45: ["الخامس والاربعون"],
    46: ["السادس والاربعون"],
    47: ["السابع والاربعون"],
    48: ["الثامن والاربعون"],
    49: ["التاسع والاربعون"],
    50: ["الخمسون"],
    51: ["الحادي والخمسون", "الحادى والخمسون", "الاحد والخمسون"],
    52: ["الثاني والخمسون", "الثانى والخمسون"],
    53: ["الثالث والخمسون"],
    54: ["الرابع والخمسون"],
    55: ["الخامس والخمسون"],
}

# Build reverse lookup: phrase -> section number (longest phrases first so
# "الحادي والعشرون" matches before "الحادي عشر")
PHRASE_TO_NUM = []
for num, phrases in SECTION_PHRASES.items():
    for ph in phrases:
        PHRASE_TO_NUM.append((ph, num))
# Sort by phrase length descending so longer phrases take priority
PHRASE_TO_NUM.sort(key=lambda x: -len(x[0]))


def find_section_markers(text: str) -> list[tuple[int, int, int]]:
    """Find all section markers in text.
    Returns list of (start_pos, end_pos, section_num)."""
    results = []
    # Scan for "الاصحاح" followed by any known phrase
    for m in re.finditer(r"الاصحاح\s*", text):
        start = m.start()
        rest = text[m.end(): m.end() + 40]  # look ahead 40 chars
        best = None
        for ph, num in PHRASE_TO_NUM:
            if rest.startswith(ph):
                best = (num, len(ph))
                break
        if best:
            num, ph_len = best
            end = m.end() + ph_len
            # Extend end to include trailing ※ if present
            trail = text[end:end+5]
            trail_m = re.match(r"\s*※", trail)
            if trail_m:
                end += trail_m.end()
            results.append((start, end, num))
    return results


def longest_increasing_sequence(candidates: list) -> list:
    """Given a list of (page_desc_order_idx, section_num, ...) tuples,
    return the longest strictly-increasing subsequence by section_num
    (preserving page order). Classic LIS O(n log n) variant."""
    if not candidates:
        return []
    # candidates should already be in reading order (high page → low page)
    # We want the longest increasing subsequence of num values
    n = len(candidates)
    # dp[i] = length of LIS ending at i
    dp = [1] * n
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if candidates[j][1] < candidates[i][1] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
                prev[i] = j
    # Find end of longest
    best_end = max(range(n), key=lambda i: dp[i])
    # Reconstruct
    result = []
    i = best_end
    while i >= 0:
        result.append(candidates[i])
        i = prev[i]
    return list(reversed(result))


def main():
    # Load all Arabic pages (133-342)
    pages = {}
    for p in range(133, 343):
        path = MERGED_DIR / f"page_{p:04d}_merged.txt"
        if path.exists():
            pages[p] = path.read_text(encoding="utf-8").strip()
    print(f"Loaded {len(pages)} pages")

    # Pass 1: collect ALL candidate markers across all pages
    # Reading order: high page → low page (book is RTL-bound)
    all_candidates = []  # list of (page, section_num, start_in_page, end_in_page)
    for p in sorted(pages.keys(), reverse=True):
        text = pages[p]
        for start, end, num in find_section_markers(text):
            all_candidates.append((p, num, start, end))
            print(f"  candidate: page {p} → section {num}")

    # Pass 2: find longest increasing subsequence by section number
    print(f"\nTotal candidates: {len(all_candidates)}")
    best_sequence = longest_increasing_sequence(all_candidates)
    print(f"Best increasing sequence: {len(best_sequence)} markers")

    # Pass 3: using the chosen markers, split text into sections
    chosen_set = {(c[0], c[2]) for c in best_sequence}  # (page, start_pos)
    sections = {}  # section_num -> {"text_parts": [], "pages": set}
    current_section = None
    current_text_parts = []
    current_pages = set()

    for p in sorted(pages.keys(), reverse=True):
        text = pages[p]
        markers = find_section_markers(text)
        # Filter to only chosen markers
        markers = [(s, e, n) for s, e, n in markers if (p, s) in chosen_set]

        if not markers:
            if current_section is not None:
                current_text_parts.append(text)
                current_pages.add(p)
            continue

        last_end = 0
        for start, end, num in markers:
            before = text[last_end:start].strip()
            if before and current_section is not None:
                current_text_parts.append(before)
                current_pages.add(p)

            # Save previous
            if current_section is not None:
                if current_section not in sections:
                    sections[current_section] = {"text_parts": [], "pages": set()}
                sections[current_section]["text_parts"].extend(current_text_parts)
                sections[current_section]["pages"].update(current_pages)

            # Start new
            current_section = num
            current_text_parts = []
            current_pages = {p}
            last_end = end

        trailing = text[last_end:].strip()
        if trailing:
            current_text_parts.append(trailing)

    # Save the final section
    if current_section is not None:
        if current_section not in sections:
            sections[current_section] = {"text_parts": [], "pages": set()}
        sections[current_section]["text_parts"].extend(current_text_parts)
        sections[current_section]["pages"].update(current_pages)

    # Finalize
    final = {}
    for num in sorted(sections.keys()):
        text = "\n".join(sections[num]["text_parts"]).strip()
        pages_list = sorted(sections[num]["pages"])
        final[str(num)] = {
            "section_num": num,
            "text": text,
            "pages": pages_list,
            "char_count": len(text),
        }

    print(f"\n=== Summary ===")
    print(f"Sections found: {len(final)} / 55")
    for num in sorted(final.keys(), key=int):
        d = final[num]
        pg = d["pages"]
        print(f"  Section {num:>2}: {d['char_count']:>6} chars, pages {pg[0] if pg else '?'}-{pg[-1] if pg else '?'}")

    missing = sorted(set(range(1, 56)) - set(int(k) for k in final.keys()))
    if missing:
        print(f"\nMissing sections: {missing}")
        print("(These may be due to OCR errors in section headers. Their text")
        print(" will be merged into the preceding section.)")

    # Save
    out_path = OUT_DIR / "arabic_sections.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
