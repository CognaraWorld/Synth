"""Retrieval-Augmented Generation (RAG) pipeline.

Manages a ChromaDB vector store for document chunks. Embeds text using
sentence-transformers and retrieves the most relevant chunks for a
given query. Used to incorporate uploaded document knowledge into
the bot's responses.

Phase 4 implementation — hardened with scope isolation, shared model,
metadata filtering, deletion, and TTL support.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Shared embedding model singleton (Item 3)
# One ~1.3 GB model for the whole process, not one per agent.
# -----------------------------------------------------------------------
_shared_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def _get_shared_model(model_name: str = "BAAI/bge-large-en-v1.5") -> SentenceTransformer:
    """Return the process-wide SentenceTransformer, loading once on first use."""
    global _shared_model
    if _shared_model is not None:
        return _shared_model
    with _model_lock:
        if _shared_model is not None:
            return _shared_model
        logger.info("Loading shared SentenceTransformer: %s", model_name)
        _shared_model = SentenceTransformer(model_name)
        return _shared_model


# Shared ChromaDB client — one per process (reused across pipelines)
_shared_chroma_client: chromadb.PersistentClient | None = None
_chroma_lock = threading.Lock()


# Shared encode lock — must be process-wide since the model is shared.
# Per-instance locks would allow concurrent .encode() on the same model.
_encode_lock = threading.Lock()


def _get_shared_chroma_client() -> chromadb.PersistentClient:
    global _shared_chroma_client
    if _shared_chroma_client is not None:
        return _shared_chroma_client
    with _chroma_lock:
        if _shared_chroma_client is not None:
            return _shared_chroma_client
        persist_dir = Path(__file__).resolve().parent.parent.parent / "chroma_data"
        try:
            persist_dir.mkdir(parents=True, exist_ok=True)
            # Verify directory is actually writable
            test_file = persist_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except OSError as exc:
            raise RuntimeError(
                f"ChromaDB persistence directory {persist_dir} is not writable"
            ) from exc
        _shared_chroma_client = chromadb.PersistentClient(path=str(persist_dir))
        return _shared_chroma_client


class RAGPipeline:
    """Vector-based retrieval pipeline for document chunks.

    Uses a shared embedding model and ChromaDB client across all
    instances to avoid per-agent memory duplication.

    Thread-safe: a dedicated lock serializes all SentenceTransformer
    encode calls (the model is not thread-safe).

    Attributes:
        collection_name: Name of the ChromaDB collection.
    """

    def __init__(
        self,
        collection_name: str = "synth_documents",
        embedding_model: str = "BAAI/bge-large-en-v1.5",
    ) -> None:
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        self._client = _get_shared_chroma_client()
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._model = _get_shared_model(embedding_model)

    def _encode(self, texts: str | list[str]) -> list:
        """Thread-safe wrapper around SentenceTransformer.encode."""
        with _encode_lock:
            return self._model.encode(texts).tolist()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_chunk(self, text: str, metadata: dict[str, Any]) -> None:
        """Add a text chunk to the vector store with full metadata.

        Raises on failure so callers can implement retry/journal logic.
        """
        embedding = self._encode(text)
        self._collection.add(
            ids=[str(uuid4())],
            documents=[text],
            metadatas=[metadata],
            embeddings=[embedding],
        )

    def add_chunks_batch(self, chunks: list[dict[str, Any]]) -> None:
        """Add multiple text chunks in a single operation."""
        if not chunks:
            return
        try:
            texts = [c["text"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]
            ids = [str(uuid4()) for _ in chunks]
            embeddings = self._encode(texts)
            self._collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings,
            )
        except Exception as exc:
            logger.error("Failed to add batch of %d chunks: %s", len(chunks), exc)

    # ------------------------------------------------------------------
    # Deletion (Item 2)
    # ------------------------------------------------------------------

    def delete_by_metadata(self, **filters: str) -> int:
        """Delete all chunks matching the given metadata key=value pairs.

        Usage::

            pipeline.delete_by_metadata(document_id="abc-123")
            pipeline.delete_by_metadata(meeting_id="xyz", source_type="transcript")

        Returns:
            Number of chunks deleted.
        """
        if not filters:
            return 0
        try:
            where: dict[str, Any] = {}
            if len(filters) == 1:
                key, val = next(iter(filters.items()))
                where = {key: val}
            else:
                where = {"$and": [{k: v} for k, v in filters.items()]}

            existing = self._collection.get(where=where, include=[])
            ids = existing.get("ids", [])
            if ids:
                self._collection.delete(ids=ids)
                logger.info("Deleted %d chunks matching %s", len(ids), filters)
            return len(ids)
        except Exception as exc:
            logger.warning("delete_by_metadata failed for %s: %s", filters, exc)
            return 0

    def delete_older_than(self, cutoff: datetime, source_type: str = "transcript") -> int:
        """Delete transcript chunks older than *cutoff* (TTL retention).

        Only affects chunks with ``source_type`` matching *source_type*.
        Uses the ``start_time`` ISO timestamp stored in metadata.
        """
        try:
            hits = self._collection.get(
                where={"source_type": source_type},
                include=["metadatas"],
            )
            ids_to_delete: list[str] = []
            for chunk_id, meta in zip(hits.get("ids", []), hits.get("metadatas", [])):
                start_str = (meta or {}).get("start_time", "")
                if not start_str:
                    continue
                try:
                    ts = datetime.fromisoformat(start_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        ids_to_delete.append(chunk_id)
                except ValueError:
                    continue
            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
                logger.info("TTL: deleted %d stale %s chunks", len(ids_to_delete), source_type)
            return len(ids_to_delete)
        except Exception as exc:
            logger.warning("delete_older_than failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Search with metadata filters (Items 1, 4)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 3,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search with optional metadata filter.

        Args:
            query: The search query text.
            top_k: Number of top results to return.
            where: Optional ChromaDB ``where`` filter for metadata scoping
                (e.g. ``{"meeting_id": "abc"}`` or ``{"source_type": "document"}``).
        """
        total = self._collection.count()
        if total == 0:
            return []

        query_embedding = self._encode(query)
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, total),
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        output: list[dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            if dist > 1.0:
                continue
            output.append({"text": doc, "metadata": meta, "score": dist})
        return output

    def hybrid_search(
        self,
        query: str,
        top_k: int = 8,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search (semantic + keyword) with optional metadata filter."""
        semantic_results = self.search(query=query, top_k=top_k, where=where)

        _stopwords = {
            "what", "when", "where", "which", "that", "this", "with",
            "from", "about", "have", "been", "were", "they", "their",
            "will", "would", "could", "should", "does",
        }
        terms = [w for w in query.lower().split() if len(w) > 3 and w not in _stopwords]

        keyword_results: list[dict[str, Any]] = []
        seen_texts: set[str] = {r["text"][:100] for r in semantic_results}

        for term in terms[:3]:
            try:
                kw_where: dict[str, Any] = {"$contains": term}
                get_kwargs: dict[str, Any] = {
                    "where_document": kw_where,
                    "limit": top_k,
                    "include": ["documents", "metadatas"],
                }
                if where:
                    get_kwargs["where"] = where
                kw_hits = self._collection.get(**get_kwargs)
                docs = kw_hits.get("documents", []) or []
                metas = kw_hits.get("metadatas", []) or []
                for doc, meta in zip(docs, metas):
                    if doc and doc[:100] not in seen_texts:
                        seen_texts.add(doc[:100])
                        keyword_results.append({
                            "text": doc,
                            "metadata": meta or {},
                            "score": 0.8,
                        })
            except Exception as exc:
                logger.debug("Keyword search for '%s' failed: %s", term, exc)

        return (semantic_results + keyword_results)[:top_k]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for a text string."""
        return self._encode(text)

    def clear(self) -> None:
        """Delete the current collection and recreate it empty."""
        self._client.delete_collection(name=self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        """Return the number of chunks currently stored."""
        return self._collection.count()
