"""To-do MCP Server.

Exposes CRUD tools for a local SQLite-backed to-do list, callable
by the LLM through the Model Context Protocol. Run as::

    python -m mcp_servers.todo_server.server

Open-LLM-VTuber's MCP registry launches this script automatically
when `todo` is listed in `mcp_enabled_servers`.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from .db import TodoDB, default_db_path


_DB = TodoDB(default_db_path())
mcp = FastMCP("todo")


def _format(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw row into LLM-friendly dict (ISO timestamps)."""
    out = dict(row)
    for k in ("due_at", "created_at", "updated_at", "completed_at"):
        v = out.get(k)
        if isinstance(v, (int, float)):
            out[k] = datetime.fromtimestamp(v).isoformat(timespec="seconds")
    return out


def _parse_due_at(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid due_at '{value}'. Use ISO 8601 (e.g. 2026-04-20T18:00) "
                "or a unix timestamp."
            ) from exc


@mcp.tool()
def add_todo(
    title: str,
    notes: Optional[str] = None,
    due_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new to-do entry.

    Args:
        title: Short description of what needs to be done.
        notes: Optional longer details / context.
        due_at: Optional ISO 8601 datetime (e.g. '2026-04-20T18:00').
    """
    due_ts = _parse_due_at(due_at)
    row = _DB.add(title=title, notes=notes, due_at=due_ts)
    return {"ok": True, "todo": _format(row)}


@mcp.tool()
def list_todos(status: str = "pending", limit: int = 20) -> Dict[str, Any]:
    """List to-do entries.

    Args:
        status: 'pending', 'completed', or 'all'. Defaults to 'pending'.
        limit: Maximum number of entries to return (default 20).
    """
    rows = _DB.list(status=status, limit=limit)
    return {
        "ok": True,
        "count": len(rows),
        "status_filter": status,
        "todos": [_format(r) for r in rows],
    }


@mcp.tool()
def complete_todo(todo_id: int) -> Dict[str, Any]:
    """Mark a to-do as completed."""
    row = _DB.complete(todo_id)
    if not row:
        return {"ok": False, "error": f"todo {todo_id} not found"}
    return {"ok": True, "todo": _format(row)}


@mcp.tool()
def update_todo(
    todo_id: int,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    due_at: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Update fields on a to-do entry. Pass only the fields you want to change."""
    due_ts = _parse_due_at(due_at) if due_at else None
    row = _DB.update(
        todo_id, title=title, notes=notes, due_at=due_ts, status=status
    )
    if not row:
        return {"ok": False, "error": f"todo {todo_id} not found"}
    return {"ok": True, "todo": _format(row)}


@mcp.tool()
def delete_todo(todo_id: int) -> Dict[str, Any]:
    """Delete a to-do entry permanently."""
    deleted = _DB.delete(todo_id)
    return {"ok": deleted, "id": todo_id}


@mcp.tool()
def stats() -> Dict[str, Any]:
    """Return aggregate counts and overdue items - useful for proactive nudges."""
    pending_rows = _DB.list(status="pending")
    completed_rows = _DB.list(status="completed", limit=500)
    now_ts = time.time()
    overdue = [
        r for r in pending_rows if r.get("due_at") and r["due_at"] < now_ts
    ]
    return {
        "ok": True,
        "pending_count": len(pending_rows),
        "completed_count": len(completed_rows),
        "overdue_count": len(overdue),
        "overdue_titles": [r["title"] for r in overdue][:10],
        "now": datetime.fromtimestamp(now_ts).isoformat(timespec="seconds"),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
