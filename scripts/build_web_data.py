"""
Build unified JSON data files for the web visualization.

Takes all corpora (Old Syriac, Peshitta, Greek NT, Hogg, Hill/Ciasca mappings,
Arabic sections) and produces:

  web/data/
    gospels.json         — unified index of 4 gospels with all versions per verse
    diatessaron.json     — 55 sections with Hogg English + Arabic + mappings
    corpus_stats.json    — overview statistics for landing page

This is the static data layer consumed by the web app.
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
WEB_DATA = PROJECT / "web" / "data"
WEB_DATA.mkdir(parents=True, exist_ok=True)

# Canonical gospel book names (normalized)
GOSPEL_BOOKS = ["Matthew", "Mark", "Luke", "John"]
BOOK_ABBREV = {
    "Matthew": "Matt", "Mark": "Mark", "Luke": "Luke", "John": "John",
    "Matt": "Matt", "Mk": "Mark", "Lk": "Luke", "Jn": "John",
    "Matth": "Matt", "Marc": "Mark", "Luc": "Luke", "Ioan": "John", "Joan": "John",
}


def normalize_book(name: str) -> str:
    """Normalize gospel book name to standard form."""
    name = name.strip().rstrip(".")
    name = BOOK_ABBREV.get(name, name)
    for canon in GOSPEL_BOOKS:
        if canon.lower().startswith(name.lower()) or name.lower().startswith(canon.lower()[:3]):
            return canon
    return name


def load_tsv(path: Path, skip_header: bool = True) -> list[dict]:
    """Load a TSV file into a list of dicts."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def build_gospels():
    """Build the unified gospel index: book → chapter → verse → {versions}."""
    print("Building unified gospel index...")
    # Structure: {book: {chapter: {verse: {greek, peshitta, old_syriac_cur, old_syriac_sin}}}}
    gospels = {book: {} for book in GOSPEL_BOOKS}

    def ensure_verse(book: str, chapter: int, verse: int) -> dict:
        if book not in gospels:
            return None
        if chapter not in gospels[book]:
            gospels[book][chapter] = {}
        if verse not in gospels[book][chapter]:
            gospels[book][chapter][verse] = {}
        return gospels[book][chapter][verse]

    # Greek NT (SBLGNT)
    greek_path = DATA / "greek_nt" / "sblgnt.tsv"
    if greek_path.exists():
        count = 0
        for row in load_tsv(greek_path):
            book = normalize_book(row["book"])
            if book not in GOSPEL_BOOKS:
                continue
            try:
                ch, vs = int(row["chapter"]), int(row["verse"])
            except ValueError:
                continue
            v = ensure_verse(book, ch, vs)
            if v is not None:
                v["greek"] = row["greek_text"]
                v["greek_lemma"] = row.get("lemmatized_text", "")
                count += 1
        print(f"  Greek NT: {count} verses")

    # Peshitta NT
    pesh_path = DATA / "peshitta_nt" / "peshitta_nt.tsv"
    if pesh_path.exists():
        count = 0
        for row in load_tsv(pesh_path):
            book = normalize_book(row["book"])
            if book not in GOSPEL_BOOKS:
                continue
            try:
                ch, vs = int(row["chapter"]), int(row["verse"])
            except ValueError:
                continue
            v = ensure_verse(book, ch, vs)
            if v is not None:
                v["peshitta"] = row["syriac_text"]
                v["peshitta_translit"] = row.get("transliteration", "")
                count += 1
        print(f"  Peshitta: {count} verses")

    # KJV English — 4 gospels, one JSON per book
    kjv_dir = DATA / "kjv"
    if kjv_dir.exists():
        count = 0
        for book in GOSPEL_BOOKS:
            path = kjv_dir / f"{book}.json"
            if not path.exists():
                continue
            kjv_data = json.loads(path.read_text(encoding="utf-8"))
            for ch_obj in kjv_data.get("chapters", []):
                try:
                    ch = int(ch_obj["chapter"])
                except (KeyError, ValueError):
                    continue
                for v_obj in ch_obj.get("verses", []):
                    try:
                        vs = int(v_obj["verse"])
                    except (KeyError, ValueError):
                        continue
                    v = ensure_verse(book, ch, vs)
                    if v is not None:
                        v["kjv"] = v_obj.get("text", "")
                        count += 1
        print(f"  KJV: {count} verses")

    # Old Syriac (CAL) — separate Cur and Sin
    os_dir = DATA / "cal_old_syriac"
    if os_dir.exists():
        for tsv_path in sorted(os_dir.glob("*.tsv")):
            name = tsv_path.stem  # e.g. MtCur, MtSin
            count = 0
            for row in load_tsv(tsv_path):
                book = normalize_book(row["book"])
                if book not in GOSPEL_BOOKS:
                    continue
                ref = row["ref"]
                # ref format is "CC:VV" (e.g. "01:01")
                try:
                    parts = ref.split(":")
                    ch, vs = int(parts[0]), int(parts[1])
                except (ValueError, IndexError):
                    continue
                if ch == 0 or vs == 0:
                    continue  # skip incipit/header rows
                v = ensure_verse(book, ch, vs)
                if v is not None:
                    witness = row["witness"]  # "Curetonian" or "Sinaiticus"
                    key = "old_syriac_cur" if witness == "Curetonian" else "old_syriac_sin"
                    v[key] = row.get("cal_text", "")
                    v[key + "_syr"] = row.get("syriac_text", "")
                    count += 1
            print(f"  {name}: {count} verses")

    # Flatten to sorted structure for output
    result = {}
    for book in GOSPEL_BOOKS:
        chapters = []
        for ch in sorted(gospels[book].keys()):
            verses = []
            for vs in sorted(gospels[book][ch].keys()):
                v_data = gospels[book][ch][vs]
                verses.append({
                    "v": vs,
                    **v_data,
                })
            chapters.append({"c": ch, "verses": verses})
        result[book] = chapters

    out_path = WEB_DATA / "gospels.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    size = out_path.stat().st_size
    print(f"  → Saved {out_path.name} ({size/1024:.0f} KB)")
    return result


