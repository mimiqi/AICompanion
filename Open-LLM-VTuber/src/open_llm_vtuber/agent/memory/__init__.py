"""Long-term memory backends for Companion agents."""

from .base import MemoryRecord, MemoryStore

__all__ = ["MemoryRecord", "MemoryStore"]

# ChromaMemoryStore is imported lazily so that ChromaDB stays an optional
# dependency: the rest of OLV keeps working even when chromadb isn't
# installed.
