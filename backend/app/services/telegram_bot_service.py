"""Telegram Bot service — second UI for AgenticFlow.

Spec: docs/TELEGRAM_BOT_SPEC.md

Runs as part of FastAPI lifespan (like SchedulerService). When
TELEGRAM_BOT_TOKEN is set, starts a long-polling loop that receives
commands and dispatches them against the existing REST API.

When token is empty, the service is a silent no-op — no error, no
import of telegram libs.

Commands:
    /workflows              — list workflows
    /run <id>               — trigger a workflow
    /status <id>            — execution detail
    /history [n]            — recent executions
    /subscribe              — get error notifications
    /unsubscribe            — stop notifications
    /help                   — command reference
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import Application

logger = get_logger("agenticflow.telegram")

# Status emoji mapping
_STATUS_EMOJI = {
    "SUCCESS": "✅",
    "ERROR": "🚨",
    "RUNNING": "⏳",
    "PENDING": "⏳",
    "CANCELLED": "⚪",
    "SKIPPED": "⏭",
}


class TelegramBotService:
    """Singleton Telegram bot — starts/stops with the app."""

    def __init__(self) -> None:
        self._app: Application | None = None
        self._task: asyncio.Task[Any] | None = None
        self._started = False
        self._token = ""
        self._default_chat_id = ""
        self._allowed_chats: set[str] = set()

    # ------------------------------------------------------------------ lifecycle

    def start(self, token: str, default_chat_id: str = "", allowed: str = "") -> None:
        if not token:
            logger.debug("telegram_bot_disabled")
            return
        self._token = token
        self._default_chat_id = default_chat_id
        self._allowed_chats = {c.strip() for c in allowed.split(",") if c.strip()}

        try:
            from telegram.ext import (
                Application,
                CommandHandler,
            )
        except ImportError:
            logger.warning(
                "telegram_bot_import_failed",
                extra={"hint": "pip install python-telegram-bot"},
            )
            return

        self._app = Application.builder().token(token).build()

        # Register command handlers
        self._app.add_handler(CommandHandler("workflows", self._cmd_workflows))
        self._app.add_handler(CommandHandler("run", self._cmd_run))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("history", self._cmd_history))
        self._app.add_handler(CommandHandler("subscribe", self._cmd_subscribe))
        self._app.add_handler(CommandHandler("unsubscribe", self._cmd_unsubscribe))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("start", self._cmd_help))

        # Start polling in background
        self._task = asyncio.get_event_loop().create_task(self._run_polling())
        self._started = True
        logger.info("telegram_bot_started")

    async def _run_polling(self) -> None:
        if not self._app:
            return
        try:
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)  # type: ignore[union-attr]
            # Keep alive until cancelled
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("telegram_bot_polling_error")
        finally:
            try:
                if self._app.updater and self._app.updater.running:
                    await self._app.updater.stop()
                if self._app.running:
                    await self._app.stop()
                await self._app.shutdown()
            except Exception:
                pass

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._started = False
        logger.info("telegram_bot_stopped")

    def is_started(self) -> bool:
        return self._started

    # ------------------------------------------------------------------ auth

    def _is_allowed(self, chat_id: str) -> bool:
        if not self._allowed_chats:
            return True  # empty = allow all (single-tenant)
        return chat_id in self._allowed_chats

    # ------------------------------------------------------------------ commands

    async def _cmd_help(self, update: Update, context: Any) -> None:
        text = (
            "🤖 <b>AgenticFlow Bot</b>\n\n"
            "/workflows — Workflow listesi\n"
            "/run &lt;id&gt; — Workflow çalıştır\n"
            "/status &lt;id&gt; — Execution detayı\n"
            "/history — Son execution'lar\n"
            "/subscribe — Hata bildirimlerine abone ol\n"
            "/unsubscribe — Aboneliği iptal et\n"
            "/help — Bu mesaj"
        )
        await update.message.reply_text(text, parse_mode="HTML")  # type: ignore[union-attr]

    async def _cmd_workflows(self, update: Update, context: Any) -> None:
        chat_id = str(update.effective_chat.id)  # type: ignore[union-attr]
        if not self._is_allowed(chat_id):
            return

        from app.database import SessionLocal
        from app.models.workflow import Workflow

        db = SessionLocal()
        try:
            wfs = db.query(Workflow).order_by(Workflow.id).all()
            if not wfs:
                await update.message.reply_text("Henüz workflow yok.")  # type: ignore[union-attr]
                return

            lines = ["📋 <b>Workflow'lar:</b>\n"]
            for wf in wfs:
                status = "⏰" if wf.is_active else "⏸"
                lines.append(f"{status} <b>{wf.id}.</b> {wf.name}")
            lines.append("\n/run &lt;id&gt; ile çalıştır")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")  # type: ignore[union-attr]
        finally:
            db.close()

    async def _cmd_run(self, update: Update, context: Any) -> None:
        chat_id = str(update.effective_chat.id)  # type: ignore[union-attr]
        if not self._is_allowed(chat_id):
            return

        args = context.args or []
        if not args:
            await update.message.reply_text("Kullanım: /run <workflow_id>")  # type: ignore[union-attr]
            return

        try:
            wf_id = int(args[0])
        except ValueError:
            await update.message.reply_text("Geçersiz workflow ID.")  # type: ignore[union-attr]
            return

        from app.database import SessionLocal
        from app.engine.executor import WorkflowExecutor
        from app.models.execution import TriggerType
        from app.models.workflow import Workflow

        db = SessionLocal()
        try:
            wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
            if not wf:
                await update.message.reply_text(f"Workflow #{wf_id} bulunamadı.")  # type: ignore[union-attr]
                return

            await update.message.reply_text(  # type: ignore[union-attr]
                f"▶ <b>{wf.name}</b> başlatılıyor...",
                parse_mode="HTML",
            )

            executor = WorkflowExecutor(db)
            execution = await executor.run(wf, trigger_type=TriggerType.MANUAL)

            emoji = _STATUS_EMOJI.get(execution.status.value, "❓")
            duration = ""
            if execution.started_at and execution.finished_at:
                dur_s = (execution.finished_at - execution.started_at).total_seconds()
                duration = f" · {dur_s:.1f}s"

            text = f"{emoji} <b>#{execution.id}</b> {execution.status.value}{duration}\n"
            if execution.error:
                text += f"\nHata: <code>{execution.error[:200]}</code>"

            text += f"\n\n/status {execution.id} ile detay gör"
            await update.message.reply_text(text, parse_mode="HTML")  # type: ignore[union-attr]
        except Exception as e:
            await update.message.reply_text(f"Hata: {e!s:.200}")  # type: ignore[union-attr]
        finally:
            db.close()

    async def _cmd_status(self, update: Update, context: Any) -> None:
        chat_id = str(update.effective_chat.id)  # type: ignore[union-attr]
        if not self._is_allowed(chat_id):
            return

        args = context.args or []
        if not args:
            await update.message.reply_text("Kullanım: /status <execution_id>")  # type: ignore[union-attr]
            return

        try:
            exec_id = int(args[0])
        except ValueError:
            await update.message.reply_text("Geçersiz execution ID.")  # type: ignore[union-attr]
            return

        from app.database import SessionLocal
        from app.models.execution import Execution

        db = SessionLocal()
        try:
            execution = db.query(Execution).filter(Execution.id == exec_id).first()
            if not execution:
                await update.message.reply_text(f"Execution #{exec_id} bulunamadı.")  # type: ignore[union-attr]
                return

            emoji = _STATUS_EMOJI.get(execution.status.value, "❓")
            duration = ""
            if execution.started_at and execution.finished_at:
                dur_s = (execution.finished_at - execution.started_at).total_seconds()
                duration = f"{dur_s:.1f}s"

            lines = [
                f"{emoji} <b>Execution #{execution.id}</b> — {execution.status.value}",
                f"Workflow: #{execution.workflow_id}",
                f"Trigger: {execution.trigger_type.value}",
            ]
            if duration:
                lines.append(f"Süre: {duration}")
            if execution.error:
                lines.append(f"\nHata: <code>{execution.error[:300]}</code>")

            # Steps
            if execution.steps:
                lines.append("\n<b>Adımlar:</b>")
                for step in execution.steps:
                    s_emoji = _STATUS_EMOJI.get(step.status.value, "❓")
                    dur = f"{step.duration_ms}ms" if step.duration_ms else "..."
                    lines.append(f"  {s_emoji} {step.node_type}  {dur}")

            await update.message.reply_text("\n".join(lines), parse_mode="HTML")  # type: ignore[union-attr]
        finally:
            db.close()

    async def _cmd_history(self, update: Update, context: Any) -> None:
        chat_id = str(update.effective_chat.id)  # type: ignore[union-attr]
        if not self._is_allowed(chat_id):
            return

        args = context.args or []
        limit = 5
        if args:
            try:
                limit = min(int(args[0]), 20)
            except ValueError:
                pass

        from app.database import SessionLocal
        from app.models.execution import Execution
        from app.models.workflow import Workflow

        db = SessionLocal()
        try:
            execs = db.query(Execution).order_by(Execution.id.desc()).limit(limit).all()
            if not execs:
                await update.message.reply_text("Henüz execution yok.")  # type: ignore[union-attr]
                return

            wf_names: dict[int, str] = {}
            for e in execs:
                if e.workflow_id not in wf_names:
                    wf = db.query(Workflow).filter(Workflow.id == e.workflow_id).first()
                    wf_names[e.workflow_id] = wf.name if wf else f"#{e.workflow_id}"

            lines = [f"📊 <b>Son {len(execs)} execution:</b>\n"]
            for e in execs:
                emoji = _STATUS_EMOJI.get(e.status.value, "❓")
                dur = ""
                if e.started_at and e.finished_at:
                    dur = f", {(e.finished_at - e.started_at).total_seconds():.1f}s"
                time_str = e.started_at.strftime("%H:%M") if e.started_at else ""
                lines.append(
                    f"{emoji} <b>#{e.id}</b> {wf_names.get(e.workflow_id, '?')} ({time_str}{dur})"
                )

            lines.append("\n/status &lt;id&gt; ile detay gör")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")  # type: ignore[union-attr]
        finally:
            db.close()

    async def _cmd_subscribe(self, update: Update, context: Any) -> None:
        chat_id = str(update.effective_chat.id)  # type: ignore[union-attr]
        if not self._is_allowed(chat_id):
            return
        # Store chat_id for notifications
        self._subscribers.add(chat_id)
        await update.message.reply_text(  # type: ignore[union-attr]
            "🔔 Tüm workflow hatalarına abone oldun.\nHer hata anında bildirim alacaksın.",
        )

    async def _cmd_unsubscribe(self, update: Update, context: Any) -> None:
        chat_id = str(update.effective_chat.id)  # type: ignore[union-attr]
        self._subscribers.discard(chat_id)
        await update.message.reply_text("🔕 Abonelik iptal edildi.")  # type: ignore[union-attr]

    # ------------------------------------------------------------------ proactive

    _subscribers: set[str] = set()

    async def notify_execution(self, execution_id: int) -> None:
        """Called by the executor when a workflow finishes. Sends to subscribers."""
        if not self._started or not self._app or not self._subscribers:
            return

        from app.database import SessionLocal
        from app.models.execution import Execution, ExecutionStatus
        from app.models.workflow import Workflow

        db = SessionLocal()
        try:
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if not execution:
                return

            wf = db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
            wf_name = wf.name if wf else f"#{execution.workflow_id}"

            emoji = _STATUS_EMOJI.get(execution.status.value, "❓")
            duration = ""
            if execution.started_at and execution.finished_at:
                dur_s = (execution.finished_at - execution.started_at).total_seconds()
                duration = f" · {dur_s:.1f}s"

            if execution.status == ExecutionStatus.ERROR:
                text = (
                    f"🚨 <b>Workflow HATA</b>\n"
                    f"{wf_name} (#{execution.id}){duration}\n"
                    f"\nHata: <code>{(execution.error or '')[:200]}</code>"
                    f"\n\n/status {execution.id} · /run {execution.workflow_id}"
                )
            else:
                text = (
                    f"{emoji} <b>#{execution.id}</b> {wf_name}{duration}\n{execution.status.value}"
                )

            # Send to all subscribers
            for chat_id in list(self._subscribers):
                try:
                    await self._app.bot.send_message(
                        chat_id=int(chat_id),
                        text=text,
                        parse_mode="HTML",
                    )
                except Exception:
                    logger.warning("telegram_notify_failed", extra={"chat_id": chat_id})
        finally:
            db.close()

    async def send_message(self, chat_id: str | None, text: str) -> bool:
        """Send a message to a specific chat. Used by output.telegram node (future)."""
        if not self._started or not self._app:
            return False
        target = chat_id or self._default_chat_id
        if not target:
            return False
        try:
            await self._app.bot.send_message(
                chat_id=int(target),
                text=text[:4096],
                parse_mode="HTML",
            )
            return True
        except Exception:
            logger.warning("telegram_send_failed", extra={"chat_id": target})
            return False


# Module-level singleton
telegram_bot_service = TelegramBotService()
