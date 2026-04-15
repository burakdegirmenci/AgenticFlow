"""UI test: navigate to /support, capture screenshot."""
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

    print("1) Navigate to /support")
    page.goto("http://127.0.0.1:5173/support")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(SCREENS / "support_01_page.png"), full_page=True)
    print("   Screenshot saved")

    # Check if tickets loaded
    ticket_items = page.locator("button:has-text('#')")
    count = ticket_items.count()
    print(f"   Ticket items visible: {count}")

    if count > 0:
        print("2) Click first ticket")
        ticket_items.first.click()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENS / "support_02_selected.png"), full_page=True)
        print("   Screenshot saved")

        # Click "Yanit Olustur"
        run_btn = page.get_by_role("button", name="Yanit Olustur")
        if run_btn.count() == 0:
            run_btn = page.locator("button:has-text('Yanit')")
        if run_btn.count() > 0:
            print("3) Click 'Yanit Olustur'")
            run_btn.first.click()
            # Wait for agent to finish (max 60s)
            page.wait_for_timeout(3000)
            page.screenshot(path=str(SCREENS / "support_03_running.png"), full_page=True)

            # Wait for draft reply or done
            try:
                page.locator("text=/Taslak Yanit/i").wait_for(timeout=60000)
                print("   Draft reply appeared!")
            except Exception:
                print("   Timeout waiting for draft reply")

            page.wait_for_timeout(1000)
            page.screenshot(path=str(SCREENS / "support_04_draft.png"), full_page=True)
            print("   Final screenshot saved")

    print(f"\nScreenshots: {SCREENS}")
    browser.close()
