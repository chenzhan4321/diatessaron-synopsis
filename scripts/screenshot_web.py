"""Take screenshots of all web views for visual verification."""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
OUT = Path(__file__).resolve().parent.parent / "data" / "web_screenshots"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    page = context.new_page()

    # Home
    page.goto(BASE + "/#/home")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "01_home.png"), full_page=True)
    print("✓ home")

    # Parallel: Matt 1:1
    page.goto(BASE + "/#/parallel/Matthew/1/1")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "02_parallel_matt_1_1.png"), full_page=True)
    print("✓ parallel Matt 1:1")

    # Parallel: Luke 22:15 (Old Syriac exists)
    page.goto(BASE + "/#/parallel/Luke/22/15")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "03_parallel_luke_22_15.png"), full_page=True)
    print("✓ parallel Luke 22:15")

    # Diatessaron Section 1
    page.goto(BASE + "/#/diatessaron/1")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "04_diatessaron_s1.png"), full_page=True)
    print("✓ dia section 1")

    # Diatessaron Section 10 (click tab English)
    page.goto(BASE + "/#/diatessaron/10")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.click("button:has-text('English')")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "05_diatessaron_s10_english.png"), full_page=True)
    print("✓ dia section 10 english")

    # Diatessaron Section 1 refs
    page.goto(BASE + "/#/diatessaron/1")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.click("button:has-text('Gospel Refs')")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "06_diatessaron_refs.png"), full_page=True)
    print("✓ dia refs")

    # About
    page.goto(BASE + "/#/about")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "07_about.png"), full_page=True)
    print("✓ about")

    browser.close()

print(f"\nScreenshots saved to {OUT}")
