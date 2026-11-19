from pydantic import BaseModel, Field, model_validator


class EvidenceBackedRedFlag(BaseModel):
    description: str = Field(min_length=8, max_length=300)
    evidence: str = Field(default="", max_length=500)


class CandidateScreeningFacts(BaseModel):
    expected_ctc_lpa: float | None = Field(default=None, ge=0)
    salary_evidence: str | None = Field(default=None, max_length=500)
    stated_notice_days: int | None = Field(default=None, ge=0)
    notice_evidence: str | None = Field(default=None, max_length=500)
    red_flags: list[EvidenceBackedRedFlag] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence_for_extracted_values(self):
        if (self.expected_ctc_lpa is None) != (self.salary_evidence is None):
            raise ValueError("Expected CTC and its answer evidence must be provided together.")
        if (self.stated_notice_days is None) != (self.notice_evidence is None):
            raise ValueError(
                "Notice period and its answer evidence must be provided together."
            )
        return self
