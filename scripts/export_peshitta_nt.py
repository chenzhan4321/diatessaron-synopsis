"""
Export the Peshitta NT (ETCBC/syrnt) corpus to TSV and JSON.

Uses Text-Fabric to load the syrnt dataset, iterates over all verses,
and collects Syriac text + ETCBC transliteration for each verse.

Output:
  - data/peshitta_nt/peshitta_nt.tsv  (book, chapter, verse, syriac_text, transliteration)
  - data/peshitta_nt/peshitta_nt.json  (same data as a list of dicts)
"""

import csv
import json
from pathlib import Path
from tf.app import use

# -- Project paths --
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "peshitta_nt"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TSV_PATH = OUT_DIR / "peshitta_nt.tsv"
JSON_PATH = OUT_DIR / "peshitta_nt.json"


def main():
    # Load the ETCBC/syrnt Text-Fabric dataset (auto-downloads on first use)
    A = use("ETCBC/syrnt", hoist=globals())
    # After hoist, F (features) and T (text API) are available in globals
    F_api = A.api.F
    T_api = A.api.T

    rows = []

    # Iterate over every verse node in the corpus
    for verse_node in F_api.otype.s("verse"):
        # T.sectionFromNode returns (book_name, chapter_num, verse_num)
        book, chapter, verse = T_api.sectionFromNode(verse_node)

        # Collect all word nodes inside this verse
        # L.d (level down) gets constituent nodes of the given type
        word_nodes = A.api.L.d(verse_node, otype="word")

        # Build Syriac text by joining word forms (right-to-left script, but we store as-is)
        syriac_words = [F_api.word.v(w) for w in word_nodes]
        syriac_text = " ".join(syriac_words)

        # Build transliteration using ETCBC/Wit transcription (Latin-script)
        translit_words = [F_api.word_etcbc.v(w) for w in word_nodes]
        transliteration = " ".join(translit_words)

        rows.append({
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "syriac_text": syriac_text,
            "transliteration": transliteration,
        })

    # -- Write TSV --
    with open(TSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["book", "chapter", "verse", "syriac_text", "transliteration"], delimiter="\t")
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
