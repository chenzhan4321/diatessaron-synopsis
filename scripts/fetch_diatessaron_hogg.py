"""
Scrape the Diatessaron (Hope W. Hogg translation) from Wikisource.

Source: Ante-Nicene Fathers, Volume IX
Uses the MediaWiki parse API for clean HTML extraction.

The Diatessaron has 55 sections (I-LV), each on a separate Wikisource page.
Each page contains:
  - Main narrative text with inline verse numbers in brackets like [1], [2,3]
  - Superscript footnote markers linking to endnotes
  - Endnotes containing gospel source refs (e.g. "Luke i. 5.") and editorial notes

Output:
  - diatessaron_hogg.json: full structured data
  - diatessaron_hogg.tsv: flat table (section, verse, gospel_refs, text)
"""

import json
import csv
import re
import ssl
import time
import urllib.request
from html import unescape
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────
API_URL = "https://en.wikisource.org/w/api.php"
PAGE_BASE = "Ante-Nicene_Fathers/Volume_IX/The_Diatessaron_of_Tatian/The_Diatessaron"
OUT_DIR = Path("/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_hogg")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CRAWL_DELAY = 2  # seconds between requests to Wikisource

# Roman numeral section names I through LV (55 sections)
ROMAN = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX",
    "XXXI", "XXXII", "XXXIII", "XXXIV", "XXXV", "XXXVI", "XXXVII", "XXXVIII", "XXXIX", "XL",
    "XLI", "XLII", "XLIII", "XLIV", "XLV", "XLVI", "XLVII", "XLVIII", "XLIX", "L",
    "LI", "LII", "LIII", "LIV", "LV",
]

# SSL context — Python 3.14 on macOS needs relaxed cipher settings for some servers
SSL_CTX = ssl.create_default_context()
SSL_CTX.set_ciphers("DEFAULT@SECLEVEL=1")


import urllib.parse  # needed for urlencode

MAX_RETRIES = 3  # retry on transient SSL errors


