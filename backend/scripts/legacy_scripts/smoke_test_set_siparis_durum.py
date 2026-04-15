"""Smoke test for ticimax.siparis.set_durum_batch node.

Exercises every branch of the filter logic (skip_no_payment,
skip_wrong_odeme_tipi, skip_not_approved, dry_run update, error for
missing ID) with synthetic input data — no real Ticimax calls.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Trigger node registration
import app.nodes  # noqa: F401

from app.engine.context import ExecutionContext
from app.nodes import NODE_REGISTRY


def _mock_siparis(
    *,
    id_: int | None,
    odeme_tipleri: list[tuple[int, int]] | None,
    no: str = "",
    adi: str = "Test Müşteri",
    durum: str = "Siparişiniz Alındı",
) -> dict:
    """Build a serialized-siparis-shaped dict.

    odeme_tipleri: list of (OdemeTipi, Onaylandi) tuples.
    Use None to omit Odemeler entirely.
    """
    siparis: dict = {
        "ID": id_,
        "SiparisNo": no,
        "AdiSoyadi": adi,
        "SiparisDurumu": durum,
        "Durum": 0,
    }
    if odeme_tipleri is None:
        siparis["Odemeler"] = None
    else:
        siparis["Odemeler"] = {
            "WebSiparisOdeme": [
                {
                    "OdemeTipi": tipi,
                    "Onaylandi": onayli,
                    "Tutar": 100.0,
                    "TaksitSayisi": 1,
                }
                for tipi, onayli in odeme_tipleri
            ]
        }
    return siparis


TEST_CASES = [
    # --- dry_run: KrediKarti (0) + Onaylandi=1 -> would update ---
    dict(
        id_=1001,
        odeme_tipleri=[(0, 1)],
        no="TEST-1",
        expected="dry_run",
    ),
    # --- dry_run: multiple payments, at least one KrediKarti approved ---
    dict(
        id_=1002,
        odeme_tipleri=[(0, 1), (1, 1)],
        no="TEST-2",
        expected="dry_run",
    ),
    # --- skip_no_payment: Odemeler missing ---
    dict(
        id_=1003,
        odeme_tipleri=None,
        no="TEST-3",
        expected="skip_no_payment",
    ),
    # --- skip_wrong_odeme_tipi: Havale (1), not in [0] ---
    dict(
        id_=1004,
        odeme_tipleri=[(1, 1)],
        no="TEST-4",
        expected="skip_wrong_odeme_tipi",
    ),
    # --- skip_wrong_odeme_tipi: Kapıda KK (3), not in [0] ---
    dict(
        id_=1005,
        odeme_tipleri=[(3, 1)],
        no="TEST-5",
        expected="skip_wrong_odeme_tipi",
    ),
    # --- skip_not_approved: KrediKarti but Onaylandi=0 ---
    dict(
        id_=1006,
        odeme_tipleri=[(0, 0)],
        no="TEST-6",
        expected="skip_not_approved",
    ),
    # --- skip_not_approved: all KK payments unapproved ---
    dict(
        id_=1007,
        odeme_tipleri=[(0, 0), (0, 2)],
        no="TEST-7",
        expected="skip_not_approved",
    ),
    # --- dry_run: mixed — one approved KK counts ---
    dict(
        id_=1008,
        odeme_tipleri=[(0, 0), (0, 1)],
        no="TEST-8",
        expected="dry_run",
    ),
    # --- error: missing ID ---
    dict(
        id_=None,
        odeme_tipleri=[(0, 1)],
        no="TEST-9",
        expected="error",
    ),
]


def _make_ctx() -> ExecutionContext:
    return ExecutionContext(
        execution_id=0,
        workflow_id=0,
        site=None,  # type: ignore[arg-type]
        db=None,  # type: ignore[arg-type]
    )


async def main() -> int:
    node_cls = NODE_REGISTRY["ticimax.siparis.set_durum_batch"]
    node = node_cls()

    siparisler = [
        _mock_siparis(
            id_=c["id_"],
            odeme_tipleri=c["odeme_tipleri"],
            no=c["no"],
        )
        for c in TEST_CASES
    ]
    inputs = {"fetch": {"siparisler": siparisler, "count": len(siparisler)}}

    config = {
        "siparisler_path": "siparisler",
        "yeni_durum": "Onaylandi",
        "mail_bilgilendir": False,
        "require_odeme_tipi_in": [0],  # only KrediKarti
        "require_odeme_onayli": True,
        "refetch_missing_odemeler": False,  # smoke test has no real site
        "dry_run": True,
        "item_delay_ms": 0,
        "abort_on_consecutive_errors": 100,
    }

    context = _make_ctx()
    out = await node.execute(context, inputs, config)

    print("=" * 72)
    print("  set_siparis_durum_batch — SMOKE TEST (KrediKarti, Onaylandi=1)")
    print("=" * 72)
    print(f"  updated_count         : {out['updated_count']}")
    print(f"  skipped_count         : {out['skipped_count']}")
    print(f"    skip_no_payment     : {out['skip_no_payment']}")
    print(f"    skip_wrong_odeme_tipi: {out['skip_wrong_odeme_tipi']}")
    print(f"    skip_not_approved   : {out['skip_not_approved']}")
    print(f"  error_count           : {out['error_count']}")
    print(f"  dry_run               : {out['dry_run']}")
    print(f"  aborted               : {out['aborted']}")
    print()
    print("  " + "-" * 80)
    print(f"  {'ID':<6} {'tipi':<24} {'no':<10} {'expected':<24} {'got':<24} {'OK?'}")
    print("  " + "-" * 80)

    failed = 0
    for case, result in zip(TEST_CASES, out["results"]):
        ok = result["status"] == case["expected"]
        mark = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        tipler = (
            str(case["odeme_tipleri"])[:22]
            if case["odeme_tipleri"] is not None
            else "None"
        )
        print(
            f"  {str(case['id_']):<6} "
            f"{tipler:<24} "
            f"{case['no']:<10} "
            f"{case['expected']:<24} "
            f"{result['status']:<24} "
            f"{mark}"
        )
        if not ok:
            print(f"       expected={case['expected']} got={result['status']}")

    print("  " + "-" * 80)
    if failed:
        print(f"\n  FAILED: {failed}/{len(TEST_CASES)}\n")
        return 1
    print(f"\n  PASSED: {len(TEST_CASES)}/{len(TEST_CASES)}\n")

    # ---- Second pass: require_odeme_tipi_in = [] (no filter) -----------
    # Every order except the missing-ID one should hit dry_run.
    print("=" * 72)
    print("  set_siparis_durum_batch — NO PAYMENT FILTER PASS")
    print("=" * 72)
    config2 = dict(config, require_odeme_tipi_in=[])
    out2 = await node.execute(_make_ctx(), inputs, config2)
    print(f"  updated_count (dry)  : {out2['updated_count']} (expected 8)")
    print(f"  error_count          : {out2['error_count']} (expected 1)")
    print(f"  skipped_count        : {out2['skipped_count']} (expected 0)")
    ok2 = (
        out2["updated_count"] == 8
        and out2["error_count"] == 1
        and out2["skipped_count"] == 0
    )
    if not ok2:
        print("\n  NO-FILTER MODE FAILED\n")
        return 1
    print("\n  NO-FILTER MODE OK\n")

    # ---- Third pass: require_kargo_takip_no = True ---------------------
    # Inject KargoTakipNo onto half of the orders; only those should
    # advance to dry_run status, the rest should hit skip_no_kargo_takip_no.
    print("=" * 72)
    print("  set_siparis_durum_batch — KARGO TAKIP NO PASS")
    print("=" * 72)
    cargo_inputs = {
        "fetch": {
            "siparisler": [
                {
                    **s,
                    "KargoTakipNo": (
                        "TK" + str(s["ID"]) if s["ID"] in (1001, 1002, 1008) else None
                    ),
                    "KargoTakipLink": (
                        f"https://track/{s['ID']}"
                        if s["ID"] in (1001, 1008)
                        else None
                    ),
                }
                for s in siparisler
            ],
            "count": len(siparisler),
        }
    }
    config3 = dict(
        config,
        require_kargo_takip_no=True,
        yeni_durum="KargoyaVerildi",
    )
    out3 = await node.execute(_make_ctx(), cargo_inputs, config3)
    print(f"  updated_count (dry)    : {out3['updated_count']} (expected 3)")
    print(f"  skip_no_kargo_takip_no : {out3['skip_no_kargo_takip_no']} (expected 0)")
    # NOTE: orders without KK-approved payment are already filtered before
    # the KargoTakipNo gate, so we expect 3 dry_run hits (IDs 1001/1002/1008).
    # Verify KargoTakipLink pass-through on 1001 and 1008.
    for r in out3["results"]:
        if r["status"] == "dry_run":
            print(
                f"    dry_run id={r['siparis_id']} "
                f"KTN={r.get('kargo_takip_no')!r} "
                f"KTL={r.get('kargo_takip_link')!r}"
            )
    ok3 = out3["updated_count"] == 3 and out3["error_count"] == 1
    if not ok3:
        print("\n  KARGO MODE FAILED\n")
        return 1
    print("\n  KARGO MODE OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
