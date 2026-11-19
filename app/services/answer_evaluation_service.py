import logging
import re

from app.ai.schemas import AnswerEvaluationSchema, RedFlagItemSchema
from app.ai.llm import generate_structured_output
from app.ai.prompts import (
    INTERVIEW_EVALUATION_SYSTEM_PROMPT,
    build_answer_evaluation_prompt,
)
from app.core.interview_design import RUBRIC_VERSION, RUBRIC_MAX_SCORES
from app.schemas.interview_history import AuditedAnswerEvaluation, RedFlagResponse
from app.schemas.screening import CandidateScreeningFacts

logger = logging.getLogger(__name__)


def _evidence_matches_answer(evidence: str, candidate_answer: str) -> bool:
    normalized_answer = " ".join(candidate_answer.casefold().split())
    normalized_evidence = " ".join(evidence.casefold().split()).strip("\"'")
    return bool(normalized_evidence) and normalized_evidence in normalized_answer


def _find_salary_evidence(candidate_answer: str, amount: float) -> str | None:
    amount_pattern = re.escape(f"{amount:g}") + r"(?:\.0+)?"
    match = re.search(
        rf"(?<![\d.]){amount_pattern}(?![\d.])\s*"
        r"(?:lpa\b|lakhs?\b|lacs?\b)",
        candidate_answer,
        re.IGNORECASE,
    )
    return match.group(0) if match else None


def _find_notice_evidence(candidate_answer: str, stated_days: int) -> str | None:
    if stated_days == 0:
        match = re.search(r"\bimmediate(?:ly)?\b", candidate_answer, re.IGNORECASE)
        if match:
            return match.group(0)

    for pattern, days_per_unit in (
        (r"(?<!\d)(\d+)\s*days?\b", 1),
        (r"(?<!\d)(\d+)\s*months?\b", 30),
    ):
        for match in re.finditer(pattern, candidate_answer, re.IGNORECASE):
            if int(match.group(1)) * days_per_unit == stated_days:
                return match.group(0)
    return None


def _validate_screening_facts(
    facts: CandidateScreeningFacts,
    candidate_answer: str,
) -> None:
    def validate_evidence(evidence: str, field_name: str) -> str:
        normalized_evidence = " ".join(evidence.casefold().split()).strip("\"'")
        if not _evidence_matches_answer(evidence, candidate_answer):
            raise ValueError(f"{field_name} evidence must quote the candidate answer.")
        return normalized_evidence

    if (facts.expected_ctc_lpa is None) != (facts.salary_evidence is None):
        raise ValueError("Expected CTC and its answer evidence must be provided together.")
    if (facts.stated_notice_days is None) != (facts.notice_evidence is None):
        raise ValueError(
            "Notice period and its answer evidence must be provided together."
        )

    if facts.expected_ctc_lpa is not None:
        if facts.salary_evidence is None:
            raise ValueError("Expected CTC requires answer evidence.")
        evidence = validate_evidence(facts.salary_evidence, "Expected CTC")
        amount = re.escape(f"{facts.expected_ctc_lpa:g}")
        if not re.search(rf"(?<!\d){amount}0*(?!\d)", evidence) or not re.search(
            r"\b(?:lpa|lakhs?|lacs?)\b",
            evidence,
            re.IGNORECASE,
        ):
            raise ValueError(
                "Expected CTC must be supported by a numeric LPA/lakh answer excerpt."
            )

    if facts.stated_notice_days is not None:
        if facts.notice_evidence is None:
            raise ValueError("Notice period requires answer evidence.")
        evidence = validate_evidence(facts.notice_evidence, "Notice period")
        stated_days = re.search(r"(?<!\d)(\d+)\s*days?\b", evidence)
        stated_months = re.search(r"(?<!\d)(\d+)\s*months?\b", evidence)
        immediate_availability = re.search(r"\bimmediate(?:ly)?\b", evidence)
        matches_days = (
            stated_days is not None
            and int(stated_days.group(1)) == facts.stated_notice_days
        )
        matches_months = (
            stated_months is not None
            and int(stated_months.group(1)) * 30 == facts.stated_notice_days
        )
        matches_immediate = (
            immediate_availability is not None
            and facts.stated_notice_days == 0
        )
        if not (matches_days or matches_months or matches_immediate):
            raise ValueError(
                "Notice period must match an answer excerpt stating days, months, "
                "or immediate availability."
            )

    for red_flag in facts.red_flags:
        validate_evidence(red_flag.evidence, "Red flag")


