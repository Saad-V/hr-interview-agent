import uuid
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class HRSectionScore(BaseModel):
    category: str
    title: str
    weight: int
    score_percentage: float
    points_awarded: int
    points_maximum: int


class HRCompetencyScore(BaseModel):
    criterion_id: str
    label: str
    points_awarded: int
    points_maximum: int
    score_percentage: float


class HRScorecard(BaseModel):
    weighted_score_percentage: float
    sections: list[HRSectionScore]
    criteria: list[HRCompetencyScore]


class HRScreeningSummary(BaseModel):
    approved_min_lpa: float | None = None
    approved_max_lpa: float | None = None
    candidate_expected_lpa: float | None = None
    candidate_current_ctc_lpa: float | None = None
    salary_alignment_status: Literal[
        "NOT_CONFIGURED",
        "NOT_DISCLOSED",
        "OUTSIDE_BAND",
        "BELOW_BAND",
        "WITHIN_BAND",
    ]
    salary_evidence: str | None = None
    max_notice_days: int
    candidate_notice_days: int | None = None
    notice_alignment_status: Literal[
        "NOT_DISCLOSED",
        "EXCEEDS_POLICY",
        "ALIGNED",
    ]
    notice_evidence: str | None = None
    policy_configured: bool
    red_flags: list[dict[str, object]] = Field(default_factory=list)
    human_checkpoint_required: bool
    checkpoint_reasons: list[str] = Field(default_factory=list)


class ReportCreate(BaseModel):
    interview_session_id: uuid.UUID
    overall_score: float
    report_json: dict
    pdf_storage_path: str | None = None

    model_config = ConfigDict(from_attributes=True)


class InterviewReportResponse(BaseModel):
    rubric_version: str | None = None
    overall_score: float | None = Field(
        default=None,
        validation_alias=AliasChoices("overall_score", "overall_percentage")
    )
    technical_score: float | None = Field(
        default=None,
        validation_alias=AliasChoices("technical_score", "technical_percentage")
    )
    communication_score: float | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "communication_score",
            "communication_percentage",
        )
    )
    strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "areas_for_improvement",
            "improvements",
            "weaknesses",
        ),
    )
    summary: str = Field(
        default="",
        validation_alias=AliasChoices("summary", "overall_summary"),
    )
    recommendation: str = Field(
        default="",
        validation_alias=AliasChoices("recommendation", "hiring_recommendation"),
    )
    total_awarded_score: int | None = None
    total_maximum_score: int | None = None
    question_count: int | None = None
    unweighted_overall_score: float | None = None
    scorecard: HRScorecard | None = None
    screening_summary: HRScreeningSummary | None = None
    salary_band_check: dict | None = None
    red_flags: list[dict] = Field(default_factory=list)
    human_checkpoint_required: bool = False
    human_checkpoint_reasons: list[str] = Field(default_factory=list)
    candidate_pool: str | None = None