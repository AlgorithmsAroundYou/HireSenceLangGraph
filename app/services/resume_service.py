from typing import List

from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.models.job_description import JobDescription
from app.models.api import ResumeUploadResponse, ResumeSummary, ResumeListResponse


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
