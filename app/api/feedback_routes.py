from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.models.user import User
from app.models.api import (
    ResumeFeedbackRequest,
    ResumeFeedbackResponse,
    ResumeFeedbackListResponse,
)
from app.services.auth_service import get_db, get_current_user
from app.services.resume_service import (
    add_resume_feedback,
    list_feedback_by_resume,
    list_feedback_by_jd,
)


router = APIRouter()


@router.post("/resumes/{resume_id}/feedback", response_model=ResumeFeedbackResponse)
async def give_resume_feedback(
    resume_id: int,
    jd_id: int,
    payload: ResumeFeedbackRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit feedback on a resume for a specific JD (good_fit / bad_fit / maybe + optional comment)."""

    from app.models.resume import Resume as ResumeModel

    resume = db.query(ResumeModel).filter(ResumeModel.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )

    if resume.jd_id != jd_id:
        raise HTTPException(
            status_code=400,
            detail="Provided jd_id does not match resume's jd_id",
        )

    fb = add_resume_feedback(
        db,
        resume_id=resume_id,
        jd_id=jd_id,
        user_name=user.user_name,
        label=payload.label,
        comment=payload.comment,
    )

    return ResumeFeedbackResponse(
        feedback_id=fb.feedback_id,
        resume_id=fb.resume_id,
        jd_id=fb.jd_id,
        user_name=fb.user_name,
        label=fb.label,
        comment=fb.comment,
        created_at=fb.created_at.isoformat() if fb.created_at else None,
    )


@router.get("/resumes/{resume_id}/feedback", response_model=ResumeFeedbackListResponse)
async def get_feedback_for_resume(
    resume_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all feedback entries for a given resume_id."""

    from app.models.resume import Resume as ResumeModel

    resume = db.query(ResumeModel).filter(ResumeModel.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )

    feedback_rows = list_feedback_by_resume(db, resume_id)
    items = [
        ResumeFeedbackResponse(
            feedback_id=row.feedback_id,
            resume_id=row.resume_id,
            jd_id=row.jd_id,
            user_name=row.user_name,
            label=row.label,
            comment=row.comment,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in feedback_rows
    ]
    return ResumeFeedbackListResponse(items=items)


@router.get("/jd/{jd_id}/feedback", response_model=ResumeFeedbackListResponse)
async def get_feedback_for_jd(
    jd_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all feedback entries across resumes for a given jd_id."""

    from app.models.job_description import JobDescription as JDModel

    jd = db.query(JDModel).filter(JDModel.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=404,
            detail="Job description not found",
        )

    feedback_rows = list_feedback_by_jd(db, jd_id)
    items = [
        ResumeFeedbackResponse(
            feedback_id=row.feedback_id,
            resume_id=row.resume_id,
            jd_id=row.jd_id,
            user_name=row.user_name,
            label=row.label,
            comment=row.comment,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in feedback_rows
    ]
    return ResumeFeedbackListResponse(items=items)
