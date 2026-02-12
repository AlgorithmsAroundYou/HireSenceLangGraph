from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.models.db import Base


class ResumeFeedback(Base):
    __tablename__ = "resume_feedback"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    resume_id = Column(Integer, ForeignKey("resume_details.resume_id"), nullable=False)
    jd_id = Column(Integer, ForeignKey("job_description_details.jd_id"), nullable=False)
    user_name = Column(String, nullable=False)
    label = Column(String, nullable=False)  # e.g., good_fit, bad_fit, maybe
    comment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
