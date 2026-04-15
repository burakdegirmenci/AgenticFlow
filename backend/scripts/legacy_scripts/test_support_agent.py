"""End-to-end test for the Support Agent API.

1. GET /api/support/tickets — verify ticket list loads
2. POST /api/support/chat — stream agent response for a real ticket
3. Verify draft_reply event is received
"""
from __future__ import annotations

import io
import json
import sys

# Fix Windows cp1254 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

API = "http://127.0.0.1:8000/api"


def test_ticket_list():
    """Test: GET /api/support/tickets returns ticket data."""
    print("1) GET /api/support/tickets?durum_id=-1&kayit_sayisi=5")
    r = httpx.get(f"{API}/support/tickets", params={"durum_id": -1, "kayit_sayisi": 5}, timeout=30)
    r.raise_for_status()
    data = r.json()
    count = data.get("count", 0)
    tickets = data.get("tickets", [])
    print(f"   Tickets: {count}")
    if not tickets:
        print("   WARN: No tickets returned")
        return None

    for t in tickets[:3]:
        print(f"   #{t.get('ID')} | {t.get('Konu') or 'N/A'} | {t.get('UyeAdi')} | Durum={t.get('DurumID')}")

    return tickets[0]


def test_agent_chat(ticket):
    """Test: POST /api/support/chat streams agent events."""
    ticket_id = ticket["ID"]
    uye_id = ticket.get("UyeID", -1)
    print(f"\n2) POST /api/support/chat (ticket={ticket_id}, uye={uye_id})")

    events = []
    draft_message = None

    with httpx.stream(
        "POST",
        f"{API}/support/chat",
        json={"ticket_id": ticket_id, "uye_id": uye_id, "site_id": 1},
        timeout=120,
    ) as r:
        r.raise_for_status()
        buffer = ""
        for chunk in r.iter_text():
            buffer += chunk
            while "\n\n" in buffer:
                idx = buffer.index("\n\n")
                raw = buffer[:idx]
                buffer = buffer[idx + 2 :]
                for line in raw.split("\n"):
                    if line.startswith("data:"):
                        payload = line[5:].strip()
                        try:
                            ev = json.loads(payload)
                            events.append(ev)
                            etype = ev.get("type")

                            if etype == "ticket_loaded":
                                print("   ticket_loaded OK")
                            elif etype == "text_delta":
                                pass  # lots of these
                            elif etype == "tool_call":
                                print(f"   tool_call: {ev.get('name')} -> {json.dumps(ev.get('input', {}), ensure_ascii=False)[:80]}")
                            elif etype == "tool_result":
                                print(f"   tool_result: {ev.get('name')} OK")
                            elif etype == "draft_reply":
                                draft_message = ev.get("message", "")
                                reasoning = ev.get("reasoning", "")
                                print(f"   draft_reply: {len(draft_message)} chars")
                                if reasoning:
                                    print(f"   reasoning: {reasoning[:100]}")
                            elif etype == "error":
                                print(f"   ERROR: {ev.get('message')}")
                            elif etype == "done":
                                print("   done")
                        except json.JSONDecodeError:
                            pass

    print(f"\n   Total events: {len(events)}")

    # Count event types
    types = {}
    for ev in events:
        t = ev.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
    print(f"   Event types: {types}")

    # Print text deltas combined
    text = "".join(ev.get("text", "") for ev in events if ev.get("type") == "text_delta")
    if text:
        print(f"\n   Agent text ({len(text)} chars):")
        for line in text[:500].split("\n"):
            print(f"     {line}")
        if len(text) > 500:
            print("     ...")

    if draft_message:
        print(f"\n   === DRAFT REPLY ===")
        print(f"   {draft_message}")
        print(f"   === END DRAFT ===")
        return True
    else:
        print("\n   WARN: No draft_reply received")
        return False


def main() -> int:
    print("=" * 70)
    print("  Support Agent — End-to-End Test")
    print("=" * 70)

    ticket = test_ticket_list()
    if not ticket:
        print("\nNo tickets to test with. Exiting.")
        return 1

    ok = test_agent_chat(ticket)
    print()
    if ok:
        print("PASS: Agent produced a draft reply")
        return 0
    else:
        print("FAIL: Agent did not produce a draft reply")
        return 1


if __name__ == "__main__":
    sys.exit(main())
