"""Retrieval-Augmented Generation (RAG) pipeline.

Manages a ChromaDB vector store for document chunks. Embeds text using
sentence-transformers and retrieves the most relevant chunks for a
given query. Used to incorporate uploaded document knowledge into
the bot's responses.

Phase 4 implementation.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Vector-based retrieval pipeline for document chunks.

    Embeds document text into vectors and stores them in ChromaDB
    for efficient similarity search during meetings.

    Thread-safe: a dedicated lock serializes all SentenceTransformer
    encode calls (the model is not thread-safe).

    Attributes:
        collection_name: Name of the ChromaDB collection.
        embedding_model: Sentence-transformer model for embeddings.
    """

    def __init__(
        self,
        collection_name: str = "synth_documents",
        embedding_model: str = "BAAI/bge-large-en-v1.5",
    ) -> None:
        """Initialize the RAG pipeline.

        Args:
            collection_name: ChromaDB collection name for storing embeddings.
            embedding_model: Sentence-transformers model ID for generating
                text embeddings.
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        # Persist embeddings to disk so they survive restarts.
        # Use an absolute path anchored to the project root so the
        # directory is consistent regardless of the working directory.
        persist_dir = Path(__file__).resolve().parent.parent.parent / "chroma_data"
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_dir))

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
        )
        self._model = SentenceTransformer(self.embedding_model)
        self._encode_lock = threading.Lock()

    def _encode(self, texts: str | list[str]) -> list:
        """Thread-safe wrapper around SentenceTransformer.encode.

        Args:
            texts: A single string or list of strings to embed.

        Returns:
            Embedding(s) as a list (single) or list-of-lists (batch).
        """
        with self._encode_lock:
            return self._model.encode(texts).tolist()

    def add_chunk(self, text: str, metadata: dict[str, Any]) -> None:
        """Add a text chunk to the vector store.

        Args:
            text: The text content to embed and store.
            metadata: Associated metadata (e.g., document_id, filename,
                chunk_index, page_number).
        """
        try:
            embedding = self._encode(text)
            self._collection.add(
                ids=[str(uuid4())],
                documents=[text],
                metadatas=[metadata],
                embeddings=[embedding],
            )
        except Exception as exc:
            logger.error("Failed to add chunk to ChromaDB: %s", exc)

    def add_chunks_batch(self, chunks: list[dict[str, Any]]) -> None:
        """Add multiple text chunks to the vector store in a single operation.

        Args:
            chunks: List of dicts, each containing ``text`` (str) and
                ``metadata`` (dict) keys.
        """
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
            logger.error("Failed to add batch of %d chunks to ChromaDB: %s", len(chunks), exc)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Search for the most relevant document chunks.

        Filters out results with cosine distance > 1.0 (too irrelevant
        to be useful).

        Args:
            query: The search query text (typically the user's question).
            top_k: Number of top results to return.

        Returns:
            List of dictionaries containing matched text, metadata,
            and similarity scores, sorted by relevance.
        """
        if self._collection.count() == 0:
            return []

        query_embedding = self._encode(query)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
        )

        output: list[dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            if dist > 1.0:  # too distant to be relevant for cosine
                continue
            output.append({
                "text": doc,
                "metadata": meta,
                "score": dist,
            })

        return output

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for a text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        return self._encode(text)

    def clear(self) -> None:
        """Delete the current collection and recreate it empty."""
        self._client.delete_collection(name=self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
        )

    def count(self) -> int:
        """Return the number of chunks currently stored in the collection."""
        return self._collection.count()
