"""
Fetch Old Syriac Gospel texts from CAL (Comprehensive Aramaic Lexicon).

Downloads all available Old Syriac texts (Curetonian + Sinaiticus) from
cal.huc.edu and saves as structured TSV + JSON files.

Total: 7 HTTP requests with 60s crawl-delay between each (~7 min).

Output:
  data/cal_old_syriac/  — one TSV per text + combined JSON
"""

import html as html_mod
import json
import re
import ssl
import time
import urllib.request
from pathlib import Path

# --- Configuration ---

# All available Old Syriac texts on CAL
TEXTS = [
    {"file": 60040, "sub": 1, "name": "MtCur", "book": "Matthew",    "witness": "Curetonian"},
    {"file": 60040, "sub": 2, "name": "MtSin", "book": "Matthew",    "witness": "Sinaiticus"},
    # MkCur does not exist (Curetonian MS lacks Mark)
    {"file": 60041, "sub": 2, "name": "MkSin", "book": "Mark",       "witness": "Sinaiticus"},
    {"file": 60042, "sub": 1, "name": "LkCur", "book": "Luke",       "witness": "Curetonian"},
    {"file": 60042, "sub": 2, "name": "LkSin", "book": "Luke",       "witness": "Sinaiticus"},
    {"file": 60043, "sub": 1, "name": "JnCur", "book": "John",       "witness": "Curetonian"},
    {"file": 60043, "sub": 2, "name": "JnSin", "book": "John",       "witness": "Sinaiticus"},
]

BASE_URL = "https://cal.huc.edu/get_a_chapter.php?file={file}&sub={sub}&cset={cset}"
CRAWL_DELAY = 60  # seconds, as specified in robots.txt
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "cal_old_syriac"

# Regex to extract verse rows from CAL HTML table
# Roman version: <td valign="top">CH:VS  </td><td>...</td>
# Syriac version: <td valign="top"><span ...><BDO dir="rtl"> CH:VS</BDO></span> </td><td>...</td>
VERSE_RE_ROMAN = re.compile(
    r'<td valign="top">([\d:]+)\s*</td><td>(.*?)</td>',
    re.DOTALL,
)
VERSE_RE_SYRIAC = re.compile(
    r'<BDO dir="rtl">\s*([\d:]+)</BDO>.*?</td>\s*<td>(.*?)</td>',
    re.DOTALL,
)
# Extract individual words from <a> tags within a verse cell
WORD_RE = re.compile(r'>([^<]+)</a>')


def fetch_page(file: int, sub: int, cset: str = "R") -> str:
    """Fetch a single CAL text page. cset: R=Roman, S=Syriac."""
    url = BASE_URL.format(file=file, sub=sub, cset=cset)
    req = urllib.request.Request(url, headers={
        "User-Agent": "AcademicResearchBot/1.0 (Syriac DH project; respectful crawl-delay)"
    })
    # CAL server has flaky SSL — retry with relaxed settings if needed
    for attempt in range(3):
        try:
            ctx = ssl.create_default_context()
            if attempt > 0:
                # Relax TLS requirements for CAL's problematic server
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (ssl.SSLError, urllib.error.URLError) as e:
            print(f"  [attempt {attempt+1}/3] SSL error: {e}")
            if attempt < 2:
                time.sleep(5)
    raise RuntimeError(f"Failed to fetch {url} after 3 attempts")


def parse_verses(html: str, syriac: bool = False) -> list[dict]:
    """Parse CAL HTML into list of {ref, words_cal, text_cal}.
    syriac=True uses the BDO-based regex for Syriac script pages."""
    regex = VERSE_RE_SYRIAC if syriac else VERSE_RE_ROMAN
    verses = []
    for match in regex.finditer(html):
        ref = match.group(1).strip()
        if syriac:
            # BDO dir="rtl" reverses digit display: "10:10" is actually "01:01"
            # Reverse each numeric part to recover the real chapter:verse
            parts = ref.split(":")
            ref = ":".join(p[::-1] for p in parts)
        cell_html = match.group(2)
        words = WORD_RE.findall(cell_html)
        # Clean up: decode HTML entities (&#776; etc.) and strip whitespace
        words = [html_mod.unescape(w.strip()) for w in words if w.strip()]
        verses.append({
            "ref": ref,
            "words_cal": words,          # list of words
            "text_cal": " ".join(words),  # full verse as string
        })
    return verses


