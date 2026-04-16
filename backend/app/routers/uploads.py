"""File upload endpoint for runtime workflow inputs.

Spec: docs/RUNTIME_INPUT_SPEC.md §2.2

Accepts a single file via multipart/form-data, validates extension + size,
saves to ``<cwd>/uploads/`` with a timestamp prefix, and returns the
filename so the caller can pass it into a workflow's ``input_data``.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.logging_config import get_logger

logger = get_logger("agenticflow.uploads")

router = APIRouter()

_UPLOADS_DIR = Path(os.getcwd()) / "uploads"
_ALLOWED_EXTENSIONS = {".xlsx", ".csv"}
_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("")
async def upload_file(file: UploadFile) -> dict:
    """Upload a file for use in workflow runs.

    Returns ``{"filename": "<timestamped>", "original": "<original>", "size": N}``.
    The ``filename`` value is what goes into ``input_data.file`` when
    triggering a workflow that uses ``{{trigger_input.file}}``.
    """
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    # Read + enforce size limit
    content = await file.read()
    if len(content) > _MAX_SIZE_BYTES:
        raise HTTPException(
            413,
            f"File too large ({len(content):,} bytes). Max: {_MAX_SIZE_BYTES:,} bytes.",
        )

    # Timestamped filename to avoid collisions
    stem = Path(file.filename).stem
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{stem}_{ts}{ext}"

    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOADS_DIR / safe_name
    dest.write_bytes(content)

    logger.info(
        "file_uploaded",
        extra={
            "original": file.filename,
            "saved_as": safe_name,
            "size": len(content),
        },
    )

    return {
        "filename": safe_name,
        "original": file.filename,
        "size": len(content),
    }
