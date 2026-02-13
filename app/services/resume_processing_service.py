import json
from typing import List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db import SessionLocal
from app.models.job_description import JobDescription
from app.models.resume import Resume, ResumeAnalysis
from app.agents.agent import build_resume_processing_agent
from langchain_core.messages import SystemMessage, HumanMessage
from app.prompts.resume_analysis_prompt import RESUME_ANALYSIS_SYSTEM_PROMPT
from app.services.file_readers import read_file_to_text
import logging


logger = logging.getLogger(__name__)


def _fetch_pending_batch(db_session: Session, jd_id: int | None = None) -> List[Resume]:
    """Fetch a batch of resumes that are not yet processed.

    If jd_id is provided, only resumes for that JD are considered; otherwise
    all pending resumes are eligible.
    """

    query = db_session.query(Resume).filter(Resume.status != "processed")
    if jd_id is not None:
        query = query.filter(Resume.jd_id == jd_id)

    return query.limit(settings.resume_process_batch_size).all()


async def _mark_error(
    db_session: Session,
    jd: JobDescription,
    resume: Resume,
    reason: str,
    processed_by: str | None,
):
    """Helper to record a processing error on a resume and bump JD counter."""

    logger.error(
        "Resume processing error for resume_id=%s jd_id=%s: %s",
        resume.resume_id,
        jd.jd_id,
        reason,
    )

    resume.status = "error"
    resume.failure_reason = reason[:500]  # avoid extremely long strings
    db_session.add(resume)

    jd.processed_resumes_count = (jd.processed_resumes_count or 0) + 1
    db_session.add(jd)

    db_session.commit()


def _extract_candidate_contact(parsed: dict) -> tuple[str | None, str | None, str | None]:
    """Best-effort extraction of candidate name/email/phone from analysis JSON.

    The RESUME_ANALYSIS_SYSTEM_PROMPT does not strictly define these keys,
    but if the LLM is extended to output them, this helper will map them.
    """

    if not isinstance(parsed, dict):
        return None, None, None

    # Support a few common key patterns
    name = parsed.get("candidate_name") or parsed.get("name")
    email = parsed.get("candidate_email") or parsed.get("email")
    phone = parsed.get("candidate_phone") or parsed.get("phone")

    return name, email, phone


def _extract_dimensions(parsed: dict) -> dict:
    """Extract per-dimension scores/notes from the LLM JSON.

    Expected shape (per prompt):
      {
        "match_score": number,
        "summary": string,
        "issues": [...],
        "dimensions": {
          "tech_stack_match": {"score": ..., "note": ...},
          ...
        }
      }
    """

    if not isinstance(parsed, dict):
        return {}

    dims = parsed.get("dimensions") or {}
    if not isinstance(dims, dict):
        return {}

    out: dict[str, dict] = {}
    for key, value in dims.items():
        if not isinstance(value, dict):
            continue
        score = value.get("score")
        note = value.get("note")
        out[key] = {"score": score, "note": note}
    return out


