"""Pick the validator once, at startup."""

from __future__ import annotations

from app.config import Settings
from app.validation.base import EmailValidator
from app.validation.mx import DnsPythonResolver, SyntaxMxValidator
from app.validation.zerobounce import ZeroBounceValidator


def build_validator(settings: Settings) -> EmailValidator:
    if settings.zerobounce_api_key.strip():
        return ZeroBounceValidator(settings.zerobounce_api_key.strip())
    return SyntaxMxValidator(DnsPythonResolver())