def _validate_red_flag_evidence(
    red_flags: list[RedFlagItemSchema],
    candidate_answer: str,
) -> list[RedFlagResponse]:
    validated = []
    discarded = 0
    for red_flag in red_flags:
        if (
            not _evidence_matches_answer(red_flag.evidence, candidate_answer)
            or not red_flag.category.strip()
            or not red_flag.description.strip()
        ):
            discarded += 1
            continue
        validated.append(
            RedFlagResponse(
                category=red_flag.category,
                description=red_flag.description,
                evidence=red_flag.evidence.strip(),
            )
        )
    if discarded:
        logger.warning(
            "Discarded %d model-generated red flag(s) without answer-supported evidence.",
            discarded,
        )
    return validated


def _anchor_screening_facts(
    evaluation: AnswerEvaluationSchema,
    candidate_answer: str,
) -> CandidateScreeningFacts:
    facts = evaluation.screening_facts
    expected_ctc_lpa = facts.expected_ctc_lpa
    extracted_expected_ctc_lpa = evaluation.extracted_expected_ctc_lpa
    if (
        expected_ctc_lpa is not None
        and extracted_expected_ctc_lpa is not None
        and expected_ctc_lpa != extracted_expected_ctc_lpa
    ):
        logger.warning("Omitting inconsistent expected CTC values from model output.")
        expected_ctc_lpa = None
    elif expected_ctc_lpa is None:
        expected_ctc_lpa = extracted_expected_ctc_lpa

    salary_evidence = (
        _find_salary_evidence(candidate_answer, expected_ctc_lpa)
        if expected_ctc_lpa is not None
        else None
    )
    if expected_ctc_lpa is not None and salary_evidence is None:
        logger.warning("Omitting expected CTC that could not be anchored to the answer.")
        expected_ctc_lpa = None

    stated_notice_days = facts.stated_notice_days
    extracted_notice_days = evaluation.extracted_notice_period_days
    if (
        stated_notice_days is not None
        and extracted_notice_days is not None
        and stated_notice_days != extracted_notice_days
    ):
        logger.warning("Omitting inconsistent notice-period values from model output.")
        stated_notice_days = None
    elif stated_notice_days is None:
        stated_notice_days = extracted_notice_days

    notice_evidence = (
        _find_notice_evidence(candidate_answer, stated_notice_days)
        if stated_notice_days is not None
        else None
    )
    if stated_notice_days is not None and notice_evidence is None:
        logger.warning("Omitting notice period that could not be anchored to the answer.")
        stated_notice_days = None

    red_flags = [
        red_flag
        for red_flag in facts.red_flags
        if _evidence_matches_answer(red_flag.evidence, candidate_answer)
    ]
    if len(red_flags) != len(facts.red_flags):
        logger.warning(
            "Discarded %d model-generated screening red flag(s) without answer-supported evidence.",
            len(facts.red_flags) - len(red_flags),
        )

    anchored_facts = CandidateScreeningFacts(
        expected_ctc_lpa=expected_ctc_lpa,
        salary_evidence=salary_evidence,
        stated_notice_days=stated_notice_days,
        notice_evidence=notice_evidence,
        red_flags=red_flags,
    )
    return anchored_facts


def _validate_evaluation_output(
    evaluation: AnswerEvaluationSchema,
    question: dict,
) -> None:
    expected_criteria = {
        point["criterion_id"]: point
        for point in question["evaluation_points"]
    }
    evaluated_criteria = set()
    for criterion in evaluation.criteria:
        criterion_id = criterion.criterion_id.value
        if criterion_id in evaluated_criteria:
            raise ValueError(f"Duplicate rubric evaluation for {criterion_id}.")
        if criterion_id not in expected_criteria:
            raise ValueError(f"Unexpected rubric evaluation for {criterion_id}.")

        if criterion.awarded_score > RUBRIC_MAX_SCORES[criterion_id]:
            raise ValueError(
                f"{criterion_id} score exceeds its "
                f"{RUBRIC_MAX_SCORES[criterion_id]}-point limit."
            )

        evidence = criterion.evidence.strip()
        if not evidence:
            raise ValueError(f"{criterion_id} must include an evidence rationale.")
        if evidence == "Not present in the answer." and criterion.awarded_score:
            raise ValueError(
                f"{criterion_id} cannot receive points without answer evidence."
            )

        evaluated_criteria.add(criterion_id)

    if evaluated_criteria != set(RUBRIC_MAX_SCORES):
        raise ValueError("The evaluation must score every rubric criterion exactly once.")