def build_diatessaron():
    """Build the Diatessaron section index with all mappings and translations."""
    print("\nBuilding Diatessaron section index...")
    sections = {}  # section_num → {arabic, hogg_english, gospel_refs, ciasca_refs}

    # 1. Load Arabic sections
    arabic_path = DATA / "diatessaron_arabic" / "arabic_sections.json"
    if arabic_path.exists():
        arabic_data = json.loads(arabic_path.read_text(encoding="utf-8"))
        for num_str, d in arabic_data.items():
            num = int(num_str)
            sections.setdefault(num, {})["arabic"] = d["text"]
            sections[num]["arabic_pages"] = d.get("pages", [])
        print(f"  Arabic: {len(arabic_data)} sections")

    # 2. Load Hogg English Diatessaron (JSON format: {"sections": [...]})
    hogg_path = DATA / "diatessaron_hogg" / "diatessaron_hogg.json"
    if hogg_path.exists():
        hogg_data = json.loads(hogg_path.read_text(encoding="utf-8"))
        hogg_sections = hogg_data.get("sections", [])
        count = 0
        for sec in hogg_sections:
            num = sec.get("section_number")
            if not num:
                continue
            subsections = sec.get("subsections", [])
            # Build concatenated text and structured verses
            text_parts = []
            hogg_verses = []
            for sub in subsections:
                t = sub.get("text", "").strip()
                if t:
                    text_parts.append(t)
                hogg_verses.append({
                    "v": sub.get("verse", ""),
                    "text": t,
                    "refs": sub.get("gospel_refs", []),
                })
            sections.setdefault(num, {})["hogg"] = " ".join(text_parts)
            sections[num]["hogg_verses"] = hogg_verses
            sections[num]["hogg_gospel_refs"] = sec.get("all_gospel_refs", [])
            count += 1
        print(f"  Hogg English: {count} sections")

    # 3. Load Hill mapping (Diatessaron → Gospel verse)
    hill_path = DATA / "diatessaron_hill" / "hill_mapping.tsv"
    if hill_path.exists():
        hill_refs = defaultdict(list)  # section_num → list of gospel refs
        for row in load_tsv(hill_path):
            try:
                sec = int(row.get("diatessaron_section", row.get("section", 0)))
            except (ValueError, TypeError):
                continue
            if not sec:
                continue
            ref = {
                "dv": row.get("diatessaron_verse", ""),
                "book": normalize_book(row.get("gospel_book", "")),
                "ch": row.get("gospel_chapter", ""),
                "v": row.get("gospel_verse", ""),
                "text": row.get("text_snippet", ""),
            }
            hill_refs[sec].append(ref)
        for sec, refs in hill_refs.items():
            sections.setdefault(sec, {})["hill_refs"] = refs
        print(f"  Hill mapping: {sum(len(v) for v in hill_refs.values())} refs across {len(hill_refs)} sections")

    # 4. Load Ciasca mapping (list of {chapter, entries})
    ciasca_path = DATA / "diatessaron_ciasca" / "ciasca_ordo.json"
    if ciasca_path.exists():
        ciasca_data = json.loads(ciasca_path.read_text(encoding="utf-8"))
        count = 0
        for item in ciasca_data:
            num = item.get("chapter")
            entries = item.get("entries", [])
            if num:
                sections.setdefault(int(num), {})["ciasca_refs"] = entries
                count += len(entries)
        print(f"  Ciasca mapping: {count} refs across {len(ciasca_data)} sections")

    # Output
    result = {}
    for num in sorted(sections.keys()):
        result[str(num)] = {
            "section": num,
            **sections[num],
        }

    out_path = WEB_DATA / "diatessaron.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    size = out_path.stat().st_size
    print(f"  → Saved {out_path.name} ({size/1024:.0f} KB)")
    return result


def build_stats(gospels: dict, diatessaron: dict):
    """Build overview statistics for the landing page."""
    print("\nBuilding corpus statistics...")
    stats = {
        "gospels": {},
        "diatessaron": {
            "total_sections": 55,
            "with_arabic": sum(1 for s in diatessaron.values() if s.get("arabic")),
            "with_hogg": sum(1 for s in diatessaron.values() if s.get("hogg")),
            "with_hill": sum(1 for s in diatessaron.values() if s.get("hill_refs")),
        },
    }
    for book, chapters in gospels.items():
        total_v = sum(len(ch["verses"]) for ch in chapters)
        versions = defaultdict(int)
        for ch in chapters:
            for v in ch["verses"]:
                for k in ("greek", "peshitta", "old_syriac_cur", "old_syriac_sin", "kjv"):
                    if v.get(k):
                        versions[k] += 1
        stats["gospels"][book] = {
            "chapters": len(chapters),
            "verses": total_v,
            "versions": dict(versions),
        }

    out_path = WEB_DATA / "corpus_stats.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  → Saved {out_path.name}")
    return stats


def main():
    gospels = build_gospels()
    diatessaron = build_diatessaron()
    stats = build_stats(gospels, diatessaron)
    print("\nAll web data built successfully.")
    print(f"Output directory: {WEB_DATA}")


if __name__ == "__main__":
    main()
