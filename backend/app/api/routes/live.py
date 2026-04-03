from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.meeting.live_control import LiveSessionService, LiveSessionServiceError
from app.models.database import User, get_db
from app.models.schemas import (
    LiveControlActionResponse,
    LiveSessionResponse,
    LiveTranscriptResponse,
    OperatorInstructionCreate,
    OperatorInstructionResponse,
)

router = APIRouter(prefix="/live-sessions", tags=["live-sessions"])


def get_live_session_service(db: AsyncSession = Depends(get_db)) -> LiveSessionService:
    return LiveSessionService(db=db)


def _raise_http(exc: LiveSessionServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/", response_model=list[LiveSessionResponse])
async def list_live_sessions(
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.list_for_user(current_user)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.post(
    "/{meeting_id}/activate",
    response_model=LiveSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def activate_live_session(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.activate_for_meeting(meeting_id, current_user)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.get("/{meeting_id}", response_model=LiveSessionResponse)
async def get_live_session(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.get_for_meeting(meeting_id, current_user)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.get("/{meeting_id}/transcript", response_model=LiveTranscriptResponse)
async def get_live_transcript(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.get_transcript_snapshot(meeting_id, current_user)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.get("/{meeting_id}/instructions", response_model=list[OperatorInstructionResponse])
async def list_operator_instructions(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.list_instructions(meeting_id, current_user)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.post("/{meeting_id}/instructions", response_model=OperatorInstructionResponse)
async def submit_operator_instruction(
    meeting_id: UUID,
    payload: OperatorInstructionCreate,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.submit_instruction(meeting_id, current_user, payload.instruction)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.post("/{meeting_id}/mute", response_model=LiveControlActionResponse)
async def mute_live_session(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.set_mute_state(meeting_id, current_user, muted=True)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.post("/{meeting_id}/unmute", response_model=LiveControlActionResponse)
async def unmute_live_session(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.set_mute_state(meeting_id, current_user, muted=False)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.post("/{meeting_id}/stop-speaking", response_model=LiveControlActionResponse)
async def stop_speaking(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.request_stop_speaking(meeting_id, current_user)
    except LiveSessionServiceError as exc:
        _raise_http(exc)


@router.post("/{meeting_id}/leave", response_model=LiveControlActionResponse)
async def leave_live_session(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    service: LiveSessionService = Depends(get_live_session_service),
):
    try:
        return await service.leave_meeting(meeting_id, current_user)
    except LiveSessionServiceError as exc:
        _raise_http(exc)
