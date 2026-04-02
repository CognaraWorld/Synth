from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.config import get_settings
from app.models.database import Agent, Document, User, get_db
from app.models.schemas import DocumentResponse
from app.utils.storage import build_agent_upload_path, is_managed_path

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def get_file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post(
    "/upload/{agent_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    agent_id: UUID,
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

        return document
    finally:
        await file.close()


@router.get("/{agent_id}", response_model=list[DocumentResponse])
async def list_documents(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify agent belongs to user
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

    # Delete file from disk
    if is_managed_path(Path(settings.upload_dir), document.file_path):
        file_path = Path(document.file_path)
        if file_path.exists():
            file_path.unlink()

    await db.delete(document)
    await db.commit()
