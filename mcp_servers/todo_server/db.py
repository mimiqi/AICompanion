"""SQLite-backed To-do storage layer."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, TypedDict


SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    notes       TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'completed'
    due_at      REAL,                              -- unix epoch seconds, optional
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_due_at ON todos(due_at);
"""


class TodoRow(TypedDict, total=False):
    id: int
    title: str
    notes: Optional[str]
    status: str
    due_at: Optional[float]
    created_at: float
    updated_at: float
    completed_at: Optional[float]


class TodoDB:
    """Thread-safe wrapper around a single SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> TodoRow:
        return {k: row[k] for k in row.keys()}

    def add(
        self,
        title: str,
        *,
        notes: Optional[str] = None,
        due_at: Optional[float] = None,
    ) -> TodoRow:
        if not title or not title.strip():
            raise ValueError("title cannot be empty")
        now = time.time()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO todos(title, notes, due_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (title.strip(), notes, due_at, now, now),
            )
            todo_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?", (todo_id,)
            ).fetchone()
        return self._row_to_dict(row)

    def list(
        self,
        *,
        status: str = "pending",
        limit: int = 100,
    ) -> List[TodoRow]:
        status = (status or "pending").lower()
        valid = {"pending", "completed", "all"}
        if status not in valid:
            raise ValueError(f"status must be one of {sorted(valid)}")
        with self._connect() as conn:
            if status == "all":
                rows = conn.execute(
                    "SELECT * FROM todos "
                    "ORDER BY (status='completed'), COALESCE(due_at, 9.9e12), created_at "
                    "LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM todos WHERE status = ? "
                    "ORDER BY COALESCE(due_at, 9.9e12), created_at "
                    "LIMIT ?",
                    (status, limit),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, todo_id: int) -> Optional[TodoRow]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?", (todo_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def update(
        self,
        todo_id: int,
        *,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        due_at: Optional[float] = None,
        status: Optional[str] = None,
    ) -> Optional[TodoRow]:
        sets: List[str] = []
        params: List[object] = []
        if title is not None:
            sets.append("title = ?")
            params.append(title.strip())
        if notes is not None:
            sets.append("notes = ?")
            params.append(notes)
        if due_at is not None:
            sets.append("due_at = ?")
            params.append(due_at)
        if status is not None:
            status_l = status.lower()
            if status_l not in {"pending", "completed"}:
                raise ValueError("status must be 'pending' or 'completed'")
            sets.append("status = ?")
            params.append(status_l)
            if status_l == "completed":
                sets.append("completed_at = ?")
                params.append(time.time())
            else:
                sets.append("completed_at = NULL")

        if not sets:
            return self.get(todo_id)

        sets.append("updated_at = ?")
        params.append(time.time())
        params.append(todo_id)

        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"UPDATE todos SET {', '.join(sets)} WHERE id = ?", params
            )
            if cur.rowcount == 0:
                return None
        return self.get(todo_id)

    def complete(self, todo_id: int) -> Optional[TodoRow]:
        return self.update(todo_id, status="completed")

    def delete(self, todo_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            return cur.rowcount > 0


def default_db_path() -> Path:
    explicit = os.environ.get("TODO_DB_PATH")
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parents[2] / "data" / "todos.db"
