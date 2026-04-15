"""Agent service - chat → workflow generator.

Given a user message, the agent picks from the node catalog and produces a
workflow graph. On providers that support structured tools (anthropic_api,
google_genai), we use a `propose_workflow` tool call. On text-only providers
(anthropic_cli), we instruct the model to emit a JSON code-fence and parse it.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.nodes import NODE_REGISTRY
from app.services.llm import LLMProviderError, get_provider
from app.services.llm.base import LLMMessage


# ---------------------------------------------------------------------------
# Catalog summary for the system prompt
# ---------------------------------------------------------------------------
def _node_catalog_summary() -> str:
    """Compact human-readable node list, grouped by category."""
    by_cat: dict[str, list[tuple[str, str]]] = {}
    for tid, cls in NODE_REGISTRY.items():
        by_cat.setdefault(cls.category, []).append((tid, cls.display_name))
    lines: list[str] = []
    order = ["trigger", "ticimax", "transform", "logic", "ai", "output"]
    for cat in order + [c for c in by_cat if c not in order]:
        entries = by_cat.get(cat)
        if not entries:
            continue
        lines.append(f"### {cat}")
        # For ticimax, the list is huge — show only the first 80 most-used ones.
        entries.sort()
        if cat == "ticimax" and len(entries) > 80:
            # Prioritize select/save/set/update heavy hitters
            def _score(pair: tuple[str, str]) -> int:
                name = pair[0].lower()
                for i, kw in enumerate(
                    [
                        "select_urun",
                        "select_siparis",
                        "save_urun",
                        "set_siparis",
                        "update_urun",
                        "select",
                        "save",
                        "set_",
                        "update_",
                        "get_",
                    ]
                ):
                    if kw in name:
                        return i
                return 99

            entries = sorted(entries, key=_score)[:80]
        for tid, name in entries:
            lines.append(f"  - {tid}  — {name}")
        lines.append("")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    catalog = _node_catalog_summary()
    return (
        "Sen AgenticFlow'un workflow tasarım asistanısın. Kullanıcı bir iş "
        "süreci tarif eder, sen aşağıdaki node kataloğundan seçerek bir React "
        "Flow graph'ı üretirsin.\n\n"
        "Kurallar:\n"
        "1. Her workflow bir trigger node ile başlar (trigger.manual, "
        "trigger.schedule, trigger.polling).\n"
        "2. Ticimax verileri çekmek için `ticimax.*` node'ları kullan. "
        "En çok kullanılanlar: `ticimax.select_urun`, `ticimax.select_siparis`.\n"
        "3. Veri dönüştürmek için `transform.*` (filter, map, parse_stok, "
        "aggregate).\n"
        "4. Dallanma için `logic.if`, `logic.switch`. `logic.if` output'u "
        "`_branches: ['true'|'false']` döner, edge'lerin `sourceHandle`'ı "
        "'true' veya 'false' olmalı.\n"
        "5. AI çağrıları için `ai.prompt`, `ai.classify`, `ai.extract`.\n"
        "6. Çıktı için `output.log`, `output.csv_export`.\n"
        "7. Her node'un benzersiz `id`'si olmalı (n1, n2, ...).\n"
        "8. Edge'lerin `source`/`target` node id'lerine işaret etmeli.\n"
        "9. Position alanları x/y koordinatı verir — sol-sağ akış için "
        "x'i 200 artır, y'yi 100 civarında tut.\n"
        "10. Her node `data.config` altında config_schema'ya uygun alanlar "
        "taşır. Bilmediğin alanı boş/default bırak.\n\n"
        "Önce kullanıcıya neyi nasıl yapacağını kısaca açıkla, sonra "
        "`propose_workflow` tool'unu çağırarak graph'ı öner. Tool "
        "desteklemeyen provider'da graph'ı ```json fenced code block içinde "
        "ver.\n\n"
        "## Node Kataloğu\n"
        f"{catalog}"
    )


# ---------------------------------------------------------------------------
# Tool schema (for providers that support tool_use)
# ---------------------------------------------------------------------------
PROPOSE_WORKFLOW_TOOL = {
    "name": "propose_workflow",
    "description": (
        "Kullanıcıya canvas'a uygulanması için bir workflow graph'ı önerir. "
        "Çağırdıktan sonra frontend canvas'a yerleştirir, kullanıcı elle "
        "düzenleyip kaydedebilir."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Workflow adı"},
            "description": {"type": "string", "description": "Kısa açıklama"},
            "nodes": {
                "type": "array",
                "description": "React Flow node'ları",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "position": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                            },
                        },
                        "data": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "config": {"type": "object"},
                            },
                        },
                    },
                    "required": ["id", "type"],
                },
            },
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "sourceHandle": {"type": ["string", "null"]},
                    },
                    "required": ["source", "target"],
                },
            },
        },
        "required": ["name", "nodes", "edges"],
    },
}


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------
def create_session(
    db: Session, title: str | None = None, workflow_id: int | None = None
) -> ChatSession:
    session = ChatSession(
        title=title or "Yeni Sohbet",
        workflow_id=workflow_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(
    db: Session, workflow_id: int | None = None, limit: int = 50
) -> list[ChatSession]:
    q = db.query(ChatSession)
    if workflow_id is not None:
        q = q.filter(ChatSession.workflow_id == workflow_id)
    return q.order_by(ChatSession.id.desc()).limit(limit).all()


def get_session(db: Session, session_id: int) -> ChatSession | None:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_messages(db: Session, session_id: int) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )


def append_message(
    db: Session,
    session_id: int,
    role: str,
    content: str,
    tool_use: dict[str, Any] | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        tool_use=tool_use,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Streaming agent loop
# ---------------------------------------------------------------------------
async def stream_chat(
    db: Session,
    session_id: int,
    user_message: str,
    workflow_id: int | None = None,
    provider_name: str | None = None,
    model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Main agent loop. Yields dicts suitable for SSE serialization.

    Event shapes (kept small):
      {"type": "session", "session_id": 5}
      {"type": "text_delta", "text": "..."}
      {"type": "tool_use", "name": "...", "input": {...}}
      {"type": "workflow_proposal", "proposal": {...}}
      {"type": "error", "message": "..."}
      {"type": "done"}
    """
    # Resolve provider
    try:
        provider = get_provider(provider_name)
    except LLMProviderError as e:
        yield {"type": "error", "message": str(e)}
        yield {"type": "done"}
        return

    # Persist user message
    try:
        append_message(db, session_id, "user", user_message)
    except Exception as e:
        yield {"type": "error", "message": f"DB error: {e}"}
        yield {"type": "done"}
        return

    yield {"type": "session", "session_id": session_id}

    # Build message history for the LLM from DB
    history = get_messages(db, session_id)
    llm_messages = [
        LLMMessage(role=m.role, content=m.content)
        for m in history
        if m.role in ("user", "assistant") and m.content
    ]

    system = _build_system_prompt()
    tools: list[dict[str, Any]] | None = (
        [PROPOSE_WORKFLOW_TOOL] if provider.supports_tools else None
    )
    if not provider.supports_tools:
        system += (
            "\n\nBu provider tool_use desteklemiyor. Workflow'u açıkladıktan "
            "sonra SADECE tek bir ```json fenced code block içinde "
            "`{name, description, nodes, edges}` JSON'ını ver."
        )

    accumulated_text = ""
    found_proposal: dict[str, Any] | None = None

    try:
        async for event in provider.stream(
            system=system,
            messages=llm_messages,
            tools=tools,
            model=model,
            temperature=0.3,
            max_tokens=8192,
        ):
            if event.type == "text_delta":
                delta = event.data.get("text", "")
                accumulated_text += delta
                yield {"type": "text_delta", "text": delta}
            elif event.type == "tool_use":
                name = event.data.get("name", "")
                tool_input = event.data.get("input", {}) or {}
                yield {
                    "type": "tool_use",
                    "name": name,
                    "input": tool_input,
                }
                if name == "propose_workflow" and isinstance(tool_input, dict):
                    found_proposal = _normalize_proposal(tool_input)
                    yield {
                        "type": "workflow_proposal",
                        "proposal": found_proposal,
                    }
            elif event.type == "error":
                yield {"type": "error", "message": event.data.get("message", "error")}
            elif event.type == "warning":
                yield {"type": "warning", "message": event.data.get("message", "")}
            elif event.type == "done":
                break
    except LLMProviderError as e:
        yield {"type": "error", "message": str(e)}
        yield {"type": "done"}
        return
    except Exception as e:  # pragma: no cover
        yield {"type": "error", "message": f"stream exception: {e}"}
        yield {"type": "done"}
        return

    # Text-only providers: try to parse a JSON fence
    if found_proposal is None and accumulated_text:
        parsed = _extract_fenced_json(accumulated_text)
        if parsed and isinstance(parsed, dict) and "nodes" in parsed:
            found_proposal = _normalize_proposal(parsed)
            yield {"type": "workflow_proposal", "proposal": found_proposal}

    # Persist assistant message
    try:
        append_message(
            db,
            session_id,
            "assistant",
            accumulated_text,
            tool_use=({"propose_workflow": found_proposal} if found_proposal else None),
        )
    except Exception as e:
        yield {"type": "error", "message": f"DB persist error: {e}"}

    yield {"type": "done"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_proposal(raw: dict[str, Any]) -> dict[str, Any]:
    """Ensure proposal has the minimum React Flow shape."""
    nodes_in = raw.get("nodes") or []
    edges_in = raw.get("edges") or []
    nodes: list[dict[str, Any]] = []
    for i, n in enumerate(nodes_in):
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or f"n{i + 1}")
        ntype = str(n.get("type") or "")
        pos = n.get("position") or {"x": 100 + i * 220, "y": 120}
        data = n.get("data") or {}
        if "config" not in data:
            data["config"] = {}
        nodes.append(
            {
                "id": nid,
                "type": ntype,
                "position": pos,
                "data": data,
            }
        )
    edges: list[dict[str, Any]] = []
    for i, e in enumerate(edges_in):
        if not isinstance(e, dict):
            continue
        edges.append(
            {
                "id": str(e.get("id") or f"e{i + 1}"),
                "source": str(e.get("source") or ""),
                "target": str(e.get("target") or ""),
                "sourceHandle": e.get("sourceHandle"),
                "targetHandle": e.get("targetHandle"),
            }
        )
    return {
        "name": str(raw.get("name") or "Yeni Workflow"),
        "description": str(raw.get("description") or ""),
        "nodes": nodes,
        "edges": edges,
    }


def _extract_fenced_json(text: str) -> Any:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
