from typing import Optional, List, Dict, Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


class LoginRequest(BaseModel):
    user_name: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None


class JobReviewRequest(BaseModel):
    raw_jd_content: str


class JobReviewResponse(BaseModel):
    message: str


class JobReviewResponse1(BaseModel):
    """Structured JD review response returning the parsed JSON from the LLM."""

    message: Dict[str, Any]


class JobUploadResponse(BaseModel):
    jd_id: int
    file_name: str
    file_saved_location: str


class JobDetailsResponse(BaseModel):
    jd_id: int
    file_name: str
    uploaded_by: Optional[str] = None
    title: Optional[str] = None
    parsed_summary: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    created_date: Optional[str] = None
    updated_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    last_reviewed_by: Optional[str] = None
    # resume counters
    resumes_uploaded_count: Optional[int] = None
    processed_resumes_count: Optional[int] = None
    download: str


class JobAnalyzeResponse(BaseModel):
    jd_id: int
    title: Optional[str] = None
    parsed_summary: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    last_reviewed_by: Optional[str] = None


class ResumeUploadResponse(BaseModel):
    resume_id: int
    jd_id: int
    file_name: str
    file_location: str
    uploaded_by: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ResumeSummary(BaseModel):
    resume_id: int
    jd_id: int
    file_name: str
    file_location: str
    uploaded_by: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    candidate_phone: Optional[str] = None


class ResumeListResponse(BaseModel):
    resumes: List[ResumeSummary]


class ResumeProcessOnceResponse(BaseModel):
    processed_count: int


class ResumeFeedbackRequest(BaseModel):
    label: str  # e.g., good_fit, bad_fit, maybe
    comment: Optional[str] = None


class ResumeFeedbackResponse(BaseModel):
    feedback_id: int
    resume_id: int
    jd_id: int
    user_name: str
    label: str
    comment: Optional[str] = None
    created_at: str


class ResumeFeedbackListResponse(BaseModel):
    items: List[ResumeFeedbackResponse]


class ResumeAnalysisSummary(BaseModel):
    resume_id: int
    jd_id: int
    file_name: Optional[str] = None
    match_score: Optional[float] = None
    status: Optional[str] = None
    failure_reason: Optional[str] = None


class ResumeAnalysisDimension(BaseModel):
    score: Optional[float] = None
    note: Optional[str] = None


class ResumeAnalysisDetail(BaseModel):
    resume_id: int
    jd_id: int
    file_name: Optional[str] = None
    # candidate contact extracted into resume_details
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    candidate_phone: Optional[str] = None
    # top-level analysis fields
    match_score: Optional[float] = None
    summary: Optional[str] = None
    # issues as parsed list for convenience
    issues: Optional[List[str]] = None
    # per-dimension structured view
    dimensions: Optional[Dict[str, ResumeAnalysisDimension]] = None
    # raw stored JSON from resume_analysis_details.analysis_json
    analysis_json: dict
    # expose raw DB fields for issues and audit as well
    issues_raw: Optional[str] = None
    tech_stack_match_score: Optional[float] = None
    tech_stack_match_note: Optional[str] = None
    relevant_experience_score: Optional[float] = None
    relevant_experience_note: Optional[str] = None
    responsibilities_impact_score: Optional[float] = None
    responsibilities_impact_note: Optional[str] = None
    seniority_fit_score: Optional[float] = None
    seniority_fit_note: Optional[str] = None
    domain_fit_score: Optional[float] = None
    domain_fit_note: Optional[str] = None
    red_flags_gaps_score: Optional[float] = None
    red_flags_gaps_note: Optional[str] = None
    communication_clarity_score: Optional[float] = None
    communication_clarity_note: Optional[str] = None
    soft_skills_professionalism_score: Optional[float] = None
    soft_skills_professionalism_note: Optional[str] = None
    project_complexity_score: Optional[float] = None
    project_complexity_note: Optional[str] = None
    consistency_trajectory_score: Optional[float] = None
    consistency_trajectory_note: Optional[str] = None
    processed_at: Optional[str] = None
    processed_by: Optional[str] = None
    # resume status fields
    status: Optional[str] = None
    failure_reason: Optional[str] = None


class ResumeAnalysisListResponse(BaseModel):
    items: List[ResumeAnalysisSummary]


class ResumeStatusUpdateRequest(BaseModel):
    business_status: str  # e.g., interview_scheduled, rejected, on_hold


class ResumeStatusUpdateResponse(BaseModel):
    resume_id: int
    jd_id: int
    business_status: Optional[str] = None
    status: Optional[str] = None
    failure_reason: Optional[str] = None
