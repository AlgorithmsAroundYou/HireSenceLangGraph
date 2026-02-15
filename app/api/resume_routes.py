from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from typing import List
import json as _json
import logging

from app.core.config import settings
from app.models.user import User
from app.models.api import (
    ResumeUploadResponse,
    ResumeListResponse,
    ResumeProcessOnceResponse,
    ResumeAnalysisListResponse,
    ResumeAnalysisDetail,
    ResumeAnalysisSummary,
    ResumeStatusUpdateRequest,
    ResumeStatusUpdateResponse,
    ResumeDeleteResponse,
    ResumeMoveRequest,
    ResumeMoveResponse,
)
from app.services.auth_service import get_db, get_current_user
from app.services.file_service import save_upload_file
from app.services.resume_service import (
    create_resume,
    list_resumes_by_jd as list_resumes_svc,
    get_resume_analysis_summaries_by_jd,
    get_resume_analysis_detail,
    delete_resume,
    update_resume_business_status,
    move_resume_to_jd,
)
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
    """Upload one or more resume files linked to a JD and persist metadata.

    Resumes are stored under a per-JD folder: <UPLOAD_DIR_RESUME>/<jd_id>/.
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
            # Store resumes under a JD-specific subfolder
            destination_dir = f"{settings.upload_dir_resume}/{jd_id}"
            saved_path = save_upload_file(file, destination_dir)
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
    jd_id: int | None = None,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return resumes; filter by jd_id when provided."""
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
async def process_resumes_once(
    jd_id: int | None = None,
    user: User = Depends(get_current_user),
):
    """Trigger a single batch of resume processing.

    If jd_id is provided, only pending resumes for that JD are processed.
    Otherwise, pending resumes across all JDs are considered.
    """

    processed = await run_resume_process_once(processed_by=user.user_name, jd_id=jd_id)
    logger.info(
        "Manual resume processing triggered by user='%s' jd_id=%s: processed_count=%d",
        user.user_name,
        jd_id,
        processed,
    )
    return ResumeProcessOnceResponse(processed_count=processed)


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
@router.get("/resume/{resume_id}/analysis", response_model=ResumeAnalysisDetail)
async def get_resume_analysis(
    resume_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return detailed analysis (including raw JSON and all extracted DB fields) for a single resume."""

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
            candidate_name=resume.candidate_name,
            candidate_email=resume.candidate_email,
            candidate_phone=resume.candidate_phone,
            match_score=resume.match_score,
            summary=None,
            issues=None,
            dimensions=None,
            analysis_json={},
            issues_raw=None,
            tech_stack_match_score=None,
            tech_stack_match_note=None,
            relevant_experience_score=None,
            relevant_experience_note=None,
            responsibilities_impact_score=None,
            responsibilities_impact_note=None,
            seniority_fit_score=None,
            seniority_fit_note=None,
            domain_fit_score=None,
            domain_fit_note=None,
            red_flags_gaps_score=None,
            red_flags_gaps_note=None,
            communication_clarity_score=None,
            communication_clarity_note=None,
            soft_skills_professionalism_score=None,
            soft_skills_professionalism_note=None,
            project_complexity_score=None,
            project_complexity_note=None,
            consistency_trajectory_score=None,
            consistency_trajectory_note=None,
            processed_at=None,
            processed_by=None,
            status=resume.status,
            failure_reason=resume.failure_reason,
        )

    try:
        analysis_obj = _json.loads(analysis.analysis_json)
    except Exception:
        analysis_obj = {"_raw": analysis.analysis_json}

    # Extract top-level fields if present
    summary = getattr(analysis, "summary", None)
    issues_text = getattr(analysis, "issues", None)
    issues_list = None
    if issues_text:
        try:
            tmp = _json.loads(issues_text)
            if isinstance(tmp, list):
                issues_list = [str(x) for x in tmp]
            else:
                issues_list = [str(tmp)]
        except Exception:
            # Fallback: treat as comma-separated or single string
            if "," in issues_text:
                issues_list = [p.strip() for p in issues_text.split(",") if p.strip()]
            else:
                issues_list = [issues_text]

    # Build dimensions dict from stored per-dimension columns
    from app.models.api import ResumeAnalysisDimension

    def dim(score, note):
        if score is None and not note:
            return None
        return ResumeAnalysisDimension(score=score, note=note)

    dimensions = {
        "tech_stack_match": dim(analysis.tech_stack_match_score, analysis.tech_stack_match_note),
        "relevant_experience": dim(analysis.relevant_experience_score, analysis.relevant_experience_note),
        "responsibilities_impact": dim(
            analysis.responsibilities_impact_score, analysis.responsibilities_impact_note
        ),
        "seniority_fit": dim(analysis.seniority_fit_score, analysis.seniority_fit_note),
        "domain_fit": dim(analysis.domain_fit_score, analysis.domain_fit_note),
        "red_flags_gaps": dim(analysis.red_flags_gaps_score, analysis.red_flags_gaps_note),
        "communication_clarity": dim(
            analysis.communication_clarity_score, analysis.communication_clarity_note
        ),
        "soft_skills_professionalism": dim(
            analysis.soft_skills_professionalism_score,
            analysis.soft_skills_professionalism_note,
        ),
        "project_complexity": dim(
            analysis.project_complexity_score, analysis.project_complexity_note
        ),
        "consistency_trajectory": dim(
            analysis.consistency_trajectory_score, analysis.consistency_trajectory_note
        ),
    }

    # Remove dimensions that are completely None
    dimensions = {k: v for k, v in dimensions.items() if v is not None}

    processed_at_str = analysis.processed_at.isoformat() if getattr(analysis, "processed_at", None) else None

    return ResumeAnalysisDetail(
        resume_id=resume.resume_id,
        jd_id=resume.jd_id,
        file_name=resume.file_name,
        candidate_name=resume.candidate_name,
        candidate_email=resume.candidate_email,
        candidate_phone=resume.candidate_phone,
        match_score=analysis.match_score,
        summary=summary,
        issues=issues_list,
        dimensions=dimensions or None,
        analysis_json=analysis_obj,
        issues_raw=issues_text,
        tech_stack_match_score=analysis.tech_stack_match_score,
        tech_stack_match_note=analysis.tech_stack_match_note,
        relevant_experience_score=analysis.relevant_experience_score,
        relevant_experience_note=analysis.relevant_experience_note,
        responsibilities_impact_score=analysis.responsibilities_impact_score,
        responsibilities_impact_note=analysis.responsibilities_impact_note,
        seniority_fit_score=analysis.seniority_fit_score,
        seniority_fit_note=analysis.seniority_fit_note,
        domain_fit_score=analysis.domain_fit_score,
        domain_fit_note=analysis.domain_fit_note,
        red_flags_gaps_score=analysis.red_flags_gaps_score,
        red_flags_gaps_note=analysis.red_flags_gaps_note,
        communication_clarity_score=analysis.communication_clarity_score,
        communication_clarity_note=analysis.communication_clarity_note,
        soft_skills_professionalism_score=analysis.soft_skills_professionalism_score,
        soft_skills_professionalism_note=analysis.soft_skills_professionalism_note,
        project_complexity_score=analysis.project_complexity_score,
        project_complexity_note=analysis.project_complexity_note,
        consistency_trajectory_score=analysis.consistency_trajectory_score,
        consistency_trajectory_note=analysis.consistency_trajectory_note,
        processed_at=processed_at_str,
        processed_by=getattr(analysis, "processed_by", None),
        status=resume.status,
        failure_reason=resume.failure_reason,
    )


@router.delete("/resumes/{resume_id}", response_model=ResumeDeleteResponse)
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
    return deleted


@router.post("/resume/{resume_id}/status", response_model=ResumeStatusUpdateResponse)
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


@router.put("/resume/{resume_id}/jd", response_model=ResumeMoveResponse)
async def update_resume_jd(
    resume_id: int,
    payload: ResumeMoveRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Move a resume to a different JD when uploaded to wrong JD by mistake."""

    return move_resume_to_jd(
        db,
        resume_id=resume_id,
        target_jd_id=payload.jd_id,
    )
