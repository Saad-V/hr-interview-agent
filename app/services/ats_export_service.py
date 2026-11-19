import csv
import io
import json
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.interview_design import RUBRIC_VERSION
from app.repositories.interview_repository import InterviewRepository
from app.repositories.report_repository import ReportRepository


def build_ats_export_csv(
    *,
    candidate_reference: str,
    completed_at: str | None,
    difficulty_pool: str,
    report_data: dict,
) -> str:
    screening = report_data.get("screening_summary") or {}
    scorecard = report_data.get("scorecard") or {}
    stage_scores = [
        {
            "stage": section.get("category"),
            "score_percentage": section.get("score_percentage"),
            "weight": section.get("weight"),
        }
        for section in scorecard.get("sections", [])
    ]

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "candidate_reference",
        "completed_at",
        "experience_pool",
        "weighted_score",
        "recommendation",
        "human_checkpoint_required",
        "checkpoint_reasons",
        "approved_min_lpa",
        "approved_max_lpa",
        "candidate_expected_lpa",
        "candidate_current_ctc_lpa",
        "salary_alignment_status",
        "max_notice_days",
        "candidate_notice_days",
        "notice_alignment_status",
        "evidence_backed_red_flag_count",
        "weighted_stage_scores",
    ])
    writer.writerow([
        candidate_reference,
        completed_at or "",
        difficulty_pool,
        report_data.get("overall_score", ""),
        report_data.get("recommendation", ""),
        screening.get("human_checkpoint_required", False),
        json.dumps(screening.get("checkpoint_reasons", []), ensure_ascii=False),
        screening.get("approved_min_lpa", ""),
        screening.get("approved_max_lpa", ""),
        screening.get("candidate_expected_lpa", ""),
        screening.get("candidate_current_ctc_lpa", ""),
        screening.get("salary_alignment_status", ""),
        screening.get("max_notice_days", ""),
        screening.get("candidate_notice_days", ""),
        screening.get("notice_alignment_status", ""),
        len(screening.get("red_flags", [])),
        json.dumps(stage_scores, ensure_ascii=False),
    ])
    return output.getvalue()


def export_ats_csv(
    db: Session,
    *,
    interview_session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str:
    session = InterviewRepository().get_by_id_for_user(
        db,
        interview_session_id,
        user_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    report = ReportRepository().get_by_session_id(db, interview_session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Interview report not found.")
    if report.report_json.get("rubric_version") != RUBRIC_VERSION:
        raise HTTPException(
            status_code=409,
            detail="ATS export is available only for reports using the current HR rubric.",
        )

    return build_ats_export_csv(
        candidate_reference=str(session.id),
        completed_at=(
            session.completed_at.isoformat()
            if session.completed_at is not None
            else None
        ),
        difficulty_pool=session.difficulty.value,
        report_data=report.report_json or {},
    )