def fetch_parsed_html(page_title: str) -> str:
    """
    Use the MediaWiki parse API to get the rendered HTML for a page.
    Retries up to MAX_RETRIES times on transient SSL/network errors.
    """
    params = urllib.parse.urlencode({
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
    })
    url = f"{API_URL}?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "DiatessaronScraper/1.0 (academic research; polite crawling)"
    })
    for attempt in range(MAX_RETRIES):
        try:
            resp = urllib.request.urlopen(req, context=SSL_CTX)
            data = json.loads(resp.read().decode("utf-8"))
            return data["parse"]["text"]["*"]
        except (urllib.error.URLError, ssl.SSLError, ConnectionError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 3  # backoff: 3s, 6s
                print(f"    Retry {attempt+1}/{MAX_RETRIES} after error: {e}")
                time.sleep(wait)
            else:
                raise


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities, returning plain text."""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return text


def extract_main_paragraphs(html: str) -> str:
    """
    Extract the main narrative content from the parsed HTML.

    Strategy: remove header/nav divs and style blocks, then collect
    all <p> tags that appear before the <ol class="references"> block.
    Return the raw HTML of those paragraphs joined together.
    """
    # Remove style blocks (CSS embedded in templates)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    # Remove ws-noexport blocks (header navigation, metadata)
    cleaned = re.sub(r'<div class="ws-noexport">.*?</div>', "", cleaned, flags=re.DOTALL)
    # Remove the header navigation bar
    # It's wrapped in <div class="ws-header ..."> with nested divs
    cleaned = re.sub(r'<div class="ws-header[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>\s*</div>',
                     "", cleaned, flags=re.DOTALL)

    # Split off the references section (footnotes)
    parts = re.split(r'<ol class="references">', cleaned, maxsplit=1)
    main_html = parts[0]

    return main_html


def extract_references(html: str) -> dict:
    """
    Parse the <ol class="references"> block into {footnote_number: text}.

    Each footnote: <li id="cite_note-N"> ... <span class="reference-text">TEXT</span>
    The cite_note id may use &#95; for underscore in some pages.
    """
    refs = {}
    pattern = r'<li id="cite(?:_|&#95;)note-(\d+)".*?<span class="reference-text">\s*(.*?)\s*</span>'
    for m in re.finditer(pattern, html, re.DOTALL):
        note_id = int(m.group(1))
        raw_text = strip_html(m.group(2)).strip()
        # Normalize internal whitespace (footnotes often span lines in HTML)
        raw_text = re.sub(r"\s+", " ", raw_text)
        refs[note_id] = raw_text
    return refs


def is_gospel_ref(text: str) -> bool:
    """
    Check if a footnote is a gospel/scripture reference vs. editorial note.

    Gospel refs are short and match patterns like:
      "John i. 1."  "Matt. xxviii. 19, 20."  "Luke i. 5."

    Editorial notes are longer explanations that we skip.
    """
    # Common biblical book names/abbreviations found in Hogg's translation
    books = (
        r"(?:Gen|Exod?|Lev|Num|Deut|Josh|Judg|Ruth|"
        r"(?:1|2)\s*Sam|(?:1|2)\s*Kings|(?:1|2)\s*Chron|"
        r"Ezra|Neh|Esth|Job|Ps|Prov|Eccles|Song|"
        r"Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jon|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|"
        r"Matt|Mark|Luke|John|Acts|Rom|(?:1|2)\s*Cor|Gal|Eph|Phil|Col|"
        r"(?:1|2)\s*Thess|(?:1|2)\s*Tim|Tit|Philem|Heb|Jas|(?:1|2)\s*Pet|"
        r"(?:1|2|3)\s*John|Jude|Rev)"
    )
    # Pattern: optional number prefix, book name, roman numeral chapter, arabic verse
    pattern = rf"^\s*(?:\d\s*)?{books}\.?\s+[ivxlc]+\.\s+\d"
    return bool(re.match(pattern, text, re.IGNORECASE))


def extract_gospel_ref(text: str) -> str:
    """
    Extract just the scripture reference from a footnote.
    E.g., "Luke i. 5." -> "Luke i. 5"
    Some footnotes have extra text after the reference; we take just the ref part.
    """
    # Match: optional number + book + roman chapter + arabic verse(s)
    m = re.match(
        r"((?:\d\s*)?[A-Za-z]+\.?\s+[ivxlc]+\.\s+\d+(?:\s*[,\-]\s*\d+)*)",
        text.strip()
    )
    if m:
        return m.group(1).rstrip(".")
    # Fallback: just return the whole thing, trimmed
    return text.strip().rstrip(".")


def parse_section_text(main_html: str, refs: dict) -> list:
    """
    Parse the main text HTML of one section into a list of verse entries.

    Each verse has:
      - verse: the Diatessaron's internal verse number(s) within this section
      - text: the narrative text for this verse
      - gospel_refs: list of gospel source references (from footnotes)
      - footnote_ids: which footnotes were referenced in this verse

    Parsing approach:
      1. Replace <sup> footnote markers with parseable tokens §FNOTE:N§
      2. Strip HTML to get plain text with our tokens
      3. Remove page markers like [Arabic, p. 2]
      4. Split on verse number markers [N] or [N,N]
      5. For each verse, collect footnote IDs and map to gospel refs
    """
    # Step 1: Replace footnote <sup> tags with markers we can find in plain text
    # Pattern: <sup id="cite_ref-N" ...>[N]</sup>
    text_html = re.sub(
        r'<sup id="cite(?:_|&#95;)ref-(\d+)"[^>]*>.*?</sup>',
        r" §FNOTE:\1§ ",
        main_html,
    )

    # Step 2: Convert to plain text, keeping our markers
    plain = strip_html(text_html)
    plain = re.sub(r"\s+", " ", plain).strip()

    # Step 3: Remove page reference markers (not verse numbers)
    # These look like [Arabic, p. 2] or [Arabic, p. 10]
    plain = re.sub(r"\[Arabic,\s*p\.\s*\d+[ab]?\]", "", plain)
    plain = re.sub(r"\[Syriac,\s*p\.\s*\d+[ab]?\]", "", plain)
    # Also remove section title markers like [Section I]
    plain = re.sub(r"\[Section [IVXLC]+\]", "", plain)

    # Step 4: Split on verse number markers
    # Verse markers: [1], [2,3], [10], [1,2,3] etc.
    # Must be careful not to match things like [Arabic, p. 2]
    verse_pattern = r"\[(\d+(?:\s*,\s*\d+)*)\]"
    parts = re.split(verse_pattern, plain)
    # parts = [preamble, verse_nums_1, text_1, verse_nums_2, text_2, ...]

    subsections = []
    for i in range(1, len(parts), 2):
        verse_nums_str = parts[i].strip()
        verse_text = parts[i + 1] if i + 1 < len(parts) else ""

        # Extract footnote IDs from this verse
        fnote_ids = [int(x) for x in re.findall(r"§FNOTE:(\d+)§", verse_text)]

        # Remove our marker tokens from the text
        clean_text = re.sub(r"\s*§FNOTE:\d+§\s*", " ", verse_text).strip()
        clean_text = re.sub(r"\s+", " ", clean_text)

        # Map footnotes to gospel references
        gospel_refs = []
        for fid in fnote_ids:
            if fid in refs and is_gospel_ref(refs[fid]):
                gospel_refs.append(extract_gospel_ref(refs[fid]))

        subsections.append({
            "verse": verse_nums_str,
            "text": clean_text,
            "gospel_refs": gospel_refs,
            "footnote_ids": fnote_ids,
        })

    return subsections


def main():
    all_sections = []
    errors = []

    for idx, roman in enumerate(ROMAN, 1):
        page_title = f"{PAGE_BASE}/Section_{roman}"
        print(f"Fetching Section {roman} ({idx}/55) ...")

        try:
            html = fetch_parsed_html(page_title)
        except Exception as e:
            print(f"  ERROR fetching: {e}")
            errors.append((roman, str(e)))
            time.sleep(CRAWL_DELAY)
            continue

        # Parse footnotes (gospel references + editorial notes)
        refs = extract_references(html)

        # Extract main content paragraphs (everything before references)
        main_html = extract_main_paragraphs(html)

        # Parse into individual verses with their references
        subsections = parse_section_text(main_html, refs)

        section_data = {
            "section_number": idx,
            "section_roman": roman,
            "subsections": subsections,
            # Deduplicated list of all gospel refs in this section (preserving order)
            "all_gospel_refs": list(dict.fromkeys(
                ref for sub in subsections for ref in sub["gospel_refs"]
            )),
        }
        all_sections.append(section_data)

        n_verses = len(subsections)
        n_refs = sum(len(s["gospel_refs"]) for s in subsections)
        print(f"  -> {n_verses} verses, {n_refs} gospel refs")

        # Respect Wikisource crawl rate
        time.sleep(CRAWL_DELAY)

    # ── Save JSON ─────────────────────────────────────────────────────────
    json_path = OUT_DIR / "diatessaron_hogg.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "title": "The Diatessaron of Tatian",
            "translator": "Hope W. Hogg",
            "source": "Ante-Nicene Fathers, Volume IX",
            "url": f"https://en.wikisource.org/wiki/{PAGE_BASE}",
            "sections": all_sections,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nSaved JSON -> {json_path}")

    # ── Save TSV ──────────────────────────────────────────────────────────
    # One row per verse: section | verse | gospel_refs | text
    tsv_path = OUT_DIR / "diatessaron_hogg.tsv"
    with open(tsv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["section", "verse", "gospel_refs", "text"])
        for sec in all_sections:
            for sub in sec["subsections"]:
                writer.writerow([
                    sec["section_roman"],
                    sub["verse"],
                    "; ".join(sub["gospel_refs"]),
                    sub["text"],
                ])
    print(f"Saved TSV -> {tsv_path}")

    # ── Summary ───────────────────────────────────────────────────────────
    total_verses = sum(len(s["subsections"]) for s in all_sections)
    total_refs = sum(
        len(sub["gospel_refs"])
        for s in all_sections
        for sub in s["subsections"]
    )
    print(f"\nTotal: {len(all_sections)} sections, {total_verses} verses, {total_refs} gospel refs")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for roman, err in errors:
            print(f"  Section {roman}: {err}")


if __name__ == "__main__":
    main()
