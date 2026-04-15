"""Full UI test: select ticket -> run agent -> verify draft reply."""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from pathlib import Path

SCREENS = Path(__file__).parent / "_ui_test_screens"
SCREENS.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})

    # 1) Navigate to /support
    print("1) Navigate to /support")
    page.goto("http://127.0.0.1:5173/support")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(SCREENS / "full_01_page.png"), full_page=True)

    # 2) Click first ticket
    ticket_items = page.locator("button:has-text('#')")
    count = ticket_items.count()
    print(f"   Ticket items visible: {count}")

    if count == 0:
        print("   ERROR: No tickets found")
        browser.close()
        sys.exit(1)

    print("2) Click first ticket")
    ticket_items.first.click()
    page.wait_for_timeout(1000)
    page.screenshot(path=str(SCREENS / "full_02_selected.png"), full_page=True)

    # 3) Click "Yanit Olustur" button (Turkish chars)
    run_btn = page.locator("button:has-text('Yan\u0131t Olu\u015Ftur')")
    btn_count = run_btn.count()
    print(f"   'Yanit Olustur' buttons found: {btn_count}")

    if btn_count == 0:
        # Fallback: find by Bot icon nearby
        run_btn = page.locator("button:has-text('Olu')")
        btn_count = run_btn.count()
        print(f"   Fallback buttons found: {btn_count}")

    if btn_count > 0:
        print("3) Click 'Yanit Olustur'")
        run_btn.first.click()
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SCREENS / "full_03_running.png"), full_page=True)
        print("   Agent running...")

        # Wait for draft reply to appear (max 90s)
        try:
            page.locator("text=Taslak Yan\u0131t").wait_for(timeout=90000)
            print("   Draft reply appeared!")
        except Exception as e:
            print(f"   Timeout waiting for draft reply: {e}")

        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENS / "full_04_draft.png"), full_page=True)
        print("   Draft screenshot saved")

        # Check if draft reply card is visible
        draft_card = page.locator("text=Taslak Yan\u0131t")
        if draft_card.count() > 0:
            print("   PASS: Draft reply card visible")

            # Check if send button is visible
            send_btn = page.locator("button:has-text('Onayla')")
            if send_btn.count() > 0:
                print("   PASS: 'Onayla & Gonder' button visible")
            else:
                print("   WARN: Send button not found")

            # Check if edit button is visible
            edit_btn = page.locator("button:has-text('D\u00fczenle')")
            if edit_btn.count() > 0:
                print("   PASS: 'Duzenle' button visible")
        else:
            print("   FAIL: Draft reply card not visible")

        # Take final full screenshot
        page.screenshot(path=str(SCREENS / "full_05_final.png"), full_page=True)
        print("   Final screenshot saved")
    else:
        print("   ERROR: Could not find 'Yanit Olustur' button")

    print(f"\nScreenshots: {SCREENS}")
    browser.close()
