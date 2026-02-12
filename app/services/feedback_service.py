from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.feedback import ResumeFeedback


def add_resume_feedback(
    db: Session,
    *,
    resume_id: int,
    jd_id: int,
    user_name: str,
    label: str,
    comment: Optional[str] = None,
) -> ResumeFeedback:
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
    return (
        db.query(ResumeFeedback)
        .filter(ResumeFeedback.resume_id == resume_id)
        .order_by(ResumeFeedback.created_at.desc())
        .all()
    )


def list_feedback_by_jd(db: Session, jd_id: int) -> List[ResumeFeedback]:
    return (
        db.query(ResumeFeedback)
        .filter(ResumeFeedback.jd_id == jd_id)
        .order_by(ResumeFeedback.created_at.desc())
        .all()
    )
