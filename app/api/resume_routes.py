from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi import status
from fastapi.responses import FileResponse
from typing import List
import logging

from app.models.user import User
from app.models.api import (
    ResumeUploadResponse,
    ResumeListResponse,
    ResumeProcessOnceResponse,
    ResumeFeedbackRequest,
    ResumeFeedbackResponse,
    ResumeFeedbackListResponse,
    ResumeAnalysisSummary,
    ResumeAnalysisDetail,
    ResumeAnalysisListResponse,
    ResumeStatusUpdateRequest,
    ResumeStatusUpdateResponse,
)
from app.services.resume_service import (
    create_resume,
    list_resumes_by_jd as list_resumes_svc,
    get_resume_analysis_summaries_by_jd,
    get_resume_analysis_detail,
    delete_resume,
    update_resume_business_status,
)
from app.services.feedback_service import (
    add_resume_feedback,
    list_feedback_by_resume,
    list_feedback_by_jd,
)
from app.services.auth_service import get_db, get_current_user
from app.services.file_service import save_upload_file
from app.core.config import settings
from app.validations.jd_validations import validate_jd_upload
from app.services.resume_processing_service import run_once as run_resume_process_once


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/resumes/upload", response_model=List[ResumeUploadResponse])
async def upload_resume(
    jd_id: int,
    files: List[UploadFile] = File(...),
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload one or more resume files linked to a JD and persist metadata."""

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

    logger.info(
        "Resume upload requested for jd_id=%s by user='%s' with %d file(s)",
        jd_id,
        user.user_name,
        len(files),
    )

    responses: List[ResumeUploadResponse] = []
    effective_uploaded_by = user.user_name

    for file in files:
        validate_jd_upload(file)

        try:
            saved_path = save_upload_file(file, settings.upload_dir_resume)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to save resume file '%s' for jd_id=%s: %s",
                file.filename,
                jd_id,
                exc,
            )
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

    logger.info(
        "Resume upload completed for jd_id=%s: %d resume(s) stored",
        jd_id,
        len(responses),
    )

    return responses


@router.get("/resumes", response_model=ResumeListResponse)
async def list_resumes_by_jd(
    jd_id: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    """Return list of resumes for a given jd_id with file locations."""
    return list_resumes_svc(db, jd_id)


@router.get("/resumes/{resume_id}/download")
async def download_resume(
    resume_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download the original resume file for a given resume_id."""

    from app.models.resume import Resume as ResumeModel

    resume = db.query(ResumeModel).filter(ResumeModel.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    if not resume.file_location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored resume file path is missing",
        )

    return FileResponse(
        path=resume.file_location,
        filename=resume.file_name or "resume",
        media_type="application/octet-stream",
    )


@router.post("/resumes/process-once", response_model=ResumeProcessOnceResponse)
async def process_resumes_once(user: User = Depends(get_current_user)):
    """Trigger a single batch of resume processing."""

    processed = await run_resume_process_once(processed_by=user.user_name)
    logger.info(
        "Manual resume processing triggered by user='%s': processed_count=%d",
        user.user_name,
        processed,
    )
    return ResumeProcessOnceResponse(processed_count=processed)


@router.post("/resumes/{resume_id}/feedback", response_model=ResumeFeedbackResponse)
async def give_resume_feedback(
    resume_id: int,
    jd_id: int,
    payload: ResumeFeedbackRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit feedback on a resume for a specific JD (good_fit / bad_fit / maybe + optional comment)."""

    # Ensure resume exists and belongs to the given jd_id
    from app.models.resume import Resume as ResumeModel

    resume = db.query(ResumeModel).filter(ResumeModel.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    if resume.jd_id != jd_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided jd_id does not match resume's jd_id",
        )

    fb = add_resume_feedback(
        db,
        resume_id=resume_id,
        jd_id=jd_id,
        user_name=user.user_name,
        label=payload.label,
        comment=payload.comment,
    )

    return ResumeFeedbackResponse(
        feedback_id=fb.feedback_id,
        resume_id=fb.resume_id,
        jd_id=fb.jd_id,
        user_name=fb.user_name,
        label=fb.label,
        comment=fb.comment,
        created_at=fb.created_at.isoformat() if fb.created_at else None,
    )


@router.get("/resumes/{resume_id}/feedback", response_model=ResumeFeedbackListResponse)
async def get_feedback_for_resume(
    resume_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all feedback entries for a given resume_id."""

    from app.models.resume import Resume as ResumeModel

    resume = db.query(ResumeModel).filter(ResumeModel.resume_id == resume_id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    feedback_rows = list_feedback_by_resume(db, resume_id)
    items = [
        ResumeFeedbackResponse(
            feedback_id=row.feedback_id,
            resume_id=row.resume_id,
            jd_id=row.jd_id,
            user_name=row.user_name,
            label=row.label,
            comment=row.comment,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in feedback_rows
    ]
    return ResumeFeedbackListResponse(items=items)


@router.get("/jd/{jd_id}/feedback", response_model=ResumeFeedbackListResponse)
async def get_feedback_for_jd(
    jd_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all feedback entries across resumes for a given jd_id."""

    from app.models.job_description import JobDescription as JDModel

    jd = db.query(JDModel).filter(JDModel.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    feedback_rows = list_feedback_by_jd(db, jd_id)
    items = [
        ResumeFeedbackResponse(
            feedback_id=row.feedback_id,
            resume_id=row.resume_id,
            jd_id=row.jd_id,
            user_name=row.user_name,
            label=row.label,
            comment=row.comment,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in feedback_rows
    ]
    return ResumeFeedbackListResponse(items=items)


@router.get("/jd/{jd_id}/analysis", response_model=ResumeAnalysisListResponse)
async def list_resume_analysis_for_jd(
    jd_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return analysis summaries (match_score, status, etc.) for all resumes under a JD."""

    from app.models.job_description import JobDescription as JDModel

    jd = db.query(JDModel).filter(JDModel.jd_id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job description not found",
        )

    rows = get_resume_analysis_summaries_by_jd(db, jd_id)
    items: list[ResumeAnalysisSummary] = []
    for resume, analysis in rows:
        items.append(
            ResumeAnalysisSummary(
                resume_id=resume.resume_id,
                jd_id=resume.jd_id,
                file_name=resume.file_name,
                match_score=(analysis.match_score if analysis else resume.match_score),
                status=resume.status,
                failure_reason=resume.failure_reason,
            )
        )

    return ResumeAnalysisListResponse(items=items)


@router.get("/resumes/{resume_id}/analysis", response_model=ResumeAnalysisDetail)
async def get_resume_analysis(
    resume_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return detailed analysis (including raw JSON) for a single resume."""

    row = get_resume_analysis_detail(db, resume_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    resume, analysis = row

    if analysis is None:
        # No analysis yet: return basic skeleton without analysis_json
        return ResumeAnalysisDetail(
            resume_id=resume.resume_id,
            jd_id=resume.jd_id,
            file_name=resume.file_name,
            match_score=resume.match_score,
            analysis_json={},
            status=resume.status,
            failure_reason=resume.failure_reason,
        )

    import json as _json

    try:
        analysis_obj = _json.loads(analysis.analysis_json)
    except Exception:
        analysis_obj = {"_raw": analysis.analysis_json}

    return ResumeAnalysisDetail(
        resume_id=resume.resume_id,
        jd_id=resume.jd_id,
        file_name=resume.file_name,
        match_score=analysis.match_score,
        analysis_json=analysis_obj,
        status=resume.status,
        failure_reason=resume.failure_reason,
    )


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_resume(
    resume_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a resume and its related analysis/feedback; adjust JD counters."""

    deleted = delete_resume(db, resume_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )
    return None


@router.patch("/resumes/{resume_id}/status", response_model=ResumeStatusUpdateResponse)
async def update_resume_status(
    resume_id: int,
    payload: ResumeStatusUpdateRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the business_status of a resume (e.g., interview_scheduled, rejected)."""

    resume = update_resume_business_status(
        db,
        resume_id=resume_id,
        business_status=payload.business_status,
    )
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    return ResumeStatusUpdateResponse(
        resume_id=resume.resume_id,
        jd_id=resume.jd_id,
        business_status=resume.business_status,
        status=resume.status,
        failure_reason=resume.failure_reason,
    )
