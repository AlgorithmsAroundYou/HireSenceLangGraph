from sqlalchemy import Column, Integer, String, DateTime, Boolean, func

from .db import Base


class JobDescription(Base):
    __tablename__ = "job_description_details"

    jd_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    file_saved_location = Column(String, nullable=False)

    # JD metadata
    title = Column(String, nullable=True)

    # AI/processing metadata
    parsed_summary = Column(String, nullable=True)
    last_reviewed_at = Column(DateTime, nullable=True)
    last_reviewed_by = Column(String, nullable=True)

    # resume counters
    resumes_uploaded_count = Column(Integer, nullable=False, default=0, server_default="0")
    processed_resumes_count = Column(Integer, nullable=False, default=0, server_default="0")

    # status & audit
    status = Column(String, nullable=False, default="active")
    uploaded_by = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)
