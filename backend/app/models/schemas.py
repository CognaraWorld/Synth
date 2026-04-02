from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


# Auth
class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: Optional[str] = None
    provider: str = "email"


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    credits: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# Agent
class AgentCreate(BaseModel):
    name: str = "Synth"
    description: str
    mode: str = "general"  # general or custom


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    mode: Optional[str] = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str
    system_prompt: str
    mode: str
    created_at: datetime

    model_config = {"from_attributes": True}


# Document
class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    parsed: bool
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# Meeting
class MeetingCreate(BaseModel):
    agent_id: UUID
    meeting_link: str


class MeetingResponse(BaseModel):
    id: UUID
    agent_id: UUID
    platform: str
    meeting_link: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MeetingDetailResponse(MeetingResponse):
    transcript: Optional[str] = None
    summary: Optional["MeetingSummaryResponse"] = None


# Summary
class MeetingSummaryResponse(BaseModel):
    id: UUID
    content: str
    key_points: Optional[str] = None
    action_items: Optional[str] = None
    decisions: Optional[str] = None
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
