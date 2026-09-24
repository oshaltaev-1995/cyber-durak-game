"""Authenticated self-service export and account deletion."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from kiba_api.api.auth import (
    AuthServiceDependency,
    CsrfDependency,
    CurrentUser,
    SettingsDependency,
    clear_auth_cookie,
)
from kiba_api.persistence import AccountDataService

router = APIRouter(tags=["account data"])


class DeleteAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)
    confirmation: Literal["DELETE"]


def get_account_data_service(request: Request) -> AccountDataService:
    return request.app.state.account_data_service


AccountDataDependency = Annotated[AccountDataService, Depends(get_account_data_service)]


@router.get("/api/account/export", summary="Download the current account's personal data")
def export_account_data(
    user: CurrentUser,
    service: AccountDataDependency,
) -> JSONResponse:
    """Build a versioned JSON export in memory without credential material."""
    payload = service.export(user.id)
    date = payload["exported_at"][:10]
    return JSONResponse(
        payload,
        headers={
            "Content-Disposition": f'attachment; filename="kiba-data-export-{date}.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/account/delete", status_code=204, summary="Permanently delete the account")
def delete_account(
    payload: DeleteAccountRequest,
    response: Response,
    request: Request,
    _csrf: CsrfDependency,
    user: CurrentUser,
    auth: AuthServiceDependency,
    account_data: AccountDataDependency,
    settings: SettingsDependency,
) -> None:
    """Verify the password, delete live data transactionally, then detach local games."""
    user_id = user.id
    auth.verify_current_password(user, payload.password)
    account_data.delete(user_id)
    request.app.state.game_service.detach_user(user_id)
    request.app.state.pvp_service.detach_user(user_id)
    clear_auth_cookie(response, settings)
