"""Support ticket API — ticket list, workflow-based reply generation, send."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.engine.executor import WorkflowExecutor
from app.models.execution import ExecutionStatus, TriggerType
from app.models.workflow import Workflow
from app.schemas.execution import ExecutionOut
from app.schemas.support import SupportSendRequest
from app.services.ticimax_service import TicimaxService
from app.utils.zeep_helpers import serialize

router = APIRouter()


# ---------------------------------------------------------------------------
# SOAP helpers (moved from support_agent_service.py)
# ---------------------------------------------------------------------------
def _unwrap_tickets(raw: Any) -> list[dict[str, Any]]:
    """Extract ticket list from nested SOAP response."""
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, dict):
        inner = raw.get("DestekTalepleri")
        if isinstance(inner, dict):
            items = inner.get("ServisMusteriTalep", [])
            return items if isinstance(items, list) else ([items] if items else [])
    return []


def _unwrap_messages(raw: Any) -> list[dict[str, Any]]:
    """Extract message list from nested SOAP response."""
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, dict):
        inner = raw.get("DestekMesajlari")
        if isinstance(inner, dict):
            items = inner.get("ServisMusteriCevap", [])
            return items if isinstance(items, list) else ([items] if items else [])
    return []


async def _fetch_tickets(
    db: Session, site_id: int, durum_id: int = -1, kayit_sayisi: int = 50
) -> list[dict[str, Any]]:
    client = TicimaxService.get_by_id(db, site_id)

    def _run() -> Any:
        filtre = client.custom_factory.WebMusteriTalepFiltre(
            ID=-1,
            UyeID=-1,
            DurumID=durum_id,
            KonuID=-1,
            Cozuldu=-1,
            DetayId=-1,
            SitedeGoster=-1,
            Tip=-1,
        )
        sayfalama = client.custom_factory.WebServisSayfalama(
            SayfaNo=1,
            KayitSayisi=kayit_sayisi,
            SiralamaDegeri="ID",
            SiralamaYonu="Desc",
        )
        req = client.custom_factory.ServisGetAllSupportTicketsRequest(
            Filtre=filtre, Sayfalama=sayfalama
        )
        result = client.custom.GetAllSupportTickets(UyeKodu=client.uye_kodu, request=req)
        return serialize(result)

    raw = await asyncio.to_thread(_run)
    return _unwrap_tickets(raw)


async def _fetch_ticket_messages(
    db: Session, site_id: int, ticket_id: int, uye_id: int = -1
) -> list[dict[str, Any]]:
    client = TicimaxService.get_by_id(db, site_id)

    def _run() -> Any:
        req = client.custom_factory.ServisGetSupportTicketMessagesRequest(
            DestekId=ticket_id, UyeID=uye_id
        )
        result = client.custom.GetSupportTicketMessages(UyeKodu=client.uye_kodu, request=req)
        return serialize(result)

    raw = await asyncio.to_thread(_run)
    return _unwrap_messages(raw)


async def _send_ticket_reply(
    db: Session, site_id: int, ticket_id: int, message: str, staff_uye_id: int = 407067
) -> dict[str, Any]:
    client = TicimaxService.get_by_id(db, site_id)

    def _run() -> Any:
        req = client.custom_factory.ServisSaveSupportTicketAnswerRequest(
            DestekId=ticket_id,
            Mesaj=message,
            UyeId=staff_uye_id,
        )
        result = client.custom.SaveSupportTicketAnswer(UyeKodu=client.uye_kodu, request=req)
        return serialize(result)

    raw = await asyncio.to_thread(_run)
    return {"status": "ok", "result": raw}


# ---------------------------------------------------------------------------
# Background workflow runner (same pattern as workflows.py)
# ---------------------------------------------------------------------------
async def _run_in_background(execution_id: int) -> None:
    db = SessionLocal()
    try:
        await WorkflowExecutor(db).run_existing(execution_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/tickets")
async def list_tickets(
    site_id: int = 2,
    durum_id: int = -1,
    kayit_sayisi: int = 50,
    db: Session = Depends(get_db),
):
    """List support tickets from Ticimax."""
    try:
        tickets = await _fetch_tickets(
            db, site_id=site_id, durum_id=durum_id, kayit_sayisi=kayit_sayisi
        )
        tickets.sort(key=lambda t: t.get("ID", 0), reverse=True)
        return {"tickets": tickets, "count": len(tickets)}
    except Exception as e:
        raise HTTPException(500, detail=f"Ticket listesi alınamadı: {e}")


@router.get("/tickets/{ticket_id}/messages")
async def get_ticket_messages(
    ticket_id: int,
    uye_id: int = -1,
    site_id: int = 2,
    db: Session = Depends(get_db),
):
    """Get conversation history for a ticket."""
    try:
        messages = await _fetch_ticket_messages(
            db, site_id=site_id, ticket_id=ticket_id, uye_id=uye_id
        )
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(500, detail=f"Ticket mesajları alınamadı: {e}")


@router.post("/tickets/{ticket_id}/generate", response_model=ExecutionOut)
async def generate_reply(
    ticket_id: int,
    uye_id: int = Query(..., description="Müşteri UyeID"),
    site_id: int = 2,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """Trigger the 'Destek Yanıtlama' workflow for a single ticket.

    Returns an Execution in PENDING state. Frontend polls
    GET /api/executions/{id} for results.
    """
    wf = db.query(Workflow).filter(Workflow.name == "Destek Yanıtlama").first()
    if not wf:
        raise HTTPException(
            404, detail="'Destek Yanıtlama' workflow bulunamadı. Seed script çalıştırın."
        )

    executor = WorkflowExecutor(db)
    execution = executor.create_execution(
        wf,
        trigger_type=TriggerType.MANUAL,
        trigger_input={
            "ticket_id": ticket_id,
            "uye_id": uye_id,
        },
        initial_status=ExecutionStatus.PENDING,
    )
    background_tasks.add_task(_run_in_background, execution.id)
    return execution


@router.post("/send")
async def send_reply(req: SupportSendRequest, db: Session = Depends(get_db)):
    """Send an approved reply to a ticket via Ticimax SOAP."""
    try:
        result = await _send_ticket_reply(
            db=db,
            site_id=req.site_id,
            ticket_id=req.ticket_id,
            message=req.message,
            staff_uye_id=req.staff_uye_id,
        )
        return result
    except Exception as e:
        raise HTTPException(500, detail=f"Yanıt gönderilemedi: {e}")
