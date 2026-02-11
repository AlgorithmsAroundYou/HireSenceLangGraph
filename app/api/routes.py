from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Optional, List
import json

from app.agents.agent import build_agent
from app.models.user import User
from app.models.job_description import JobDescription
from app.prompts.review_job_description_prompt import (
    REVIEW_JOB_DESCRIPTION_SYSTEM_PROMPT,
)
from app.models.api import (
    ChatRequest,
    ChatResponse,
    LoginRequest,
    LoginResponse,
    JobReviewResponse1,
    JobReviewResponse,
    JobUploadResponse,
    JobDetailsResponse,
    JobAnalyzeResponse,
    ResumeUploadResponse,
    ResumeSummary,
    ResumeListResponse,
    ResumeProcessOnceResponse,
)
from app.services.jd_service import (
    create_job_description,
    get_job_description_details as get_jd_details_svc,
    analyze_job_description,
)
from app.services.resume_service import (
    create_resume,
    list_resumes_by_jd as list_resumes_svc,
)
from app.services.auth_service import get_db, create_access_token, get_current_user
from app.services.file_service import save_upload_file
from app.core.config import settings
from app.validations.jd_validations import validate_jd_upload
from app.services.resume_processing_service import run_once as run_resume_process_once


router = APIRouter()
agent = build_agent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: User = Depends(get_current_user)):
    result = agent.invoke({"messages": [HumanMessage(content=request.message)]})
    last_message = result["messages"][-1]
    return ChatResponse(response=last_message.content)


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    from app.models.user import User as UserModel

    user = db.query(UserModel).filter(UserModel.user_name == request.user_name).first()

    # NOTE: currently comparing plain text password to password_hash placeholder.
    # Replace this with proper hashing & verification later.
    if user is None or user.password_hash != request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    access_token = create_access_token(data={"sub": user.user_name})

    return LoginResponse(
        success=True,
        message="Login successful",
        token=access_token,
    )


@router.post("/jd/builder", response_model=JobReviewResponse1)
async def review_job_description(
    raw_jd_content: str = Body(..., media_type="text/plain"),
    user: User = Depends(get_current_user),
):
    """Review a job description from raw text body."""

    messages = [
        SystemMessage(content=REVIEW_JOB_DESCRIPTION_SYSTEM_PROMPT),
        HumanMessage(content=raw_jd_content),
    ]

    result = agent.invoke({"messages": messages})
    last_message = result["messages"][-1]

    try:
        parsed = json.loads(last_message.content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model returned invalid JSON. Please try again or contact support.",
        )

    return JobReviewResponse1(message=parsed)


