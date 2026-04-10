/* =========================================================================
   Diatessaron Synopsis — Alpine.js application
   =========================================================================
   Loads the three JSON data files produced by scripts/build_web_data.py
   and exposes a reactive store for the UI.
   ========================================================================= */

// Roman numeral conversion (1-55 suffices for Diatessaron sections)
function toRoman(n) {
  if (!n || n < 1 || n > 3999) return "";
  const table = [
    ["M", 1000], ["CM", 900], ["D", 500], ["CD", 400],
    ["C", 100], ["XC", 90], ["L", 50], ["XL", 40],
    ["X", 10], ["IX", 9], ["V", 5], ["IV", 4], ["I", 1],
  ];
  let result = "";
  for (const [r, v] of table) {
    while (n >= v) { result += r; n -= v; }
  }
  return result;
}

function diatessaronApp() {
  return {
    // --- State ---
    route: "home",
    stats: null,
    gospels: null,       // {Matthew: [{c, verses:[{v, greek, peshitta, ...}]}], ...}
    diatessaron: null,   // {"1": {section, arabic, hogg, hill_refs, ciasca_refs, ...}}

    books: ["Matthew", "Mark", "Luke", "John"],

    sel: { book: "Matthew", chapter: 1, verse: 1 },

    selSection: 1,
    tab: "fourlang",

    // --- Init ---
    async init() {
      // Parse hash route on load and on every change.
      // The browser's native hash navigation drives the route.
      const applyHash = () => this.parseHash();
      applyHash();
      window.addEventListener("hashchange", applyHash);

      // Watch dropdown changes (inside Parallel View) to update hash
      // so URL stays in sync with selection.
      this.$watch("sel.book",    () => this.syncHashIfParallel());
      this.$watch("sel.chapter", () => this.syncHashIfParallel());
      this.$watch("sel.verse",   () => this.syncHashIfParallel());
      this.$watch("selSection",  () => this.syncHashIfDia());

      // Load data files
      try {
        const [stats, gospels, dia] = await Promise.all([
          fetch("data/corpus_stats.json").then((r) => r.json()),
          fetch("data/gospels.json").then((r) => r.json()),
          fetch("data/diatessaron.json").then((r) => r.json()),
        ]);
        this.stats = stats;
        this.gospels = gospels;
        this.diatessaron = dia;
        console.log("Data loaded:",
          Object.keys(gospels).length, "gospels,",
          Object.keys(dia).length, "Diatessaron sections");
      } catch (e) {
        console.error("Failed to load data:", e);
      }
    },

    // --- Routing ---
    parseHash() {
      const hash = window.location.hash.slice(2); // strip "#/"
      if (!hash) { this.route = "home"; return; }
      const parts = hash.split("/").filter(Boolean);
      if (parts[0] === "parallel") {
        this.route = "parallel";
        if (parts[1] && this.books.includes(parts[1])) this.sel.book = parts[1];
        if (parts[2]) this.sel.chapter = parseInt(parts[2]) || 1;
        if (parts[3]) this.sel.verse = parseInt(parts[3]) || 1;
      } else if (parts[0] === "diatessaron") {
        this.route = "diatessaron";
        if (parts[1]) this.selSection = parseInt(parts[1]) || 1;
      } else if (parts[0] === "about") {
        this.route = "about";
      } else {
        this.route = "home";
      }
    },

    updateHash(path) {
      // Use replaceState to avoid adding entries for every dropdown change
      const target = `#/${path}`;
      if (window.location.hash !== target) {
        if (history.replaceState) {
          history.replaceState(null, "", target);
        } else {
          window.location.hash = `/${path}`;
        }
      }
    },

    syncHashIfParallel() {
      if (this.route === "parallel") {
        this.updateHash(`parallel/${this.sel.book}/${this.sel.chapter}/${this.sel.verse}`);
      }
    },

    syncHashIfDia() {
      if (this.route === "diatessaron") {
        this.updateHash(`diatessaron/${this.selSection}`);
      }
    },

    // --- Parallel view helpers ---
    chaptersOf(book) {
      if (!this.gospels || !this.gospels[book]) return [];
      return this.gospels[book].map((c) => c.c);
    },

    versesOf(book, chapter) {
      if (!this.gospels || !this.gospels[book]) return [];
      const ch = this.gospels[book].find((c) => c.c === chapter);
      return ch ? ch.verses.map((v) => v.v) : [];
    },

    currentVerse() {
      if (!this.gospels || !this.gospels[this.sel.book]) return null;
      const ch = this.gospels[this.sel.book].find((c) => c.c === this.sel.chapter);
      if (!ch) return null;
      return ch.verses.find((v) => v.v === this.sel.verse) || null;
    },

    nextVerse() {
      const verses = this.versesOf(this.sel.book, this.sel.chapter);
      const idx = verses.indexOf(this.sel.verse);
      if (idx >= 0 && idx < verses.length - 1) {
        this.sel.verse = verses[idx + 1];
      } else {
        // Move to next chapter
        const chapters = this.chaptersOf(this.sel.book);
        const chIdx = chapters.indexOf(this.sel.chapter);
        if (chIdx >= 0 && chIdx < chapters.length - 1) {
          this.sel.chapter = chapters[chIdx + 1];
          this.sel.verse = this.versesOf(this.sel.book, this.sel.chapter)[0] || 1;
        }
      }
    },

    prevVerse() {
      const verses = this.versesOf(this.sel.book, this.sel.chapter);
      const idx = verses.indexOf(this.sel.verse);
      if (idx > 0) {
        this.sel.verse = verses[idx - 1];
      } else {
        // Move to previous chapter
        const chapters = this.chaptersOf(this.sel.book);
        const chIdx = chapters.indexOf(this.sel.chapter);
        if (chIdx > 0) {
          this.sel.chapter = chapters[chIdx - 1];
          const pv = this.versesOf(this.sel.book, this.sel.chapter);
          this.sel.verse = pv[pv.length - 1] || 1;
        }
      }
    },

    // --- Diatessaron explorer helpers ---
    get sectionNumbers() {
      // Show all 55 even if some are missing — user should see the full structure
      return Array.from({ length: 55 }, (_, i) => i + 1);
    },

    currentSection() {
      if (!this.diatessaron) return null;
      return this.diatessaron[String(this.selSection)] || null;
    },

    romanNumeral(n) { return toRoman(n); },

    // Jump from Diatessaron refs to the canonical verse in Parallel view
    jumpToVerse(book, chapter, verse) {
      if (!book || !chapter || !verse) return;
      this.sel.book = book;
      this.sel.chapter = chapter;
      this.sel.verse = verse;
      window.location.hash = `#/parallel/${book}/${chapter}/${verse}`;
    },

    // Look up a canonical verse in the gospels index.
    // Returns {greek, peshitta, old_syriac_cur, old_syriac_sin, ...} or null.
    getGospelVerse(book, chapter, verse) {
      if (!this.gospels || !this.gospels[book]) return null;
      const ch = this.gospels[book].find((c) => c.c === chapter);
      if (!ch) return null;
      return ch.verses.find((v) => v.v === verse) || null;
    },

    // Parse a Diatessaron-Arabic section's body text into a map:
    //   Arabic-numeral "verse" -> text chunk
    // The Arabic text uses Eastern Arabic digits (١٢٣...) in parentheses,
    // e.g. "(١) وقال يسوع ..." to mark verse boundaries.
    //
    // Returns a Map keyed by ASCII digit string ("1", "2", ...).
    parseArabicVerses(arabicText) {
      const map = new Map();
      if (!arabicText) return map;
      // Convert Eastern Arabic digits to ASCII for matching
      const EAST_TO_ASCII = {"٠":"0","١":"1","٢":"2","٣":"3","٤":"4","٥":"5","٦":"6","٧":"7","٨":"8","٩":"9"};
      // Regex matches "(X)" where X is one or more Eastern Arabic digits
      // (possibly with a leading marker) — captured as the verse number.
      // We split on these markers to get per-verse chunks.
      const markerRe = /[\(（]\s*([٠١٢٣٤٥٦٧٨٩]+)\s*[\)）]\.?/g;
      const matches = [];
      let m;
      while ((m = markerRe.exec(arabicText)) !== null) {
        const eastDigits = m[1];
        const ascii = eastDigits.split("").map((c) => EAST_TO_ASCII[c] || c).join("");
        matches.push({ verseNum: ascii, start: m.index, end: m.index + m[0].length });
      }
      if (matches.length === 0) {
        // No verse markers — return whole text under key "1"
        map.set("1", arabicText.trim());
        return map;
      }
      // Text before first marker → belongs to verse 1 (or ignore as incipit)
      // Iterate pairs
      for (let i = 0; i < matches.length; i++) {
        const cur = matches[i];
        const next = matches[i + 1];
        const chunk = arabicText.slice(cur.end, next ? next.start : undefined).trim();
        // Prepend prior existing text (for the first chunk before verse 1, ignore)
        map.set(cur.verseNum, chunk);
      }
      return map;
    },

    // For the CURRENT Diatessaron section, build a row-per-verse table of
    // SEVEN languages:
    //   1. Greek (SBLGNT)
    //   2. Peshitta (Syriac)
    //   3. Old Syriac Curetonian
    //   4. Old Syriac Sinaiticus
    //   5. Arabic Diatessaron (Ciasca 1888) — split by verse markers
    //   6. English Hogg — translated FROM the Arabic
    //   7. English KJV — translated FROM the Greek (reference standard)
    //
    // Row unit = Hogg sub-verse. We use its verse number ("1", "2,3") to
    // look up the matching Arabic verse chunk, and its gospel ref (from
    // Hogg's own margin) to look up Greek/Peshitta/Old Syriac/KJV.
    sevenLangRows() {
      const sec = this.currentSection();
      if (!sec || !sec.hogg_verses || !this.gospels) return [];
      const arabicMap = this.parseArabicVerses(sec.arabic || "");

      const rows = [];
      for (const hv of sec.hogg_verses) {
        const verseKey = (hv.v || "").trim(); // e.g. "1" or "2,3"
        const firstKey = verseKey.split(/[,\s\-–]/)[0]; // first part for Arabic lookup

        // Parse the first gospel ref to get canonical verse
        // Hogg gospel_refs format: ["John i. 1", "Luke iii. 5"]
        const firstRef = (hv.refs && hv.refs[0]) || "";
        const parsed = this.parseGospelRef(firstRef);

        let greek = "", peshitta = "", cur = "", sin = "", kjv = "";
        if (parsed) {
          const gv = this.getGospelVerse(parsed.book, parsed.ch, parsed.v);
          if (gv) {
            greek = gv.greek || "";
            peshitta = gv.peshitta || "";
            cur = gv.old_syriac_cur_syr || gv.old_syriac_cur || "";
            sin = gv.old_syriac_sin_syr || gv.old_syriac_sin || "";
            kjv = gv.kjv || "";
          }
        }

        rows.push({
          dv: verseKey,
          ref: firstRef,
          parsedRef: parsed,
          greek,
          peshitta,
          old_syriac_cur: cur,
          old_syriac_sin: sin,
          arabic: arabicMap.get(firstKey) || "",
          hogg: hv.text || "",
          kjv,
        });
      }
      return rows;
    },

    // Backwards-compatible alias in case anything still calls sixLangRows
    sixLangRows() { return this.sevenLangRows(); },

    // Visibility toggle state for each language column (user can hide any).
    langVisible: {
      greek: true,
      peshitta: true,
      cur: true,
      sin: true,
      arabic: true,
      hogg: true,
      kjv: true,
    },

    toggleLang(key) {
      this.langVisible[key] = !this.langVisible[key];
    },

    // Parse a Hogg gospel reference like "John i. 1" or "Matt. xvi. 17" into
    // {book, ch, v}. Roman numerals for chapter, arabic for verse.
    parseGospelRef(ref) {
      if (!ref) return null;
      // Normalize whitespace and punctuation
      const m = ref.match(/^([A-Za-z]+)\.?\s+([ivxlcdmIVXLCDM]+)\.?\s+(\d+)/);
      if (!m) return null;
      const bookAbbrev = m[1];
      const chRoman = m[2].toUpperCase();
      const v = parseInt(m[3]);
      const bookMap = { Matt: "Matthew", Mat: "Matthew", Mark: "Mark", Mk: "Mark",
                        Luke: "Luke", Lk: "Luke", Luc: "Luke",
                        John: "John", Jn: "John", Joh: "John", Ioan: "John" };
      const book = bookMap[bookAbbrev] || bookAbbrev;
      const ch = this.romanToInt(chRoman);
      if (!ch || !v) return null;
      return { book, ch, v };
    },

    romanToInt(s) {
      if (!s) return 0;
      const map = { I:1, V:5, X:10, L:50, C:100, D:500, M:1000 };
      let total = 0;
      for (let i = 0; i < s.length; i++) {
        const cur = map[s[i]], next = map[s[i + 1]];
        if (next && cur < next) { total -= cur; } else { total += cur; }
      }
      return total;
    },

    // Given a gospel verse, find which Diatessaron section(s) contain it
    // (by scanning Hill mapping)
    diatessaronSectionsFor(book, chapter, verse) {
      if (!this.diatessaron) return [];
      const matches = new Set();
      for (const [secNum, data] of Object.entries(this.diatessaron)) {
        const refs = data.hill_refs || [];
        for (const r of refs) {
          if (r.book === book &&
              parseInt(r.ch) === chapter &&
              parseInt(r.v) === verse) {
            matches.add(parseInt(secNum));
            break;
          }
        }
      }
      return Array.from(matches).sort((a, b) => a - b);
    },
  };
}
