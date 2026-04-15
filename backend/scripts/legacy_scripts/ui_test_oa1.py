"""Playwright UI test for workflow #7 (OzelAlan1 Batch Güncelleme).

Opens the workflow editor, verifies the canvas renders all 4 nodes and
3 edges, clicks the Run button, waits for the execution to finish, and
prints a detailed OzelAlan1 summary from the update_oa1 step output.

Assumes backend (8000) and frontend (5173) are already running.
"""
from __future__ import annotations

import json
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
WORKFLOW_ID = 7


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        console_log: list[str] = []

        def _safe_log(prefix: str, text: str) -> None:
            try:
                console_log.append(f"{prefix} {text}")
            except Exception:
                pass

        page.on("console", lambda m: _safe_log(f"[console:{m.type}]", m.text))
        page.on("pageerror", lambda err: _safe_log("[pageerror]", str(err)))

        # ---- 1. Open editor -------------------------------------------------
        print(f"1. Opening {FRONTEND}/workflows/{WORKFLOW_ID}")
        page.goto(f"{FRONTEND}/workflows/{WORKFLOW_ID}")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)

        # ---- 2. Fit view and take an initial screenshot ---------------------
        print("2. Clicking React Flow fit-view control")
        page.locator(".react-flow__controls-fitview").click()
        time.sleep(0.6)
        page.screenshot(
            path=str(OUT_DIR / "oa1_01_canvas.png"), full_page=True
        )

        # ---- 3. Verify the 4 nodes + 3 edges are actually rendered ----------
        node_ids = ["trigger", "fetch", "update_oa1", "log_summary"]
        missing: list[str] = []
        for nid in node_ids:
            if page.locator(f'.react-flow__node[data-id="{nid}"]').count() == 0:
                missing.append(nid)
        if missing:
            print(f"   ERROR: missing nodes on canvas: {missing}")
            page.screenshot(
                path=str(OUT_DIR / "oa1_ERR_missing_nodes.png"), full_page=True
            )
            return 1
        print(f"   all {len(node_ids)} nodes rendered: {', '.join(node_ids)}")

        edge_count = page.locator(".react-flow__edge").count()
        print(f"   edges rendered: {edge_count}")
        if edge_count < 3:
            print(f"   ERROR: expected 3 edges, got {edge_count}")
            return 1

        # ---- 4. Click the Run button ----------------------------------------
        print("3. Clicking Run")
        run_button = page.get_by_role("button", name="Run", exact=True)
        if run_button.count() == 0:
            run_button = page.locator('button:has-text("Run")').first
        run_button.click()
        time.sleep(0.5)
        page.screenshot(
            path=str(OUT_DIR / "oa1_02_running.png"), full_page=True
        )

        # ---- 5. Wait for execution to finish --------------------------------
        print("4. Waiting for execution to finish…")
        deadline = time.time() + 180
        last_label = ""
        while time.time() < deadline:
            try:
                btn = page.locator(
                    'button:has-text("Run"), button:has-text("Çalıştırılıyor")'
                ).first
                label = btn.inner_text(timeout=2000).strip()
            except Exception:
                label = "?"
            if label != last_label:
                print(f"   button label: {label}")
                last_label = label
            if "Çalıştırılıyor" not in label:
                break
            time.sleep(1.0)
        time.sleep(2.0)
        page.screenshot(
            path=str(OUT_DIR / "oa1_03_finished.png"), full_page=True
        )

        # ---- 6. Fetch newest execution from backend -------------------------
        print(f"5. Fetching newest execution for workflow #{WORKFLOW_ID}")
        with httpx.Client(base_url=BACKEND, timeout=30.0) as http:
            r = http.get(
                "/api/executions",
                params={"workflow_id": WORKFLOW_ID, "limit": 1},
            )
            r.raise_for_status()
            execs = r.json()
            if not execs:
                print("   no executions found")
                return 1
            latest = execs[0]
            exec_id = latest["id"]
            print(f"   exec_id={exec_id} status={latest['status']}")
            r = http.get(f"/api/executions/{exec_id}")
            r.raise_for_status()
            detail = r.json()

        # ---- 7. Navigate to the execution detail page -----------------------
        print(f"6. Opening execution detail page for #{exec_id}")
        page.goto(f"{FRONTEND}/executions/{exec_id}")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)
        page.screenshot(
            path=str(OUT_DIR / "oa1_04_exec_detail.png"), full_page=True
        )

        # ---- 8. Print a compact summary -------------------------------------
        print()
        print("=" * 72)
        print(f"EXECUTION {exec_id} — {detail.get('status')}")
        print("=" * 72)
        print(f"  workflow_id : {detail.get('workflow_id')}")
        print(f"  trigger     : {detail.get('trigger_type')}")
        print(f"  started     : {detail.get('started_at')}")
        print(f"  finished    : {detail.get('finished_at')}")
        if detail.get("error"):
            print(f"  error       : {detail['error'][:500]}")
        steps = detail.get("steps") or []
        print(f"  steps       : {len(steps)}")
        for s in steps:
            print(
                f"    - {s.get('node_id'):<15} "
                f"{s.get('node_type'):<45} "
                f"{s.get('status'):<10} "
                f"{s.get('duration_ms', 0)}ms"
            )
            if s.get("error"):
                print(f"        error: {s['error'][:200]}")

        # ---- 9. Dump the update_oa1 summary ---------------------------------
        print()
        print("=" * 72)
        print("  update_oa1 — OzelAlan1 SUMMARY")
        print("=" * 72)
        for s in steps:
            if s.get("node_id") == "update_oa1":
                out = s.get("output_data") or {}
                print(f"  updated_count  : {out.get('updated_count')}")
                print(f"  error_count    : {out.get('error_count')}")
                print(f"  skipped_count  : {out.get('skipped_count')}")
                print(f"    skip_no_sku  : {out.get('skip_no_sku')}")
                print(f"    skip_noop    : {out.get('skip_noop')}")
                print(f"    skip_same    : {out.get('skip_same')}")
                print(f"  dry_run        : {out.get('dry_run')}")
                print(f"  aborted        : {out.get('aborted')}")
                results = out.get("results") or []
                print(f"  results count  : {len(results)}")

                from collections import Counter
                dist = Counter(r.get("status", "?") for r in results)
                print()
                print("  --- Status distribution ---")
                for k, v in sorted(dist.items(), key=lambda x: -x[1]):
                    print(f"    {k:15} : {v}")

                print()
                print("  --- Sample first 5 results ---")
                for r in results[:5]:
                    status = r.get("status", "")
                    name = (r.get("urun_adi", "") or "")[:28]
                    stok = r.get("stok_kodu", "")
                    eski = r.get("eski_oa1", "")
                    yeni = r.get("yeni_oa1", "")
                    print(
                        f"    [{status:10}] {name:<28} "
                        f"stok={stok:<22} eski={eski!r:<12} yeni={yeni!r}"
                    )

                summary_path = OUT_DIR / "oa1_execution.json"
                summary_path.write_text(
                    json.dumps(detail, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                print(f"\n  dump: {summary_path}")
                break

        if console_log:
            log_path = OUT_DIR / "oa1_console.log"
            log_path.write_text(
                "\n".join(console_log), encoding="utf-8", errors="replace"
            )
            print(
                f"\nbrowser console log → {log_path} "
                f"({len(console_log)} entries)"
            )

        browser.close()

        # Final OK/FAIL exit
        if detail.get("status") != "SUCCESS":
            print(f"\nFAIL: execution ended with status {detail.get('status')}")
            return 2
        print("\nOK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
