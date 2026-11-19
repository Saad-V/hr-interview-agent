import csv
import io
from pathlib import Path
import uuid
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from app.ai.prompts import (
    INTERVIEW_BLUEPRINT_SYSTEM_PROMPT,
    INTERVIEW_EVALUATION_SYSTEM_PROMPT,
    INTERVIEW_REPORT_SYSTEM_PROMPT,
    JOB_PROFILE_SYSTEM_PROMPT,
    build_answer_evaluation_prompt,
    build_interview_blueprint_prompt,
)
from app.ai.schemas import (
    AnswerEvaluationSchema,
    CandidateProfileSchema,
    HRPolicyBandSchema,
    InterviewBlueprintSchema,
    JobProfileSchema,
    RedFlagItemSchema,
)
from app.ai import llm
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
    calculate_hr_scorecard,
    evaluate_human_checkpoint,
    recommendation_for_score,
    section_question_counts,
    validate_prohibited_question_guardrail,
)
from app.schemas.screening import CandidateScreeningFacts, EvidenceBackedRedFlag
from app.schemas.report import InterviewReportResponse
from app.schemas.job_description import HRPolicyConfigRequest
from app.services.ats_export_service import build_ats_export_csv
from app.services.answer_evaluation_service import (
    _validate_red_flag_evidence,
    _validate_screening_facts,
    evaluate_answer,
)
from app.services.hr_screening_service import build_hr_screening_result
from app.services.document_parser_service import extract_text
from app.services.interview_service import _build_hr_policy_screening
from app.services import interview_service
from app.services import interview_report_service
from app.services.job_description_service import create_hr_policy_job_description
from app.utils import file_storage


def test_gemini_client_has_bounded_timeout_and_no_sdk_retries(monkeypatch):
    client_options = []

    class FakeClient:
        pass

    def create_client(**kwargs):
        client_options.append(kwargs)
        return FakeClient()

    monkeypatch.setattr(llm.genai, "Client", create_client)
    llm._create_client("test-key")

    http_options = client_options[0]["http_options"]
    assert http_options.timeout == llm.GEMINI_REQUEST_TIMEOUT_MS
    assert http_options.retry_options.attempts == 1


def test_gemini_503_retries_then_uses_fallback_model(monkeypatch):
    class Result(BaseModel):
        value: str

    monkeypatch.setattr(llm.settings, "gemini_model", "primary")
    monkeypatch.setattr(llm.settings, "gemini_fallback_models", ["fallback"])
    monkeypatch.setattr(llm, "_client_for_attempt", lambda attempt: attempt)
    delays = []
    monkeypatch.setattr(llm.time, "sleep", delays.append)
    calls = []

    def generate(**kwargs):
        calls.append((kwargs["model"], kwargs["client"]))
        if kwargs["model"] == "primary":
            raise llm.errors.ServerError(503, {"error": {"message": "Unavailable"}})
        return Result(value="fallback response")

    monkeypatch.setattr(llm, "_try_generate", generate)
    result = llm.generate_structured_output(
        system_prompt="",
        user_prompt="",
        response_schema=Result,
    )

    assert result.value == "fallback response"
    assert calls == [
        ("primary", 0),
        ("primary", 1),
        ("primary", 2),
        ("fallback", 0),
    ]
    assert delays == [5, 10]


def test_gemini_generation_error_reports_exhausted_models(monkeypatch):
    class Result(BaseModel):
        value: str

    monkeypatch.setattr(llm.settings, "gemini_model", "primary")
    monkeypatch.setattr(llm.settings, "gemini_fallback_models", ["fallback"])
    monkeypatch.setattr(llm, "_client_for_attempt", lambda attempt: attempt)
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    attempted_models = []

    def fail_with_deadline(**kwargs):
        attempted_models.append(kwargs["model"])
        raise llm.errors.ServerError(
            504,
            {"error": {"code": 504, "status": "DEADLINE_EXCEEDED"}},
        )

    monkeypatch.setattr(llm, "_try_generate", fail_with_deadline)
    with pytest.raises(llm.LLMGenerationError) as exc_info:
        llm.generate_structured_output(
            system_prompt="",
            user_prompt="",
            response_schema=Result,
        )

    assert attempted_models == ["primary", "fallback"]
    assert isinstance(exc_info.value.__cause__, llm.errors.ServerError)