def save_tsv(verses: list[dict], path: Path, text_info: dict):
    """Save verses as TSV: book, witness, chapter:verse, cal_text, syriac_text."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("book\twitness\tref\tcal_text\tsyriac_text\n")
        for v in verses:
            syr = v.get("text_syriac", "")
            f.write(f"{text_info['book']}\t{text_info['witness']}\t{v['ref']}\t{v['text_cal']}\t{syr}\n")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_data = {}  # name -> {info + verses}
    total = len(TEXTS)

    for i, t in enumerate(TEXTS):
        name = t["name"]
        tsv_path = OUTPUT_DIR / f"{name}.tsv"

        # Skip if already downloaded (resume mode)
        if tsv_path.exists() and tsv_path.stat().st_size > 100:
            print(f"[{i+1}/{total}] {name} already exists, skipping.")
            # Reload from TSV for combined JSON
            verses = []
            with open(tsv_path, "r", encoding="utf-8") as f:
                next(f)  # skip header
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) >= 4:
                        v = {"ref": parts[2], "words_cal": parts[3].split(), "text_cal": parts[3]}
                        if len(parts) >= 5 and parts[4]:
                            v["words_syriac"] = parts[4].split()
                            v["text_syriac"] = parts[4]
                        verses.append(v)
            all_data[name] = {
                "book": t["book"], "witness": t["witness"],
                "file": t["file"], "sub": t["sub"],
                "verse_count": len(verses), "verses": verses,
            }
            continue

        print(f"[{i+1}/{total}] Fetching {name} (file={t['file']}, sub={t['sub']})...")

        # Fetch Roman transliteration (CAL encoding, machine-readable)
        html_roman = fetch_page(t["file"], t["sub"], cset="R")
        verses = parse_verses(html_roman)
        print(f"  -> {len(verses)} verses parsed")

        if not verses:
            print(f"  -> SKIP (no data)")
            if i < total - 1:
                print(f"  Waiting {CRAWL_DELAY}s (crawl-delay)...")
                time.sleep(CRAWL_DELAY)
            continue

        # Also fetch Syriac Unicode version
        print(f"  Fetching Syriac script version...")
        time.sleep(CRAWL_DELAY)
        html_syriac = fetch_page(t["file"], t["sub"], cset="S")
        verses_syr = parse_verses(html_syriac, syriac=True)

        # Merge Syriac text into verses by matching ref keys
        # Syriac version may use different ref format (e.g. "10:10" vs "01:01")
        # so we normalize: strip leading zeros from each part
        def norm_ref(r):
            parts = r.split(":")
            return ":".join(str(int(p)) for p in parts)

        syr_by_ref = {norm_ref(vs["ref"]): vs for vs in verses_syr}
        merged = 0
        for v in verses:
            key = norm_ref(v["ref"])
            if key in syr_by_ref:
                vs = syr_by_ref[key]
                v["words_syriac"] = vs["words_cal"]  # Syriac Unicode words
                v["text_syriac"] = vs["text_cal"]
                merged += 1
        print(f"  -> Syriac script merged: {merged}/{len(verses)} verses matched ({len(verses_syr)} syriac total)")

        # Save individual TSV
        tsv_path = OUTPUT_DIR / f"{name}.tsv"
        save_tsv(verses, tsv_path, t)
        print(f"  -> Saved {tsv_path.name}")

        # Collect for combined JSON
        all_data[name] = {
            "book": t["book"],
            "witness": t["witness"],
            "file": t["file"],
            "sub": t["sub"],
            "verse_count": len(verses),
            "verses": verses,
        }

        # Respect crawl-delay before next request
        if i < total - 1:
            print(f"  Waiting {CRAWL_DELAY}s (crawl-delay)...")
            time.sleep(CRAWL_DELAY)

    # Save combined JSON
    json_path = OUTPUT_DIR / "old_syriac_all.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"\nAll done! Combined JSON: {json_path}")

    # Summary
    print("\n=== Summary ===")
    for name, d in all_data.items():
        print(f"  {name:8s} ({d['witness']:12s} {d['book']:8s}): {d['verse_count']:4d} verses")

    total_verses = sum(d["verse_count"] for d in all_data.values())
    print(f"  {'TOTAL':8s}: {' ':21s} {total_verses:4d} verses")


if __name__ == "__main__":
    main()
