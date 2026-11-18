from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    database_url: str
    gemini_api_key: str
    gemini_api_key_2: str
    jwt_secret_key: str | None = None
    access_token_expire_minutes: int = Field(default=30, gt=0)
    deepgram_stt_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_fallback_models: list[str] = Field(default_factory=lambda: ["gemini-3.5-flash", "gemini-3.1-flash-lite"])
    hr_salary_min_lpa: float | None = Field(default=None, ge=0)
    hr_salary_max_lpa: float | None = Field(default=None, ge=0)
    hr_notice_max_days: int = Field(default=60, ge=0)

    @model_validator(mode="after")
    def validate_hr_salary_band(self):
        if (self.hr_salary_min_lpa is None) != (self.hr_salary_max_lpa is None):
            raise ValueError(
                "Configure both HR_SALARY_MIN_LPA and HR_SALARY_MAX_LPA, or neither."
            )
        if (
            self.hr_salary_min_lpa is not None
            and self.hr_salary_max_lpa is not None
            and self.hr_salary_min_lpa > self.hr_salary_max_lpa
        ):
            raise ValueError("HR_SALARY_MIN_LPA must not exceed HR_SALARY_MAX_LPA.")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()