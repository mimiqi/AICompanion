"""Mail MCP Server.

Exposes IMAP-backed mail tools to the LLM via MCP. Run as::

    python -m mcp_servers.mail_server.server

Configure via mail_config.json (see mail_config.example.json).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from .config import MailConfig
from .imap_client import IMAPClient


_CFG = MailConfig.load()
_CLIENT = IMAPClient(_CFG)
mcp = FastMCP("mail")


@mcp.tool()
def fetch_recent_emails(
    unread_only: bool = True,
    limit: int = 10,
    include_body: bool = False,
) -> Dict[str, Any]:
    """Fetch recent emails from the configured INBOX.

    Args:
        unread_only: If True, return only unread messages. Default True.
        limit: Max number of messages to return (default 10).
        include_body: If True, include a short snippet of the body.
    """
    try:
        messages = _CLIENT.fetch_recent(
            unread_only=unread_only, limit=limit, include_body=include_body
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "count": len(messages),
        "unread_only": unread_only,
        "emails": [m.to_dict() for m in messages],
    }


@mcp.tool()
def get_email_detail(uid: str) -> Dict[str, Any]:
    """Fetch the full body of a specific email by UID."""
    try:
        msg = _CLIENT.fetch_by_uid(uid)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if not msg:
        return {"ok": False, "error": f"email uid {uid} not found"}
    payload = msg.to_dict()
    payload["body"] = msg.body
    return {"ok": True, "email": payload}


@mcp.tool()
def get_unread_count() -> Dict[str, Any]:
    """Return the current unread email count."""
    try:
        count = _CLIENT.unread_count()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "unread_count": count}


@mcp.tool()
def get_mail_account_info() -> Dict[str, Any]:
    """Report which mailbox/host this server is connected to (no credentials)."""
    return {
        "ok": True,
        "imap_host": _CFG.imap_host,
        "username": _CFG.username,
        "mailbox": _CFG.mailbox,
        "proactive_enabled": _CFG.proactive_enabled,
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
