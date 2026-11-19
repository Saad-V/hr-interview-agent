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


def _validate_screening_facts(
    facts: CandidateScreeningFacts,
    candidate_answer: str,
) -> None:
    normalized_answer = " ".join(candidate_answer.casefold().split())

    def validate_evidence(evidence: str, field_name: str) -> str:
        normalized_evidence = " ".join(evidence.casefold().split()).strip("\"'")
        if not normalized_evidence or normalized_evidence not in normalized_answer:
            raise ValueError(f"{field_name} evidence must quote the candidate answer.")
        return normalized_evidence

    if facts.expected_ctc_lpa is not None:
        if facts.salary_evidence is None:
            raise ValueError("Expected CTC requires answer evidence.")
        evidence = validate_evidence(facts.salary_evidence, "Expected CTC")
        amount = re.escape(f"{facts.expected_ctc_lpa:g}")
        if not re.search(rf"(?<!\d){amount}0*(?!\d)", evidence) or not re.search(
            r"\b(?:lpa|lakhs?)\b",
            evidence,
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
    for red_flag in red_flags:
        if not red_flag.evidence or red_flag.evidence not in candidate_answer:
            raise ValueError("Red flag evidence must quote the candidate answer.")
        if not red_flag.category.strip() or not red_flag.description.strip():
            raise ValueError("Red flags must include a category and description.")
        validated.append(
            RedFlagResponse(
                category=red_flag.category,
                description=red_flag.description,
                evidence=red_flag.evidence.strip(),
            )
        )
    return validated


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
    )
    _validate_screening_facts(evaluation.screening_facts, candidate_answer)

    extracted_expected_ctc_lpa = evaluation.extracted_expected_ctc_lpa
    if extracted_expected_ctc_lpa is None:
        extracted_expected_ctc_lpa = evaluation.screening_facts.expected_ctc_lpa
    elif extracted_expected_ctc_lpa != evaluation.screening_facts.expected_ctc_lpa:
        raise ValueError(
            "Expected CTC extraction must match the evidence-validated screening fact."
        )

    extracted_notice_period_days = evaluation.extracted_notice_period_days
    if extracted_notice_period_days is None:
        extracted_notice_period_days = evaluation.screening_facts.stated_notice_days
    elif extracted_notice_period_days != evaluation.screening_facts.stated_notice_days:
        raise ValueError(
            "Notice-period extraction must match the evidence-validated screening fact."
        )

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
            for red_flag in evaluation.screening_facts.red_flags
        ]

    expected_criteria = {
        point["criterion_id"]: point
        for point in question["evaluation_points"]
    }
    evaluated_criteria = {}
    for criterion in evaluation.criteria:
        criterion_id = criterion.criterion_id.value
        if criterion_id in evaluated_criteria:
            raise ValueError(f"Duplicate rubric evaluation for {criterion_id}.")
        if criterion_id not in expected_criteria:
            raise ValueError(f"Unexpected rubric evaluation for {criterion_id}.")

        rubric_point = expected_criteria[criterion_id]
        maximum_score = RUBRIC_MAX_SCORES[criterion_id]
        if criterion.awarded_score > maximum_score:
            raise ValueError(f"{criterion_id} score exceeds its {maximum_score}-point limit.")

        evidence = criterion.evidence.strip()
        if evidence != "Not present in the answer.":
            normalized_answer = " ".join(candidate_answer.casefold().split())
            normalized_evidence = " ".join(evidence.casefold().split()).strip("\"'")
            if not normalized_evidence or normalized_evidence not in normalized_answer:
                raise ValueError(
                    f"{criterion_id} evidence must quote the candidate answer."
                )
        elif criterion.awarded_score:
            raise ValueError(
                f"{criterion_id} cannot receive points without answer evidence."
            )

        evaluated_criteria[criterion_id] = {
            "criterion_id": criterion_id,
            "criterion": rubric_point["criterion"],
            "description": rubric_point["description"],
            "maximum_score": maximum_score,
            "awarded_score": criterion.awarded_score,
            "evidence": evidence,
        }

    if set(evaluated_criteria) != set(RUBRIC_MAX_SCORES):
        raise ValueError("The evaluation must score every rubric criterion exactly once.")

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
        screening_facts=evaluation.screening_facts,
        red_flags=red_flags,
        extracted_expected_ctc_lpa=extracted_expected_ctc_lpa,
        extracted_current_ctc_lpa=evaluation.extracted_current_ctc_lpa,
        extracted_notice_period_days=extracted_notice_period_days,
    )