import pytest

from app.ai.prompts import (
    build_answer_evaluation_prompt,
    build_interview_blueprint_prompt,
)
from app.ai.schemas import (
    CandidateProfileSchema,
    InterviewBlueprintSchema,
    JobProfileSchema,
)
from app.core.config import Settings
from app.core.enums import InterviewDifficulty
from app.core.interview_design import (
    INTERVIEW_DESIGN_VERSION,
    RUBRIC_CRITERION_LABELS,
    RUBRIC_MAX_SCORES,
    RUBRIC_VERSION,
    SECTION_TITLES,
    SECTION_WEIGHTS,
    band_lookup_tool,
    evaluate_human_checkpoint,
    recommendation_for_score,
    section_question_counts,
    validate_prohibited_question_guardrail,
)
from app.schemas.screening import CandidateScreeningFacts, EvidenceBackedRedFlag
from app.services.answer_evaluation_service import _validate_screening_facts


def _blueprint_payload() -> dict:
    counts = section_question_counts(4)
    sections = []
    for category, count in counts.items():
        sections.append(
            {
                "category": category,
                "title": SECTION_TITLES[category],
                "objective": f"Assess job-related {category.lower()} evidence.",
                "weight": SECTION_WEIGHTS[category],
                "questions": [
                    {
                        "question": f"Describe a relevant {category.lower()} example.",
                        "difficulty": InterviewDifficulty.EASY,
                        "expected_topics": ["A concrete example"],
                        "follow_up_questions": [],
                        "max_score": 10,
                        "evaluation_points": [
                            {
                                "criterion_id": criterion_id,
                                "criterion": RUBRIC_CRITERION_LABELS[criterion_id],
                                "description": (
                                    f"Assess observable {criterion_id.lower()} "
                                    "evidence from the answer."
                                ),
                                "max_score": max_score,
                            }
                            for criterion_id, max_score in RUBRIC_MAX_SCORES.items()
                        ],
                    }
                    for _ in range(count)
                ],
            }
        )
    return {
        "design_version": INTERVIEW_DESIGN_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "duration_minutes": 10,
        "difficulty": InterviewDifficulty.EASY,
        "overall_focus": ["Job-related screening evidence"],
        "interview_instructions": "Answer with factual work examples.",
        "sections": sections,
    }


@pytest.mark.parametrize(
    "question",
    [
        "How old are you?",
        "What is your religion?",
        "Are you married?",
        "Do you have kids?",
        "Tell me about your medical history.",
        "What is your caste?",
    ],
)
def test_guardrail_rejects_prohibited_personal_questions(question):
    with pytest.raises(ValueError, match="Guardrail Violation"):
        validate_prohibited_question_guardrail(question)


def test_guardrail_uses_word_boundaries_for_incidental_substrings():
    validate_prohibited_question_guardrail(
        "How do you manage package usage at this stage?"
    )


def test_blueprint_schema_applies_hr_titles_weights_and_question_guardrails():
    payload = _blueprint_payload()
    blueprint = InterviewBlueprintSchema.model_validate(payload)
    assert [section.title for section in blueprint.sections] == [
        SECTION_TITLES[category] for category in SECTION_WEIGHTS
    ]

    payload["sections"][0]["questions"][0]["follow_up_questions"] = [
        "What is your date of birth?"
    ]
    with pytest.raises(ValueError, match="Guardrail Violation"):
        InterviewBlueprintSchema.model_validate(payload)


def test_blueprint_prompt_contains_hr_pool_and_final_salary_stage():
    prompt = build_interview_blueprint_prompt(
        candidate_profile=CandidateProfileSchema(),
        job_profile=JobProfileSchema(),
        duration_minutes=10,
        difficulty=InterviewDifficulty.EASY,
    )
    assert "Fresher Candidate Pool (0 years professional experience)" in prompt
    assert SECTION_TITLES["BEHAVIORAL"] in prompt
    assert "20% weight" in prompt
    assert "do not infer protected or demographic traits" in (
        build_answer_evaluation_prompt(
            question={
                "question": "Share an example.",
                "difficulty": "EASY",
                "expected_topics": [],
                "evaluation_points": [],
            },
            candidate_answer="I led a project.",
        )
    )


