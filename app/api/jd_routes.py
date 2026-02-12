from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage, SystemMessage
import json
import logging

from app.agents.agent import build_agent
from app.models.user import User
from app.models.job_description import JobDescription
from app.prompts.review_job_description_prompt import (
    REVIEW_JOB_DESCRIPTION_SYSTEM_PROMPT,
)
from app.prompts.jd_analyze_prompt import JD_ANALYZE_SYSTEM_PROMPT
from app.models.api import (
    JobReviewResponse1,
    JobUploadResponse,
    JobDetailsResponse,
    JobAnalyzeResponse,
)
from app.services.jd_service import (
    create_job_description,
    get_job_description_details as get_jd_details_svc,
    analyze_job_description,
)
from app.services.auth_service import get_db, get_current_user
from app.services.file_service import save_upload_file
from app.core.config import settings
from app.validations.jd_validations import validate_jd_upload
from app.services.file_readers import read_file_to_text


logger = logging.getLogger(__name__)
router = APIRouter()
agent = build_agent()


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
        logger.exception("JD builder: model returned invalid JSON")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model returned invalid JSON. Please try again or contact support.",
        )

    return JobReviewResponse1(message=parsed)


@router.post("/jd/upload", response_model=JobUploadResponse)
async def upload_job_description(
    file: UploadFile = File(...),
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a JD file, validate, save it locally, store metadata in DB."""

    logger.info(
        "JD upload requested by user='%s' filename='%s'",
        user.user_name,
        file.filename,
    )

    validate_jd_upload(file)

    try:
        saved_path = save_upload_file(file, settings.upload_dir_jd)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save JD file '%s': %s", file.filename, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {exc}",
        )

    effective_uploaded_by = user.user_name

    upload_resp = create_job_description(
        db,
        file_name=file.filename or "uploaded_file",
        file_saved_location=saved_path,
        uploaded_by=effective_uploaded_by,
    )

    logger.info(
        "JD uploaded successfully: jd_id=%s file_name='%s' by user='%s'",
        upload_resp.jd_id,
        upload_resp.file_name,
        effective_uploaded_by,
    )

    return upload_resp


@router.post("/jd/{jd_id}/analyze", response_model=JobAnalyzeResponse)
async def analyze_job_description_endpoint(
    jd_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Analyze an uploaded JD using the agent and persist structured fields."""

    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    try:
        raw_jd_content = read_file_to_text(jd.file_saved_location)
    except FileNotFoundError:
        logger.exception("Stored JD file not found for jd_id=%s", jd_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored JD file not found on server.",
        )
    except Exception as exc:
        logger.exception("Failed to read JD file for jd_id=%s: %s", jd_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read JD file: {exc}",
        )

    messages = [
        SystemMessage(content=JD_ANALYZE_SYSTEM_PROMPT),
        HumanMessage(content=raw_jd_content),
    ]

    result = agent.invoke({"messages": messages})
    last_message = result["messages"][-1]
    raw_content = last_message.content

    def _try_parse_json(text: str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    parsed = _try_parse_json(raw_content)

    if parsed is None:
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = raw_content[start : end + 1]
            parsed = _try_parse_json(candidate)

    if parsed is None or not isinstance(parsed, dict):
        logger.exception(
            "JD analysis: model returned invalid JSON for jd_id=%s: %r",
            jd_id,
            raw_content[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model returned invalid JSON during JD analysis.",
        )

    title = parsed.get("title")
    summary = parsed.get("summary")

    analyze_job_description(
        db,
        jd_id=jd_id,
        title=title,
        parsed_summary=summary,
        reviewed_by=user.user_name,
    )

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


@router.get("/jd/{jd_id}/download")
async def download_job_description(
    jd_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download the original JD file for a given jd_id."""

    jd = db.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    if not jd.file_saved_location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored JD file path is missing",
        )

    return FileResponse(
        path=jd.file_saved_location,
        filename=jd.file_name or "job_description",
        media_type="application/octet-stream",
    )
