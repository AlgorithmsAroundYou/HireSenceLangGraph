from typing import List, Optional
import os

from sqlalchemy.orm import Session

from app.models.resume import Resume, ResumeAnalysis
from app.models.job_description import JobDescription
from app.models.api import ResumeUploadResponse, ResumeSummary, ResumeListResponse
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


def list_resumes_by_jd(db: Session, jd_id: int) -> ResumeListResponse:
    resumes = db.query(Resume).filter(Resume.jd_id == jd_id).all()

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


def delete_resume(db: Session, resume_id: int) -> bool:
    """Delete a resume and its related analysis and feedback, and adjust JD counters.

    Also attempts to delete the underlying resume file from disk.

    Returns True if a resume was deleted, False if not found.
    """

    resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
    if not resume:
        return False

    # Try to delete the file from disk (best-effort, errors ignored)
    if resume.file_location:
        try:
            if os.path.exists(resume.file_location):
                os.remove(resume.file_location)
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
    return True


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
