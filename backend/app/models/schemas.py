from datetime import datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator


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
VoiceField = Literal["female", "male"]
ResponseModeField = Literal["name_only", "proactive"]


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
    voice: VoiceField = "female"
    response_mode: ResponseModeField = "name_only"


class AgentUpdate(BaseModel):
    name: Optional[NameField] = None
    description: Optional[LongTextField] = None
    system_prompt: Optional[PromptField] = None
    mode: Optional[Literal["general", "custom"]] = None
    voice: Optional[VoiceField] = None
    response_mode: Optional[ResponseModeField] = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str
    system_prompt: str
    mode: str
    voice: str
    response_mode: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BotProfileUpsert(BaseModel):
    name: NameField = "Synth"
    description: LongTextField
    mode: Literal["general", "custom"] = "general"
    voice: VoiceField = "female"
    response_mode: ResponseModeField = "name_only"
    system_prompt: Optional[PromptField] = None


class BotProfileResponse(AgentResponse):
    pass


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
    agent_id: Optional[UUID] = None
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
    override: Optional["MeetingOverrideResponse"] = None


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


class MeetingOverrideUpsert(BaseModel):
    description: Optional[LongTextField] = None
    mode: Optional[Literal["general", "custom"]] = None
    system_prompt: Optional[PromptField] = None
    voice: Optional[VoiceField] = None
    response_mode: Optional[ResponseModeField] = None

    @model_validator(mode="after")
    def validate_non_empty(self) -> "MeetingOverrideUpsert":
        if not any(
            value is not None
            for value in (
                self.description,
                self.mode,
                self.system_prompt,
                self.voice,
                self.response_mode,
            )
        ):
            raise ValueError("At least one override field must be provided.")
        return self


class MeetingOverrideResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    description: Optional[str] = None
    mode: Optional[str] = None
    system_prompt: Optional[str] = None
    voice: Optional[str] = None
    response_mode: Optional[str] = None
    created_at: datetime
    updated_at: datetime

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


# Live sessions
class LiveSessionResponse(BaseModel):
    meeting_id: UUID
    meeting_status: str
    platform: str
    meeting_link: str
    engine_session_id: Optional[str] = None
    provider_bot_id: Optional[str] = None
    session_status: str
    is_active: bool
    is_muted: bool
    stop_requested: bool
    websocket_path: Optional[str] = None
    transcript_length: int = 0
    last_instruction_at: Optional[datetime] = None
    last_transcript_at: Optional[datetime] = None
    provider_last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime] = None


class LiveTranscriptResponse(BaseModel):
    meeting_id: UUID
    engine_session_id: Optional[str] = None
    session_status: str
    source: str
    transcript: str
    updated_at: datetime


class OperatorInstructionCreate(BaseModel):
    instruction: LongTextField


class OperatorInstructionResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    live_session_id: Optional[UUID] = None
    instruction: str
    delivery_status: str
    delivery_error: Optional[str] = None
    created_at: datetime
    applied_at: Optional[datetime] = None


class LiveControlActionResponse(BaseModel):
    meeting_id: UUID
    session_status: str
    provider_status: str
    detail: Optional[str] = None
    is_muted: Optional[bool] = None
    stop_requested: Optional[bool] = None
    ended_at: Optional[datetime] = None
