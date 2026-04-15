"""UI test: pick an iade ticket to test tool_call rendering in agent log."""
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

    page.goto("http://127.0.0.1:5173/support")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # Find an iade ticket (second item should be iade)
    ticket_items = page.locator("button:has-text('#')")
    count = ticket_items.count()
    print(f"Ticket items: {count}")

    # Pick ticket #19510 (Iade Hakkinda) - second item
    iade_ticket = page.locator("button:has-text('#19510')")
    if iade_ticket.count() > 0:
        print("1) Clicking ticket #19510 (Iade Hakkinda)")
        iade_ticket.first.click()
        page.wait_for_timeout(1000)
    else:
        # Fallback to second item
        print("1) Clicking second ticket")
        ticket_items.nth(1).click()
        page.wait_for_timeout(1000)

    page.screenshot(path=str(SCREENS / "iade_01_selected.png"), full_page=True)

    # Click Yanit Olustur
    run_btn = page.locator("button:has-text('Yan\u0131t Olu\u015Ftur')")
    if run_btn.count() > 0:
        print("2) Click 'Yanit Olustur'")
        run_btn.first.click()
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SCREENS / "iade_02_running.png"), full_page=True)

        # Wait for draft
        try:
            page.get_by_text("Taslak Yan\u0131t", exact=True).wait_for(timeout=90000)
            print("   Draft reply appeared!")
        except Exception as e:
            print(f"   Timeout: {e}")

        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENS / "iade_03_draft.png"), full_page=True)

        # Check for tool_call entries (should see lookup_customer_orders)
        tool_entries = page.locator("text=lookup_customer_orders")
        print(f"   Tool call entries for lookup_customer_orders: {tool_entries.count()}")

        tool_detail = page.locator("text=lookup_order_detail")
        print(f"   Tool call entries for lookup_order_detail: {tool_detail.count()}")

        draft_visible = page.get_by_text("Taslak Yan\u0131t", exact=True).count()
        print(f"   Draft card visible: {draft_visible > 0}")

        send_btn = page.locator("button:has-text('Onayla')")
        print(f"   Send button visible: {send_btn.count() > 0}")

        print("\n   PASS" if draft_visible > 0 else "\n   FAIL")

    print(f"\nScreenshots: {SCREENS}")
    browser.close()
