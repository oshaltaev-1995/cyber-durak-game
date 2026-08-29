"""FastAPI dependency for supported presentation-language negotiation."""

from typing import Annotated

from fastapi import Depends, Request

from kiba_api.locale import Locale, parse_locale


def request_locale(request: Request) -> Locale:
    return parse_locale(request.headers.get("accept-language"))


RequestLocale = Annotated[Locale, Depends(request_locale)]
