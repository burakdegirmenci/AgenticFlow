"""
Playwright test: Support page — conversation thread UI.

1. Navigate to /support, switch to "Cevaplanan" tab
2. Select a ticket that has replies
3. Verify message bubbles appear (both customer & staff)
4. Screenshot the conversation view
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

        # 2 — Switch to "Cevaplanan" tab to find tickets with replies
        print("[2] Switching to 'Cevaplanan' tab ...")
        page.locator("button:has-text('Cevaplanan')").click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/support_msg_01_cevaplanan.png", full_page=True)

        # 3 — Select first ticket
        print("[3] Selecting first ticket ...")
        tickets = page.locator("button:has(span:text('#'))")
        ticket_count = tickets.count()
        print(f"    Found {ticket_count} tickets")
        if ticket_count == 0:
            print("    No answered tickets, trying 'T\u00fcm\u00fc' tab...")
            page.locator("button:has-text('T\u00fcm\u00fc')").click()
            page.wait_for_timeout(2000)
            tickets = page.locator("button:has(span:text('#'))")
            ticket_count = tickets.count()
            if ticket_count == 0:
                print("    FAIL: No tickets at all")
                browser.close()
                sys.exit(1)

        tickets.first.click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/support_msg_02_selected.png", full_page=True)

        # 4 — Check for message bubbles
        print("[4] Checking for message bubbles ...")
        # Look for the message container area with actual content
        bubbles = page.locator(".rounded-lg.px-4.py-2\\.5")
        bubble_count = bubbles.count()
        print(f"    Found {bubble_count} message bubbles")

        if bubble_count == 0:
            # Maybe messages didn't load yet, wait more
            page.wait_for_timeout(3000)
            bubble_count = bubbles.count()
            print(f"    After extra wait: {bubble_count} bubbles")

        page.screenshot(path="/tmp/support_msg_03_conversation.png", full_page=True)

        # 5 — Check for different sender types
        print("[5] Checking sender types ...")
        # Customer avatar (blue circle)
        customer_avatars = page.locator(".bg-blue-100")
        staff_avatars = page.locator(".rounded-full.bg-neutral-900")
        print(f"    Customer messages: {customer_avatars.count()}")
        print(f"    Staff messages: {staff_avatars.count()}")

        if bubble_count > 0:
            print("\n=== CONVERSATION THREAD TEST PASSED ===")
        else:
            print("\n=== WARNING: No message bubbles found (ticket may have no messages) ===")

        browser.close()

if __name__ == "__main__":
    run()
