"""Document processor for uploaded files.

Handles parsing PDF and DOCX files into raw text, chunking the text
into appropriately sized segments, and embedding those chunks into
the RAG vector store for retrieval during meetings.

Phase 4 implementation.
"""

from __future__ import annotations

import os
from pathlib import Path

import docx
import pdfplumber

from app.context.rag import RAGPipeline


class DocumentProcessor:
    """Parses, chunks, and embeds uploaded documents.

    Supports PDF, DOCX, and plain text file formats. Extracts text,
    splits it into semantic chunks suitable for embedding, and stores
    the embeddings in the RAG pipeline's vector store.

    Attributes:
        default_chunk_size: Default number of words per chunk.
        rag_pipeline: Optional RAG pipeline for storing embeddings.
    """

    def __init__(
        self,
        default_chunk_size: int = 200,
        rag_pipeline: RAGPipeline | None = None,
    ) -> None:
        """Initialize the document processor.

        Args:
            default_chunk_size: Default number of words per text chunk
                when splitting documents for embedding.
            rag_pipeline: Optional RAGPipeline instance for embedding
                storage. If ``None``, chunking and parsing still work
                but ``process_and_embed`` will skip the embedding step.
        """
        self.default_chunk_size = default_chunk_size
        self.rag_pipeline = rag_pipeline

    def parse_pdf(self, file_path: str) -> str:
        """Extract text content from a PDF file.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            Extracted text content from all pages of the PDF.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid PDF.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

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
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"DOCX file not found: {file_path}")

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

    async def process_and_embed(self, file_path: str, file_type: str) -> None:
        """Parse a file, chunk it, and embed all chunks into the vector store.

        End-to-end pipeline: parse -> chunk -> embed -> store.

        Args:
            file_path: Absolute path to the uploaded file.
            file_type: File format identifier ("pdf", "docx", "txt").

        Raises:
            ValueError: If file_type is not supported.
        """
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
                        "filename": filename,
                        "chunk_index": idx,
                        "file_type": file_type_lower,
                    },
                }
                for idx, chunk in enumerate(chunks)
            ]
            self.rag_pipeline.add_chunks_batch(batch)
