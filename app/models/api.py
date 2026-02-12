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


class ResumeAnalysisDetail(BaseModel):
    resume_id: int
    jd_id: int
    file_name: Optional[str] = None
    match_score: Optional[float] = None
    analysis_json: dict
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
