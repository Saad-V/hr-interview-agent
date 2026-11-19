from typing import Callable, Type, TypeVar
import json
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
import time
from app.core.config import settings

MAX_ATTEMPTS = 3
INITIAL_DELAY = 5
GEMINI_REQUEST_TIMEOUT_MS = 60_000

T = TypeVar("T", bound=BaseModel)


class OutputValidationError(ValueError):
    pass


class LLMGenerationError(RuntimeError):
    """Raised when every configured model fails to generate valid output."""


def _create_client(api_key: str) -> genai.Client:
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=GEMINI_REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


primary_client = _create_client(settings.gemini_api_key)
secondary_client = (
    _create_client(settings.gemini_api_key_2)
    if settings.gemini_api_key_2
    else primary_client
)


def _build_model_sequence() -> list[str]:
    models = [settings.gemini_model]
    for fallback in settings.gemini_fallback_models:
        if fallback and fallback not in models:
            models.append(fallback)
    return models


def _client_for_attempt(attempt: int) -> genai.Client:
    if attempt == 0 or not settings.gemini_api_key_2:
        return primary_client
    return secondary_client


def _is_retryable_503(exc: Exception) -> bool:
    status_value = getattr(exc, "status", None)
    if status_value is None:
        status_value = getattr(exc, "code", None)
    if isinstance(status_value, int):
        return status_value == 503
    if isinstance(status_value, str):
        normalized = status_value.strip().upper()
        if normalized in {"503", "UNAVAILABLE"}:
            return True
    error_text = str(exc).upper()
    return "503" in error_text and "UNAVAILABLE" in error_text


def _try_generate(
    *,
    client: genai.Client,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_schema: Type[T],
    temperature: float,
) -> T:
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
        ),
    )

    if response.parsed is not None:
        return response.parsed

    raw_text = getattr(response, "text", None)
    if raw_text:
        try:
            return response_schema.model_validate_json(raw_text)
        except Exception:
            try:
                return response_schema.model_validate(json.loads(raw_text))
            except Exception:
                pass

    raise ValueError("Gemini response did not contain a valid parsed model or JSON payload.")


def generate_structured_output(
    *,
    system_prompt: str,
    user_prompt: str,
    response_schema: Type[T],
    temperature: float = 0.2,
    validator: Callable[[T], None] | None = None,
) -> T:
    model_sequence = _build_model_sequence()
    last_exception: Exception | None = None

    for fallback_model in model_sequence:
        for attempt in range(MAX_ATTEMPTS):
            client = _client_for_attempt(attempt)
            try:
                output = _try_generate(
                    client=client,
                    model=fallback_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    temperature=temperature,
                )
                if validator is not None:
                    try:
                        validator(output)
                    except ValueError as e:
                        raise OutputValidationError(str(e)) from e
                return output
            except OutputValidationError as e:
                last_exception = e
                print(
                    f"Gemini model {fallback_model} returned output that failed "
                    f"validation: {e}. Trying the next model."
                )
                break
            except errors.ServerError as e:
                last_exception = e
                if _is_retryable_503(e):
                    if attempt < MAX_ATTEMPTS - 1:
                        delay = INITIAL_DELAY * (2 ** attempt)
                        print(
                            f"Gemini model {fallback_model} unavailable (503) on attempt {attempt + 1}. Retrying same model in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    print(
                        f"Gemini model {fallback_model} unavailable after "
                        f"{MAX_ATTEMPTS} attempts. Trying fallback model."
                    )
                    break
                print(
                    f"Gemini model {fallback_model} returned server error "
                    f"({getattr(e, 'code', 'unknown')}). Trying fallback model."
                )
                break
            except Exception as e:
                last_exception = e
                if attempt < MAX_ATTEMPTS - 1:
                    delay = INITIAL_DELAY * (2 ** attempt)
                    print(
                        f"Gemini request failed for model {fallback_model} on attempt {attempt + 1}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    continue
                print(
                    f"Gemini request failed for model {fallback_model} after "
                    f"{MAX_ATTEMPTS} attempts."
                )
                break

    if last_exception is not None:
        if isinstance(last_exception, OutputValidationError):
            raise last_exception
        raise LLMGenerationError(
            "All configured Gemini models failed to generate valid output."
        ) from last_exception

    raise LLMGenerationError(
        "No Gemini models are configured for output generation."
    )