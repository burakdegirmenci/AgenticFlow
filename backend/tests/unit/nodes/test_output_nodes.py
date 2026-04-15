"""output/log / csv_export / excel_export / json_export."""

from __future__ import annotations

import json
from pathlib import Path

from app.nodes.output.csv_export import CsvExportNode
from app.nodes.output.excel_export import ExcelExportNode
from app.nodes.output.json_export import JsonExportNode, _walk_dotted
from app.nodes.output.log_node import LogNode


# ---------------------------------------------------------------------------
# LogNode
# ---------------------------------------------------------------------------
async def test_log_serializes_inputs_to_json(execution_context) -> None:
    node = LogNode()
    out = await node.execute(
        execution_context,
        {"n1": {"items": [1, 2, 3]}},
        {"label": "sanity", "max_length": 5000},
    )
    assert out["label"] == "sanity"
    assert out["input_count"] == 1
    assert "items" in out["logged"]


async def test_log_truncates_over_max_length(execution_context) -> None:
    node = LogNode()
    huge = {"big": "x" * 10_000}
    out = await node.execute(execution_context, huge, {"label": "big", "max_length": 100})
    assert len(out["logged"]) <= 100 + len("...[truncated]")
    assert out["logged"].endswith("[truncated]")


async def test_log_handles_non_serializable(execution_context) -> None:
    node = LogNode()

    class Weird:
        def __repr__(self) -> str:
            return "<weird>"

    out = await node.execute(execution_context, {"w": Weird()}, {})
    # str() fallback is used; we just need it to not raise.
    assert "logged" in out


# ---------------------------------------------------------------------------
# JsonExportNode — pure helper
# ---------------------------------------------------------------------------
class TestWalkDotted:
    def test_dict_path(self) -> None:
        assert _walk_dotted({"a": {"b": {"c": 1}}}, "a.b.c") == 1

    def test_list_index(self) -> None:
        assert _walk_dotted({"items": [{"id": 10}, {"id": 20}]}, "items.1.id") == 20

    def test_missing_key_returns_none(self) -> None:
        assert _walk_dotted({"a": 1}, "nope") is None

    def test_invalid_list_index_returns_none(self) -> None:
        assert _walk_dotted({"xs": [1]}, "xs.5") is None
        assert _walk_dotted({"xs": [1]}, "xs.abc") is None

    def test_empty_segments_skipped(self) -> None:
        assert _walk_dotted({"a": {"b": 1}}, "a..b") == 1


# ---------------------------------------------------------------------------
# JsonExportNode — end-to-end write
# ---------------------------------------------------------------------------
async def test_json_export_writes_file(execution_context, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    node = JsonExportNode()

    out = await node.execute(
        execution_context,
        {"parent": {"urunler": [{"StokKodu": "A1"}, {"StokKodu": "B2"}]}},
        {"filename": "urunler", "source_field": "urunler", "indent": 2},
    )

    assert out["bytes_written"] > 0
    path = Path(out["file_path"])
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == [{"StokKodu": "A1"}, {"StokKodu": "B2"}]


async def test_json_export_full_inputs_when_source_field_empty(
    execution_context, tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    node = JsonExportNode()

    out = await node.execute(
        execution_context,
        {"parent": {"a": 1}},
        {"filename": "full", "source_field": ""},
    )

    data = json.loads(Path(out["file_path"]).read_text(encoding="utf-8"))
    assert data == {"parent": {"a": 1}}


async def test_json_export_missing_source_field_returns_note(
    execution_context, tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    node = JsonExportNode()

    out = await node.execute(
        execution_context,
        {"parent": {"a": 1}},
        {"filename": "nope", "source_field": "not.here"},
    )
    assert out["file_path"] == ""
    assert out["bytes_written"] == 0
    assert "note" in out


# ---------------------------------------------------------------------------
# CsvExportNode
# ---------------------------------------------------------------------------
async def test_csv_export_writes_headers_and_rows(execution_context, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    node = CsvExportNode()

    out = await node.execute(
        execution_context,
        {"parent": [{"sku": "A", "qty": 10}, {"sku": "B", "qty": 20}]},
        {"filename": "stok"},
    )

    assert out["rows_written"] == 2
    content = Path(out["file_path"]).read_text(encoding="utf-8-sig")
    assert "sku" in content and "qty" in content
    assert "A" in content and "B" in content


async def test_csv_export_no_list_returns_note(execution_context, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    node = CsvExportNode()
    out = await node.execute(execution_context, {"parent": []}, {"filename": "empty"})
    assert out["rows_written"] == 0
    assert out["file_path"] == ""
    assert "note" in out


# ---------------------------------------------------------------------------
# ExcelExportNode
# ---------------------------------------------------------------------------
async def test_excel_export_writes_xlsx(execution_context, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    node = ExcelExportNode()

    out = await node.execute(
        execution_context,
        {"parent": [{"id": 1, "name": "X"}, {"id": 2, "name": "Y"}]},
        {"filename": "items"},
    )

    assert out["rows_written"] == 2
    path = Path(out["file_path"])
    assert path.exists()
    assert path.suffix == ".xlsx"


async def test_excel_export_source_field_drills_in(
    execution_context, tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    node = ExcelExportNode()

    out = await node.execute(
        execution_context,
        {"parent": {"result": {"UrunList": [{"SKU": "A"}]}}},
        {"filename": "from_field", "source_field": "result.UrunList"},
    )

    assert out["rows_written"] == 1
    assert Path(out["file_path"]).exists()
