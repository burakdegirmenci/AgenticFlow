"""Anthropic Claude Code CLI provider (subprocess, subscription auth).

This wraps the `claude` CLI that ships with Claude Code. Authentication is
delegated to whatever session you already have via `claude login` — so it
works with Pro/Max subscriptions without needing an API key.

Trade-offs vs the API provider:
- No structured tool_use: we use `--print --output-format stream-json`
  which streams text deltas. Tool calls are NOT supported here; the agent
  service must fall back to text-only workflow parsing (JSON code-fence)
  when this provider is selected.
- Slightly slower first-token latency (process startup cost).
- Requires `claude` binary on PATH (or CLAUDE_CLI_PATH set in settings).

Nested-session note:
- The CLI refuses to launch if `CLAUDECODE` env var is set (it's a safety
  guard against running Claude Code inside Claude Code). When the AgenticFlow
  backend is itself spawned from a Claude Code session, that env var is
  inherited and the CLI errors out. We strip CLAUDE-related env vars before
  spawning the subprocess to bypass that guard for our isolated child.

Windows event loop note:
- uvicorn on Windows forces `WindowsSelectorEventLoopPolicy` for aiohttp/aiodns
  compatibility, but SelectorEventLoop does NOT support `subprocess_exec` and
  raises `NotImplementedError`. We therefore use a synchronous
  `subprocess.Popen` with a background reader thread and bridge it back to
  the async world via `asyncio.to_thread` / a thread-safe queue. Works under
  any event loop implementation on any platform.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import shutil
import subprocess
import threading
from collections.abc import AsyncIterator
from typing import Any

from app.services.llm import register
from app.services.llm.base import (
    LLMEvent,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)


@register
class AnthropicCLIProvider(LLMProvider):
    name = "anthropic_cli"
    display_name = "Anthropic (Claude Code CLI — Subscription)"
    supports_tools = False  # Text-only fallback
    supports_streaming = True
    default_model = ""  # CLI picks the default tied to the account

    def _cli_path(self) -> str:
        from app.services.settings_service import get_llm_setting

        configured = get_llm_setting("CLAUDE_CLI_PATH") or "claude"
        resolved = shutil.which(configured)
        if not resolved:
            raise LLMProviderError(
                f"Claude CLI not found at {configured!r}. Install Claude Code "
                "and run `claude login`, or set CLAUDE_CLI_PATH in Settings."
            )
        return resolved

    async def is_available(self) -> tuple[bool, str]:
        from app.services.settings_service import get_llm_setting

        configured = get_llm_setting("CLAUDE_CLI_PATH") or "claude"
        resolved = shutil.which(configured)
        if not resolved:
            return False, f"{configured!r} not on PATH"
        return True, f"cli at {resolved}"

    def _build_prompt(self, system: str, messages: list[LLMMessage]) -> str:
        """Flatten the conversation into a single prompt.

        The CLI doesn't accept structured roles, so we prepend a system
        block and mark turns with simple delimiters.
        """
        lines: list[str] = []
        if system:
            lines.append("## System")
            lines.append(system.strip())
            lines.append("")
        for m in messages:
            tag = "User" if m.role == "user" else "Assistant"
            lines.append(f"## {tag}")
            lines.append(m.content.strip())
            lines.append("")
        lines.append("## Assistant")
        return "\n".join(lines).strip()

    async def _run(
        self,
        prompt: str,
        model: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Spawn `claude --print --output-format stream-json` via a sync
        subprocess + reader thread, yielding JSON events.

        Why sync Popen instead of `asyncio.create_subprocess_exec`:
        uvicorn pins `WindowsSelectorEventLoopPolicy` on Windows which does
        not implement `_make_subprocess_transport`. We therefore drive the
        subprocess from a daemon thread and shuttle lines through a
        thread-safe queue, awaiting on it via `asyncio.to_thread`.
        """
        cli = self._cli_path()
        args = [
            cli,
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if model:
            args += ["--model", model]

        # Strip CLAUDE_CODE_* / CLAUDECODE env vars so the CLI's nested-session
        # guard doesn't trip when AgenticFlow itself is launched from inside
        # a Claude Code shell.
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if not (k == "CLAUDECODE" or k.startswith("CLAUDE_CODE_"))
        }

        creationflags = 0
        if os.name == "nt":
            # Avoid flashing a console window on Windows.
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env,
            bufsize=1,  # line-buffered
            creationflags=creationflags,
        )
        assert proc.stdin and proc.stdout and proc.stderr

        # Write the prompt and close stdin so the CLI starts processing.
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except Exception:
            proc.kill()
            raise

        # Background reader thread: pushes raw bytes lines into a queue.
        line_q: queue.Queue[bytes | None] = queue.Queue()

        def _reader() -> None:
            try:
                for raw in proc.stdout:  # blocking readline loop
                    line_q.put(raw)
            finally:
                line_q.put(None)  # sentinel: EOF

        reader_thread = threading.Thread(
            target=_reader,
            name="anthropic_cli-reader",
            daemon=True,
        )
        reader_thread.start()

        try:
            while True:
                raw = await asyncio.to_thread(line_q.get)
                if raw is None:
                    break
                text = raw.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    yield json.loads(text)
                except json.JSONDecodeError:
                    # Non-JSON line, emit as raw text delta
                    yield {"type": "raw_text", "text": text}
        finally:
            # Drain the process cleanly.
            try:
                await asyncio.to_thread(proc.wait, 10)
            except subprocess.TimeoutExpired:
                proc.kill()
                await asyncio.to_thread(proc.wait)
            except Exception:
                proc.kill()
            reader_thread.join(timeout=2)
            try:
                stderr = (await asyncio.to_thread(proc.stderr.read)).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                stderr = ""
            if proc.returncode and proc.returncode != 0:
                raise LLMProviderError(
                    f"claude CLI exited {proc.returncode}: {stderr.strip()[:500]}"
                )

    async def complete(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        # No real non-streaming mode; buffer the stream into a single response.
        text_parts: list[str] = []
        async for event in self.stream(
            system=system,
            messages=messages,
            tools=tools,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if event.type == "text_delta":
                text_parts.append(event.data.get("text", ""))
            elif event.type == "error":
                raise LLMProviderError(event.data.get("message", "CLI error"))
        return LLMResponse(text="".join(text_parts))

    async def stream(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMEvent]:
        if tools:
            # Warn but proceed — CLI provider cannot use structured tools
            yield LLMEvent(
                "warning",
                {"message": "anthropic_cli does not support tool_use; ignoring tools."},
            )

        prompt = self._build_prompt(system, messages)

        try:
            yield LLMEvent("message_start", {})
            async for event in self._run(prompt, model):
                etype = event.get("type", "")
                # Claude Code stream-json shape (simplified). The CLI emits
                # several event types — we only care about text payloads for
                # the MVP. Anything else is ignored.
                if etype == "assistant" or etype == "message":
                    # Look for content.text or message.content[].text
                    msg = event.get("message") or event
                    content = msg.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if (
                                isinstance(block, dict)
                                and block.get("type") == "text"
                                and block.get("text")
                            ):
                                yield LLMEvent(
                                    "text_delta",
                                    {"text": block["text"]},
                                )
                    elif isinstance(content, str):
                        yield LLMEvent("text_delta", {"text": content})
                elif etype == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield LLMEvent(
                            "text_delta",
                            {"text": delta.get("text", "")},
                        )
                elif etype == "raw_text":
                    yield LLMEvent("text_delta", {"text": event.get("text", "")})
                elif etype == "result":
                    yield LLMEvent(
                        "done",
                        {"stop_reason": event.get("stop_reason", "end_turn")},
                    )
                    return
            yield LLMEvent("done", {"stop_reason": "end_turn"})
        except LLMProviderError as e:
            yield LLMEvent("error", {"message": str(e)})
        except Exception as e:
            yield LLMEvent(
                "error",
                {"message": f"CLI stream error [{type(e).__name__}]: {e}"},
            )
