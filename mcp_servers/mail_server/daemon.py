"""Mail polling daemon.

Periodically polls IMAP for new mail; on detecting unseen messages
that haven't been seen before, it connects to OLV's `/client-ws`
WebSocket and sends an `ai-speak-signal` to trigger proactive
narration ("you've got mail" behaviour).

Run as::

    python -m mcp_servers.mail_server.daemon

Should be started AFTER the OLV server is up. Will retry forever on
IMAP / WebSocket failures with exponential back-off.
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import threading
import time
from typing import Set

from .config import MailConfig, load_state, save_state
from .imap_client import IMAPClient


logging.basicConfig(
    level=logging.INFO,
    format="[mail-daemon %(asctime)s %(levelname)s] %(message)s",
)
log = logging.getLogger("mail-daemon")


class _StopFlag:
    def __init__(self) -> None:
        self._event = threading.Event()

    def set(self, *_args: object) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)


def _send_proactive_speak(ws_url: str, message_hint: str) -> bool:
    """Connect once to OLV WebSocket and emit ai-speak-signal.

    Returns True on success. We use the synchronous `websocket-client`
    package which is already an OLV dependency.
    """
    try:
        from websocket import create_connection
    except ImportError:
        log.error(
            "websocket-client not installed; daemon cannot trigger proactive speak. "
            "Install via `pip install websocket-client`."
        )
        return False

    try:
        ws = create_connection(ws_url, timeout=10)
    except Exception as exc:
        log.warning(f"WebSocket connect failed ({ws_url}): {exc}")
        return False

    try:
        payload = {
            "type": "ai-speak-signal",
            "source": "mail-daemon",
            "hint": message_hint,
        }
        ws.send(json.dumps(payload))
        log.info(f"sent ai-speak-signal: {message_hint}")
        time.sleep(0.5)
        return True
    except Exception as exc:
        log.warning(f"WebSocket send failed: {exc}")
        return False
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _poll_once(
    client: IMAPClient,
    cfg: MailConfig,
    seen_uids: Set[str],
) -> Set[str]:
    """Return UIDs of new unseen messages, updating `seen_uids` in place."""
    try:
        messages = client.fetch_recent(unread_only=True, limit=cfg.fetch_limit)
    except Exception as exc:
        log.warning(f"IMAP fetch failed: {exc}")
        return set()

    new_uids: Set[str] = set()
    for m in messages:
        if m.uid in seen_uids:
            continue
        if cfg.senders_whitelist:
            if not any(
                s.lower() in (m.sender or "").lower() for s in cfg.senders_whitelist
            ):
                continue
        new_uids.add(m.uid)

    seen_uids.update(m.uid for m in messages)
    return new_uids


def main() -> None:
    cfg = MailConfig.load()
    state_path = cfg.state_file()
    state = load_state(state_path)
    seen_uids: Set[str] = set(state.get("seen_uids", []))

    stop_flag = _StopFlag()
    signal.signal(signal.SIGINT, stop_flag.set)
    signal.signal(signal.SIGTERM, stop_flag.set)

    client = IMAPClient(cfg)
    backoff = 1.0
    max_backoff = 300.0

    log.info(
        f"daemon started: host={cfg.imap_host} user={cfg.username} "
        f"interval={cfg.poll_interval_seconds}s proactive={cfg.proactive_enabled}"
    )

    while not stop_flag.is_set():
        try:
            new_uids = _poll_once(client, cfg, seen_uids)
            if new_uids:
                log.info(f"detected {len(new_uids)} new unread email(s)")
                if cfg.proactive_enabled:
                    hint = (
                        f"You have {len(new_uids)} new unread email(s). "
                        "Briefly notify the user and offer to summarize using the mail tool."
                    )
                    _send_proactive_speak(cfg.olv_websocket_url, hint)
                state["seen_uids"] = sorted(seen_uids)[-500:]
                save_state(state_path, state)
            backoff = 1.0
        except Exception as exc:
            log.warning(f"poll loop error: {exc}; backing off {backoff:.1f}s")
            stop_flag.wait(backoff)
            backoff = min(backoff * 2, max_backoff)
            continue

        stop_flag.wait(cfg.poll_interval_seconds)

    log.info("daemon stopped")
    sys.exit(0)


if __name__ == "__main__":
    main()
