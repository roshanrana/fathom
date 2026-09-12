"""Append-only audit writer with never-log rules (LLD §2.9)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from fathom.config import Settings
from fathom.errors import Code, FathomError

logger = logging.getLogger("fathom")


class AuditRecord(BaseModel):
    """One line of the append-only audit log."""

    ts: datetime
    ticker: str
    purpose: Literal["brief", "ask", "probe"]
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    prompt_sha256: str
    response_sha256: str
    claims_total: int
    claims_verified: int
    guard_hits: int
    prompt: str | None = None
    response: str | None = None


def record(settings: Settings, rec: AuditRecord) -> None:
    """Append one JSON line for `rec` to `settings.audit_path`, creating parent dirs.

    `prompt`/`response` are dropped entirely unless `settings.audit_bodies` is True.
    Never logs bodies, keys, or question text — only the destination path on success.
    """
    payload = json.loads(rec.model_dump_json())
    if not settings.audit_bodies:
        payload.pop("prompt", None)
        payload.pop("response", None)
    line = json.dumps(payload, ensure_ascii=False)

    path = settings.audit_path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        raise FathomError(
            Code.AUDIT_WRITE,
            f"failed to write audit record to {path}",
            {"path": str(path)},
        ) from exc

    logger.info("audit written path=%s", path)
