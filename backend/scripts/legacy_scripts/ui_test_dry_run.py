"""Playwright-driven UI test: open workflow #6, click Run, capture results.

Assumes backend (8000) and frontend (5173) are already running.
Saves:
  - screenshots into ./exports/ui_test_*.png
  - execution summary to ./exports/ui_test_execution.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows so Turkish characters don't crash print().
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import httpx
from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent / "exports"
OUT_DIR.mkdir(exist_ok=True)

FRONTEND = "http://127.0.0.1:5173"
BACKEND = "http://127.0.0.1:8000"
WORKFLOW_ID = 6


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        # Collect console/page errors into a buffer (printing during the
        # event callback can raise UnicodeEncodeError on Windows cp1254).
        console_log: list[str] = []

        def _safe_log(prefix: str, text: str) -> None:
            try:
                console_log.append(f"{prefix} {text}")
            except Exception:
                pass

        page.on("console", lambda m: _safe_log(f"[console:{m.type}]", m.text))
        page.on("pageerror", lambda err: _safe_log("[pageerror]", str(err)))

        print(f"1. Opening {FRONTEND}/workflows/{WORKFLOW_ID}")
        page.goto(f"{FRONTEND}/workflows/{WORKFLOW_ID}")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)  # let React Flow settle

        page.screenshot(
            path=str(OUT_DIR / "ui_test_01_loaded.png"), full_page=True
        )
        print("   loaded")

        # Look for the Run button (text "Run")
        run_button = page.get_by_role("button", name="Run", exact=True)
        run_count = run_button.count()
        print(f"2. Found {run_count} 'Run' button(s)")
        if run_count == 0:
            # Fallback: try any button containing Run
            run_button = page.locator('button:has-text("Run")').first
        run_button.click()
        print("   clicked Run")
        time.sleep(0.5)

        page.screenshot(
            path=str(OUT_DIR / "ui_test_02_running.png"), full_page=True
        )

        # Wait until the Run button is no longer "Çalıştırılıyor…"
        print("3. Waiting for execution to finish…")
        deadline = time.time() + 240
        last_label = ""
        while time.time() < deadline:
            try:
                btn = page.locator('button:has-text("Run"), button:has-text("Çalıştırılıyor")').first
                label = btn.inner_text(timeout=2000).strip()
            except Exception:
                label = "?"
            if label != last_label:
                print(f"   button label: {label}")
                last_label = label
            if "Çalıştırılıyor" not in label:
                # Double-check by querying backend for newest execution
                break
            time.sleep(1.0)
        time.sleep(2.0)  # Let the canvas paint the final status

        page.screenshot(
            path=str(OUT_DIR / "ui_test_03_finished.png"), full_page=True
        )
        print("   finished")

        # Pull the newest execution for this workflow from the backend API
        print("4. Fetching newest execution for workflow", WORKFLOW_ID)
        with httpx.Client(base_url=BACKEND, timeout=30.0) as http:
            r = http.get(
                "/api/executions", params={"workflow_id": WORKFLOW_ID, "limit": 1}
            )
            r.raise_for_status()
            execs = r.json()
            if not execs:
                print("   no executions found")
                return
            latest = execs[0]
            exec_id = latest["id"]
            print(f"   latest execution id={exec_id} status={latest['status']}")
            d = http.get(f"/api/executions/{exec_id}")
            d.raise_for_status()
            detail = d.json()

        # Navigate to the execution detail page and screenshot it
        print(f"5. Opening execution detail page for {exec_id}")
        page.goto(f"{FRONTEND}/executions/{exec_id}")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)
        page.screenshot(
            path=str(OUT_DIR / "ui_test_04_exec_detail.png"), full_page=True
        )

        # Dump the execution detail summary
        summary_path = OUT_DIR / "ui_test_execution.json"
        summary_path.write_text(
            json.dumps(detail, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"   dumped: {summary_path}")

        # Print a compact summary to stdout
        print()
        print("=" * 72)
        print(f"EXECUTION {exec_id} — {detail.get('status')}")
        print("=" * 72)
        print(f"workflow_id: {detail.get('workflow_id')}")
        print(f"trigger:     {detail.get('trigger_type')}")
        print(f"started:     {detail.get('started_at')}")
        print(f"finished:    {detail.get('finished_at')}")
        if detail.get("error"):
            print(f"error:       {detail['error'][:500]}")
        steps = detail.get("steps") or []
        print(f"steps:       {len(steps)}")
        for s in steps:
            print(
                f"  - {s.get('node_id'):<20} {s.get('node_type'):<40} "
                f"{s.get('status'):<10} {s.get('duration_ms', 0)}ms"
            )
            if s.get("error"):
                print(f"      error: {s['error'][:200]}")

        if console_log:
            log_path = OUT_DIR / "ui_test_console.log"
            log_path.write_text(
                "\n".join(console_log), encoding="utf-8", errors="replace"
            )
            print(f"\nbrowser console log → {log_path} ({len(console_log)} entries)")

        browser.close()


if __name__ == "__main__":
    main()
