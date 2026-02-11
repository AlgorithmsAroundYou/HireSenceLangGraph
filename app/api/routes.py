from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
import os
from typing import Optional, List

from app.agents.agent import build_agent
from app.models.db import SessionLocal
from app.models.user import User
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.prompts.review_job_description_prompt import (
    REVIEW_JOB_DESCRIPTION_SYSTEM_PROMPT,
)
import markdown


router = APIRouter()
agent = build_agent()


DEMO_AUTH_TOKEN = "demo-token"  # simple placeholder; replace with real auth later


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

class JobReviewResponse1(BaseModel):
    message: str

class JobReviewResponse(BaseModel):
    updated_jd_content: str
    score: str
    suggestions: str


class JobUploadResponse(BaseModel):
    jd_id: int
    file_name: str
    file_saved_location: str


class JobDetailsResponse(BaseModel):
    jd_id: int
    file_name: str
    uploaded_by: Optional[str] = None
    created_date: str
    download: str


class ResumeUploadResponse(BaseModel):
    resume_id: int
    jd_id: int
    file_name: str
    file_location: str


class ResumeSummary(BaseModel):
    resume_id: int
    jd_id: int
    file_name: str
    file_location: str
    uploaded_by: Optional[str] = None
    created_date: Optional[str] = None


class ResumeListResponse(BaseModel):
    resumes: List[ResumeSummary]


UPLOAD_DIR = "uploaded_jds"
ALLOWED_EXTENSIONS = {"txt", "pdf", "doc", "docx"}


def save_upload_file(upload_file: UploadFile, destination_dir: str) -> str:
    """Save an uploaded file to a destination directory and return the full path.

    This helper is reusable for other services.
    """

    os.makedirs(destination_dir, exist_ok=True)

    # Basic extension validation
    _, ext = os.path.splitext(upload_file.filename or "")
    ext = ext.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{ext}",
        )

    safe_name = upload_file.filename or "uploaded_file"
    dest_path = os.path.join(destination_dir, safe_name)

    with open(dest_path, "wb") as out_file:
        out_file.write(upload_file.file.read())

    return dest_path


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(lambda: None)):
    """Very simple token check placeholder.

    In production replace this with proper session/JWT handling.
    """
    # In FastAPI you'd normally get the token from headers or cookies.
    # Here we expect an `Authorization: Bearer <token>` header; FastAPI
    # can't grab it via lambda, so this is a stub hook for future work.
    # For now, callers should send token via `Authorization` header and
    # you can wire a real dependency later.
    # This implementation always requires DEMO_AUTH_TOKEN when wired.
    if token != DEMO_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return {"user_name": "demo"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = agent.invoke({"messages": [HumanMessage(content=request.message)]})
    last_message = result["messages"][-1]
    return ChatResponse(response=last_message.content)


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.user_name == request.user_name).first()

    if user is None or user.password != request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    # For now, return a static demo token. Replace with real token/session later.
    return LoginResponse(success=True, message="Login successful", token=DEMO_AUTH_TOKEN)


@router.post("/jd/builder", response_model=JobReviewResponse1)
async def review_job_description(request: JobReviewRequest):
    messages = [
        SystemMessage(content=REVIEW_JOB_DESCRIPTION_SYSTEM_PROMPT),
        HumanMessage(content=request.raw_jd_content),
    ]

    result = agent.invoke({"messages": messages})
    last_message = result["messages"][-1]
    html_output = markdown.markdown(last_message.content)
    return JobReviewResponse1(message=html_output)

    # The model is instructed to return JSON; parse defensively
    # import json

    # try:
    #     payload = json.loads(last_message.content)
    # except json.JSONDecodeError:
    #     # Fallback: wrap raw content if model didn't follow instructions
    #     return JobReviewResponse(
    #         updated_jd_content=last_message.content,
    #         score="",
    #         suggestions="Model did not return valid JSON; please try again.",
    #     )

    # return JobReviewResponse(
    #     updated_jd_content=payload.get("updated_jd_content", ""),
    #     score=str(payload.get("score", "")),
    #     suggestions=payload.get("suggestions", ""),
    # )


@router.post("/jd/upload", response_model=JobUploadResponse)
async def upload_job_description(
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """Upload a JD file, save it locally, and store metadata in DB."""

    try:
        saved_path = save_upload_file(file, UPLOAD_DIR)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {exc}",
        )

    jd = JobDescription(
        file_name=file.filename or "uploaded_file",
        file_saved_location=saved_path,
        uploaded_by=uploaded_by,
        is_active=True,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)

    return JobUploadResponse(
        jd_id=jd.jd_id,
        file_name=jd.file_name,
        file_saved_location=jd.file_saved_location,
    )


@router.get("/jd/{jd_id}", response_model=JobDetailsResponse)
async def get_job_description_details(jd_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    # Format created_date as ISO string if not None
    created_str = jd.created_date.isoformat() if jd.created_date else ""

    return JobDetailsResponse(
        jd_id=jd.jd_id,
        file_name=jd.file_name,
        uploaded_by=jd.uploaded_by,
        created_date=created_str,
        download=jd.file_saved_location,
    )


@router.post("/resumes/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    jd_id: int,
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """Upload a resume file linked to a JD and persist metadata.

    - jd_id is mandatory and must reference an existing job_description_details row.
    - uploaded_by can be passed explicitly (e.g., current username).
    """

    # Ensure JD exists
    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid jd_id: job description does not exist",
        )

    try:
        saved_path = save_upload_file(file, UPLOAD_DIR)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {exc}",
        )

    resume = Resume(
        jd_id=jd_id,
        file_name=file.filename or "uploaded_resume",
        file_location=saved_path,
        uploaded_by=uploaded_by,
        is_active=True,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    return ResumeUploadResponse(
        resume_id=resume.resume_id,
        jd_id=resume.jd_id,
        file_name=resume.file_name,
        file_location=resume.file_location,
    )


@router.get("/resumes", response_model=ResumeListResponse)
async def list_resumes_by_jd(jd_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """Return list of resumes for a given jd_id with file locations."""
    resumes = db.query(Resume).filter(Resume.jd_id == jd_id).all()

    summaries: List[ResumeSummary] = []
    for r in resumes:
        created_str = r.created_date.isoformat() if r.created_date else ""
        summaries.append(
            ResumeSummary(
                resume_id=r.resume_id,
                jd_id=r.jd_id,
                file_name=r.file_name,
                file_location=r.file_location,
                uploaded_by=r.uploaded_by,
                created_date=created_str,
            )
        )

    return ResumeListResponse(resumes=summaries)
