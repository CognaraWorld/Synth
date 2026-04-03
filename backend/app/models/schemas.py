from datetime import datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints


NameField = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
LongTextField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=5000),
]
PromptField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20000),
]
MeetingLinkField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1024),
]


# Auth
class UserCreate(BaseModel):
    email: EmailStr
    name: NameField
    password: Optional[str] = Field(default=None, max_length=128)
    provider: Literal["email", "google"] = "email"


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
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


# Agent
class AgentCreate(BaseModel):
    name: NameField = "Synth"
    description: LongTextField
    mode: Literal["general", "custom"] = "general"


class AgentUpdate(BaseModel):
    name: Optional[NameField] = None
    description: Optional[LongTextField] = None
    system_prompt: Optional[PromptField] = None
    mode: Optional[Literal["general", "custom"]] = None


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
    doc_summary: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Meeting
class MeetingCreate(BaseModel):
    agent_id: UUID
    meeting_link: MeetingLinkField


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


# Payments
class CheckoutRequest(BaseModel):
    pack_id: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Credit pack identifier (pack_5, pack_20, pack_50)",
    )


class CheckoutResponse(BaseModel):
    checkout_url: str


# Credits
class CreditBalanceResponse(BaseModel):
    credits: int
    user_id: UUID


class CreditTransactionResponse(BaseModel):
    id: UUID
    meeting_id: Optional[UUID] = None
    amount: int
    balance_after: int
    transaction_type: str
    description: str
    stripe_session_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditTransactionListResponse(BaseModel):
    transactions: list[CreditTransactionResponse]
    total: int
    page: int
    per_page: int
