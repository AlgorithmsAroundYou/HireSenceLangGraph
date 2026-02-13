from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, func

from .db import Base


class Resume(Base):
    __tablename__ = "resume_details"

    resume_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    jd_id = Column(Integer, ForeignKey("job_description_details.jd_id"), nullable=False)
    file_name = Column(String, nullable=False)
    file_location = Column(String, nullable=False)

    # candidate info
    candidate_name = Column(String, nullable=True)
    candidate_email = Column(String, nullable=True)
    candidate_phone = Column(String, nullable=True)

    # AI/processing metadata
    parsed_summary = Column(String, nullable=True)
    parsed_skills = Column(String, nullable=True)
    match_score = Column(Float, nullable=True)

    # status & audit
    status = Column(String, nullable=False, default="new")
    failure_reason = Column(String, nullable=True)
    uploaded_by = Column(String, nullable=True)
    business_status = Column(String, nullable=True)  # interview_scheduled, rejected, etc.
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)


class ResumeAnalysis(Base):
    __tablename__ = "resume_analysis_details"

    analysis_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    resume_id = Column(Integer, ForeignKey("resume_details.resume_id"), nullable=False)
    jd_id = Column(Integer, ForeignKey("job_description_details.jd_id"), nullable=False)

    # Raw JSON from LLM
    analysis_json = Column(String, nullable=False)

    # Optional extracted fields for quick filtering/sorting
    match_score = Column(Float, nullable=True)
    summary = Column(String, nullable=True)
    issues = Column(String, nullable=True)

    # Per-dimension scores and notes
    tech_stack_match_score = Column(Float, nullable=True)
    tech_stack_match_note = Column(String, nullable=True)

    relevant_experience_score = Column(Float, nullable=True)
    relevant_experience_note = Column(String, nullable=True)

    responsibilities_impact_score = Column(Float, nullable=True)
    responsibilities_impact_note = Column(String, nullable=True)

    seniority_fit_score = Column(Float, nullable=True)
    seniority_fit_note = Column(String, nullable=True)

    domain_fit_score = Column(Float, nullable=True)
    domain_fit_note = Column(String, nullable=True)

    red_flags_gaps_score = Column(Float, nullable=True)
    red_flags_gaps_note = Column(String, nullable=True)

    communication_clarity_score = Column(Float, nullable=True)
    communication_clarity_note = Column(String, nullable=True)

    soft_skills_professionalism_score = Column(Float, nullable=True)
    soft_skills_professionalism_note = Column(String, nullable=True)

    project_complexity_score = Column(Float, nullable=True)
    project_complexity_note = Column(String, nullable=True)

    consistency_trajectory_score = Column(Float, nullable=True)
    consistency_trajectory_note = Column(String, nullable=True)

    # audit
    processed_at = Column(DateTime, nullable=False, server_default=func.now())
    processed_by = Column(String, nullable=True)
