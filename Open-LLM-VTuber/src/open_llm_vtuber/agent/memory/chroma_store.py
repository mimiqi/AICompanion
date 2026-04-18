"""ChromaDB-backed long-term memory store.

Uses ChromaDB's PersistentClient so memories survive process
restarts. Embeddings default to ChromaDB's built-in
`all-MiniLM-L6-v2` (downloaded on first use, ~80MB). To override,
pass `embedding_model='your-model'` and the store will switch to
the SentenceTransformer with that name.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .base import MemoryRecord, MemoryStore


class ChromaMemoryStore(MemoryStore):
    """Persist conversation memories in a local ChromaDB collection."""

    def __init__(
        self,
        persist_directory: str | Path,
        *,
        collection_name: str = "companion_memory",
        embedding_model: Optional[str] = None,
    ) -> None:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise ImportError(
                "ChromaMemoryStore requires the `chromadb` package. "
                "Install with `uv pip install chromadb` or `pip install chromadb`."
            ) from exc

        persist_path = Path(persist_directory).expanduser().resolve()
        persist_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False),
        )

        embedding_function = self._build_embedding_function(embedding_model)

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"ChromaMemoryStore: ready at {persist_path} "
            f"collection='{collection_name}' model='{embedding_model or 'default'}'"
        )

    @staticmethod
    def _build_embedding_function(model_name: Optional[str]):
        from chromadb.utils import embedding_functions

        if not model_name:
            return embedding_functions.DefaultEmbeddingFunction()
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )

    def add(
        self,
        text: str,
        *,
        role: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not text or not text.strip():
            return

        record_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        meta: Dict[str, Any] = {
            "role": role,
            "timestamp": time.time(),
        }
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    meta[k] = v

        try:
            self._collection.add(
                ids=[record_id],
                documents=[text.strip()],
                metadatas=[meta],
            )
        except Exception as exc:
            logger.warning(f"ChromaMemoryStore.add failed: {exc}")

    def query(self, text: str, *, top_k: int = 4) -> List[MemoryRecord]:
        if not text or not text.strip() or top_k <= 0:
            return []

        try:
            collection_size = self._collection.count()
        except Exception:
            collection_size = 0

        if collection_size == 0:
            return []

        n_results = min(top_k, collection_size)

        try:
            result = self._collection.query(
                query_texts=[text.strip()],
                n_results=n_results,
            )
        except Exception as exc:
            logger.warning(f"ChromaMemoryStore.query failed: {exc}")
            return []

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        records: List[MemoryRecord] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            meta = meta or {}
            records.append(
                MemoryRecord(
                    text=doc,
                    role=str(meta.get("role", "user")),
                    score=float(1.0 - dist) if dist is not None else 0.0,
                    metadata={k: v for k, v in meta.items() if k != "role"},
                )
            )
        return records

    def reset(self) -> None:
        try:
            name = self._collection.name
            self._client.delete_collection(name=name)
            self._collection = self._client.create_collection(
                name=name, metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaMemoryStore: collection reset")
        except Exception as exc:
            logger.warning(f"ChromaMemoryStore.reset failed: {exc}")
