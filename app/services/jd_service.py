from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.models.job_description import JobDescription
from app.models.api import JobUploadResponse, JobDetailsResponse


def create_job_description(
    db: Session,
    *,
    file_name: str,
    file_saved_location: str,
    uploaded_by: str | None,
) -> JobUploadResponse:
    jd = JobDescription(
        file_name=file_name,
        file_saved_location=file_saved_location,
        uploaded_by=uploaded_by,
        is_active=True,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)

    return JobUploadResponse(
        jd_id=jd.jd_id,
        file_name=jd.file_name,
        file_saved_location=jd.file_saved_location,
    )


def analyze_job_description(
    db: Session,
    *,
    jd_id: int,
    title: str | None,
    parsed_summary: str | None,
    reviewed_by: str,
) -> None:
    """Update JD analysis-related fields after agent processing."""

    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        return

    if title is not None:
        jd.title = title
    if parsed_summary is not None:
        jd.parsed_summary = parsed_summary

    now = datetime.utcnow()
    jd.last_reviewed_at = now
    jd.last_reviewed_by = reviewed_by
    jd.updated_at = now

    db.add(jd)
    db.commit()


def get_job_description_details(db: Session, jd_id: int) -> JobDetailsResponse | None:
    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        return None

    created_str = jd.created_at.isoformat() if jd.created_at else None
    updated_str = jd.updated_at.isoformat() if jd.updated_at else None
    last_reviewed_str = (
        jd.last_reviewed_at.isoformat() if jd.last_reviewed_at else None
    )

    return JobDetailsResponse(
        jd_id=jd.jd_id,
        file_name=jd.file_name,
        uploaded_by=jd.uploaded_by,
        title=jd.title,
        parsed_summary=jd.parsed_summary,
        status=jd.status,
        is_active=jd.is_active,
        created_date=created_str,
        updated_at=updated_str,
        last_reviewed_at=last_reviewed_str,
        last_reviewed_by=jd.last_reviewed_by,
        resumes_uploaded_count=jd.resumes_uploaded_count,
        processed_resumes_count=jd.processed_resumes_count,
        download=jd.file_saved_location,
    )
