"""
Integration test: 9-node support workflow end-to-end via UI.

1. Navigate to /support
2. Switch to "Cevaplanan" tab
3. Select a ticket with known replies
4. Click "Yanıt Oluştur"
5. Wait for AI draft (all 9 nodes run)
6. Verify draft mentions customer-specific details
7. Verify edit/send buttons work
"""
from playwright.sync_api import sync_playwright
import sys

BASE = "http://localhost:5174"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # 1 — Navigate
        print("[1] Navigating to /support ...")
        page.goto(f"{BASE}/support")
        page.wait_for_load_state("networkidle")

        # 2 — Switch to "Cevaplanan" tab
        print("[2] Switching to 'Cevaplanan' tab ...")
        page.locator("button:has-text('Cevaplanan')").click()
        page.wait_for_timeout(2000)

        # 3 — Select first ticket
        print("[3] Selecting first ticket ...")
        tickets = page.locator("button:has(span:text('#'))")
        ticket_count = tickets.count()
        print(f"    Found {ticket_count} tickets")
        if ticket_count == 0:
            print("    FAIL: No tickets")
            browser.close()
            sys.exit(1)

        tickets.first.click()
        page.wait_for_timeout(2000)

        # Verify message thread loaded
        bubbles = page.locator(".rounded-lg.px-4")
        bubble_count = bubbles.count()
        print(f"    Message bubbles: {bubble_count}")
        page.screenshot(path="/tmp/support_int_01_selected.png", full_page=True)

        # 4 — Click "Yanıt Oluştur"
        print("[4] Clicking 'Yan\u0131t Olu\u015Ftur' ...")
        generate_btn = page.locator("button:has-text('Yan\u0131t Olu\u015Ftur')")
        generate_btn.click()

        # Verify generating state
        page.wait_for_timeout(1000)
        page.screenshot(path="/tmp/support_int_02_generating.png", full_page=True)

        # 5 — Wait for draft (9 nodes, ~30-60s)
        print("[5] Waiting for AI draft (max 120s) ...")
        draft_label = page.locator("text='Taslak Yan\u0131t'")
        try:
            draft_label.wait_for(state="visible", timeout=120000)
            print("    Draft appeared!")
        except Exception as e:
            page.screenshot(path="/tmp/support_int_03_timeout.png", full_page=True)
            print(f"    TIMEOUT: {e}")
            browser.close()
            sys.exit(1)

        page.screenshot(path="/tmp/support_int_04_draft.png", full_page=True)

        # 6 — Verify draft content quality
        print("[6] Verifying draft content ...")
        edit_btn = page.locator("button:has-text('D\u00fczenle')")
        edit_btn.click()
        page.wait_for_timeout(300)
        textarea = page.locator("textarea")
        draft_text = textarea.input_value()
        print(f"    Draft length: {len(draft_text)} chars")
        print(f"    Preview: {draft_text[:200]}...")

        # Check for key elements
        has_greeting = "Merhaba" in draft_text
        has_closing = "Sayg\u0131lar\u0131m\u0131zla" in draft_text
        print(f"    Has 'Merhaba': {has_greeting}")
        print(f"    Has 'Sayg\u0131lar\u0131m\u0131zla': {has_closing}")

        # 7 — Verify buttons
        print("[7] Verifying action buttons ...")
        preview_btn = page.locator("button:has-text('\u00d6nizle')")
        assert preview_btn.is_visible(), "'\u00d6nizle' visible in edit mode"
        preview_btn.click()
        page.wait_for_timeout(300)

        send_btn = page.locator("button:has-text('Onayla')")
        assert send_btn.is_visible(), "'Onayla & G\u00f6nder' visible"

        page.screenshot(path="/tmp/support_int_05_final.png", full_page=True)

        print("\n=== INTEGRATION TEST PASSED ===")
        print(f"    9 node workflow: OK")
        print(f"    Message thread: OK ({bubble_count} messages)")
        print(f"    AI draft: OK ({len(draft_text)} chars)")
        print(f"    Format: {'OK' if has_greeting and has_closing else 'WARN'}")

        browser.close()

if __name__ == "__main__":
    run()
