"""Minimal IMAP client for fetching unread / recent messages."""

from __future__ import annotations

import email
import imaplib
from contextlib import contextmanager
from dataclasses import dataclass
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Iterator, List, Optional

from .config import MailConfig


@dataclass
class MailMessage:
    uid: str
    subject: str
    sender: str
    date: Optional[str]
    snippet: str
    is_unread: bool
    body: str = ""

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "subject": self.subject,
            "sender": self.sender,
            "date": self.date,
            "snippet": self.snippet,
            "is_unread": self.is_unread,
        }


def _decode_header(value: Optional[str]) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            try:
                out.append(chunk.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                out.append(chunk.decode("utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out).strip()


def _extract_body(msg: email.message.Message, max_chars: int = 4000) -> str:
    """Pull the best-effort plain-text body out of a multipart message."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")[:max_chars]
                except Exception:
                    continue
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")[:max_chars]
                except Exception:
                    continue
        return ""

    try:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")[:max_chars]
    except Exception:
        return ""


class IMAPClient:
    def __init__(self, config: MailConfig) -> None:
        self._cfg = config

    @contextmanager
    def _connect(self) -> Iterator[imaplib.IMAP4]:
        cls = imaplib.IMAP4_SSL if self._cfg.use_ssl else imaplib.IMAP4
        conn = cls(self._cfg.imap_host, self._cfg.imap_port)
        try:
            conn.login(self._cfg.username, self._cfg.password)
            conn.select(self._cfg.mailbox, readonly=True)
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass
            try:
                conn.logout()
            except Exception:
                pass

    def fetch_recent(
        self,
        *,
        unread_only: bool = False,
        limit: Optional[int] = None,
        include_body: bool = False,
        max_body_chars: int = 4000,
    ) -> List[MailMessage]:
        limit = limit or self._cfg.fetch_limit
        criterion = "UNSEEN" if unread_only else "ALL"

        with self._connect() as conn:
            typ, data = conn.uid("search", None, criterion)
            if typ != "OK" or not data or not data[0]:
                return []
            uids = data[0].split()
            uids = uids[-limit:][::-1]

            messages: List[MailMessage] = []
            for uid in uids:
                fetch_parts = "(BODY.PEEK[] FLAGS)" if include_body else "(BODY.PEEK[HEADER] FLAGS)"
                typ, msg_data = conn.uid("fetch", uid, fetch_parts)
                if typ != "OK" or not msg_data:
                    continue

                raw_bytes = b""
                flags_str = ""
                for chunk in msg_data:
                    if isinstance(chunk, tuple) and len(chunk) >= 2:
                        raw_bytes = chunk[1]
                    elif isinstance(chunk, bytes):
                        flags_str += chunk.decode("utf-8", errors="ignore")

                if not raw_bytes:
                    continue
                msg = email.message_from_bytes(raw_bytes)

                subject = _decode_header(msg.get("Subject"))
                sender = _decode_header(msg.get("From"))
                date_str = msg.get("Date")
                date_iso: Optional[str] = None
                if date_str:
                    try:
                        date_iso = parsedate_to_datetime(date_str).isoformat()
                    except Exception:
                        date_iso = date_str

                body = ""
                snippet = ""
                if include_body:
                    body = _extract_body(msg, max_chars=max_body_chars)
                    snippet = body[:200].replace("\r", " ").replace("\n", " ").strip()

                messages.append(
                    MailMessage(
                        uid=uid.decode() if isinstance(uid, bytes) else str(uid),
                        subject=subject,
                        sender=sender,
                        date=date_iso,
                        snippet=snippet,
                        is_unread="\\Seen" not in flags_str,
                        body=body,
                    )
                )
            return messages

    def fetch_by_uid(self, uid: str, *, max_body_chars: int = 8000) -> Optional[MailMessage]:
        with self._connect() as conn:
            typ, msg_data = conn.uid("fetch", uid, "(BODY.PEEK[] FLAGS)")
            if typ != "OK" or not msg_data:
                return None
            raw_bytes = b""
            flags_str = ""
            for chunk in msg_data:
                if isinstance(chunk, tuple) and len(chunk) >= 2:
                    raw_bytes = chunk[1]
                elif isinstance(chunk, bytes):
                    flags_str += chunk.decode("utf-8", errors="ignore")
            if not raw_bytes:
                return None
            msg = email.message_from_bytes(raw_bytes)
            subject = _decode_header(msg.get("Subject"))
            sender = _decode_header(msg.get("From"))
            date_str = msg.get("Date")
            try:
                date_iso = (
                    parsedate_to_datetime(date_str).isoformat() if date_str else None
                )
            except Exception:
                date_iso = date_str
            body = _extract_body(msg, max_chars=max_body_chars)
            return MailMessage(
                uid=uid,
                subject=subject,
                sender=sender,
                date=date_iso,
                snippet=body[:200].replace("\r", " ").replace("\n", " ").strip(),
                is_unread="\\Seen" not in flags_str,
                body=body,
            )

    def unread_count(self) -> int:
        with self._connect() as conn:
            typ, data = conn.uid("search", None, "UNSEEN")
            if typ != "OK" or not data or not data[0]:
                return 0
            return len(data[0].split())
