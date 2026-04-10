"""Extract PDF pages 133-140 from Ciasca 1888 as high-resolution PNG images (300 DPI)."""
import fitz  # PyMuPDF
import os

PDF_PATH = "/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_arabic_ocr/Ciasca 1888_Tatiani Evangeliorum Harmoniae....pdf"
OUT_DIR = "/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_arabic_ocr/ciasca_pages"

os.makedirs(OUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)
print(f"Total pages in PDF: {doc.page_count}")

# PDF pages 133-140 (0-indexed: 132-139)
for page_num in range(132, 140):
    page = doc[page_num]
    # 300 DPI: default is 72 DPI, so zoom factor = 300/72 ≈ 4.17
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    out_path = os.path.join(OUT_DIR, f"page_{page_num + 1:04d}.png")
    pix.save(out_path)
    print(f"Saved {out_path} ({pix.width}x{pix.height})")

doc.close()
print("Done!")
