from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.routes.auth import get_current_user
from app.config import get_settings
from app.meeting.reporting import (
    build_report_preview,
    deserialize_summary_items,
    finalize_meeting_artifacts,
    resolve_report_export_path,
)
from app.models.database import Meeting, MeetingSummary, User, get_db
from app.models.schemas import ReportDetailResponse, ReportListItemResponse, ReportListResponse

router = APIRouter(prefix="/reports", tags=["reports"])
settings = get_settings()


def _build_report_list_item(report: MeetingSummary) -> ReportListItemResponse:
    meeting = report.meeting
    return ReportListItemResponse(
        id=report.id,
        meeting_id=meeting.id,
        platform=str(meeting.platform),
        meeting_link=meeting.meeting_link,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        duration_minutes=meeting.duration_minutes,
        content_preview=build_report_preview(report.content),
        action_items=deserialize_summary_items(report.action_items),
        email_delivery_status=report.email_delivery_status,
        email_delivered_at=report.email_delivered_at,
        has_pdf=bool(report.pdf_path),
        has_docx=bool(report.docx_path),
        created_at=report.created_at,
    )


def _build_report_detail(report: MeetingSummary) -> ReportDetailResponse:
    meeting = report.meeting
    return ReportDetailResponse(
        id=report.id,
        meeting_id=meeting.id,
        platform=str(meeting.platform),
        meeting_link=meeting.meeting_link,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        duration_minutes=meeting.duration_minutes,
        content=report.content,
        key_points=deserialize_summary_items(report.key_points),
        action_items=deserialize_summary_items(report.action_items),
        decisions=deserialize_summary_items(report.decisions),
        email_delivery_status=report.email_delivery_status,
        email_delivered_at=report.email_delivered_at,
        has_pdf=bool(report.pdf_path),
        has_docx=bool(report.docx_path),
        pdf_download_path=(
            f"/api/reports/{report.id}/download/pdf" if report.pdf_path else None
        ),
        docx_download_path=(
            f"/api/reports/{report.id}/download/docx" if report.docx_path else None
        ),
        created_at=report.created_at,
    )


async def _get_report_for_user(
    report_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> MeetingSummary:
    result = await db.execute(
        select(MeetingSummary)
        .join(Meeting)
        .options(joinedload(MeetingSummary.meeting))
        .where(MeetingSummary.id == report_id, Meeting.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page

    count_result = await db.execute(
        select(func.count(MeetingSummary.id))
        .select_from(MeetingSummary)
        .join(Meeting)
        .where(Meeting.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(MeetingSummary)
        .join(Meeting)
        .options(joinedload(MeetingSummary.meeting))
        .where(Meeting.user_id == current_user.id)
        .order_by(MeetingSummary.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    reports = result.scalars().all()

    return ReportListResponse(
        reports=[_build_report_list_item(report) for report in reports],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await _get_report_for_user(report_id=report_id, current_user=current_user, db=db)
    return _build_report_detail(report)


@router.post("/meetings/{meeting_id}/generate", response_model=ReportDetailResponse)
async def generate_report_for_meeting(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.summary))
        .where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    if meeting.status not in {"ended", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reports can only be generated after a meeting has ended",
        )

    report, _ = await finalize_meeting_artifacts(
        db=db,
        meeting=meeting,
        current_user=current_user,
        settings=settings,
    )
    await db.commit()
    await db.refresh(report)
    return _build_report_detail(report)


@router.get("/{report_id}/download/{file_format}")
async def download_report_export(
    report_id: UUID,
    file_format: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await _get_report_for_user(report_id=report_id, current_user=current_user, db=db)

    if file_format not in {"pdf", "docx"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported report format")

    raw_path = report.pdf_path if file_format == "pdf" else report.docx_path
    if not raw_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report export not found")

    try:
        export_path = resolve_report_export_path(raw_path=raw_path, summary_dir=settings.summary_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if not export_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report export not found")

    media_type = (
        "application/pdf"
        if file_format == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=export_path,
        media_type=media_type,
        filename=f"meeting-report-{report.meeting_id}.{file_format}",
    )
