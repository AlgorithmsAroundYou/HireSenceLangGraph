from typing import List, Optional
import os
import shutil

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resume import Resume, ResumeAnalysis
from app.models.job_description import JobDescription
from app.models.api import (
    ResumeUploadResponse,
    ResumeSummary,
    ResumeListResponse,
    ResumeDeleteResponse,
    ResumeMoveResponse,
)
from app.models.feedback import ResumeFeedback


def create_resume(
    db: Session,
    *,
    jd_id: int,
    file_name: str,
    file_location: str,
    uploaded_by: str | None,
) -> ResumeUploadResponse:
    resume = Resume(
        jd_id=jd_id,
        file_name=file_name or "uploaded_resume",
        file_location=file_location,
        uploaded_by=uploaded_by,
        is_active=True,
    )
    db.add(resume)

    # Increment resume counter on related JD
    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if jd is not None:
        current_total = jd.resumes_uploaded_count or 0
        jd.resumes_uploaded_count = current_total + 1
        db.add(jd)

    db.commit()
    db.refresh(resume)

    created_str = resume.created_at.isoformat() if resume.created_at else None
    updated_str = resume.updated_at.isoformat() if resume.updated_at else None

    return ResumeUploadResponse(
        resume_id=resume.resume_id,
        jd_id=resume.jd_id,
        file_name=resume.file_name,
        file_location=resume.file_location,
        uploaded_by=resume.uploaded_by,
        status=resume.status,
        is_active=resume.is_active,
        created_at=created_str,
        updated_at=updated_str,
    )


def list_resumes_by_jd(db: Session, jd_id: int | None = None) -> ResumeListResponse:
    query = db.query(Resume)
    if jd_id is not None:
        query = query.filter(Resume.jd_id == jd_id)

    resumes = query.all()

    summaries: List[ResumeSummary] = []
    for r in resumes:
        created_str = r.created_at.isoformat() if r.created_at else None
        summaries.append(
            ResumeSummary(
                resume_id=r.resume_id,
                jd_id=r.jd_id,
                file_name=r.file_name,
                file_location=r.file_location,
                uploaded_by=r.uploaded_by,
                status=r.status,
                is_active=r.is_active,
                created_at=created_str,
                candidate_name=r.candidate_name,
                candidate_email=r.candidate_email,
                candidate_phone=r.candidate_phone,
            )
        )

    return ResumeListResponse(resumes=summaries)


def get_resume_analysis_summaries_by_jd(
    db: Session, jd_id: int
) -> List[tuple[Resume, Optional[ResumeAnalysis]]]:
    """Return list of (Resume, ResumeAnalysis|None) for a given jd_id, for API summaries."""

    query = (
        db.query(Resume, ResumeAnalysis)
        .outerjoin(
            ResumeAnalysis,
            (ResumeAnalysis.resume_id == Resume.resume_id)
            & (ResumeAnalysis.jd_id == Resume.jd_id),
        )
        .filter(Resume.jd_id == jd_id)
    )
    return query.all()


def get_resume_analysis_detail(
    db: Session, resume_id: int
) -> Optional[tuple[Resume, Optional[ResumeAnalysis]]]:
    """Return (Resume, ResumeAnalysis|None) for a single resume_id."""

    return (
        db.query(Resume, ResumeAnalysis)
        .outerjoin(
            ResumeAnalysis,
            (ResumeAnalysis.resume_id == Resume.resume_id)
            & (ResumeAnalysis.jd_id == Resume.jd_id),
        )
        .filter(Resume.resume_id == resume_id)
        .first()
    )