async def _process_single_resume(
    db_session: Session,
    agent,
    jd: JobDescription,
    resume: Resume,
    processed_by: str | None = "system",
):
    """Stateless per-resume processing: send JD + this resume only."""

    try:
        jd_text = read_file_to_text(jd.file_saved_location)
    except Exception as exc:
        await _mark_error(db_session, jd, resume, f"JD read error: {exc}", processed_by)
        return

    try:
        resume_text = read_file_to_text(resume.file_location)
    except Exception as exc:
        await _mark_error(db_session, jd, resume, f"Resume read error: {exc}", processed_by)
        return

    messages = [
        SystemMessage(content=RESUME_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=f"JOB DESCRIPTION:\n{jd_text}\n\nRESUME:\n{resume_text}"),
    ]

    try:
        result = agent.invoke({"messages": messages})
        last_message = result["messages"][-1]
        raw = getattr(last_message, "content", str(last_message))
    except Exception as exc:
        await _mark_error(db_session, jd, resume, f"LLM invoke error: {exc}", processed_by)
        return

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"raw": raw}

    # Top-level match_score
    match_score = None
    if isinstance(parsed, dict) and parsed.get("match_score") is not None:
        try:
            match_score = float(parsed.get("match_score"))
        except Exception:
            match_score = None

    # Top-level summary
    summary = None
    if isinstance(parsed, dict):
        s = parsed.get("summary")
        if isinstance(s, str):
            summary = s

    # Top-level issues -> serialize as JSON string for DB storage
    issues_serialized = None
    if isinstance(parsed, dict):
        issues = parsed.get("issues")
        if issues is not None:
            try:
                issues_serialized = json.dumps(issues)
            except Exception:
                issues_serialized = str(issues)

    # Per-dimension scores/notes
    dims = _extract_dimensions(parsed)

    def _dim(name: str) -> tuple[float | None, str | None]:
        d = dims.get(name) or {}
        score = d.get("score")
        note = d.get("note")
        try:
            score_f = float(score) if score is not None else None
        except Exception:
            score_f = None
        note_s = str(note) if note is not None else None
        return score_f, note_s

    tech_stack_match_score, tech_stack_match_note = _dim("tech_stack_match")
    relevant_experience_score, relevant_experience_note = _dim("relevant_experience")
    responsibilities_impact_score, responsibilities_impact_note = _dim("responsibilities_impact")
    seniority_fit_score, seniority_fit_note = _dim("seniority_fit")
    domain_fit_score, domain_fit_note = _dim("domain_fit")
    red_flags_gaps_score, red_flags_gaps_note = _dim("red_flags_gaps")
    communication_clarity_score, communication_clarity_note = _dim("communication_clarity")
    soft_skills_professionalism_score, soft_skills_professionalism_note = _dim(
        "soft_skills_professionalism"
    )
    project_complexity_score, project_complexity_note = _dim("project_complexity")
    consistency_trajectory_score, consistency_trajectory_note = _dim("consistency_trajectory")

    # Candidate info (optional, if present in JSON)
    cand_name, cand_email, cand_phone = _extract_candidate_contact(parsed)
    if cand_name:
        resume.candidate_name = cand_name
    if cand_email:
        resume.candidate_email = cand_email
    if cand_phone:
        resume.candidate_phone = cand_phone

    # Persist analysis row with all new columns
    analysis = ResumeAnalysis(
        resume_id=resume.resume_id,
        jd_id=jd.jd_id,
        analysis_json=json.dumps(parsed),
        match_score=match_score,
        summary=summary,
        issues=issues_serialized,
        tech_stack_match_score=tech_stack_match_score,
        tech_stack_match_note=tech_stack_match_note,
        relevant_experience_score=relevant_experience_score,
        relevant_experience_note=relevant_experience_note,
        responsibilities_impact_score=responsibilities_impact_score,
        responsibilities_impact_note=responsibilities_impact_note,
        seniority_fit_score=seniority_fit_score,
        seniority_fit_note=seniority_fit_note,
        domain_fit_score=domain_fit_score,
        domain_fit_note=domain_fit_note,
        red_flags_gaps_score=red_flags_gaps_score,
        red_flags_gaps_note=red_flags_gaps_note,
        communication_clarity_score=communication_clarity_score,
        communication_clarity_note=communication_clarity_note,
        soft_skills_professionalism_score=soft_skills_professionalism_score,
        soft_skills_professionalism_note=soft_skills_professionalism_note,
        project_complexity_score=project_complexity_score,
        project_complexity_note=project_complexity_note,
        consistency_trajectory_score=consistency_trajectory_score,
        consistency_trajectory_note=consistency_trajectory_note,
        processed_by=processed_by,
    )
    db_session.add(analysis)

    # Update resume status and JD counters
    resume.status = "processed"
    resume.failure_reason = None
    db_session.add(resume)

    jd.processed_resumes_count = (jd.processed_resumes_count or 0) + 1
    db_session.add(jd)

    db_session.commit()


async def run_once(processed_by: str | None = "system", jd_id: int | None = None) -> int:
    """Process a batch of pending resumes, independently per resume.

    If jd_id is provided, only pending resumes for that JD are processed.
    Otherwise, pending resumes across all JDs are considered.

    Each resume call is stateless from the model's perspective: it receives
    only the JD and that resume's content, so there is no cross-resume
    contamination in the LLM evaluation.
    """

    db = SessionLocal()
    try:
        pending = _fetch_pending_batch(db, jd_id=jd_id)
        if not pending:
            logger.info("Resume worker: no pending resumes to process")
            return 0

        logger.info(
            "Resume worker: starting batch with %d pending resumes for jd_id=%s (requested by %s)",
            len(pending),
            jd_id,
            processed_by,
        )

        agent = build_resume_processing_agent()

        for resume in pending:
            jd = db.query(JobDescription).filter(JobDescription.jd_id == resume.jd_id).first()
            if not jd:
                logger.error(
                    "Resume worker: jd_id=%s not found for resume_id=%s",
                    resume.jd_id,
                    resume.resume_id,
                )
                continue

            await _process_single_resume(
                db_session=db,
                agent=agent,
                jd=jd,
                resume=resume,
                processed_by=processed_by,
            )

        logger.info(
            "Resume worker: finished batch, attempted %d resumes", len(pending)
        )
        return len(pending)
    finally:
        db.close()
