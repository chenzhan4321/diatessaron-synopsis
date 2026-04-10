"""
Test QARI-OCR (NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct) on Ciasca 1888 Arabic pages.

QARI-OCR is a Qwen2-VL based vision-language model fine-tuned for Arabic OCR.
We load it in float16 on Apple Silicon (no bitsandbytes needed).
"""
import os
import sys
import glob
import time
import torch
from pathlib import Path

# Paths
IMAGE_DIR = "/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_arabic_ocr/ciasca_pages"
OUTPUT_DIR = "/Users/zhanchen/Library/CloudStorage/Dropbox/Projects/test.tatian/data/diatessaron_arabic_ocr/results/ciasca_qari"
# v0.3 is a fully merged model (not a LoRA adapter), so it loads directly
MODEL_ID = "NAMAA-Space/Qari-OCR-v0.3-VL-2B-Instruct"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -- Load model and processor --
print(f"Loading model: {MODEL_ID}")
t0 = time.time()

from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# Use float16 on Apple Silicon (MPS) or CPU
# device_map="auto" should pick MPS on macOS with Apple Silicon
model = Qwen2VLForConditionalGeneration.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    device_map="auto",
)
processor = AutoProcessor.from_pretrained(MODEL_ID)

print(f"Model loaded in {time.time() - t0:.1f}s")
print(f"Model device: {next(model.parameters()).device}")

# -- Process pages --
# Only process first 4 pages for testing
image_files = sorted(glob.glob(os.path.join(IMAGE_DIR, "page_*.png")))[:4]
print(f"\nWill process {len(image_files)} pages: {[os.path.basename(f) for f in image_files]}")

for img_path in image_files:
    page_name = Path(img_path).stem
    print(f"\n{'='*60}")
    print(f"Processing: {page_name}")
    t1 = time.time()

    # Build the chat message with image input
    # QARI-OCR expects a simple prompt asking to read Arabic text
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{img_path}"},
                {"type": "text", "text": "اقرأ النص العربي في هذه الصورة بدقة."},
            ],
        }
    ]

    # Prepare inputs using Qwen2-VL chat template
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    # Generate OCR output
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=2048,
            do_sample=False,  # greedy for reproducibility
        )

    # Decode only the generated tokens (skip input tokens)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]

    elapsed = time.time() - t1
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Output length: {len(output_text)} chars")
    print(f"  Preview (first 200 chars):\n{output_text[:200]}")

    # Save output
    out_path = os.path.join(OUTPUT_DIR, f"{page_name}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output_text)
    print(f"  Saved to: {out_path}")

print(f"\n{'='*60}")
print("All done!")
