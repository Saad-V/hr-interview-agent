import logging

from app.ai.llm import LLMGenerationError, generate_structured_output
from app.ai.prompts import (
    INTERVIEW_REPORT_SYSTEM_PROMPT,
    build_interview_report_prompt,
)
from app.ai.schemas import InterviewReportNarrativeSchema

logger = logging.getLogger(__name__)


def _build_deterministic_narrative(
    conversation_turns: list[dict],
) -> InterviewReportNarrativeSchema:
    criterion_scores: dict[str, dict] = {}
    strengths: list[str] = []
    areas_for_improvement: list[str] = []
    total_score = 0
    total_maximum = 0

    for turn in conversation_turns:
        evaluation = turn.get("evaluation") or {}
        if not isinstance(evaluation, dict):
            continue

        for field, destination in (
            ("strengths", strengths),
            ("weaknesses", areas_for_improvement),
        ):
            items = evaluation.get(field, [])
            if isinstance(items, list):
                destination.extend(
                    item.strip()
                    for item in items
                    if isinstance(item, str) and item.strip()
                )
        suggestion = evaluation.get("suggested_improvement")
        if isinstance(suggestion, str) and suggestion.strip():
            areas_for_improvement.append(suggestion.strip())

        for criterion in evaluation.get("criteria", []):
            if not isinstance(criterion, dict):
                continue
            awarded = criterion.get("awarded_score")
            maximum = criterion.get("maximum_score")
            if (
                not isinstance(awarded, int)
                or isinstance(awarded, bool)
                or not isinstance(maximum, int)
                or isinstance(maximum, bool)
                or maximum <= 0
            ):
                continue

            criterion_id = str(
                criterion.get("criterion_id")
                or criterion.get("criterion")
                or "criterion"
            )
            label = str(criterion.get("criterion") or criterion_id)
            stats = criterion_scores.setdefault(
                criterion_id,
                {"label": label, "awarded": 0, "maximum": 0},
            )
            stats["awarded"] += awarded
            stats["maximum"] += maximum
            total_score += awarded
            total_maximum += maximum

    def unique(items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            normalized = item.casefold()
            if normalized not in seen:
                seen.add(normalized)
                result.append(item)
        return result

    strengths.extend(
        f"{stats['label']}: scored {stats['awarded']}/{stats['maximum']} points."
        for stats in criterion_scores.values()
        if stats["awarded"] / stats["maximum"] >= 0.6
    )
    areas_for_improvement.extend(
        f"{stats['label']}: scored {stats['awarded']}/{stats['maximum']} points."
        for stats in criterion_scores.values()
        if stats["awarded"] < stats["maximum"]
    )
    strengths = unique(strengths)[:5]
    areas_for_improvement = unique(areas_for_improvement)[:5]

    if total_maximum:
        percentage = total_score * 100 / total_maximum
        summary = (
            f"Across {len(conversation_turns)} evaluated answers, the candidate "
            f"earned {total_score}/{total_maximum} rubric points ({percentage:.1f}%). "
            "This summary is based on the recorded answer evaluations."
        )
    else:
        summary = (
            f"The interview contains {len(conversation_turns)} evaluated answers, "
            "but no rubric scores were available for a narrative summary."
        )

    return InterviewReportNarrativeSchema(
        strengths=strengths,
        areas_for_improvement=areas_for_improvement,
        summary=summary,
    )


def generate_interview_report(
    *,
    blueprint: dict,
    conversation_turns: list[dict],
) -> InterviewReportNarrativeSchema:

    prompt = build_interview_report_prompt(
        blueprint=blueprint,
        conversation_turns=conversation_turns,
    )

    try:
        return generate_structured_output(
            system_prompt=INTERVIEW_REPORT_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=InterviewReportNarrativeSchema,
            temperature=0.0,
        )
    except LLMGenerationError as exc:
        logger.warning(
            "Gemini report narrative unavailable; using rubric-based fallback: %s",
            exc,
        )
        return _build_deterministic_narrative(conversation_turns)