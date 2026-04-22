from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.routes.auth import get_current_user
from app.models.database import Meeting, UsageRecord, User, get_db
from app.models.schemas import UsageRecordListResponse, UsageRecordResponse, UsageSummaryResponse

router = APIRouter(prefix="/usage", tags=["usage"])


def _month_window(year: int, month: int) -> tuple[datetime, datetime]:
    # Return naive UTC datetimes. UsageRecord.recorded_at is mapped as
    # DateTime (no timezone) in SQLAlchemy — asyncpg raises DataError if
    # we compare it to tz-aware values ("can't subtract offset-naive and
    # offset-aware datetimes"). The values are still UTC by convention,
    # same as what UsageRecord.default=_utcnow produces.
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _default_month() -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    return now.year, now.month


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    year: int | None = Query(default=None, ge=2000, le=3000),
    month: int | None = Query(default=None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if year is None or month is None:
        year, month = _default_month()

    period_start, period_end = _month_window(year=year, month=month)

    result = await db.execute(
        select(
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.minutes_used), 0.0),
        ).where(
            UsageRecord.user_id == current_user.id,
            UsageRecord.recorded_at >= period_start,
            UsageRecord.recorded_at < period_end,
        )
    )
    meeting_count, total_minutes = result.one()
    total_minutes = float(total_minutes or 0.0)
    average_minutes = round(total_minutes / meeting_count, 2) if meeting_count else 0.0

    return UsageSummaryResponse(
        year=year,
        month=month,
        period_start=period_start,
        period_end=period_end,
        meeting_count=meeting_count,
        total_minutes=round(total_minutes, 2),
        average_minutes=average_minutes,
    )


@router.get("/records", response_model=UsageRecordListResponse)
async def list_usage_records(
    year: int | None = Query(default=None, ge=2000, le=3000),
    month: int | None = Query(default=None, ge=1, le=12),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if year is None or month is None:
        year, month = _default_month()

    offset = (page - 1) * per_page
    period_start, period_end = _month_window(year=year, month=month)

    count_result = await db.execute(
        select(func.count(UsageRecord.id)).where(
            UsageRecord.user_id == current_user.id,
            UsageRecord.recorded_at >= period_start,
            UsageRecord.recorded_at < period_end,
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(UsageRecord)
        .join(Meeting)
        .options(joinedload(UsageRecord.meeting))
        .where(
            UsageRecord.user_id == current_user.id,
            UsageRecord.recorded_at >= period_start,
            UsageRecord.recorded_at < period_end,
        )
        .order_by(UsageRecord.recorded_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    records = result.scalars().all()

    return UsageRecordListResponse(
        records=[
            UsageRecordResponse(
                id=record.id,
                meeting_id=record.meeting_id,
                platform=str(record.meeting.platform),
                meeting_link=record.meeting.meeting_link,
                minutes_used=record.minutes_used,
                recorded_at=record.recorded_at,
                started_at=record.meeting.started_at,
                ended_at=record.meeting.ended_at,
            )
            for record in records
        ],
        total=total,
        page=page,
        per_page=per_page,
    )
