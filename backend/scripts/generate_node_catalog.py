"""Generate BaseNode subclasses from ProductDetail/server.py @mcp.tool functions.

Usage:
    python scripts/generate_node_catalog.py

Reads:
    C:/Users/burakdegirmenci/Desktop/ProductDetail/server.py

Writes:
    backend/app/nodes/ticimax/_auto_generated.py

Strategy:
    - AST-parse server.py
    - For each function decorated with @mcp.tool(), emit a BaseNode subclass
    - Copy the function body verbatim (dedented) into async execute()
    - Replace `client = _get_client(alan_adi, uye_kodu)` with a local shim that
      uses TicimaxService to obtain a cached client for the workflow's site
    - Extract typed params into a JSON Schema config_schema (skips the first
      two args alan_adi/uye_kodu because those come from the site)
    - Wrap the function's return value in {"result": ...}
"""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

SERVER_PY = Path(
    r"C:/Users/burakdegirmenci/Desktop/ProductDetail/server.py"
)
OUT_FILE = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "nodes"
    / "ticimax"
    / "_auto_generated.py"
)

# Categorize by verb prefix for nicer UX in the palette
CATEGORY_ICONS: dict[str, tuple[str, str]] = {
    "select": ("search", "#0ea5e9"),   # blue
    "get": ("download", "#0ea5e9"),
    "save": ("save", "#10b981"),       # green
    "update": ("edit-3", "#f59e0b"),   # amber
    "set": ("edit-3", "#f59e0b"),
    "delete": ("trash-2", "#ef4444"),  # red
    "guncelle": ("edit-3", "#f59e0b"),
    "stok": ("box", "#10b981"),
    "test": ("zap", "#6b7280"),
}


def snake_to_pascal(name: str) -> str:
    return "".join(p.title() for p in name.split("_") if p)


def ann_to_schema(ann: ast.expr | None) -> dict:
    """Map a Python annotation to a JSON Schema fragment."""
    if ann is None:
        return {"type": "string"}
    src = ast.unparse(ann)
    if src == "int":
        return {"type": "integer"}
    if src == "float":
        return {"type": "number"}
    if src == "bool":
        return {"type": "boolean"}
    if src == "str":
        return {"type": "string"}
    if src.startswith("list"):
        return {"type": "array", "items": {"type": "object"}}
    if src.startswith("dict"):
        return {"type": "object"}
    return {"type": "string"}


def extract_tools(tree: ast.Module) -> list[ast.FunctionDef]:
    tools: list[ast.FunctionDef] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            # @mcp.tool() — Call(func=Attribute(attr='tool'))
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "tool"
            ):
                tools.append(node)
                break
            if isinstance(deco, ast.Attribute) and deco.attr == "tool":
                tools.append(node)
                break
    return tools


