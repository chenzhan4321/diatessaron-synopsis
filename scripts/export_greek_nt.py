"""
Export the Greek NT (MorphGNT/SBLGNT) corpus to TSV and JSON.

Parses the MorphGNT SBLGNT word-per-line files, aggregates words into verses,
and exports verse-level Greek text alongside lemmatized text.

MorphGNT file format (space-separated, 7 columns):
  BBCCVV  POS  parsing  text  word  normalized  lemma
  - BBCCVV: 2-digit book (61=Matt) + 2-digit chapter + 2-digit verse
  - text: the surface form as printed (with accents/punctuation)
  - lemma: dictionary form

Output:
  - data/greek_nt/sblgnt.tsv   (book, chapter, verse, greek_text, lemmatized_text)
  - data/greek_nt/sblgnt.json  (same data as a list of dicts)
"""

import csv
import json
import re
from collections import OrderedDict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SBLGNT_DIR = Path("/tmp/sblgnt")
OUT_DIR = PROJECT_ROOT / "data" / "greek_nt"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TSV_PATH = OUT_DIR / "sblgnt.tsv"
JSON_PATH = OUT_DIR / "sblgnt.json"

# Map the 2-digit book codes in MorphGNT to human-readable names
# MorphGNT uses 61=Matt through 87=Revelation
BOOK_NAMES = {
    "61": "Matthew", "62": "Mark", "63": "Luke", "64": "John",
    "65": "Acts",
    "66": "Romans", "67": "1 Corinthians", "68": "2 Corinthians",
    "69": "Galatians", "70": "Ephesians", "71": "Philippians",
    "72": "Colossians", "73": "1 Thessalonians", "74": "2 Thessalonians",
    "75": "1 Timothy", "76": "2 Timothy", "77": "Titus", "78": "Philemon",
    "79": "Hebrews",
    "80": "James", "81": "1 Peter", "82": "2 Peter",
    "83": "1 John", "84": "2 John", "85": "3 John",
    "86": "Jude", "87": "Revelation",
}


def parse_sblgnt_files():
    """
    Parse all MorphGNT txt files and aggregate words into verses.
    Returns an OrderedDict keyed by (book_code, chapter, verse) → { texts: [], lemmas: [] }
    """
    verses = OrderedDict()

    # Files are named like 61-Mt-morphgnt.txt, sorted alphabetically = canonical order
    for txt_file in sorted(SBLGNT_DIR.glob("*-morphgnt.txt")):
        for line in txt_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            # Split into exactly 7 columns
            parts = line.split()
            if len(parts) < 7:
                continue

            ref = parts[0]       # e.g. "010101"
            text = parts[3]      # surface form with punctuation
            lemma = parts[6]     # dictionary/lemma form

            # Decode the reference: first 2 digits = book code in filename
            # Actually the ref is BBCCVV where BB is relative chapter for the book
            # In MorphGNT, the ref is chapter*100+verse within the file
            # Book is identified by the filename prefix (61=Matt, 62=Mark, etc.)
            book_code = txt_file.name[:2]
            # Reference format is BBCCVV: 2-digit book + 2-digit chapter + 2-digit verse
            # BB is sequential (01-27) within the corpus; we use filename for book identity
            chapter = int(ref[2:4])
            verse = int(ref[4:6])

            key = (book_code, chapter, verse)
            if key not in verses:
                verses[key] = {"texts": [], "lemmas": []}

            verses[key]["texts"].append(text)
            verses[key]["lemmas"].append(lemma)

    return verses


def main():
    verses = parse_sblgnt_files()
    rows = []

    for (book_code, chapter, verse), data in verses.items():
        book_name = BOOK_NAMES.get(book_code, f"Book_{book_code}")
        # Join words with spaces to form verse-level text
        greek_text = " ".join(data["texts"])
        lemmatized_text = " ".join(data["lemmas"])

        rows.append({
            "book": book_name,
            "chapter": chapter,
            "verse": verse,
            "greek_text": greek_text,
            "lemmatized_text": lemmatized_text,
        })

    # -- Write TSV --
    with open(TSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["book", "chapter", "verse", "greek_text", "lemmatized_text"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    # -- Write JSON --
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(rows)} verses")
    print(f"  TSV  → {TSV_PATH}")
    print(f"  JSON → {JSON_PATH}")


if __name__ == "__main__":
    main()
