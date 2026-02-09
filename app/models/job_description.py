from sqlalchemy import Column, Integer, String, DateTime, Boolean, func

from .db import Base


class JobDescription(Base):
    __tablename__ = "job_description_details"

    jd_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    file_saved_location = Column(String, nullable=False)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    uploaded_by = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
