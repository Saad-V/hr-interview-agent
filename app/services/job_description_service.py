from pathlib import Path
import uuid
from typing import Iterable

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession
from app.models.job_description import JobDescription
from app.repositories.job_description_repository import JobDescriptionRepository
from app.schemas.job_description import (
    HRPolicyConfigRequest,
    JobDescriptionCreate,
)
from app.utils.file_storage import (
    save_job_description_file,
    save_job_description_text_file,
)

VALID_JOB_DESCRIPTION_EXTENSIONS = {".pdf", ".docx"}
MAX_JOB_DESCRIPTION_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_STORAGE_PROVIDER = "local"

repository = JobDescriptionRepository()


def _validate_job_description_extension(filename: str, allowed_extensions: Iterable[str] = VALID_JOB_DESCRIPTION_EXTENSIONS) -> str:
    extension = Path(filename).suffix.lower()
    if not extension:
        raise HTTPException(status_code=400, detail="Job description file must have a valid file extension.")
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid job description extension '{extension}'. "
                f"Allowed extensions: {', '.join(sorted(allowed_extensions))}."
            ),
        )
    return extension


def _validate_job_description_file_size(file: UploadFile, max_bytes: int = MAX_JOB_DESCRIPTION_FILE_SIZE) -> int:
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Job description file size exceeds the {max_bytes // (1024 * 1024)} MB limit. "
                f"Uploaded file size is {size} bytes."
            ),
        )
    return size


def create_job_description(
    db: Session,
    interview_session_id: uuid.UUID,
    file: UploadFile,
    owner_id: uuid.UUID,
) -> JobDescription:
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing.")
    _validate_job_description_extension(file.filename)
    file_size = _validate_job_description_file_size(file)

    session_exists = (
        db.query(InterviewSession)
        .filter_by(id=interview_session_id, user_id=owner_id)
        .first()
    )
    if session_exists is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found.",
        )

    storage_path = save_job_description_file(interview_session_id, file)

    job_description_create = JobDescriptionCreate(
        interview_session_id=interview_session_id,
        original_filename=file.filename,
        storage_path=str(storage_path),
        mime_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        raw_text=None,
    )

    return repository.create(db, job_description_create)


def create_hr_policy_job_description(
    db: Session,
    interview_session_id: uuid.UUID,
    policy: HRPolicyConfigRequest,
    owner_id: uuid.UUID,
) -> JobDescription:
    session_exists = (
        db.query(InterviewSession)
        .filter_by(id=interview_session_id, user_id=owner_id)
        .first()
    )
    if session_exists is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found.",
        )

    policy_text = "\n".join(
        [
            "HR Policy and Role Requirements",
            f"Role title: {policy.role_title}",
            (
                "Approved salary band: "
                f"{policy.min_salary_lpa:g} to {policy.max_salary_lpa:g} LPA"
            ),
            f"Maximum notice period: {policy.max_notice_period_days} days",
            f"Work location: {policy.work_location}",
            "Role requirements:",
            policy.role_requirements.strip() or "Not specified.",
        ]
    )
    storage_path = save_job_description_text_file(
        interview_session_id,
        policy_text,
    )
    job_description_create = JobDescriptionCreate(
        interview_session_id=interview_session_id,
        original_filename="hr_policy.docx",
        storage_path=str(storage_path),
        mime_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        file_size=storage_path.stat().st_size,
        raw_text=policy_text,
    )
    return repository.create_or_update(db, job_description_create)
