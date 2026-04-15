"""UI-driven schedule test.

Opens workflow #6 in the React editor, changes the schedule trigger's cron
to ``* * * * *`` via the config panel, clicks Save, then clicks the new
activate button in the header to register the APScheduler job. Watches the
executions API for 3 minutes and prints every new run that fires. Finally
deactivates the workflow so the job is removed again.

Assumes backend (8000) and frontend (5173) are already running.
"""
from __future__ import annotations

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
WATCH_SECONDS = 180  # 3 minutes → expect ~3 scheduled runs


def print_jobs(tag: str) -> None:
    """Dump APScheduler's current job list via the debug endpoint."""
    with httpx.Client(base_url=BACKEND, timeout=10.0) as http:
        r = http.get("/api/workflows/scheduler/jobs")
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        print(f"   [{tag}] scheduler has {len(jobs)} job(s):")
        for j in jobs:
            print(
                f"      - {j['id']:30} next={j.get('next_run_time')} "
                f"trigger={j.get('trigger')}"
            )


def main() -> None:
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

        # ---- 2a. Fit all nodes into the viewport first ----------------------
        # React Flow's built-in Controls component renders a "fit view" button
        # at the bottom-left of the canvas. Without this the leftmost node
        # (our trigger) lives offscreen entirely.
        print("2a. Clicking React Flow fit-view control")
        fitview_btn = page.locator(".react-flow__controls-fitview")
        fitview_btn.click()
        time.sleep(0.6)

        # ---- 2b. Select the trigger node programmatically -------------------
        # The trigger node's DOM position overlaps geometrically with the
        # left-hand palette sidebar (React Flow nodes are rendered via
        # `transform: translate(...)` on a viewport that overflows its
        # container). Any real mouse click sent to the node's center
        # coordinate lands on the palette instead. Previous attempts
        # (fitView, force=True, pane dragging) all failed for the same
        # reason: whatever coordinate we pick, the palette is still on top.
        #
        # Instead of fighting the hit testing we dispatch the full pointer
        # event sequence directly onto the node DOM element via JS. React
        # Flow uses pointerdown/pointerup for selection, so firing those
        # synthesised events on the node wrapper triggers the selection
        # path without going through Playwright's geometric actionability
        # checks.
        print("2b. Selecting schedule trigger node via DOM dispatch")

        def select_node_via_dom(data_id: str) -> None:
            page.evaluate(
                """
                (dataId) => {
                  const node = document.querySelector(
                    `.react-flow__node[data-id="${dataId}"]`
                  );
                  if (!node) {
                    throw new Error('node not found: ' + dataId);
                  }
                  const rect = node.getBoundingClientRect();
                  const cx = rect.left + rect.width / 2;
                  const cy = rect.top + rect.height / 2;
                  const makeEvt = (type) => new PointerEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    view: window,
                    clientX: cx,
                    clientY: cy,
                    screenX: cx,
                    screenY: cy,
                    button: 0,
                    buttons: type === 'pointerdown' ? 1 : 0,
                    pointerType: 'mouse',
                    pointerId: 1,
                    isPrimary: true,
                  });
                  node.dispatchEvent(makeEvt('pointerdown'));
                  node.dispatchEvent(makeEvt('pointerup'));
                  // React Flow's internal useNodeOrEdgeTypes hooks fire
                  // on click too; send a plain click as well to be safe.
                  node.dispatchEvent(new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    view: window,
                    clientX: cx,
                    clientY: cy,
                    button: 0,
                  }));
                }
                """,
                data_id,
            )

        select_node_via_dom("trigger")
        time.sleep(0.8)
        page.screenshot(
            path=str(OUT_DIR / "sched_00_after_click.png"), full_page=True
        )
        # Wait for the config panel to swap from its "Bir node seç" placeholder
        # to the schedule form. The heading reads the node's display_name
        # ("Zamanlanmış") and the body renders a <label> around each config
        # property — we wait on the cron label specifically.
        page.wait_for_selector(
            'aside label:has-text("Cron İfadesi")',
            timeout=10000,
        )
        time.sleep(0.3)

        page.screenshot(
            path=str(OUT_DIR / "sched_01_node_selected.png"), full_page=True
        )

        # ---- 3. Replace the cron expression in the config panel --------------
        # The config panel wraps each field in `<label><span>Title</span>
        # <input .../></label>`. Implicit-association labels aren't matched
        # by `get_by_label`, so target the input via `:has-text` on the label.
        print("3. Updating cron to '* * * * *'")
        cron_input = page.locator(
            'label:has-text("Cron İfadesi") input[type="text"]'
        )
        cron_input.fill("* * * * *")
        time.sleep(0.3)

        # ---- 4. Save ---------------------------------------------------------
        print("4. Clicking Kaydet")
        save_btn = page.get_by_role("button", name="Kaydet", exact=True)
        save_btn.click()
        # Wait for the button to re-enable (mutation success clears `dirty`)
        page.wait_for_function(
            "() => { const b = [...document.querySelectorAll('button')]"
            ".find(el => el.textContent.trim() === 'Kaydet'); return b && b.disabled; }",
            timeout=10000,
        )
        time.sleep(0.5)

        page.screenshot(
            path=str(OUT_DIR / "sched_02_saved.png"), full_page=True
        )

        # ---- 5. Activate -----------------------------------------------------
        print("5. Clicking activate button (Pasif → Aktif)")
        activate_btn = page.get_by_role("button", name="Pasif")
        activate_btn.click()
        # Wait until the button flips to "Aktif"
        page.wait_for_selector('button:has-text("Aktif")', timeout=10000)
        time.sleep(0.5)

        page.screenshot(
            path=str(OUT_DIR / "sched_03_activated.png"), full_page=True
        )

        print_jobs("after activate")

        # ---- 6. Watch executions for 3 minutes -------------------------------
        # We poll /api/executions?workflow_id=6 every 10s, printing every
        # new execution we see. Wait until the number of SCHEDULE runs
        # we've seen reaches ~3 or the window expires.
        print()
        print(f"6. Watching executions for {WATCH_SECONDS}s "
              f"(expect ~{WATCH_SECONDS // 60} runs)")
        print("   " + "=" * 68)

        seen: set[int] = set()
        baseline_max: int | None = None
        end = time.time() + WATCH_SECONDS

        while time.time() < end:
            try:
                with httpx.Client(base_url=BACKEND, timeout=15.0) as http:
                    r = http.get(
                        "/api/executions",
                        params={"workflow_id": WORKFLOW_ID, "limit": 20},
                    )
                    r.raise_for_status()
                    execs = r.json()
            except Exception as e:
                print(f"   (poll error: {e})")
                time.sleep(10)
                continue

            # Establish a baseline so we only report runs that happen AFTER
            # we activated the scheduler; older manual runs are ignored.
            if baseline_max is None:
                baseline_max = max((e["id"] for e in execs), default=0)
                print(f"   baseline: newest existing execution id={baseline_max}")

            new_runs = [e for e in execs if e["id"] > baseline_max and e["id"] not in seen]
            for exec_row in sorted(new_runs, key=lambda e: e["id"]):
                seen.add(exec_row["id"])
                started = exec_row.get("started_at", "")[:19].replace("T", " ")
                finished = (exec_row.get("finished_at") or "")[:19].replace("T", " ")
                status = exec_row.get("status", "?")
                trigger = exec_row.get("trigger_type", "?")
                print(
                    f"   → exec #{exec_row['id']:<4} {trigger:<10} "
                    f"{status:<8} started={started} finished={finished}"
                )

            time.sleep(10)

        print("   " + "=" * 68)
        print(f"   total new executions: {len(seen)}")

        # ---- 7. Deactivate so the cron job gets removed ---------------------
        print()
        print("7. Clicking deactivate (Aktif → Pasif)")
        deactivate_btn = page.get_by_role("button", name="Aktif")
        deactivate_btn.click()
        page.wait_for_selector('button:has-text("Pasif")', timeout=10000)
        time.sleep(0.5)

        page.screenshot(
            path=str(OUT_DIR / "sched_04_deactivated.png"), full_page=True
        )

        # Also reset the cron expression back to daily so the workflow is
        # left in a sensible idle state even if the user re-activates it
        # later without looking at the config panel.
        print("8. Resetting cron back to '0 13 * * *' (daily 13:00)")
        # Re-select the trigger node to reopen its config panel. Using the
        # same DOM-dispatch helper as step 2b because a real Playwright
        # click would still get intercepted by the palette sidebar.
        select_node_via_dom("trigger")
        page.wait_for_selector(
            'aside label:has-text("Cron İfadesi")',
            timeout=10000,
        )
        cron_input = page.locator(
            'label:has-text("Cron İfadesi") input[type="text"]'
        )
        cron_input.fill("0 13 * * *")
        save_btn = page.get_by_role("button", name="Kaydet", exact=True)
        save_btn.click()
        page.wait_for_function(
            "() => { const b = [...document.querySelectorAll('button')]"
            ".find(el => el.textContent.trim() === 'Kaydet'); return b && b.disabled; }",
            timeout=10000,
        )

        print_jobs("after deactivate")

        # ---- 8. Summary per execution ---------------------------------------
        if seen:
            print()
            print("=" * 72)
            print(f"SCHEDULED RUN SUMMARY — {len(seen)} execution(s)")
            print("=" * 72)
            with httpx.Client(base_url=BACKEND, timeout=30.0) as http:
                for eid in sorted(seen):
                    r = http.get(f"/api/executions/{eid}")
                    if r.status_code != 200:
                        continue
                    detail = r.json()
                    print(
                        f"\nexec #{eid} — {detail.get('status')} "
                        f"(trigger={detail.get('trigger_type')})"
                    )
                    for s in detail.get("steps") or []:
                        nid = s.get("node_id") or ""
                        ntype = s.get("node_type") or ""
                        status = s.get("status") or ""
                        dur = s.get("duration_ms") or 0
                        print(
                            f"   - {nid:<20} {ntype:<40} {status:<10} {dur}ms"
                        )
                        if s.get("error"):
                            print(f"       error: {s['error'][:200]}")

        if console_log:
            log_path = OUT_DIR / "sched_console.log"
            log_path.write_text(
                "\n".join(console_log), encoding="utf-8", errors="replace"
            )
            print(f"\nbrowser console log → {log_path} ({len(console_log)} entries)")

        browser.close()


if __name__ == "__main__":
    main()
