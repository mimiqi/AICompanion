"""Mail server configuration loader."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MailConfig:
    imap_host: str
    imap_port: int = 993
    use_ssl: bool = True
    username: str = ""
    password: str = ""
    mailbox: str = "INBOX"
    fetch_limit: int = 20
    poll_interval_seconds: int = 90
    olv_websocket_url: str = "ws://127.0.0.1:12393/client-ws"
    state_path: str = "../data/mail_state.json"
    proactive_enabled: bool = True
    senders_whitelist: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "MailConfig":
        cfg_path = Path(
            path
            or os.environ.get("MAIL_CONFIG_PATH")
            or (Path(__file__).resolve().parent / "mail_config.json")
        )
        if not cfg_path.is_file():
            raise FileNotFoundError(
                f"Mail config not found at {cfg_path}. "
                "Copy mail_config.example.json to mail_config.json and fill it in."
            )
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))

        return cls(
            imap_host=raw["imap_host"],
            imap_port=int(raw.get("imap_port", 993)),
            use_ssl=bool(raw.get("use_ssl", True)),
            username=raw.get("username", ""),
            password=raw.get("password", ""),
            mailbox=raw.get("mailbox", "INBOX"),
            fetch_limit=int(raw.get("fetch_limit", 20)),
            poll_interval_seconds=int(raw.get("poll_interval_seconds", 90)),
            olv_websocket_url=raw.get(
                "olv_websocket_url", "ws://127.0.0.1:12393/client-ws"
            ),
            state_path=raw.get("state_path", "../data/mail_state.json"),
            proactive_enabled=bool(raw.get("proactive_enabled", True)),
            senders_whitelist=list(raw.get("senders_whitelist") or []),
            raw=raw,
        )

    def state_file(self) -> Path:
        return Path(self.state_path).expanduser().resolve()


def load_state(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
