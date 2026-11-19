import uuid

from pydantic import BaseModel, Field, model_validator

from app.core.enums import InterviewDifficulty
from app.core.interview_design import (
    INTERVIEW_DESIGN_VERSION,
    QUESTION_MAX_SCORE,
    RUBRIC_CRITERION_LABELS,
    RUBRIC_MAX_SCORES,
    RUBRIC_VERSION,
    SECTION_TITLES,
    SECTION_WEIGHTS,
    InterviewSectionCategory,
    RubricCriterionId,
    question_count_for_duration,
    section_question_counts,
    validate_prohibited_question_guardrail,
)
from app.schemas.screening import CandidateScreeningFacts


# ----------------------------
# Candidate Profile
# ----------------------------

class Education(BaseModel):
    degree: str | None = None
    specialization: str | None = None
    institution: str | None = None
    cgpa: float | None = None


class Project(BaseModel):
    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)


class CandidateProfileSchema(BaseModel):
    summary: str = ""
    education: Education = Field(default_factory=Education)
    skills: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


# ----------------------------
# Job Profile
# ----------------------------

class HRPolicyBandSchema(BaseModel):
    min_salary_lpa: float = 6.0
    max_salary_lpa: float = 12.0
    currency: str = "INR"
    max_notice_period_days: int = 30
    work_location: str = "Hybrid / Onsite"


class JobProfileSchema(BaseModel):
    role: str = ""
    summary: str = ""
    required_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    education_requirement: str | None = None
    experience_requirement: str | None = None
    hr_policy: HRPolicyBandSchema = Field(default_factory=HRPolicyBandSchema)


# ----------------------------
# Interview Blueprint
# ----------------------------

class EvaluationPointSchema(BaseModel):
    criterion_id: RubricCriterionId
    criterion: str = Field(min_length=3)
    description: str = Field(min_length=10)
    max_score: int

    @model_validator(mode="after")
    def validate_score_limit(self):
        expected = RUBRIC_MAX_SCORES[self.criterion_id.value]
        if self.max_score != expected:
            raise ValueError(
                f"{self.criterion_id.value} must be worth exactly {expected} points."
            )
        expected_label = RUBRIC_CRITERION_LABELS[self.criterion_id.value]
        if self.criterion != expected_label:
            raise ValueError(
                f"{self.criterion_id.value} must use the label {expected_label!r}."
            )
        return self


class InterviewQuestionSchema(BaseModel):
    question: str = Field(min_length=10)
    difficulty: InterviewDifficulty
    expected_topics: list[str] = Field(min_length=1)
    follow_up_questions: list[str] = Field(default_factory=list)
    max_score: int = Field(ge=QUESTION_MAX_SCORE, le=QUESTION_MAX_SCORE)
    evaluation_points: list[EvaluationPointSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rubric(self):
        validate_prohibited_question_guardrail(self.question)
        for follow_up in self.follow_up_questions:
            validate_prohibited_question_guardrail(follow_up)
        if self.max_score != QUESTION_MAX_SCORE:
            raise ValueError(f"Every question must be worth {QUESTION_MAX_SCORE} points.")
        expected = set(RubricCriterionId)
        actual = {point.criterion_id for point in self.evaluation_points}
        if len(self.evaluation_points) != len(expected) or actual != expected:
            raise ValueError("Every question must define each rubric criterion exactly once.")
        return self


class InterviewSectionSchema(BaseModel):
    category: InterviewSectionCategory
    title: str
    objective: str
    weight: int
    questions: list[InterviewQuestionSchema] = Field(default_factory=list)


class InterviewBlueprintSchema(BaseModel):
    design_version: str = INTERVIEW_DESIGN_VERSION
    rubric_version: str = RUBRIC_VERSION
    duration_minutes: int
    difficulty: InterviewDifficulty
    overall_focus: list[str] = Field(default_factory=list)
    interview_instructions: str
    sections: list[InterviewSectionSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_design(self):
        if self.design_version != INTERVIEW_DESIGN_VERSION:
            raise ValueError("Interview blueprint uses an unsupported design version.")
        if self.rubric_version != RUBRIC_VERSION:
            raise ValueError("Interview blueprint uses an unsupported scoring rubric.")

        expected_counts = section_question_counts(
            question_count_for_duration(self.duration_minutes)
        )
        sections = {section.category.value: section for section in self.sections}
        if set(sections) != set(expected_counts):
            raise ValueError("Blueprint must contain each required interview section exactly once.")
        if [section.category.value for section in self.sections] != list(SECTION_WEIGHTS):
            raise ValueError("Interview sections must be returned in the required order.")

        seen_questions = set()
        for category, expected_count in expected_counts.items():
            section = sections[category]
            if section.title != SECTION_TITLES[category]:
                raise ValueError(f"{category} has an invalid HR workflow title.")
            if len(section.questions) != expected_count:
                raise ValueError(
                    f"{category} must contain exactly {expected_count} questions."
                )
            if section.weight != SECTION_WEIGHTS[category]:
                raise ValueError(f"{category} has an invalid section weight.")
            if any(question.difficulty != self.difficulty for question in section.questions):
                raise ValueError("Every question must match the selected interview difficulty.")
            for question in section.questions:
                normalized_question = " ".join(question.question.casefold().split())
                if normalized_question in seen_questions:
                    raise ValueError("Interview blueprint contains duplicate questions.")
                seen_questions.add(normalized_question)
        return self


class InterviewReportNarrativeSchema(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)
    summary: str


class CriterionEvaluationSchema(BaseModel):
    criterion_id: RubricCriterionId
    awarded_score: int = Field(ge=0, le=max(RUBRIC_MAX_SCORES.values()))
    evidence: str


class RedFlagItemSchema(BaseModel):
    category: str = Field(
        description=(
            "e.g. BACKGROUND_GAP, NOTICE_PERIOD_RISK, CULTURE_CONCERN, "
            "COMPENSATION_MISMATCH"
        )
    )
    description: str
    evidence: str = Field(
        description="Exact verbatim quote from the candidate answer supporting this red flag."
    )


class AnswerEvaluationSchema(BaseModel):
    criteria: list[CriterionEvaluationSchema]
    feedback: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)
    suggested_improvement: str
    screening_facts: CandidateScreeningFacts = Field(
        default_factory=CandidateScreeningFacts
    )
    red_flags: list[RedFlagItemSchema] = Field(default_factory=list)
    extracted_expected_ctc_lpa: float | None = Field(
        default=None,
        description=(
            "Candidate's stated expected annual salary/CTC in LPA "
            "(Lakhs Per Annum) if mentioned in this answer, otherwise null."
        ),
    )
    extracted_current_ctc_lpa: float | None = Field(
        default=None,
        description=(
            "Candidate's stated current annual salary/CTC in LPA if mentioned, "
            "otherwise null."
        ),
    )
    extracted_notice_period_days: int | None = Field(
        default=None,
        description=(
            "Candidate's stated notice period in days (e.g. immediate=0, "
            "1 month=30, 2 months=60) if mentioned, otherwise null."
        ),
    )