@pytest.mark.parametrize(
    ("salary", "notice", "salary_status", "notice_status"),
    [
        (None, None, "NOT_DISCLOSED", "NOT_DISCLOSED"),
        (36.0, 60, "OUTSIDE_BAND", "ALIGNED"),
        (12.0, 61, "BELOW_BAND", "EXCEEDS_POLICY"),
        (24.0, 60, "WITHIN_BAND", "ALIGNED"),
    ],
)
def test_band_lookup_reports_salary_and_notice_alignment(
    salary,
    notice,
    salary_status,
    notice_status,
):
    result = band_lookup_tool(
        expected_ctc_lpa=salary,
        min_band_lpa=15,
        max_band_lpa=30,
        stated_notice_days=notice,
    )
    assert result["salary_alignment_status"] == salary_status
    assert result["notice_alignment_status"] == notice_status
    assert result["approved_min_lpa"] == 15
    assert result["approved_max_lpa"] == 30


def test_human_checkpoint_reasons_are_deterministic():
    result = evaluate_human_checkpoint(
        salary_alignment_status="OUTSIDE_BAND",
        notice_alignment_status="EXCEEDS_POLICY",
        red_flags=[{"description": "Conflicting delivery dates"}],
    )
    assert result == {
        "human_checkpoint_required": True,
        "checkpoint_reasons": [
            "Expected salary exceeds approved band — requires human approval.",
            "Notice period exceeds maximum allowed threshold.",
            "1 evidence-backed red flag(s) identified during screening.",
        ],
    }


@pytest.mark.parametrize(
    ("score", "checkpoint", "expected"),
    [
        (85, False, "Pass to Final Round (Strong Fit)"),
        (70, False, "Pass to Final Round"),
        (55, False, "Borderline — Recruiter Review"),
        (54.99, False, "Do Not Pass"),
        (55, True, "Human Checkpoint — Pending Approval"),
        (54.99, True, "Do Not Pass"),
    ],
)
def test_recommendation_thresholds_and_checkpoint(score, checkpoint, expected):
    assert recommendation_for_score(score, checkpoint) == expected


def test_screening_extraction_requires_matching_explicit_answer_evidence():
    facts = CandidateScreeningFacts(
        expected_ctc_lpa=18.5,
        salary_evidence="I expect 18.5 LPA",
        stated_notice_days=45,
        notice_evidence="My notice is 45 days",
        red_flags=[
            EvidenceBackedRedFlag(
                description="The answer gives conflicting timelines.",
                evidence="I said the launch was in May, but later said June.",
            )
        ],
    )
    _validate_screening_facts(
        facts,
        "I expect 18.5 LPA. My notice is 45 days. "
        "I said the launch was in May, but later said June.",
    )

    unsupported = CandidateScreeningFacts(
        expected_ctc_lpa=18.5,
        salary_evidence="I expect 18.5 LPA",
    )
    with pytest.raises(ValueError, match="evidence must quote"):
        _validate_screening_facts(unsupported, "I expect 20 LPA.")


def test_settings_require_salary_band_bounds_to_be_configured_together():
    with pytest.raises(ValueError, match="both HR_SALARY_MIN_LPA"):
        Settings(
            database_url="postgresql://example",
            gemini_api_key="key",
            gemini_api_key_2="key2",
            hr_salary_min_lpa=10,
        )
    with pytest.raises(ValueError, match="must not exceed"):
        Settings(
            database_url="postgresql://example",
            gemini_api_key="key",
            gemini_api_key_2="key2",
            hr_salary_min_lpa=20,
            hr_salary_max_lpa=10,
        )
