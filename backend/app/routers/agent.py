"""Agent chat API — SSE streaming for workflow generator."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.agent import (
    ChatMessageOut,
    ChatRequest,
    ProviderInfo,
    SessionCreateRequest,
    SessionOut,
)
from app.services import agent_service
from app.services.llm import available_providers, get_provider


router = APIRouter()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@router.post("/sessions", response_model=SessionOut)
def create_session(req: SessionCreateRequest, db: Session = Depends(get_db)):
    return agent_service.create_session(
        db, title=req.title, workflow_id=req.workflow_id
    )


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    workflow_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return agent_service.list_sessions(db, workflow_id=workflow_id, limit=limit)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = agent_service.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageOut],
)
def get_messages(session_id: int, db: Session = Depends(get_db)):
    session = agent_service.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return agent_service.get_messages(db, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = agent_service.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    db.delete(session)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Providers info
# ---------------------------------------------------------------------------
@router.get("/providers", response_model=list[ProviderInfo])
async def providers_info():
    out: list[ProviderInfo] = []
    for name in available_providers():
        try:
            p = get_provider(name)
            ok, reason = await p.is_available()
            out.append(
                ProviderInfo(
                    name=p.name,
                    display_name=p.display_name,
                    supports_tools=p.supports_tools,
                    supports_streaming=p.supports_streaming,
                    available=ok,
                    reason=reason,
                )
            )
        except Exception as e:
            out.append(
                ProviderInfo(
                    name=name,
                    display_name=name,
                    supports_tools=False,
                    supports_streaming=False,
                    available=False,
                    reason=f"init error: {e}",
                )
            )
    return out


# ---------------------------------------------------------------------------
# SSE chat stream
# ---------------------------------------------------------------------------
@router.post("/chat")
async def chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """Stream agent response as Server-Sent Events.

    Event format (one per SSE chunk):
        data: {"type": "text_delta", "text": "..."}\n\n

    The client should parse each `data:` line as JSON. The stream ends with
    `{"type": "done"}`.
    """
    # Resolve or create session
    session_id = req.session_id
    if session_id is None:
        session = agent_service.create_session(
            db, title=req.message[:60], workflow_id=req.workflow_id
        )
        session_id = session.id
    else:
        session = agent_service.get_session(db, session_id)
        if not session:
            raise HTTPException(404, "Session not found")

    async def event_source() -> AsyncIterator[bytes]:
        # Emit session id first so the client can track new sessions
        first = {"type": "session", "session_id": session_id}
        yield f"data: {json.dumps(first, ensure_ascii=False)}\n\n".encode("utf-8")
        try:
            async for event in agent_service.stream_chat(
                db=db,
                session_id=session_id,
                user_message=req.message,
                workflow_id=req.workflow_id,
                provider_name=req.provider,
                model=req.model,
            ):
                # Skip duplicate session event
                if event.get("type") == "session":
                    continue
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n".encode("utf-8")
                # Give the event loop a chance to flush
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            return
        except Exception as e:
            err = {"type": "error", "message": f"stream failure: {e}"}
            yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
            yield b'data: {"type": "done"}\n\n'

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
