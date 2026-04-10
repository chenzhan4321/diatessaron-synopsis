"""
Transliterate CAL (Comprehensive Aramaic Lexicon) ASCII encoding
into Syriac Unicode.

CAL uses a reversible one-to-one mapping between ASCII and Syriac letters,
plus punctuation/diacritic conventions. See:
  https://cal.huc.edu/searching/CALCODE.pdf

This is needed because the `_syr` fields we scraped from CAL's Syriac-script
pages had mismatched verse numbering (BDO-reversed digits got normalized
wrong), leaving many verses displaying the Syriac from the *wrong* verse.
The CAL-romanization columns, however, are reliable — so we treat them as
ground truth and convert them to Syriac script ourselves.
"""

# --- Letter map: CAL char -> Syriac Unicode letter ---
# Source: CAL code help page + standard Unicode Syriac block U+0700-074F
CAL_LETTER = {
    ")": "ܐ",  # Alaph
    "b": "ܒ",  # Beth
    "g": "ܓ",  # Gamal
    "d": "ܕ",  # Dalath
    "h": "ܗ",  # He
    "w": "ܘ",  # Waw
    "z": "ܙ",  # Zayn
    "x": "ܚ",  # Heth
    "T": "ܛ",  # Teth
    "y": "ܝ",  # Yudh
    "k": "ܟ",  # Kaph
    "l": "ܠ",  # Lamadh
    "m": "ܡ",  # Mim
    "n": "ܢ",  # Nun
    "s": "ܣ",  # Semkath
    "(": "ܥ",  # E (Ayin)
    "p": "ܦ",  # Pe
    "c": "ܨ",  # Sadhe
    "q": "ܩ",  # Qoph
    "r": "ܪ",  # Resh
    "$": "ܫ",  # Shin
    "t": "ܬ",  # Taw
    # Rare/variant letters
    "P": "ܦ",  # Pe reversed — same letter
    "S": "ܣ",  # Sin (merges with Semkath in printed Syriac)
    "X": "ܟ",  # Kaph variant
}

# --- Punctuation / diacritics ---
# CAL uses a few special markers for Syriac diacritical points.
CAL_PUNCT = {
    ",": "܂",   # Pasuq (small stop)
    ".": "܂",   # also a stop
    "*": "܀",   # End marker
    "?": "܆",   # Elaya / question mark variant
    "!": "܁",
    # Seyame marker — CAL uses ":" BEFORE the letter it modifies to indicate
    # the plural dots. The actual Unicode combining seyame is U+0308 COMBINING
    # DIAERESIS (◌̈), which must come AFTER the letter. We handle this in
    # transliterate() as a stateful prefix flag.
}

# Combining seyame (two dots above) — U+0308
SEYAME = "\u0308"


def transliterate(cal_text: str) -> str:
    """Convert a CAL-romanized Syriac string to Syriac Unicode.

    Handles:
    - Basic letter-by-letter substitution
    - Seyame markers: CAL writes ":" AFTER the letter that carries the
      seyame (two dots above), so we append U+0308 to the previously-
      written Syriac letter.
    - Punctuation (",", ".", "*")
    - Preserves whitespace and unknown characters pass-through
    """
    if not cal_text:
        return ""

    out = []

    for ch in cal_text:
        if ch == ":":
            # Seyame marker — applies to PREVIOUSLY written letter.
            # Only append if the last output char is an actual letter
            # (not a space or punctuation).
            if out and out[-1] and out[-1][-1] not in " ܀܂܆܁":
                out.append(SEYAME)
            continue

        if ch in CAL_LETTER:
            out.append(CAL_LETTER[ch])
        elif ch in CAL_PUNCT:
            out.append(CAL_PUNCT[ch])
        elif ch == " ":
            out.append(" ")
        elif ch in "-_":
            # Word-internal separator; CAL uses "-" to join proclitics
            pass
        else:
            # Unknown character — pass through (numbers, foreign chars, etc.)
            out.append(ch)

    return "".join(out).strip()


def test():
    """Quick sanity test."""
    samples = [
        ("ktb) dt:wldth dy$w( m$yx), brh ddwyd brh d)brhm,",
         "Matt 1:1 — 'Book of the genealogy of Jesus Christ, son of David, son of Abraham'"),
        (")brhm )wld l)ysxq, )ysxq )wld ly(qwb, y(qwb )wld lyhwd) wl):xwhy,",
         "Matt 1:2 — 'Abraham begat Isaac...'"),
        ("br$yt )ytwhy hw) ml:t) whw ml:t) )ytwhy hw) lwt )lh) w)lh) )ytwhy hw) hw ml:t)",
         "John 1:1 — 'In the beginning was the Word...'"),
    ]
    for cal, label in samples:
        print(f"\n{label}")
        print(f"  CAL:    {cal}")
        print(f"  Syriac: {transliterate(cal)}")


if __name__ == "__main__":
    test()
