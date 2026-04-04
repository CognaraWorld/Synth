"""Document processor for uploaded files.

Handles parsing PDF and DOCX files into raw text, chunking the text
into appropriately sized segments, embedding those chunks into the RAG
vector store, and generating a full-document summary via LLM for broad
questions that need whole-document understanding.

Phase 4 implementation.
"""

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = (
    "Summarize the following document in 300-500 words. Cover the key topics, "
    "main arguments, important data points, decisions, and conclusions. "
    "Preserve specific names, numbers, and dates. Structure the summary with "
    "clear sections if the document covers multiple topics.\n\n"
    "Document:\n{text}"
)


class ChunkEmbeddingPipeline(Protocol):
    def add_chunks_batch(self, chunks: list[dict[str, object]]) -> None:
        """Persist a batch of embedded document chunks."""


class DocumentProcessor:
    """Parses, chunks, embeds, and summarizes uploaded documents.

    Supports PDF, DOCX, and plain text file formats. Extracts text,
    splits it into semantic chunks suitable for embedding, stores the
    embeddings in the RAG pipeline's vector store, and generates a
    full-document summary for broad questions.

    Attributes:
        default_chunk_size: Default number of words per chunk.
        rag_pipeline: Optional RAG pipeline for storing embeddings.
        llm_client: Optional LLM client for generating document summaries.
    """

    def __init__(
        self,
        default_chunk_size: int = 200,
        rag_pipeline: ChunkEmbeddingPipeline | None = None,
        llm_client: object | None = None,
    ) -> None:
        """Initialize the document processor.

        Args:
            default_chunk_size: Default number of words per text chunk
                when splitting documents for embedding.
            rag_pipeline: Optional RAGPipeline instance for embedding
                storage. If ``None``, chunking and parsing still work
                but ``process_and_embed`` will skip the embedding step.
            llm_client: Optional LLM client with a ``query(context, question)``
                method for generating document summaries.
        """
        self.default_chunk_size = default_chunk_size
        self.rag_pipeline = rag_pipeline
        self.llm_client = llm_client

    @staticmethod
    def _import_optional_dependency(module_name: str, feature_name: str) -> object:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"{feature_name} processing is unavailable because the optional "
                f"dependency '{module_name}' is not installed."
            ) from exc

    def parse_pdf(self, file_path: str) -> str:
        """Extract text content from a PDF file.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            Extracted text content from all pages of the PDF.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid PDF.
            RuntimeError: If the optional PDF dependency is not installed.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        pdfplumber = self._import_optional_dependency("pdfplumber", "PDF")
        pages_text: list[str] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
        except Exception as exc:
            raise ValueError(f"Failed to parse PDF: {exc}") from exc

        return "\n".join(pages_text)

    def parse_docx(self, file_path: str) -> str:
        """Extract text content from a DOCX file.

        Args:
            file_path: Absolute path to the DOCX file.

        Returns:
            Extracted text content from all paragraphs and tables
            of the document.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid DOCX.
            RuntimeError: If the optional DOCX dependency is not installed.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"DOCX file not found: {file_path}")

        docx = self._import_optional_dependency("docx", "DOCX")
        try:
            doc = docx.Document(file_path)
        except Exception as exc:
            raise ValueError(f"Failed to parse DOCX: {exc}") from exc

        parts: list[str] = []

        # Extract paragraph text
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                parts.append(text)

        # Extract table text
        for table in doc.tables:
            for row in table.rows:
                row_text = "\t".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    parts.append(row_text)

        return "\n".join(parts)

    def parse_txt(self, file_path: str) -> str:
        """Extract text content from a plain text file.

        Args:
            file_path: Absolute path to the text file.

        Returns:
            The full text content of the file.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Text file not found: {file_path}")

        return Path(file_path).read_text(encoding="utf-8")

    def chunk_text(self, text: str, chunk_size: int = 200) -> list[str]:
        """Split text into overlapping chunks for embedding.

        Uses a word-based sliding window with ~10% overlap to create
        chunks that preserve context at boundaries.

        Args:
            text: The full text to chunk.
            chunk_size: Target number of words per chunk.

        Returns:
            List of text chunks suitable for embedding.
        """
        words = text.split()
        if not words:
            return []

        overlap = chunk_size // 10
        chunks: list[str] = []
        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)

            if end >= len(words):
                break

            start = end - overlap

        return chunks

    def generate_summary(self, text: str) -> str:
        """Generate a full-document summary via the LLM.

        Truncates the document to ~12K words (~15K tokens) to stay
        within Haiku's context window while leaving room for the
        summary prompt and response.

        Args:
            text: The full document text.

        Returns:
            A 300-500 word summary of the document, or a truncated
            excerpt if no LLM client is available.
        """
        if not text.strip():
            return ""

        # Truncate to ~12K words to fit in Haiku's context
        words = text.split()
        if len(words) > 12000:
            truncated = " ".join(words[:12000])
            truncated += "\n\n[Document truncated — original has {} words]".format(len(words))
        else:
            truncated = text

        if self.llm_client is None:
            # Fallback: return first 500 words as a basic excerpt
            excerpt_words = words[:500]
            return " ".join(excerpt_words) + (
                "\n\n[Auto-excerpt — full summary requires LLM]" if len(words) > 500 else ""
            )

        try:
            prompt = _SUMMARY_PROMPT.format(text=truncated)
            summary = self.llm_client.query(context="", question=prompt)
            return summary
        except Exception as exc:
            logger.error("Failed to generate document summary: %s", exc)
            excerpt_words = words[:500]
            return " ".join(excerpt_words) + "\n\n[Summary generation failed — showing excerpt]"

    def process_and_embed_sync(
        self, file_path: str, file_type: str
    ) -> dict[str, int | str]:
        """Synchronous version of process_and_embed.

        Suitable for running in a thread via anyio.to_thread.run_sync.

        Args:
            file_path: Absolute path to the uploaded file.
            file_type: File format identifier ("pdf", "docx", "txt").

        Returns:
            A dict with ``chunk_count`` (int) and ``summary`` (str).
        """
        return self._process_and_embed_impl(file_path, file_type)

    def _process_and_embed_impl(
        self, file_path: str, file_type: str
    ) -> dict[str, int | str]:
        """Shared implementation for sync and async process_and_embed."""
        parsers = {
            "pdf": self.parse_pdf,
            "docx": self.parse_docx,
            "txt": self.parse_txt,
        }

        file_type_lower = file_type.lower()
        if file_type_lower not in parsers:
            raise ValueError(
                f"Unsupported file type: {file_type!r}. "
                f"Supported types: {', '.join(parsers)}"
            )

        text = parsers[file_type_lower](file_path)
        chunks = self.chunk_text(text, self.default_chunk_size)
        filename = os.path.basename(file_path)

        if self.rag_pipeline is not None:
            batch = [
                {
                    "text": chunk,
                    "metadata": {
                        "source": "document",
                        "filename": filename,
                        "chunk_index": idx,
                        "file_type": file_type_lower,
                    },
                }
                for idx, chunk in enumerate(chunks)
            ]
            self.rag_pipeline.add_chunks_batch(batch)

        summary = self.generate_summary(text)

        return {"chunk_count": len(chunks), "summary": summary}

    async def process_and_embed(
        self, file_path: str, file_type: str
    ) -> dict[str, int | str]:
        """Parse a file, chunk it, embed into vector store, and generate summary.

        End-to-end pipeline: parse -> chunk -> embed -> summarize.

        Args:
            file_path: Absolute path to the uploaded file.
            file_type: File format identifier ("pdf", "docx", "txt").

        Returns:
            A dict with ``chunk_count`` (int) and ``summary`` (str).

        Raises:
            ValueError: If file_type is not supported.
        """
        return self._process_and_embed_impl(file_path, file_type)
