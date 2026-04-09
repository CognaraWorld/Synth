import logging
import importlib
from pathlib import Path
from uuid import UUID

import anyio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.config import get_settings
from app.models.database import Agent, Document, User, get_db, AsyncSessionLocal
from app.models.schemas import DocumentResponse
from app.utils.storage import build_agent_upload_path, is_managed_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Magic byte signatures for content-type verification.
# Prevents attackers from uploading executables disguised with safe extensions
# (OWASP A04:2021 - Insecure Design).
_MAGIC_BYTES: dict[str, bytes | None] = {
    ".pdf": b"%PDF",
    ".docx": b"PK",     # ZIP/OOXML format
    ".txt": None,        # plain text has no magic bytes
}


def get_file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _multipart_support_available() -> bool:
    """Return whether FastAPI file upload dependencies are installed correctly."""
    try:
        multipart_module = importlib.import_module("multipart")
        if not getattr(multipart_module, "__version__", None):
            return False
        multipart_helpers = importlib.import_module("multipart.multipart")
        return hasattr(multipart_helpers, "parse_options_header")
    except Exception:
        return False


# Shared RAG pipelines keyed by agent_id — persists across requests
_rag_pipelines: dict[str, object | None] = {}


def _get_rag_pipeline(agent_id: str) -> object | None:
    """Get or create a persistent RAG pipeline for an agent."""
    if agent_id not in _rag_pipelines:
        try:
            from app.context.rag import RAGPipeline

            _rag_pipelines[agent_id] = RAGPipeline(collection_name=f"agent_{agent_id}")
        except ModuleNotFoundError:
            logger.info(
                "RAG dependencies not installed — document uploads will skip embeddings for agent %s",
                agent_id,
            )
            _rag_pipelines[agent_id] = None
        except Exception as exc:
            logger.warning("RAG pipeline init failed for agent %s: %s", agent_id, exc)
            return None
    return _rag_pipelines[agent_id]


async def _process_document_background(document_id: UUID, file_path: str, ext: str, agent_id: str):
    """Background task: parse, chunk, embed, and summarize a document."""
    async with AsyncSessionLocal() as db:
        try:
            from app.context.documents import DocumentProcessor

            rag = _get_rag_pipeline(agent_id)

            llm_client = None
            try:
                from app.core.llm import LLMClient
                llm_client = LLMClient()
            except ModuleNotFoundError:
                logger.info("Anthropic SDK not installed — document summary will use excerpt fallback")
            except Exception as exc:
                logger.warning("LLM client init failed: %s", exc)

            processor = DocumentProcessor(
                rag_pipeline=rag,
                llm_client=llm_client,
            )
            # Pass scope metadata for chunk isolation (Item 1)
            processor._current_document_id = str(document_id)
            processor._current_agent_id = agent_id
            processor._current_user_id = ""  # populated by caller if needed

            # Run sync processing in a thread to avoid blocking the event loop
            result = await anyio.to_thread.run_sync(
                lambda: processor.process_and_embed_sync(file_path, ext)
            )

            document = await db.get(Document, document_id)
            if document:
                document.parsed = True
                document.chunk_count = result["chunk_count"]
                document.doc_summary = result["summary"]
                await db.commit()

            logger.info(
                "Document %s processed: %d chunks, summary %d chars",
                document_id, result["chunk_count"], len(result.get("summary", "")),
            )
        except Exception as exc:
            logger.warning("Background document processing failed for %s: %s", document_id, exc)


if _multipart_support_available():

    @router.post(
        "/upload/{agent_id}",
        response_model=DocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_document(
        agent_id: UUID,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        try:
            result = await db.execute(
                select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
            )
            agent = result.scalar_one_or_none()
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            original_filename = Path(file.filename or "").name
            ext = get_file_extension(original_filename)
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '.{ext}' not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                )

            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail="File too large. Max 50MB.")

            # Verify file content matches claimed extension via magic bytes
            expected_magic = _MAGIC_BYTES.get(f".{ext}")
            if expected_magic and not content[:8].startswith(expected_magic):
                raise HTTPException(
                    status_code=400,
                    detail=f"File content does not match .{ext} format",
                )

            display_name, file_path = build_agent_upload_path(
                Path(settings.upload_dir),
                str(agent_id),
                original_filename,
            )
            file_path.write_bytes(content)

            document = Document(
                agent_id=agent_id,
                filename=display_name,
                file_path=str(file_path),
                file_type=ext,
                file_size=len(content),
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)

            # Process document in background — doesn't block the upload response
            background_tasks.add_task(
                _process_document_background, document.id, str(file_path), ext, str(agent_id)
            )

            return document
        finally:
            await file.close()

else:

    @router.post(
        "/upload/{agent_id}",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
    async def upload_document(
        agent_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Document uploads require "python-multipart" to be installed',
        )


@router.get("/{agent_id}", response_model=list[DocumentResponse])
async def list_documents(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(Document).where(Document.agent_id == agent_id).order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .join(Agent)
        .where(Document.id == document_id, Agent.user_id == current_user.id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if is_managed_path(Path(settings.upload_dir), document.file_path):
        file_path = Path(document.file_path)
        if file_path.exists():
            file_path.unlink()

    # Remove document embeddings from ChromaDB (Item 2)
    agent_id = str(document.agent_id)
    rag = _get_rag_pipeline(agent_id)
    if rag and hasattr(rag, "delete_by_metadata"):
        rag.delete_by_metadata(document_id=str(document_id))

    await db.delete(document)
    await db.commit()