@router.post("/jd/upload", response_model=JobUploadResponse)
async def upload_job_description(
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = None,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a JD file, validate, save it locally, store metadata in DB, and trigger analysis.

    If analysis fails, the upload still succeeds; errors are surfaced via logs/HTTP 500
    only for catastrophic failures (e.g., cannot read file).
    """

    # 1) Validate file (extension, size, etc.)
    validate_jd_upload(file)

    # 2) Persist file to disk
    try:
        saved_path = save_upload_file(file, settings.upload_dir_jd)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {exc}",
        )

    # 3) Always use logged-in user as uploaded_by; ignore explicit parameter
    effective_uploaded_by = user.user_name

    upload_resp = create_job_description(
        db,
        file_name=file.filename or "uploaded_file",
        file_saved_location=saved_path,
        uploaded_by=effective_uploaded_by,
    )

    # Best-effort JD analysis using the same logic as /jd/{jd_id}/analyze
    try:
        # Read raw text from the JD file
        with open(saved_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_jd_content = f.read()

        messages = [
            SystemMessage(content=REVIEW_JOB_DESCRIPTION_SYSTEM_PROMPT),
            HumanMessage(content=raw_jd_content),
        ]

        result = agent.invoke({"messages": messages})
        last_message = result["messages"][-1]

        parsed = json.loads(last_message.content)
        if isinstance(parsed, dict):
            title = parsed.get("title")
            summary = parsed.get("summary")

            analyze_job_description(
                db,
                jd_id=upload_resp.jd_id,
                title=title,
                parsed_summary=summary,
                reviewed_by=user.user_name,
            )
    except json.JSONDecodeError:
        # Ignore analysis failure; upload already succeeded
        pass
    except Exception:
        # Swallow analysis errors to not break upload; can be logged later
        pass

    return upload_resp


@router.post("/jd/{jd_id}/analyze", response_model=JobAnalyzeResponse)
async def analyze_job_description_endpoint(
    jd_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Analyze an uploaded JD using the agent and persist structured fields.

    Populates title, parsed_summary, last_reviewed_at, last_reviewed_by, updated_at.
    """

    # Load JD to get file path
    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    # Read raw text from the JD file
    try:
        with open(jd.file_saved_location, "r", encoding="utf-8", errors="ignore") as f:
            raw_jd_content = f.read()
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored JD file not found on server.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read JD file: {exc}",
        )

    # Call agent with same prompt as /jd/builder
    messages = [
        SystemMessage(content=REVIEW_JOB_DESCRIPTION_SYSTEM_PROMPT),
        HumanMessage(content=raw_jd_content),
    ]

    result = agent.invoke({"messages": messages})
    last_message = result["messages"][-1]

    try:
        parsed = json.loads(last_message.content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model returned invalid JSON during JD analysis.",
        )

    # Extract fields from parsed JSON; adjust keys to your JD review schema
    title = parsed.get("title") if isinstance(parsed, dict) else None
    summary = parsed.get("summary") if isinstance(parsed, dict) else None

    # Persist analysis results
    analyze_job_description(
        db,
        jd_id=jd_id,
        title=title,
        parsed_summary=summary,
        reviewed_by=user.user_name,
    )

    # Build response with timestamps from DB
    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()

    return JobAnalyzeResponse(
        jd_id=jd.jd_id,
        title=jd.title,
        parsed_summary=jd.parsed_summary,
        last_reviewed_at=jd.last_reviewed_at.isoformat() if jd.last_reviewed_at else None,
        last_reviewed_by=jd.last_reviewed_by,
    )


@router.get("/jd/{jd_id}", response_model=JobDetailsResponse)
async def get_job_description_details(
    jd_id: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    jd_details = get_jd_details_svc(db, jd_id)
    if jd_details is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    return jd_details


@router.post("/resumes/upload", response_model=List[ResumeUploadResponse])
async def upload_resume(
    jd_id: int,
    files: List[UploadFile] = File(...),
    uploaded_by: Optional[str] = None,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload one or more resume files linked to a JD and persist metadata.

    - jd_id is mandatory and must reference an existing job_description_details row.
    - Up to 10 files per request are allowed.
    - uploaded_by can be passed explicitly (e.g., current username).
    """

    from app.models.job_description import JobDescription as JDModel

    jd = db.query(JDModel).filter(JDModel.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid jd_id: job description does not exist",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one resume file must be provided",
        )

    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A maximum of 10 resume files can be uploaded at once",
        )

    responses: List[ResumeUploadResponse] = []
    effective_uploaded_by = uploaded_by or user.user_name

    for file in files:
        # Validate each file (extension, size, etc.)
        validate_jd_upload(file)

        try:
            saved_path = save_upload_file(file, settings.upload_dir_resume)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file '{file.filename}': {exc}",
            )

        resp = create_resume(
            db,
            jd_id=jd_id,
            file_name=file.filename or "uploaded_resume",
            file_location=saved_path,
            uploaded_by=effective_uploaded_by,
        )
        responses.append(resp)

    return responses


@router.get("/resumes", response_model=ResumeListResponse)
async def list_resumes_by_jd(
    jd_id: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    """Return list of resumes for a given jd_id with file locations."""
    return list_resumes_svc(db, jd_id)


@router.post("/resumes/process-once", response_model=ResumeProcessOnceResponse)
async def process_resumes_once(user: User = Depends(get_current_user)):
    """Trigger a single batch of resume processing.

    Uses the same logic as the background worker, respecting batch size config.
    """

    processed = await run_resume_process_once(processed_by=user.user_name)
    return ResumeProcessOnceResponse(processed_count=processed)