def add_resume_feedback(
    db: Session,
    *,
    resume_id: int,
    jd_id: int,
    user_name: str,
    label: str,
    comment: str | None = None,
) -> ResumeFeedback:
    """Create a new feedback entry for a resume."""

    feedback = ResumeFeedback(
        resume_id=resume_id,
        jd_id=jd_id,
        user_name=user_name,
        label=label,
        comment=comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_feedback_by_resume(db: Session, resume_id: int) -> List[ResumeFeedback]:
    """Return all feedback rows for a given resume_id."""

    return (
        db.query(ResumeFeedback)
        .filter(ResumeFeedback.resume_id == resume_id)
        .order_by(ResumeFeedback.created_at.asc())
        .all()
    )


def list_feedback_by_jd(db: Session, jd_id: int) -> List[ResumeFeedback]:
    """Return all feedback rows across resumes for a given jd_id."""

    return (
        db.query(ResumeFeedback)
        .filter(ResumeFeedback.jd_id == jd_id)
        .order_by(ResumeFeedback.created_at.asc())
        .all()
    )


def delete_resume(db: Session, resume_id: int) -> ResumeDeleteResponse | None:
    """Delete a resume and its related analysis and feedback, and adjust JD counters.

    Also attempts to delete the underlying resume file from disk.

    Returns delete details if found, else None.
    """

    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        return None

    # Try to delete the file from disk (best-effort, errors ignored)
    file_deleted = False
    if resume.file_location:
        try:
            if os.path.exists(resume.file_location):
                os.remove(resume.file_location)
                file_deleted = True
        except Exception:
            # Intentionally ignore file deletion errors to avoid blocking DB cleanup
            pass

    jd = db.query(JobDescription).filter(JobDescription.jd_id == resume.jd_id).first()

    # Delete related analysis records
    db.query(ResumeAnalysis).filter(ResumeAnalysis.resume_id == resume_id).delete()

    # Delete related feedback records
    db.query(ResumeFeedback).filter(ResumeFeedback.resume_id == resume_id).delete()

    # Delete the resume itself
    db.delete(resume)

    # Adjust JD counters if we found a JD row
    if jd is not None:
        if jd.resumes_uploaded_count is not None and jd.resumes_uploaded_count > 0:
            jd.resumes_uploaded_count -= 1
        if (
            resume.status == "processed"
            and jd.processed_resumes_count is not None
            and jd.processed_resumes_count > 0
        ):
            jd.processed_resumes_count -= 1

    db.commit()
    return ResumeDeleteResponse(
        resume_id=resume_id,
        file_deleted=file_deleted,
        message="Resume deleted successfully",
    )


def update_resume_business_status(
    db: Session,
    *,
    resume_id: int,
    business_status: str,
) -> Optional[Resume]:
    """Update the business_status (human pipeline status) for a resume."""

    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        return None

    resume.business_status = business_status
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def _move_resume_file_to_target_jd(current_file_location: str | None, target_jd_id: int) -> str | None:
    if not current_file_location:
        return current_file_location

    if not os.path.exists(current_file_location):
        return current_file_location

    target_dir = os.path.join(settings.upload_dir_resume, str(target_jd_id))
    os.makedirs(target_dir, exist_ok=True)

    file_name = os.path.basename(current_file_location)
    target_path = os.path.join(target_dir, file_name)

    if os.path.abspath(target_path) == os.path.abspath(current_file_location):
        return current_file_location

    base, ext = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(target_path):
        target_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
        counter += 1

    shutil.move(current_file_location, target_path)
    return target_path


def _decrement_source_jd_counters(source_jd: JobDescription | None, old_status: str | None) -> None:
    if source_jd is None:
        return

    if source_jd.resumes_uploaded_count and source_jd.resumes_uploaded_count > 0:
        source_jd.resumes_uploaded_count -= 1

    if (
        old_status == "processed"
        and source_jd.processed_resumes_count
        and source_jd.processed_resumes_count > 0
    ):
        source_jd.processed_resumes_count -= 1


def move_resume_to_jd(
    db: Session,
    *,
    resume_id: int,
    target_jd_id: int,
) -> ResumeMoveResponse:
    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    target_jd = db.query(JobDescription).filter(JobDescription.jd_id == target_jd_id).first()
    if not target_jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target job description not found",
        )

    source_jd_id = resume.jd_id
    if source_jd_id == target_jd_id:
        return ResumeMoveResponse(
            resume_id=resume.resume_id,
            previous_jd_id=source_jd_id,
            jd_id=target_jd_id,
            file_location=resume.file_location,
            status=resume.status,
            message="Resume is already linked to this JD",
        )

    source_jd = db.query(JobDescription).filter(JobDescription.jd_id == source_jd_id).first()

    old_status = resume.status

    # Move physical file to target JD folder if present
    resume.file_location = _move_resume_file_to_target_jd(resume.file_location, target_jd_id)

    # Re-link resume to target JD
    resume.jd_id = target_jd_id

    # Reset status so it can be evaluated against new JD context
    resume.status = "new"
    resume.failure_reason = None

    # Remove old analysis records because they belong to old JD context
    db.query(ResumeAnalysis).filter(ResumeAnalysis.resume_id == resume.resume_id).delete()

    # Update JD counters
    if source_jd is not None:
        _decrement_source_jd_counters(source_jd, old_status)
        db.add(source_jd)

    target_jd.resumes_uploaded_count = (target_jd.resumes_uploaded_count or 0) + 1
    db.add(target_jd)

    db.add(resume)
    db.commit()
    db.refresh(resume)

    return ResumeMoveResponse(
        resume_id=resume.resume_id,
        previous_jd_id=source_jd_id,
        jd_id=resume.jd_id,
        file_location=resume.file_location,
        status=resume.status,
        message="Resume moved to target JD successfully",
    )
