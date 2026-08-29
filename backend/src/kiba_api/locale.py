"""Supported presentation locales and request-language negotiation."""

from __future__ import annotations

from enum import StrEnum


class Locale(StrEnum):
    """Locales supported by the single Kiba runtime."""

    RU = "ru"
    EN = "en"


def parse_locale(value: str | None, *, fallback: Locale = Locale.RU) -> Locale:
    """Resolve one locale or Accept-Language value without exposing free-form strings."""
    if not value:
        return fallback
    for item in value.split(","):
        tag = item.split(";", 1)[0].strip().lower()
        if tag == "ru" or tag.startswith("ru-"):
            return Locale.RU
        if tag == "en" or tag.startswith("en-"):
            return Locale.EN
    return fallback
