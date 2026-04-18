"""Companion REST routes for the React panels (todos / mail).

These endpoints share storage with the MCP servers but bypass MCP
itself for low-latency UI access. Mounted under `/api/companion/*`
in `server.py`.

The router is intentionally tolerant: when the optional dependencies
are missing (sqlite, the project-root mcp_servers package, IMAP
credentials), endpoints return graceful HTTP 503 instead of crashing
the whole server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MCP_SERVERS_PATH = _PROJECT_ROOT.parent / "mcp_servers"

if str(_PROJECT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT.parent))


def _load_todo_db():
    try:
        from mcp_servers.todo_server.db import TodoDB, default_db_path
    except Exception as exc:
        logger.warning(f"companion_panels: TodoDB unavailable - {exc}")
        return None
    db_path = os.environ.get("TODO_DB_PATH") or str(default_db_path())
    try:
        return TodoDB(db_path)
    except Exception as exc:
        logger.warning(f"companion_panels: failed to open todo db - {exc}")
        return None


def _load_mail_client():
    try:
        from mcp_servers.mail_server.config import MailConfig
        from mcp_servers.mail_server.imap_client import IMAPClient
    except Exception as exc:
        logger.info(f"companion_panels: mail client unavailable - {exc}")
        return None
    try:
        cfg = MailConfig.load()
        return IMAPClient(cfg)
    except FileNotFoundError:
        logger.info("companion_panels: mail_config.json not configured; mail panel disabled")
        return None
    except Exception as exc:
        logger.warning(f"companion_panels: failed to init mail client - {exc}")
        return None


class TodoCreate(BaseModel):
    title: str
    notes: Optional[str] = None
    due_at: Optional[float] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    due_at: Optional[float] = None
    status: Optional[str] = None


def init_companion_panel_routes() -> APIRouter:
    """Build the /api/companion/* router."""
    router = APIRouter(prefix="/api/companion", tags=["companion-panels"])

    todo_db = _load_todo_db()
    mail_client = _load_mail_client()

    @router.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "ok": True,
            "todo_enabled": todo_db is not None,
            "mail_enabled": mail_client is not None,
        }

    @router.get("/todos")
    async def list_todos(status: str = "pending", limit: int = 50) -> Dict[str, Any]:
        if not todo_db:
            raise HTTPException(503, "todo backend unavailable")
        try:
            return {"ok": True, "todos": todo_db.list(status=status, limit=limit)}
        except Exception as exc:
            raise HTTPException(400, str(exc))

    @router.post("/todos")
    async def create_todo(payload: TodoCreate) -> Dict[str, Any]:
        if not todo_db:
            raise HTTPException(503, "todo backend unavailable")
        try:
            row = todo_db.add(
                title=payload.title, notes=payload.notes, due_at=payload.due_at
            )
            return {"ok": True, "todo": row}
        except Exception as exc:
            raise HTTPException(400, str(exc))

    @router.patch("/todos/{todo_id}")
    async def update_todo(todo_id: int, payload: TodoUpdate) -> Dict[str, Any]:
        if not todo_db:
            raise HTTPException(503, "todo backend unavailable")
        try:
            row = todo_db.update(
                todo_id,
                title=payload.title,
                notes=payload.notes,
                due_at=payload.due_at,
                status=payload.status,
            )
            if not row:
                raise HTTPException(404, "todo not found")
            return {"ok": True, "todo": row}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, str(exc))

    @router.delete("/todos/{todo_id}")
    async def delete_todo(todo_id: int) -> Dict[str, Any]:
        if not todo_db:
            raise HTTPException(503, "todo backend unavailable")
        deleted = todo_db.delete(todo_id)
        if not deleted:
            raise HTTPException(404, "todo not found")
        return {"ok": True, "id": todo_id}

    @router.get("/mail/recent")
    async def list_mail(unread_only: bool = True, limit: int = 20) -> Dict[str, Any]:
        if not mail_client:
            raise HTTPException(
                503, "mail panel disabled; see mcp_servers/mail_server/README.md"
            )
        try:
            messages = mail_client.fetch_recent(
                unread_only=unread_only, limit=limit, include_body=False
            )
        except Exception as exc:
            raise HTTPException(502, f"IMAP error: {exc}")
        return {"ok": True, "emails": [m.to_dict() for m in messages]}

    @router.get("/mail/{uid}")
    async def get_mail(uid: str) -> Dict[str, Any]:
        if not mail_client:
            raise HTTPException(503, "mail panel disabled")
        try:
            msg = mail_client.fetch_by_uid(uid)
        except Exception as exc:
            raise HTTPException(502, f"IMAP error: {exc}")
        if not msg:
            raise HTTPException(404, f"email uid {uid} not found")
        payload = msg.to_dict()
        payload["body"] = msg.body
        return {"ok": True, "email": payload}

    return router
