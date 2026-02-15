from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
import json
import os
import logging
from fastapi import HTTPException, status

from app.models.job_description import JobDescription
from app.models.resume import Resume, ResumeAnalysis
from app.models.api import JobUploadResponse, JobDetailsResponse, JobDeleteResponse


logger = logging.getLogger(__name__)


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


def list_job_descriptions(db: Session) -> list[dict]:
    """Return JD list entries from job_description_details table."""

    rows = (
        db.query(JobDescription)
        .filter(JobDescription.is_active.is_(True))
        .order_by(JobDescription.jd_id.desc())
        .all()
    )

    return [
        {
            "jd_id": row.jd_id,
            "title": row.title,
            "file_name": row.file_name,
        }
        for row in rows
    ]


def delete_job_description(db: Session, jd_id: int) -> JobDeleteResponse:
    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    resume_exists = db.query(Resume.resume_id).filter(Resume.jd_id == jd_id).first()
    if resume_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete JD with associated resumes",
        )

    file_path = jd.file_saved_location

    db.delete(jd)
    db.commit()

    file_deleted = False
    if file_path:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                file_deleted = True
        except Exception as exc:
            logger.warning(
                "JD deleted in DB but failed to delete file '%s' for jd_id=%s: %s",
                file_path,
                jd_id,
                exc,
            )

    return JobDeleteResponse(
        jd_id=jd_id,
        file_deleted=file_deleted,
        message="Job description deleted successfully",
    )


def get_dashboard_summary(db: Session) -> dict:
    """Return realtime dashboard summary metrics from DB."""

    jds_count = (
        db.query(func.count(JobDescription.jd_id))
        .filter(JobDescription.is_active.is_(True))
        .scalar()
        or 0
    )

    processed_resumes_count = (
        db.query(func.count(Resume.resume_id))
        .filter(Resume.status == "processed")
        .scalar()
        or 0
    )

    pending_resumes_count = (
        db.query(func.count(Resume.resume_id))
        .filter(Resume.status == "new")
        .scalar()
        or 0
    )

    unprocessed_resumes_count = (
        db.query(func.count(Resume.resume_id))
        .filter(Resume.status != "processed")
        .scalar()
        or 0
    )

    recent_events: list[tuple[datetime, dict]] = []

    latest_jds = (
        db.query(JobDescription)
        .filter(JobDescription.is_active.is_(True))
        .order_by(JobDescription.created_at.desc())
        .limit(5)
        .all()
    )
    for jd in latest_jds:
        if jd.created_at:
            recent_events.append(
                (
                    jd.created_at,
                    {
                        "activity_type": "jd_uploaded",
                        "message": f"JD uploaded: {jd.file_name}",
                        "timestamp": jd.created_at.isoformat(),
                    },
                )
            )

    latest_resumes = (
        db.query(Resume)
        .order_by(Resume.created_at.desc())
        .limit(5)
        .all()
    )
    for resume in latest_resumes:
        if resume.created_at:
            recent_events.append(
                (
                    resume.created_at,
                    {
                        "activity_type": "resume_uploaded",
                        "message": f"Resume uploaded: {resume.file_name} (JD {resume.jd_id})",
                        "timestamp": resume.created_at.isoformat(),
                    },
                )
            )

    latest_analyses = (
        db.query(ResumeAnalysis)
        .order_by(ResumeAnalysis.processed_at.desc())
        .limit(5)
        .all()
    )
    for analysis in latest_analyses:
        if analysis.processed_at:
            recent_events.append(
                (
                    analysis.processed_at,
                    {
                        "activity_type": "resume_processed",
                        "message": f"Resume analyzed: {analysis.resume_id} (JD {analysis.jd_id})",
                        "timestamp": analysis.processed_at.isoformat(),
                    },
                )
            )

    recent_events.sort(key=lambda item: item[0], reverse=True)
    recent_activity = [event for _, event in recent_events[:10]]

    return {
        "jds_count": int(jds_count),
        "unprocessed_resumes_count": int(unprocessed_resumes_count),
        "processed_resumes_count": int(processed_resumes_count),
        "pending_resumes_count": int(pending_resumes_count),
        "recent_activity": recent_activity,
    }