def evaluate_answer(
    *,
    question: dict,
    candidate_answer: str,
) -> AuditedAnswerEvaluation:

    user_prompt = build_answer_evaluation_prompt(
        question=question,
        candidate_answer=candidate_answer,
    )

    evaluation: AnswerEvaluationSchema = generate_structured_output(
        system_prompt=INTERVIEW_EVALUATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=AnswerEvaluationSchema,
        temperature=0.0,
        validator=lambda output: _validate_evaluation_output(
            output,
            question,
        ),
    )

    screening_facts = _anchor_screening_facts(evaluation, candidate_answer)
    _validate_screening_facts(screening_facts, candidate_answer)
    extracted_expected_ctc_lpa = screening_facts.expected_ctc_lpa
    extracted_notice_period_days = screening_facts.stated_notice_days

    red_flags = _validate_red_flag_evidence(
        evaluation.red_flags,
        candidate_answer,
    )
    if not red_flags:
        red_flags = [
            RedFlagResponse(
                category="SCREENING_CONCERN",
                description=red_flag.description,
                evidence=red_flag.evidence,
            )
            for red_flag in screening_facts.red_flags
        ]

    expected_criteria = {
        point["criterion_id"]: point
        for point in question["evaluation_points"]
    }
    evaluated_criteria = {}
    for criterion in evaluation.criteria:
        criterion_id = criterion.criterion_id.value
        rubric_point = expected_criteria[criterion_id]
        maximum_score = RUBRIC_MAX_SCORES[criterion_id]

        evidence = criterion.evidence.strip()
        evaluated_criteria[criterion_id] = {
            "criterion_id": criterion_id,
            "criterion": rubric_point["criterion"],
            "description": rubric_point["description"],
            "maximum_score": maximum_score,
            "awarded_score": criterion.awarded_score,
            "evidence": evidence,
        }

    ordered_criteria = [
        evaluated_criteria[criterion_id]
        for criterion_id in RUBRIC_MAX_SCORES
    ]
    awarded_score = sum(item["awarded_score"] for item in ordered_criteria)
    technical_score = sum(
        item["awarded_score"]
        for item in ordered_criteria
        if item["criterion_id"] != "COMMUNICATION"
    )
    communication_score = evaluated_criteria["COMMUNICATION"]["awarded_score"]

    return AuditedAnswerEvaluation(
        rubric_version=RUBRIC_VERSION,
        awarded_score=awarded_score,
        maximum_score=sum(RUBRIC_MAX_SCORES.values()),
        technical_score=technical_score,
        communication_score=communication_score,
        score_percentage=round(awarded_score * 100 / sum(RUBRIC_MAX_SCORES.values()), 2),
        technical_percentage=round(
            technical_score * 100 / sum(
                RUBRIC_MAX_SCORES[criterion_id]
                for criterion_id in RUBRIC_MAX_SCORES
                if criterion_id != "COMMUNICATION"
            ),
            2,
        ),
        communication_percentage=round(
            communication_score * 100 / RUBRIC_MAX_SCORES["COMMUNICATION"],
            2,
        ),
        criteria=ordered_criteria,
        feedback=evaluation.feedback,
        strengths=evaluation.strengths,
        weaknesses=evaluation.weaknesses,
        missing_topics=evaluation.missing_topics,
        suggested_improvement=evaluation.suggested_improvement,
        screening_facts=screening_facts,
        red_flags=red_flags,
        extracted_expected_ctc_lpa=extracted_expected_ctc_lpa,
        extracted_current_ctc_lpa=evaluation.extracted_current_ctc_lpa,
        extracted_notice_period_days=extracted_notice_period_days,
    )