def test_report_uses_rubric_fallback_when_gemini_models_fail(monkeypatch):
    monkeypatch.setattr(
        interview_report_service,
        "generate_structured_output",
        Mock(side_effect=llm.LLMGenerationError("models unavailable")),
    )
    conversation_turns = [
        {
            "evaluation": {
                "criteria": [
                    {
                        "criterion_id": "ACCURACY",
                        "criterion": "Accuracy",
                        "awarded_score": 4,
                        "maximum_score": 4,
                    },
                    {
                        "criterion_id": "COMMUNICATION",
                        "criterion": "Communication",
                        "awarded_score": 1,
                        "maximum_score": 4,
                    },
                ]
            }
        }
    ]

    narrative = interview_report_service.generate_interview_report(
        blueprint={},
        conversation_turns=conversation_turns,
    )

    assert narrative.summary.startswith(
        "Across 1 evaluated answers, the candidate earned 5/8 rubric points (62.5%)."
    )
    assert narrative.strengths == ["Accuracy: scored 4/4 points."]
    assert narrative.areas_for_improvement == [
        "Communication: scored 1/4 points."
    ]


def test_final_report_fallback_failure_returns_retryable_503(monkeypatch):
    interview = Mock(
        status=interview_service.InterviewStatus.IN_PROGRESS,
        difficulty=InterviewDifficulty.EASY,
    )
    blueprint = Mock(
        blueprint_json={
            "rubric_version": RUBRIC_VERSION,
            "sections": [
                {
                    "title": "Introduction",
                    "questions": [{"question": "Tell me about yourself."}],
                }
            ],
        }
    )
    evaluation = Mock()
    evaluation.model_dump.return_value = {"red_flags": []}
    candidate_profile = Mock()
    job_profile = Mock(profile_json={})
    scorecard = Mock(weighted_score_percentage=75)
    scorecard_schema = Mock()
    scorecard_schema.model_validate.return_value = scorecard

    monkeypatch.setattr(
        interview_service.interview_repository,
        "get_by_id",
        Mock(return_value=interview),
    )
    monkeypatch.setattr(
        interview_service.interview_blueprint_repository,
        "get_by_session_id",
        Mock(return_value=blueprint),
    )
    monkeypatch.setattr(
        interview_service.conversation_turn_repository,
        "get_last_turn",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        interview_service.conversation_turn_repository,
        "get_by_session_id",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(
        interview_service.candidate_profile_repository,
        "get_by_session_id",
        Mock(return_value=candidate_profile),
    )
    monkeypatch.setattr(
        interview_service.job_profile_repository,
        "get_by_session_id",
        Mock(return_value=job_profile),
    )
    monkeypatch.setattr(
        interview_service.conversation_turn_repository,
        "create",
        Mock(),
    )
    monkeypatch.setattr(interview_service, "evaluate_answer", Mock(return_value=evaluation))
    monkeypatch.setattr(
        interview_service,
        "calculate_report_scores",
        Mock(return_value={"overall_score": 75}),
    )
    monkeypatch.setattr(interview_service, "calculate_hr_scorecard", Mock(return_value={}))
    monkeypatch.setattr(interview_service, "HRScorecard", scorecard_schema)
    monkeypatch.setattr(
        interview_service,
        "_build_hr_policy_screening",
        Mock(return_value=(None, [], Mock(), False, [])),
    )
    monkeypatch.setattr(
        interview_service,
        "generate_interview_report",
        Mock(side_effect=llm.LLMGenerationError("models unavailable")),
    )
    db = Mock()

    with pytest.raises(interview_service.HTTPException) as exc_info:
        interview_service.submit_answer(
            db=db,
            interview_session_id=uuid.uuid4(),
            answer="My answer.",
        )

    assert exc_info.value.status_code == 503
    assert db.commit.call_count == 2
    interview_service.conversation_turn_repository.create.assert_not_called()


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

    payload["sections"][0]["questions"][0]["follow_up_questions"] = []
    payload["sections"][0]["questions"][0]["question"] = "How old are you?"
    with pytest.raises(ValueError, match="Guardrail Violation"):
        InterviewBlueprintSchema.model_validate(payload)


def test_job_profile_has_default_hr_policy_band():
    policy = JobProfileSchema().hr_policy
    assert policy == HRPolicyBandSchema(
        min_salary_lpa=6.0,
        max_salary_lpa=12.0,
        currency="INR",
        max_notice_period_days=30,
        work_location="Hybrid / Onsite",
    )


def test_legacy_report_defaults_new_hr_scorecard_fields():
    report = InterviewReportResponse.model_validate({"summary": "Legacy report"})
    assert report.salary_band_check is None
    assert report.red_flags == []
    assert report.human_checkpoint_required is False
    assert report.human_checkpoint_reasons == []
    assert report.candidate_pool is None


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


def test_hr_prompts_specify_policy_workflow_extraction_and_report_scope():
    assert "min_salary_lpa" in JOB_PROFILE_SYSTEM_PROMPT
    assert "6.0 and 12.0 LPA" in JOB_PROFILE_SYSTEM_PROMPT
    assert "30 days" in JOB_PROFILE_SYSTEM_PROMPT

    blueprint = build_interview_blueprint_prompt(
        candidate_profile=CandidateProfileSchema(),
        job_profile=JobProfileSchema(),
        duration_minutes=10,
        difficulty=InterviewDifficulty.EASY,
    )
    expected_titles = [
        "01 / VERIFY: Background, Notice Period & Availability",
        "02 / STAR PROJECTS: Past Project Probing",
        "03 / ASSESS: Motivation, Communication & Culture Fit",
        "04 / SALARY: Compensation Band & Final Logistics",
    ]
    assert [blueprint.index(title) for title in expected_titles] == sorted(
        blueprint.index(title) for title in expected_titles
    )
    assert "Do not ask current CTC" in blueprint
    assert "employer buyout" in blueprint
    assert "STRICT GUARDRAIL" in blueprint
    assert "ACCURACY (4)" in blueprint

    assert "extracted_expected_ctc_lpa" in INTERVIEW_EVALUATION_SYSTEM_PROMPT
    assert '"8 to 10 lakhs" -> 10.0' in INTERVIEW_EVALUATION_SYSTEM_PROMPT
    assert '"immediate" -> 0' in INTERVIEW_EVALUATION_SYSTEM_PROMPT
    assert "verbatim substring quote" in INTERVIEW_EVALUATION_SYSTEM_PROMPT
    assert "confidential, structured" in INTERVIEW_REPORT_SYSTEM_PROMPT
    assert "STAR project competency" in INTERVIEW_REPORT_SYSTEM_PROMPT


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


def test_candidate_screening_facts_requires_value_and_evidence_together():
    with pytest.raises(ValueError, match="must be provided together"):
        CandidateScreeningFacts(expected_ctc_lpa=18.5)


@pytest.mark.parametrize(
    ("notice_days", "evidence", "answer"),
    [
        (0, "I am available immediately", "I am available immediately."),
        (15, "I have 15 days' notice", "I have 15 days' notice."),
        (30, "My notice period is 1 month", "My notice period is 1 month."),
        (60, "My notice period is 2 months", "My notice period is 2 months."),
        (90, "My notice period is 90 days", "My notice period is 90 days."),
    ],
)
def test_notice_extraction_accepts_days_months_and_immediate(
    notice_days,
    evidence,
    answer,
):
    _validate_screening_facts(
        CandidateScreeningFacts(
            stated_notice_days=notice_days,
            notice_evidence=evidence,
        ),
        answer,
    )


def test_notice_extraction_rejects_mismatched_converted_months():
    with pytest.raises(ValueError, match="must match"):
        _validate_screening_facts(
            CandidateScreeningFacts(
                stated_notice_days=60,
                notice_evidence="My notice period is 1 month",
            ),
            "My notice period is 1 month.",
        )


def test_red_flag_validation_normalizes_quotes_and_discards_hallucinations():
    valid_flag = RedFlagItemSchema(
        category="BACKGROUND_GAP",
        description="The candidate gives conflicting timelines.",
        evidence="i LEFT in   March.",
    )
    unsupported_flag = RedFlagItemSchema(
        category="CULTURE_CONCERN",
        description="Unsupported concern.",
        evidence="I refused to work with the team.",
    )
    validated = _validate_red_flag_evidence(
        [valid_flag, unsupported_flag],
        "I left in March. I started my next role in April.",
    )
    assert len(validated) == 1
    assert validated[0].category == "BACKGROUND_GAP"


def test_hr_policy_submission_saves_extractable_docx_and_job_description(
    tmp_path,
    monkeypatch,
):
    session_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    db = Mock()
    db.query.return_value.filter_by.return_value.first.return_value = object()
    repository = Mock()
    repository.create_or_update.side_effect = lambda _db, document: document

    monkeypatch.setattr(file_storage, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        "app.services.job_description_service.repository",
        repository,
    )

    policy = HRPolicyConfigRequest(
        role_title="HR Coordinator",
        min_salary_lpa=6,
        max_salary_lpa=12,
        max_notice_period_days=30,
        work_location="Hybrid / Bengaluru",
        role_requirements="Coordinate interviews.\nMaintain candidate records.",
    )
    result = create_hr_policy_job_description(
        db=db,
        interview_session_id=session_id,
        policy=policy,
        owner_id=owner_id,
    )

    assert Path(result.storage_path).suffix == ".docx"
    extracted_text = extract_text(Path(result.storage_path))
    assert "Role title: HR Coordinator" in extracted_text
    assert "Approved salary band: 6 to 12 LPA" in extracted_text
    assert "Maximum notice period: 30 days" in extracted_text
    assert "Coordinate interviews." in extracted_text
    assert result.raw_text == extracted_text
    repository.create_or_update.assert_called_once()


def test_final_hr_screening_uses_job_policy_and_aggregates_all_turns():
    salary_band_check, red_flags, summary, checkpoint_required, reasons = (
        _build_hr_policy_screening(
            [
                {
                    "extracted_expected_ctc_lpa": 25,
                    "extracted_current_ctc_lpa": 18,
                    "extracted_notice_period_days": 45,
                    "screening_facts": {
                        "salary_evidence": "My expected CTC is 25 LPA.",
                        "notice_evidence": "My notice is 45 days.",
                    },
                    "red_flags": [
                        {
                            "category": "BACKGROUND_GAP",
                            "description": "Timeline conflict.",
                            "evidence": "I left in March.",
                        }
                    ],
                },
                {
                    "extracted_expected_ctc_lpa": None,
                    "extracted_notice_period_days": None,
                    "screening_facts": {},
                    "red_flags": [
                        {
                            "category": "CULTURE_CONCERN",
                            "description": "Hostile description of collaboration.",
                            "evidence": "I refused to work with them.",
                        }
                    ],
                },
            ],
            [2, 3],
            {
                "hr_policy": {
                    "min_salary_lpa": 10,
                    "max_salary_lpa": 20,
                    "max_notice_period_days": 30,
                    "work_location": "Onsite",
                }
            },
        )
    )

    assert salary_band_check["salary_alignment_status"] == "OUTSIDE_BAND"
    assert salary_band_check["notice_alignment_status"] == "EXCEEDS_POLICY"
    assert salary_band_check["candidate_current_ctc_lpa"] == 18
    assert [flag["turn_number"] for flag in red_flags] == [2, 3]
    assert checkpoint_required is True
    assert len(reasons) == 3
    assert summary.policy_configured is True
    assert summary.salary_evidence == "My expected CTC is 25 LPA."


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


def test_hr_scorecard_applies_stage_weights_to_stage_percentages():
    scores_by_section = {
        "INTRODUCTION": [4, 2, 2, 2],
        "PROJECTS": [4, 2, 1, 1],
        "TECHNICAL": [2, 1, 1, 2],
        "BEHAVIORAL": [1, 1, 0, 2],
    }
    answers = []
    for category, scores in scores_by_section.items():
        answers.append({
            "section_title": SECTION_TITLES[category],
            "evaluation": {
                "criteria": [
                    {
                        "criterion_id": criterion_id,
                        "awarded_score": scores[index],
                    }
                    for index, criterion_id in enumerate(RUBRIC_MAX_SCORES)
                ]
            },
        })

    scorecard = calculate_hr_scorecard(answers)
    assert scorecard["weighted_score_percentage"] == 71.0
    assert [
        section["category"] for section in scorecard["sections"]
    ] == list(SECTION_WEIGHTS)


def test_hr_screening_checks_salary_notice_and_evidence_flags():
    result = build_hr_screening_result(
        [
            {
                "turn_number": 4,
                "section_title": SECTION_TITLES["BEHAVIORAL"],
                "evaluation": {
                    "screening_facts": {
                        "expected_ctc_lpa": 35.0,
                        "salary_evidence": "My expected CTC is 35 LPA",
                        "stated_notice_days": 75,
                        "notice_evidence": "I have a 75 days notice",
                        "red_flags": [
                            {
                                "description": "Conflicting delivery timelines.",
                                "evidence": "The release was in May, then I said June.",
                            }
                        ],
                    }
                },
            }
        ],
        min_band_lpa=15,
        max_band_lpa=30,
        max_notice_days=60,
    )
    assert result["salary_alignment_status"] == "OUTSIDE_BAND"
    assert result["notice_alignment_status"] == "EXCEEDS_POLICY"
    assert result["human_checkpoint_required"] is True
    assert len(result["red_flags"]) == 1


def test_hr_screening_aggregates_new_extraction_and_categorized_flags():
    result = build_hr_screening_result(
        [
            {
                "turn_number": 3,
                "section_title": SECTION_TITLES["BEHAVIORAL"],
                "evaluation": {
                    "extracted_expected_ctc_lpa": 24.0,
                    "extracted_current_ctc_lpa": 18.0,
                    "extracted_notice_period_days": 45,
                    "red_flags": [
                        {
                            "category": "COMPENSATION_MISMATCH",
                            "description": "Candidate's expectation exceeds policy.",
                            "evidence": "My expected CTC is 24 LPA.",
                        }
                    ],
                    "screening_facts": {
                        "salary_evidence": "My expected CTC is 24 LPA.",
                        "notice_evidence": "My notice is 45 days.",
                    },
                },
            }
        ],
        min_band_lpa=15,
        max_band_lpa=20,
        max_notice_days=60,
    )
    assert result["candidate_expected_lpa"] == 24.0
    assert result["candidate_current_ctc_lpa"] == 18.0
    assert result["candidate_notice_days"] == 45
    assert result["salary_alignment_status"] == "OUTSIDE_BAND"
    assert result["red_flags"][0]["category"] == "COMPENSATION_MISMATCH"
    assert result["red_flags"][0]["turn_number"] == 3


def test_missing_salary_band_is_visible_and_does_not_claim_alignment():
    result = build_hr_screening_result(
        [],
        min_band_lpa=None,
        max_band_lpa=None,
        max_notice_days=60,
    )
    assert result["salary_alignment_status"] == "NOT_CONFIGURED"
    assert result["policy_configured"] is False
    assert result["human_checkpoint_required"] is False


def test_notice_limit_still_triggers_without_a_configured_salary_band():
    result = build_hr_screening_result(
        [
            {
                "turn_number": 1,
                "section_title": SECTION_TITLES["INTRODUCTION"],
                "evaluation": {
                    "screening_facts": {
                        "stated_notice_days": 75,
                        "notice_evidence": "My notice is 75 days",
                    }
                },
            }
        ],
        min_band_lpa=None,
        max_band_lpa=None,
        max_notice_days=60,
    )
    assert result["salary_alignment_status"] == "NOT_CONFIGURED"
    assert result["notice_alignment_status"] == "EXCEEDS_POLICY"
    assert result["human_checkpoint_required"] is True


def test_ats_export_contains_summary_without_answer_evidence():
    content = build_ats_export_csv(
        candidate_reference="session-123",
        completed_at="2026-11-19T00:00:00+00:00",
        difficulty_pool="MEDIUM",
        report_data={
            "overall_score": 78.25,
            "recommendation": "Pass to Final Round",
            "screening_summary": {
                "human_checkpoint_required": False,
                "checkpoint_reasons": [],
                "approved_min_lpa": 15,
                "approved_max_lpa": 30,
                "candidate_expected_lpa": 24,
                "candidate_current_ctc_lpa": 18,
                "salary_alignment_status": "WITHIN_BAND",
                "max_notice_days": 60,
                "candidate_notice_days": 45,
                "notice_alignment_status": "ALIGNED",
                "red_flags": [
                    {
                        "description": "Sensitive internal concern",
                        "evidence": "Do not export this answer quote",
                    }
                ],
            },
            "scorecard": {
                "sections": [
                    {
                        "category": "INTRODUCTION",
                        "score_percentage": 80,
                        "weight": 20,
                    }
                ]
            },
        },
    )
    row = next(csv.DictReader(io.StringIO(content)))
    assert row["candidate_reference"] == "session-123"
    assert row["weighted_score"] == "78.25"
    assert row["candidate_expected_lpa"] == "24"
    assert row["candidate_current_ctc_lpa"] == "18"
    assert row["salary_alignment_status"] == "WITHIN_BAND"
    assert row["candidate_notice_days"] == "45"
    assert '"INTRODUCTION"' in row["weighted_stage_scores"]
    assert "Do not export this answer quote" not in content
    assert row["evidence_backed_red_flag_count"] == "1"


@pytest.mark.parametrize(
    (
        "candidate_answer",
        "expected_salary",
        "salary_evidence",
        "notice_days",
        "notice_evidence",
        "include_model_evidence",
    ),
    [
        (
            "I built project alpha. My expected CTC is 9 to 10.5 lakh per annum, "
            "and I can join in 2 months.",
            10.5,
            "10.5 lakh",
            60,
            "2 months",
            True,
        ),
        ("I built project alpha.", None, None, None, None, True),
        (
            "I built project alpha. My expected CTC is 9 to 10.5 lakh per annum, "
            "and I can join in 2 months.",
            10.5,
            "10.5 lakh",
            60,
            "2 months",
            False,
        ),
        ("I built project alpha.", None, None, None, None, False),
    ],
)
def test_answer_evaluation_anchors_or_omits_screening_evidence(
    monkeypatch,
    candidate_answer,
    expected_salary,
    salary_evidence,
    notice_days,
    notice_evidence,
    include_model_evidence,
):
    monkeypatch.setattr(llm.settings, "gemini_model", "primary-model")
    monkeypatch.setattr(llm.settings, "gemini_fallback_models", ["fallback-model"])

    def build_evaluation():
        return AnswerEvaluationSchema(
            criteria=[
                {
                    "criterion_id": criterion_id,
                    "awarded_score": 4 if criterion_id == "ACCURACY" else 0,
                    "evidence": "A concise rationale about the candidate's answer."
                    if criterion_id == "ACCURACY"
                    else "Not present in the answer.",
                }
                for criterion_id in RUBRIC_MAX_SCORES
            ],
            feedback="The answer is evaluated against the rubric.",
            suggested_improvement="Provide additional details.",
            screening_facts={
                "expected_ctc_lpa": 10.5,
                "salary_evidence": (
                    "The candidate expects ten point five."
                    if include_model_evidence
                    else None
                ),
                "stated_notice_days": 60,
                "notice_evidence": (
                    "The candidate has a two-month notice."
                    if include_model_evidence
                    else None
                ),
                "red_flags": [
                    {
                        "description": "Unsupported concern.",
                        "evidence": "I refused to work with the team.",
                    }
                ],
            },
            extracted_expected_ctc_lpa=10.5,
            extracted_notice_period_days=60,
            red_flags=[
                {
                    "category": "CULTURE_CONCERN",
                    "description": "Unsupported concern.",
                    "evidence": "I refused to work with the team.",
                }
            ],
        )

    model_calls = []

    def generate_output(**kwargs):
        model_calls.append(kwargs["model"])
        return build_evaluation()

    monkeypatch.setattr(llm, "_try_generate", generate_output)
    question = {
        "question": "Describe a project you worked on.",
        "difficulty": "EASY",
        "expected_topics": ["project"],
        "evaluation_points": [
            {
                "criterion_id": criterion_id,
                "criterion": RUBRIC_CRITERION_LABELS[criterion_id],
                "description": "Evaluate observable candidate evidence.",
                "max_score": score,
            }
            for criterion_id, score in RUBRIC_MAX_SCORES.items()
        ],
    }

    result = evaluate_answer(
        question=question,
        candidate_answer=candidate_answer,
    )

    accuracy = next(
        criterion for criterion in result.criteria
        if criterion.criterion_id == "ACCURACY"
    )
    assert accuracy.evidence == "A concise rationale about the candidate's answer."
    assert result.screening_facts.expected_ctc_lpa == expected_salary
    assert result.screening_facts.salary_evidence == salary_evidence
    assert result.screening_facts.stated_notice_days == notice_days
    assert result.screening_facts.notice_evidence == notice_evidence
    assert result.red_flags == []
    assert model_calls == ["primary-model"]
