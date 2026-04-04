from datetime import datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.utils.report_data import build_embedded_summary_payload, deserialize_summary_items


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
PersonaField = Literal["general", "strategist", "analyst", "challenger", "facilitator"]


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
    mode: Literal["general"] = "general"
    persona_id: PersonaField = "general"
    voice: VoiceField = "female"
    response_mode: ResponseModeField = "name_only"


class AgentUpdate(BaseModel):
    name: Optional[NameField] = None
    description: Optional[LongTextField] = None
    system_prompt: Optional[PromptField] = None
    mode: Optional[Literal["general"]] = None
    persona_id: Optional[PersonaField] = None
    voice: Optional[VoiceField] = None
    response_mode: Optional[ResponseModeField] = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str
    system_prompt: str
    mode: str
    persona_id: str
    voice: str
    response_mode: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BotProfileUpsert(BaseModel):
    name: NameField = "Synth"
    description: LongTextField
    mode: Literal["general"] = "general"
    persona_id: PersonaField = "general"
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
    key_points: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    email_delivery_status: str = "pending"
    email_delivered_at: Optional[datetime] = None
    has_pdf: bool = False
    has_docx: bool = False
    pdf_download_path: Optional[str] = None
    docx_download_path: Optional[str] = None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _sanitize_embedded_exports(cls, value: object) -> object:
        if value is None or isinstance(value, dict):
            return value
        return build_embedded_summary_payload(value)

    @field_validator("key_points", "action_items", "decisions", mode="before")
    @classmethod
    def _parse_list_fields(cls, value: object) -> list[str]:
        return deserialize_summary_items(value)

    model_config = {"from_attributes": True}


class MeetingOverrideUpsert(BaseModel):
    description: Optional[LongTextField] = None
    mode: Optional[Literal["general"]] = None
    persona_id: Optional[PersonaField] = None
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
                self.persona_id,
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
    persona_id: Optional[str] = None
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


class ReportListItemResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    platform: str
    meeting_link: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    content_preview: str
    action_items: list[str] = Field(default_factory=list)
    email_delivery_status: str
    email_delivered_at: Optional[datetime] = None
    has_pdf: bool
    has_docx: bool
    created_at: datetime


class ReportListResponse(BaseModel):
    reports: list[ReportListItemResponse]
    total: int
    page: int
    per_page: int


class ReportDetailResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    platform: str
    meeting_link: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    content: str
    key_points: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    email_delivery_status: str
    email_delivered_at: Optional[datetime] = None
    has_pdf: bool
    has_docx: bool
    pdf_download_path: Optional[str] = None
    docx_download_path: Optional[str] = None
    created_at: datetime


class UsageRecordResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    platform: str
    meeting_link: str
    minutes_used: float
    recorded_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class UsageRecordListResponse(BaseModel):
    records: list[UsageRecordResponse]
    total: int
    page: int
    per_page: int


class UsageSummaryResponse(BaseModel):
    year: int
    month: int
    period_start: datetime
    period_end: datetime
    meeting_count: int
    total_minutes: float
    average_minutes: float


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
