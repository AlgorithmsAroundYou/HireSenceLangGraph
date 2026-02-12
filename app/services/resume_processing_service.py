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


def _fetch_pending_batch(db_session: Session) -> List[Resume]:
    return (
        db_session.query(Resume)
        .filter(Resume.status != "processed")
        .limit(settings.resume_process_batch_size)
        .all()
    )


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

    match_score = None
    if isinstance(parsed, dict) and parsed.get("match_score") is not None:
        try:
            match_score = float(parsed.get("match_score"))
        except Exception:
            match_score = None

    analysis = ResumeAnalysis(
        resume_id=resume.resume_id,
        jd_id=jd.jd_id,
        analysis_json=json.dumps(parsed),
        match_score=match_score,
        processed_by=processed_by,
    )
    db_session.add(analysis)

    resume.status = "processed"
    resume.failure_reason = None
    db_session.add(resume)

    jd.processed_resumes_count = (jd.processed_resumes_count or 0) + 1
    db_session.add(jd)

    db_session.commit()


async def run_once(processed_by: str | None = "system") -> int:
    """Process a batch of pending resumes, independently per resume.

    Each resume call is stateless from the model's perspective: it receives
    only the JD and that resume's content, so there is no cross-resume
    contamination in the LLM evaluation.
    """

    db = SessionLocal()
    try:
        pending = _fetch_pending_batch(db)
        if not pending:
            logger.info("Resume worker: no pending resumes to process")
            return 0

        logger.info(
            "Resume worker: starting batch with %d pending resumes (requested by %s)",
            len(pending),
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
