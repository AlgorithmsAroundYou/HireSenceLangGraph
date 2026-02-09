from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func

from .db import Base


class Resume(Base):
    __tablename__ = "resume_details"

    resume_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    jd_id = Column(Integer, ForeignKey("job_description_details.jd_id"), nullable=False)
    file_name = Column(String, nullable=False)
    file_location = Column(String, nullable=False)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    uploaded_by = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
