# Arabic OCR Quality Report: Marmardji 1935 Diatessaron

## Document Overview

The Marmardji 1935 edition (*Diatessaron de Tatien*) is a critical edition of
the Arabic Diatessaron. The main text is in French (translation), with the
Arabic text appearing in the **critical apparatus (footnotes)** along with
Syriac script variants and manuscript sigla.

This is a challenging OCR target because:
1. The Arabic text is mixed with Syriac (Estrangela) and French in the same lines
2. The text is small (footnote size, ~8-10pt)
3. The 1935 printing uses typefaces that differ from modern Arabic fonts
4. Manuscript sigla (BE, SC, SCP, ACa, etc.) intermix with the scripts

## Models Tested

| Model | Arabic Support | Speed | Notes |
|-------|---------------|-------|-------|
| **Tesseract 5.5.2** (ara+fra) | Good | ~1-5s/page | Best overall for this document |
| **EasyOCR** (ar) | Poor | ~20-370s/page | Very fragmented, low confidence |
| **Kraken** (arabic_generalized) | Failed | N/A | Segmenter breaks on mixed layout |
| **Archive.org ABBYY** | None | N/A | Zero Arabic recognized |

## Detailed Quality Assessment

### page_n200 footnote

- **Exact word matches**: 5/10 (50.0%)
- **Fuzzy word matches**: 5/10 (50.0%)

  MISS:  ليحملوك
  MISS:  ليحملونك
  EXACT: يتناولونك
  MISS:  أذرعهم
  EXACT: أذرعتهم
  MISS:  فقد
  MISS:  بالا
  EXACT: واصعده
  EXACT: قال
  EXACT: يكون

### page_n300 footnote

- **Exact word matches**: 6/8 (75.0%)
- **Fuzzy word matches**: 7/8 (87.5%)

  EXACT: اتكى
  FUZZY: خالي -> found as 'خال'
  EXACT: الفريسي
  MISS:  قارورة
  EXACT: ابدت
  EXACT: ذلك
  EXACT: الذي
  EXACT: المتزلي

### page_n400 footnote

- **Exact word matches**: 7/10 (70.0%)
- **Fuzzy word matches**: 8/10 (80.0%)

  EXACT: جاروا
  FUZZY: ماذا -> found as 'اذا'
  MISS:  بينكم
  EXACT: في
  EXACT: الطريق
  EXACT: درهمين
  EXACT: من
  EXACT: كل
  EXACT: واحد
  MISS:  قبر

## Overall Results

- **Exact Arabic word recognition rate**: 18/28 (64.3%)
- **Fuzzy recognition rate** (1-char tolerance): 20/28 (71.4%)

## Key Findings

1. **Tesseract is the best open-source option** for this specific document.
   It recognizes common Arabic words (articles, prepositions, nouns) with
   moderate accuracy, but struggles with:
   - Words adjacent to Syriac script (script confusion)
   - Manuscript sigla mixed into the text
   - Small footnote font size

2. **EasyOCR performs poorly** on this document. It over-fragments the text
   and has very low confidence scores (avg 0.1-0.3). Not recommended.

3. **Kraken's Arabic model fails** due to the mixed-script layout breaking
   its line segmentation algorithm (hundreds of polygonizer errors).

4. **Archive.org's ABBYY OCR** has zero Arabic recognition - all Arabic
   characters are misrecognized as Latin garbage.

5. **Qari-OCR (NAMAA)** is a promising newer model based on Qwen2-VL-2B
   fine-tuned for Arabic OCR. It requires a GPU and ~4GB VRAM. It would
   be worth testing on a GPU machine (e.g., HPC) as it claims state-of-the-art
   Arabic OCR performance including diacritics support.

## Recommendations for the Diatessaron Project

### Is OCR sufficient for computational analysis?

**Not yet, with current open-source tools.** The Arabic text in the Marmardji
edition is a particularly challenging OCR target due to the tri-script
(Arabic + Syriac + French) mixed layout. Estimated character-level accuracy
for the Arabic portions is approximately **40-60%** with Tesseract, which is
insufficient for reliable computational text analysis.

### Recommended Approaches

1. **Use Qari-OCR on GPU** (priority: test on HPC with A100 GPUs)
   - NAMAA-Space/Qari-OCR-v0.3-VL-2B-Instruct on HuggingFace
   - Vision-language model approach may handle mixed scripts better

2. **Pre-segment the page** before OCR:
   - Separate French main text from footnotes
   - Within footnotes, try to isolate Arabic-only spans
   - Run Arabic-only OCR on isolated Arabic segments

3. **Google Cloud Vision API** (commercial option)
   - Typically handles mixed-script documents better
   - Free tier allows 1000 pages/month

4. **Fine-tune a model** on this specific document type:
   - Create ground truth from manually transcribed pages
   - Fine-tune Kraken or TrOCR on Marmardji's specific typeface
   - This would give the best results but requires manual effort

5. **Check existing digital editions:**
   - The Arabic Diatessaron text may already exist in digital form
   - OpenITI/KITAB corpus may have it
   - The Vetus Latina project or other biblical text databases
