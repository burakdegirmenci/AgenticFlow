"""
Playwright UI test: Support page with workflow-based reply generation.

Flow:
1. Navigate to /support
2. Verify ticket list loads
3. Select first ticket
4. Click "Yanıt Oluştur" (triggers workflow)
5. Wait for draft reply to appear (polling-based)
6. Verify draft card with "Onayla & Gönder" and "Düzenle" buttons
"""
from playwright.sync_api import sync_playwright
import time
import sys

BASE = "http://localhost:5174"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # 1 — Navigate to /support
        print("[1] Navigating to /support ...")
        page.goto(f"{BASE}/support")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="/tmp/support_01_loaded.png", full_page=True)

        # 2 — Wait for ticket list
        print("[2] Waiting for ticket list ...")
        # Wait for either a ticket button or "Ticket bulunamad\u0131" text
        ticket_or_empty = page.locator(
            "button:has(span:text('#'))"
        )
        ticket_or_empty.first.wait_for(state="visible", timeout=15000)
        ticket_count = ticket_or_empty.count()
        print(f"    Found {ticket_count} tickets")

        if ticket_count == 0:
            print("    No tickets found, cannot continue test.")
            browser.close()
            sys.exit(1)

        # 3 — Select first ticket
        print("[3] Selecting first ticket ...")
        ticket_or_empty.first.click()
        page.wait_for_timeout(500)
        page.screenshot(path="/tmp/support_02_selected.png", full_page=True)

        # Verify right panel shows ticket details
        header = page.locator("span:text('#'):visible").first
        assert header.is_visible(), "Ticket header should be visible"
        print("    Ticket selected, details visible.")

        # 4 — Click "Yanıt Oluştur" button
        print("[4] Clicking 'Yan\u0131t Olu\u015Ftur' ...")
        generate_btn = page.locator("button:has-text('Yan\u0131t Olu\u015Ftur')")
        generate_btn.wait_for(state="visible", timeout=5000)
        generate_btn.click()
        page.screenshot(path="/tmp/support_03_generating.png", full_page=True)

        # Should see "Oluşturuluyor…" state
        page.wait_for_timeout(500)
        generating_text = page.locator("text=Yan\u0131t olu\u015Fturuluyor")
        if generating_text.count() > 0:
            print("    Generating state visible.")
        else:
            print("    Warning: 'Yanıt oluşturuluyor' text not found (may have completed very fast)")

        # 5 — Wait for draft to appear (workflow takes ~10-30s)
        print("[5] Waiting for draft reply (max 120s) ...")
        draft_label = page.locator("text='Taslak Yan\u0131t'")
        try:
            draft_label.wait_for(state="visible", timeout=120000)
            print("    Draft reply appeared!")
        except Exception as e:
            page.screenshot(path="/tmp/support_04_timeout.png", full_page=True)
            print(f"    TIMEOUT waiting for draft: {e}")
            browser.close()
            sys.exit(1)

        page.screenshot(path="/tmp/support_05_draft.png", full_page=True)

        # 6 — Verify action buttons
        print("[6] Verifying action buttons ...")

        send_btn = page.locator("button:has-text('Onayla')")
        assert send_btn.is_visible(), "'Onayla & Gönder' button should be visible"
        print("    'Onayla & Gönder' button visible.")

        edit_btn = page.locator("button:has-text('D\u00fczenle')")
        assert edit_btn.is_visible(), "'Düzenle' button should be visible"
        print("    'Düzenle' button visible.")

        # 7 — Test edit mode
        print("[7] Testing edit mode ...")
        edit_btn.click()
        page.wait_for_timeout(300)

        textarea = page.locator("textarea")
        assert textarea.is_visible(), "Textarea should be visible in edit mode"
        draft_text = textarea.input_value()
        print(f"    Draft text length: {len(draft_text)} chars")
        assert len(draft_text) > 20, "Draft text should be substantial"

        # Verify "Önizle" button (edit mode toggle)
        preview_btn = page.locator("button:has-text('\u00d6nizle')")
        assert preview_btn.is_visible(), "'Önizle' button should be visible in edit mode"
        preview_btn.click()
        page.wait_for_timeout(300)
        page.screenshot(path="/tmp/support_06_preview.png", full_page=True)

        print("\n=== ALL TESTS PASSED ===")
        browser.close()

if __name__ == "__main__":
    run()
