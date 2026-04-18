"""Abstract long-term memory protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryRecord:
    """A single memory entry recalled from a long-term store."""

    text: str
    role: str = "user"
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render(self, *, include_role: bool = True) -> str:
        if include_role:
            speaker = "User" if self.role == "user" else "AI"
            return f"[{speaker}] {self.text}"
        return self.text


class MemoryStore(ABC):
    """Common interface for long-term memory backends."""

    @abstractmethod
    def add(
        self,
        text: str,
        *,
        role: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None: ...

    @abstractmethod
    def query(self, text: str, *, top_k: int = 4) -> List[MemoryRecord]: ...

    def reset(self) -> None:
        """Optional: clear all stored memories."""
        return None
