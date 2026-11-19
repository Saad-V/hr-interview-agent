from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HRPolicyConfigRequest(BaseModel):
    role_title: str = Field(min_length=1)
    min_salary_lpa: float = Field(ge=0)
    max_salary_lpa: float = Field(gt=0)
    max_notice_period_days: int = Field(ge=0)
    work_location: str = "Hybrid / Bengaluru"
    role_requirements: str = ""

    @model_validator(mode="after")
    def validate_policy(self):
        if not self.role_title.strip():
            raise ValueError("Role title must not be blank.")
        if self.min_salary_lpa > self.max_salary_lpa:
            raise ValueError("Minimum salary must not exceed maximum salary.")
        return self


class JobDescriptionCreate(BaseModel):
    interview_session_id: uuid.UUID
    original_filename: str
    storage_path: str
    mime_type: str
    file_size: int
    raw_text: str | None



class JobDescriptionResponse(BaseModel):
    id: uuid.UUID
    interview_session_id: uuid.UUID
    original_filename: str
    storage_path: str
    mime_type: str
    file_size: int
    raw_text: str | None
    model_config = ConfigDict(from_attributes=True)
