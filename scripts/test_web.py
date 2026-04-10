"""Automated browser test for the Diatessaron Synopsis web app.

Uses Playwright + Chromium to verify:
  1. Home page loads and Alpine.js initializes
  2. Nav links work (route switching)
  3. Parallel view shows data for Matt 1:1
  4. Diatessaron explorer shows section content
  5. No JS console errors
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"


def test():
    errors = []
    console_messages = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Capture console messages and errors
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: errors.append(f"PAGE ERROR: {err}"))

        # === TEST 1: Home page loads ===
        print("Test 1: Home page loads...")
        page.goto(BASE)
        page.wait_for_load_state("networkidle")

        # Check header present
        title = page.locator(".site-title").inner_text()
        assert "Diatessaron Synopsis" in title, f"Title wrong: {title}"

        # Check home section is visible
        home_visible = page.locator(".page.home").is_visible()
        if not home_visible:
            errors.append("Home section not visible after load")
        else:
            print("  ✓ Home section visible")

        # Check hero title
        hero = page.locator(".hero-title")
        if hero.count() > 0:
            hero_text = hero.inner_text()
            print(f"  ✓ Hero: {hero_text[:60]}...")
        else:
            errors.append("Hero title not rendered")

        # Check corpus cards rendered (data loaded)
        cards = page.locator(".corpus-card")
        card_count = cards.count()
        print(f"  ✓ {card_count} corpus cards rendered")
        if card_count < 5:
            errors.append(f"Only {card_count} corpus cards, expected >=5")

        # === TEST 2: Navigation works ===
        print("\nTest 2: Navigation works...")
        page.click("a[href='#/parallel']")
        page.wait_for_timeout(300)

        parallel_visible = page.locator(".page.parallel").is_visible()
        home_hidden = not page.locator(".page.home").is_visible()
        print(f"  Parallel visible: {parallel_visible}, Home hidden: {home_hidden}")
        if not parallel_visible:
            errors.append("Parallel page did not show after click")
        if not home_hidden:
            errors.append("Home page still visible after nav to parallel")

        # === TEST 3: Parallel view shows data for Matt 1:1 ===
        print("\nTest 3: Parallel view shows data...")
        page.wait_for_timeout(500)  # let data render

        version_cards = page.locator(".version-card")
        n_versions = version_cards.count()
        print(f"  ✓ {n_versions} version cards shown")
        if n_versions < 3:
            errors.append(f"Only {n_versions} version cards, expected >=3")

        # Check Greek text is visible
        greek = page.locator(".verse-text.grk").first
        if greek.count() > 0:
            greek_text = greek.inner_text()
            print(f"  ✓ Greek: {greek_text[:60]}...")
        else:
            errors.append("No Greek text rendered")

        # Check Peshitta (Syriac) text
        syr = page.locator(".verse-text.syr").first
        if syr.count() > 0:
            syr_text = syr.inner_text()
            print(f"  ✓ Syriac: {syr_text[:30]}...")
        else:
            errors.append("No Syriac text rendered")

        # === TEST 4: Diatessaron explorer ===
        print("\nTest 4: Diatessaron explorer...")
        page.click("a[href='#/diatessaron']")
        page.wait_for_timeout(500)

        dia_visible = page.locator(".page.diatessaron").is_visible()
        print(f"  Diatessaron visible: {dia_visible}")
        if not dia_visible:
            errors.append("Diatessaron page did not show")

        section_btns = page.locator(".section-btn")
        n_sections = section_btns.count()
        print(f"  ✓ {n_sections} section buttons")
        if n_sections != 55:
            errors.append(f"Expected 55 section buttons, got {n_sections}")

        # Check section 1 content
        section_header = page.locator(".section-header h2")
        if section_header.count() > 0:
            print(f"  ✓ Section header: {section_header.inner_text()[:60]}")
        else:
            errors.append("No section header")

        # Click section 5 button
        if n_sections >= 5:
            section_btns.nth(4).click()
            page.wait_for_timeout(200)

        # === TEST 5: About page ===
        print("\nTest 5: About page...")
        page.click("a[href='#/about']")
        page.wait_for_timeout(300)
        about_visible = page.locator(".page.about").is_visible()
        print(f"  About visible: {about_visible}")
        if not about_visible:
            errors.append("About page did not show")

        # === TEST 6: Hash URL persistence ===
        print("\nTest 6: Hash URL persistence...")
        page.goto(BASE + "/#/parallel/John/1/1")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        parallel_visible = page.locator(".page.parallel").is_visible()
        if not parallel_visible:
            errors.append("Deep link #/parallel/John/1/1 did not load parallel page")
        else:
            # Check Book selector shows John
            book_sel = page.locator("select").first
            book_val = book_sel.input_value()
            print(f"  ✓ Book selector: {book_val}")
            if book_val != "John":
                errors.append(f"Deep link: book is {book_val}, expected John")

        browser.close()

    # Report
    print("\n" + "=" * 60)
    if errors:
        print(f"FAILURES ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("ALL TESTS PASSED ✓")

    if console_messages:
        print(f"\nConsole messages ({len(console_messages)}):")
        for m in console_messages[-10:]:
            print(f"  {m}")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(test())
