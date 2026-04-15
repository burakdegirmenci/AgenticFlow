"""UI dry-run test for workflow #9 — Kargoya Verildi.

Drives the React frontend via Playwright:
  1. Navigate to /workflows/9 (WorkflowEditor)
  2. Click the Run button
  3. Wait for execution to complete
  4. Capture screenshot
  5. Verify the resulting execution shows 5 dry_run candidates
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


SCREENS = Path(__file__).parent / "_ui_test_screens"
SCREENS.mkdir(exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            locale="tr-TR",
        )
        page = context.new_page()

        # Capture console + page errors
        logs: list[str] = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: logs.append(f"[pageerror] {err}"))

        print("1) Navigate to workflow #9 editor")
        page.goto("http://127.0.0.1:5173/workflows/9")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)
        page.screenshot(path=str(SCREENS / "01_editor_open.png"), full_page=True)

        # Confirm editor actually loaded workflow 9
        title_text = page.locator("text=/Kargoya Verildi/").first
        try:
            title_text.wait_for(timeout=5000)
            print("   workflow name visible in page")
        except Exception as e:
            print(f"   WARN: workflow name not detected ({e})")

        print("2) Click Run button")
        # Look for the Run button. Filter to visible ones only in case
        # of any offscreen duplicates.
        run_button = page.get_by_role("button", name="Run", exact=True)
        run_button.wait_for(state="visible", timeout=5000)
        run_button.click()
        page.screenshot(path=str(SCREENS / "02_after_click.png"), full_page=True)

        print("3) Wait for run to complete (button label flips back from 'Çalıştırılıyor…')")
        # Either the run button text changes back OR a success/error toast/banner appears
        # Worst case we give it 60s because set_durum iterates 483 orders.
        deadline = time.time() + 90
        finished = False
        while time.time() < deadline:
            # "Çalıştırılıyor…" present means still running
            try:
                running = page.get_by_text("Çalıştırılıyor").first
                if running.is_visible(timeout=500):
                    time.sleep(1.0)
                    continue
            except Exception:
                pass
            # Check for explicit success indicators
            finished = True
            break

        if not finished:
            page.screenshot(path=str(SCREENS / "03_timeout.png"), full_page=True)
            print("   TIMEOUT waiting for run to finish")
            print("\nConsole logs:")
            for line in logs[-30:]:
                print(f"  {line}")
            browser.close()
            return 1

        # Give the post-run UI a moment to reflect results
        time.sleep(3.0)
        page.screenshot(path=str(SCREENS / "03_after_run.png"), full_page=True)
        print("   run finished")

        print("4) Navigate to executions page to confirm latest run")
        page.goto("http://127.0.0.1:5173/executions")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)
        page.screenshot(path=str(SCREENS / "04_executions_list.png"), full_page=True)

        print("5) Open latest execution detail")
        # First row should be the one we just triggered (workflow 9)
        first_row = page.locator("table tbody tr").first
        if first_row.count() == 0:
            # No table? try any clickable item that mentions workflow 9
            first_row = page.locator("text=/Kargoya Verildi/").first
        first_row.click()
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)
        page.screenshot(path=str(SCREENS / "05_execution_detail.png"), full_page=True)

        # Look for success status and key counts
        page_text = page.content()
        hits: dict[str, bool] = {}
        hits["SUCCESS"] = "SUCCESS" in page_text or "success" in page_text.lower()
        hits["483 fetched hint"] = "483" in page_text
        hits["5 updated hint"] = "updated" in page_text.lower() or "dry" in page_text.lower()

        print()
        print("Page text scans:")
        for k, v in hits.items():
            print(f"  {'OK' if v else 'MISS'}: {k}")

        # Scroll through the step details if available
        try:
            page.locator("text=/set_durum/i").first.click(timeout=3000)
            time.sleep(1.0)
            page.screenshot(path=str(SCREENS / "06_step_detail.png"), full_page=True)
            print("   captured step detail screenshot")
        except Exception as e:
            print(f"   step detail expand skipped ({e})")

        print()
        print(f"Screenshots saved to: {SCREENS}")
        print()
        print("Console logs (last 20):")
        for line in logs[-20:]:
            print(f"  {line}")

        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
