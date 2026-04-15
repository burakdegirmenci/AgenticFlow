"""Smoke test for ticimax.urun.update_ozel_alan_1_batch node.

Exercises every branch of the node logic (skip_no_sku, skip_noop,
skip_same, dry_run/would-update, error for missing ID) with synthetic
input data — no real Ticimax calls needed. Validates that the port from
worker/parse.py + worker/worker.py to AgenticFlow is behaviourally
equivalent.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the app package importable when running from backend/
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Trigger node registration side effects
import app.nodes  # noqa: F401

from app.engine.context import ExecutionContext
from app.nodes import NODE_REGISTRY


def _mock_urun(
    *,
    id_: int,
    name: str,
    eski_oa1: str,
    first_stok: str | None,
) -> dict:
    """Build a serialized-product-shaped dict mimicking SelectUrun output."""
    urun: dict = {
        "ID": id_,
        "UrunAdi": name,
        "OzelAlan1": eski_oa1,
        "Varyasyonlar": None,
    }
    if first_stok is not None:
        urun["Varyasyonlar"] = {
            "Varyasyon": [{"StokKodu": first_stok}]
        }
    return urun


TEST_CASES = [
    # --- skip_has_oa1: existing OA1 set (matches derived) ---
    dict(
        id_=1,
        name="Bej Deri",
        eski_oa1="INTESI",
        first_stok="INTESI-BJ-12",
        expected="skip_has_oa1",
    ),
    # --- skip_has_oa1: existing OA1 set (even if it's wrong — preserve manual) ---
    dict(
        id_=2,
        name="ORAFOT test",
        eski_oa1="ORAFOT-1",
        first_stok="ORAFOT-1-BJ-12",
        expected="skip_has_oa1",
    ),
    # --- dry_run: would-update (existing OA1 differs from derived) ---
    dict(
        id_=3,
        name="Missing OA1",
        eski_oa1="",
        first_stok="RANFOR-GR-09",
        expected="dry_run",
    ),
    # --- skip_has_oa1: existing OA1 is wrong but we preserve it ---
    dict(
        id_=4,
        name="Wrong OA1 preserved",
        eski_oa1="WRONG_VALUE",
        first_stok="JEMINA-6-R-01",
        expected="skip_has_oa1",
    ),
    dict(
        id_=5,
        name="Two trailing variant segments",
        eski_oa1="",
        first_stok="JEMINA-8-YS-378",
        expected="dry_run",
    ),
    dict(
        id_=6,
        name="Alphanumeric variant",
        eski_oa1="",
        first_stok="CALANDRA-hz4",
        expected="dry_run",
    ),
    # --- skip_no_sku: Varyasyonlar missing (eski_oa1 empty → runs full logic) ---
    dict(
        id_=7,
        name="No variations at all",
        eski_oa1="",
        first_stok=None,
        expected="skip_no_sku",
    ),
    # --- skip_no_sku: Varyasyonlar present but empty stok ---
    dict(
        id_=8,
        name="Empty stok",
        eski_oa1="",
        first_stok="",
        expected="skip_no_sku",
    ),
    # --- skip_noop: single-segment stok (nothing to strip) ---
    dict(
        id_=9,
        name="Single segment",
        eski_oa1="",
        first_stok="MONOKOD",
        expected="skip_noop",
    ),
    # --- skip_noop: 1-char tokens preserved, no trailing variant ---
    dict(
        id_=10,
        name="All single-char segments",
        eski_oa1="",
        first_stok="A-B-C",
        expected="skip_noop",
    ),
]


def _make_ctx() -> ExecutionContext:
    # Minimal stub — we never touch site/db because dry_run=True
    return ExecutionContext(
        execution_id=0,
        workflow_id=0,
        site=None,  # type: ignore[arg-type]
        db=None,  # type: ignore[arg-type]
    )


async def main() -> int:
    node_cls = NODE_REGISTRY["ticimax.urun.update_ozel_alan_1_batch"]
    node = node_cls()

    # Build mock urunler from test cases
    urunler = [
        _mock_urun(
            id_=c["id_"],
            name=c["name"],
            eski_oa1=c["eski_oa1"],
            first_stok=c["first_stok"],
        )
        for c in TEST_CASES
    ]
    inputs = {"fetch": {"urunler": urunler, "count": len(urunler)}}
    config = {
        "urunler_path": "urunler",
        "max_strip": 2,
        "dry_run": True,  # NO real Ticimax calls
        "skip_if_has_oa1": True,  # New default: preserve existing OA1
        "item_delay_ms": 0,
        "abort_on_consecutive_errors": 100,
    }

    context = _make_ctx()
    out = await node.execute(context, inputs, config)

    print("=" * 72)
    print("  update_ozel_alan_1_batch — SMOKE TEST (skip_if_has_oa1=True)")
    print("=" * 72)
    print(f"  updated_count : {out['updated_count']}")
    print(f"  skipped_count : {out['skipped_count']}")
    print(f"    skip_has_oa1: {out['skip_has_oa1']}")
    print(f"    skip_no_sku : {out['skip_no_sku']}")
    print(f"    skip_noop   : {out['skip_noop']}")
    print(f"    skip_same   : {out['skip_same']}")
    print(f"  error_count   : {out['error_count']}")
    print(f"  dry_run       : {out['dry_run']}")
    print(f"  aborted       : {out['aborted']}")
    print()
    print("  " + "-" * 70)
    print(f"  {'ID':<4} {'stok':<22} {'eski':<18} {'yeni':<18} {'status':<12} {'OK?'}")
    print("  " + "-" * 70)

    failed = 0
    for case, result in zip(TEST_CASES, out["results"]):
        ok = result["status"] == case["expected"]
        mark = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(
            f"  {case['id_']:<4} "
            f"{str(case['first_stok']):<22} "
            f"{case['eski_oa1']!r:<18} "
            f"{result.get('yeni_oa1', '')!r:<18} "
            f"{result['status']:<12} "
            f"{mark}"
        )
        if not ok:
            print(
                f"       expected={case['expected']} "
                f"got={result['status']}"
            )

    print("  " + "-" * 70)
    if failed:
        print(f"\n  FAILED: {failed}/{len(TEST_CASES)}\n")
        return 1
    print(f"\n  PASSED: {len(TEST_CASES)}/{len(TEST_CASES)}\n")

    # ---- Second pass: skip_if_has_oa1=False -------------------------------
    # Verify legacy behaviour still works when the new toggle is disabled.
    # Cases 1 & 2 should now hit skip_same (eski == derived) instead of
    # skip_has_oa1.
    print("=" * 72)
    print("  update_ozel_alan_1_batch — LEGACY MODE (skip_if_has_oa1=False)")
    print("=" * 72)
    config2 = dict(config, skip_if_has_oa1=False)
    out2 = await node.execute(_make_ctx(), inputs, config2)
    print(f"  skip_has_oa1  : {out2['skip_has_oa1']} (expected 0)")
    print(f"  skip_same     : {out2['skip_same']} (expected 2)")
    print(f"  skip_no_sku   : {out2['skip_no_sku']} (expected 2)")
    print(f"  skip_noop     : {out2['skip_noop']} (expected 2)")
    print(f"  updated_count : {out2['updated_count']} (expected 4)")

    ok2 = (
        out2["skip_has_oa1"] == 0
        and out2["skip_same"] == 2
        and out2["skip_no_sku"] == 2
        and out2["skip_noop"] == 2
        and out2["updated_count"] == 4
    )
    if not ok2:
        print("\n  LEGACY MODE FAILED\n")
        return 1
    print("\n  LEGACY MODE OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