def get_body_source(func: ast.FunctionDef, source_lines: list[str]) -> str:
    """Extract the function body source (skip docstring), dedented."""
    body = list(func.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body:
        return "pass"
    start = body[0].lineno
    end = body[-1].end_lineno or body[-1].lineno
    raw = "\n".join(source_lines[start - 1 : end])
    return textwrap.dedent(raw)


def build_config_schema(
    func: ast.FunctionDef,
) -> tuple[dict, list[tuple[str, object]]]:
    """Return (config_schema, [(param_name, default_value), ...]).

    Skips the first two params (alan_adi, uye_kodu) because those are supplied
    from the workflow's site.
    """
    args = func.args.args
    defaults = func.args.defaults

    # Defaults align to the tail of args
    default_offset = len(args) - len(defaults)
    default_map: dict[str, object] = {}
    for i, arg in enumerate(args):
        d_idx = i - default_offset
        if d_idx >= 0:
            try:
                default_map[arg.arg] = ast.literal_eval(defaults[d_idx])
            except Exception:
                default_map[arg.arg] = None

    props: dict[str, dict] = {}
    required: list[str] = []
    param_list: list[tuple[str, object]] = []
    for arg in args[2:]:
        pname = arg.arg
        prop = ann_to_schema(arg.annotation)
        prop["title"] = pname
        if pname in default_map:
            default_val = default_map[pname]
            if default_val is not None:
                prop["default"] = default_val
        else:
            required.append(pname)
        props[pname] = prop
        param_list.append((pname, default_map.get(pname, None)))

    schema: dict = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema, param_list


def pick_icon_color(name: str) -> tuple[str, str]:
    # name is without "ticimax_" prefix
    for prefix, (icon, color) in CATEGORY_ICONS.items():
        if name.startswith(prefix + "_") or name == prefix:
            return icon, color
    return ("box", "#0ea5e9")


def extract_description(docstring: str | None) -> str:
    if not docstring:
        return ""
    first = docstring.strip().split("\n", 1)[0].strip()
    if len(first) > 180:
        first = first[:177] + "…"
    return first


def sanitize_body(body: str) -> str:
    """Rewrite the verbatim body so it compiles inside our execute() closure."""
    # The body assumes a `client` obtained via `_get_client`. Our nested
    # `_get_client` closure proxies to TicimaxService, so we can keep the call
    # as-is. No rewrite needed here.
    return body


def generate() -> str:
    source = SERVER_PY.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source)
    tools = extract_tools(tree)

    out: list[str] = []
    out.append('"""AUTO-GENERATED — do not edit by hand.')
    out.append("")
    out.append("Generated by backend/scripts/generate_node_catalog.py from")
    out.append("ProductDetail/server.py. Re-run the script when server.py changes.")
    out.append('"""')
    out.append("from __future__ import annotations")
    out.append("")
    out.append("import asyncio")
    out.append("from typing import Any")
    out.append("")
    out.append("from app.engine.node_base import BaseNode")
    out.append("from app.engine.context import ExecutionContext")
    out.append("from app.nodes import register")
    out.append("from app.services.crypto_service import CryptoService")
    out.append("from app.services.ticimax_service import TicimaxService")
    out.append("from app.utils.zeep_helpers import serialize as _serialize")
    out.append("")
    out.append("")

    seen_type_ids: set[str] = set()
    generated = 0

    for func in tools:
        name = func.name
        if not name.startswith("ticimax_"):
            continue
        short = name.removeprefix("ticimax_")
        type_id = f"ticimax.{short}"
        if type_id in seen_type_ids:
            continue
        seen_type_ids.add(type_id)

        class_name = snake_to_pascal(short) + "Node"
        display_name = short.replace("_", " ").title()
        icon, color = pick_icon_color(short)
        description = extract_description(ast.get_docstring(func))

        config_schema, params = build_config_schema(func)

        body_src = get_body_source(func, source_lines)
        body_src = sanitize_body(body_src)
        # Body goes inside `def _run():` which is at col 8, so body is at col 12.
        body_indented = textwrap.indent(body_src, " " * 12)

        out.append("@register")
        out.append(f"class {class_name}(BaseNode):")
        out.append(f"    type_id = {type_id!r}")
        out.append('    category = "ticimax"')
        out.append(f"    display_name = {display_name!r}")
        out.append(f"    description = {description!r}")
        out.append(f"    icon = {icon!r}")
        out.append(f"    color = {color!r}")
        out.append(f"    config_schema = {config_schema!r}")
        out.append("")
        out.append(
            "    async def execute(self, context: ExecutionContext, "
            "inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:"
        )
        # Site credentials
        out.append("        site = context.site")
        out.append("        if site is None:")
        out.append(
            '            raise RuntimeError("Ticimax node requires a site on the workflow")'
        )
        out.append("        alan_adi = site.domain")
        out.append(
            "        uye_kodu = CryptoService.decrypt(site.uye_kodu_encrypted)"
        )
        out.append("")
        out.append("        def _get_client(a: str, u: str):")
        out.append("            return TicimaxService.get_client(site)")
        out.append("")
        # Extract config params with defaults
        for pname, default_val in params:
            out.append(
                f"        {pname} = config.get({pname!r}, {default_val!r})"
            )
        out.append("")
        out.append("        def _run():")
        out.append(body_indented.rstrip() or "            pass")
        out.append("")
        out.append('        # Run the synchronous SOAP call in a worker thread so we')
        out.append('        # do not block the FastAPI event loop (zeep is sync).')
        out.append('        return {"result": await asyncio.to_thread(_run)}')
        out.append("")
        out.append("")
        generated += 1

    out.append(f"# Total generated nodes: {generated}")
    return "\n".join(out)


def main() -> None:
    code = generate()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(code, encoding="utf-8")
    lines = code.count("\n")
    print(f"Wrote {OUT_FILE} ({lines} lines)")

    # Verify it parses
    try:
        ast.parse(code)
        print("[OK] Generated file parses cleanly.")
    except SyntaxError as e:
        print(f"[FAIL] Generated file has syntax error: {e}")
        raise


if __name__ == "__main__":
    main()
