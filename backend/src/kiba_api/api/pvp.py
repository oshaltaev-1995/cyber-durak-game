"""REST invitation flow and authoritative WebSocket transport for private rooms."""

from __future__ import annotations

import json
from contextlib import suppress
from threading import RLock
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from kiba_api.api.auth import OptionalCurrentUser, is_trusted_origin
from kiba_api.api.cards import CardCodeError, parse_card_codes
from kiba_api.api.pvp_schemas import (
    RoomCreateRequest,
    RoomIdentityRequest,
    RoomJoinResponse,
    RoomStatusResponse,
    WebSocketActionMessage,
    WebSocketAuthMessage,
    WebSocketHintRequestMessage,
    WebSocketLeaveMessage,
    WebSocketPingMessage,
    WebSocketRematchMessage,
)
from kiba_api.api.pvp_serialization import (
    serialize_pvp_state,
    serialize_room_join,
    serialize_room_status,
)
from kiba_api.api.serialization import serialize_move_hints
from kiba_api.auth import AuthError
from kiba_api.game import GamePhase
from kiba_api.locale import parse_locale
from kiba_api.pvp import (
    PvPActionError,
    PvPError,
    PvPErrorCode,
    PvPParticipant,
    PvPRoom,
    PvPRoomPhase,
    PvPRoomService,
    normalize_guest_nickname,
)

router = APIRouter(prefix="/api/pvp/rooms", tags=["private multiplayer"])


class _MessageTooLarge(ValueError):
    pass


class PvPConnectionHub:
    """Track live sockets separately from immutable room/game snapshots."""

    def __init__(self) -> None:
        self._connections: dict[str, dict[str, tuple[str, WebSocket]]] = {}
        self._lock = RLock()

    def register(
        self,
        invite_code: str,
        participant_id: str,
        connection_id: str,
        websocket: WebSocket,
    ) -> WebSocket | None:
        with self._lock:
            participants = self._connections.setdefault(invite_code, {})
            previous = participants.get(participant_id)
            participants[participant_id] = (connection_id, websocket)
            return previous[1] if previous is not None else None

    def unregister(self, invite_code: str, participant_id: str, connection_id: str) -> None:
        with self._lock:
            participants = self._connections.get(invite_code)
            if participants is None:
                return
            current = participants.get(participant_id)
            if current is not None and current[0] == connection_id:
                participants.pop(participant_id, None)
            if not participants:
                self._connections.pop(invite_code, None)

    def connections(self, invite_code: str) -> tuple[tuple[str, WebSocket], ...]:
        with self._lock:
            participants = self._connections.get(invite_code, {})
            return tuple(
                (participant_id, value[1]) for participant_id, value in participants.items()
            )


def get_pvp_service(request: Request) -> PvPRoomService:
    return request.app.state.pvp_service


def get_pvp_hub(request: Request) -> PvPConnectionHub:
    return request.app.state.pvp_hub


PvPServiceDependency = Annotated[PvPRoomService, Depends(get_pvp_service)]
PvPHubDependency = Annotated[PvPConnectionHub, Depends(get_pvp_hub)]


@router.post("", response_model=RoomJoinResponse, status_code=201, summary="Create a private room")
async def create_room(
    payload: RoomCreateRequest,
    request: Request,
    service: PvPServiceDependency,
    user: OptionalCurrentUser,
) -> RoomJoinResponse:
    """Create a guest-friendly invitation and assign its creator to Seat.ONE."""
    if payload.capacity > 2 and not request.app.state.settings.multiplayer_3_4_enabled:
        raise PvPError(PvPErrorCode.FEATURE_NOT_AVAILABLE)
    display_name = user.display_name if user is not None else _guest_name(payload.nickname)
    room, participant = service.create_room(
        display_name,
        capacity=payload.capacity,
        user_id=user.id if user is not None else None,
        preferred_locale=(
            parse_locale(user.preferred_locale)
            if user is not None
            else parse_locale(request.headers.get("accept-language"))
        ),
    )
    return serialize_room_join(room, participant)


@router.post(
    "/{invite_code}/join",
    response_model=RoomJoinResponse,
    summary="Join a private room",
)
async def join_room(
    invite_code: str,
    payload: RoomIdentityRequest,
    request: Request,
    service: PvPServiceDependency,
    hub: PvPHubDependency,
    user: OptionalCurrentUser,
) -> RoomJoinResponse:
    """Assign the lowest free seat and start the room when it reaches capacity."""
    display_name = user.display_name if user is not None else _guest_name(payload.nickname)
    room, participant = service.join_room(
        invite_code,
        display_name,
        user_id=user.id if user is not None else None,
        preferred_locale=(
            parse_locale(user.preferred_locale)
            if user is not None
            else parse_locale(request.headers.get("accept-language"))
        ),
    )
    await _broadcast_event(
        room,
        hub,
        "OPPONENT_CONNECTED",
        exclude=participant.participant_id,
        affected=participant,
    )
    await _broadcast_state(room, hub)
    return serialize_room_join(room, participant)


@router.get("/{invite_code}", response_model=RoomStatusResponse, summary="Get room status")
def get_room_status(invite_code: str, service: PvPServiceDependency) -> RoomStatusResponse:
    """Return invitation status without private cards or reconnect credentials."""
    return serialize_room_status(service.get_room(invite_code))


@router.websocket("/{invite_code}/ws")
async def room_websocket(websocket: WebSocket, invite_code: str) -> None:
    """Authenticate a participant then process versioned authoritative actions."""
    service: PvPRoomService = websocket.app.state.pvp_service
    hub: PvPConnectionHub = websocket.app.state.pvp_hub
    if not _websocket_origin_allowed(websocket):
        await websocket.close(code=4403)
        return

    await websocket.accept()
    connection_id = uuid4().hex
    participant_id: str | None = None
    reconnect_token: str | None = None
    try:
        try:
            auth = WebSocketAuthMessage.model_validate(await _receive_payload(websocket))
            reconnect_token = auth.credential
            registration = service.connect(invite_code, reconnect_token, connection_id)
        except PvPError as error:
            await websocket.send_json(_error_message("ERROR", error.code))
            close_code = (
                4404
                if error.code
                in {
                    PvPErrorCode.ROOM_NOT_FOUND,
                    PvPErrorCode.INVITE_EXPIRED,
                    PvPErrorCode.ROOM_CLOSED,
                }
                else 4401
            )
            await websocket.close(code=close_code)
            return
        except (ValidationError, _MessageTooLarge, json.JSONDecodeError, TypeError):
            await websocket.send_json(_error_message("ERROR", PvPErrorCode.INVALID_CREDENTIAL))
            await websocket.close(code=4401)
            return

        participant_id = registration.participant.participant_id
        replaced = hub.register(invite_code, participant_id, connection_id, websocket)
        if replaced is not None and replaced is not websocket:
            with suppress(RuntimeError, WebSocketDisconnect):
                await replaced.close(code=4001, reason="connection replaced")
        await _send_state(websocket, registration.room, registration.participant)
        await _broadcast_event(
            registration.room,
            hub,
            "OPPONENT_CONNECTED",
            exclude=participant_id,
            affected=registration.participant,
        )
        await _broadcast_state(registration.room, hub, exclude=participant_id)

        while True:
            try:
                payload = await _receive_payload(websocket)
            except _MessageTooLarge:
                await websocket.send_json(_error_message("ERROR", PvPErrorCode.MESSAGE_TOO_LARGE))
                continue
            except (json.JSONDecodeError, TypeError):
                await websocket.send_json(
                    _error_message("ERROR", PvPErrorCode.ILLEGAL_ACTION, "invalid_json")
                )
                continue
            message_type = payload.get("type") if isinstance(payload, dict) else None
            if message_type == "PING":
                try:
                    WebSocketPingMessage.model_validate(payload)
                    room = service.get_room(invite_code)
                    await websocket.send_json({"type": "PONG", "version": room.version})
                except (ValidationError, PvPError):
                    await websocket.send_json(_error_message("ERROR", PvPErrorCode.ROOM_NOT_FOUND))
                continue
            if message_type == "LEAVE":
                leaving_participant = registration.room.participant_by_id(participant_id)
                try:
                    WebSocketLeaveMessage.model_validate(payload)
                    room = service.leave_room(invite_code, reconnect_token, connection_id)
                except ValidationError:
                    await websocket.send_json(
                        _error_message("ERROR", PvPErrorCode.ILLEGAL_ACTION, "invalid_request")
                    )
                    continue
                except PvPError as error:
                    await websocket.send_json(_error_message("ERROR", error.code))
                    continue
                if room.phase is PvPRoomPhase.CLOSED:
                    await _broadcast_room_closed(room, hub, participant_id)
                else:
                    await websocket.close(code=4000, reason="participant left room")
                    await _broadcast_event(
                        room,
                        hub,
                        "PARTICIPANT_LEFT",
                        exclude=participant_id,
                        affected=leaving_participant,
                    )
                    await _broadcast_state(room, hub, exclude=participant_id)
                return
            if message_type in {
                "REMATCH_REQUEST",
                "REMATCH_ACCEPT",
                "REMATCH_DECLINE",
                "REMATCH_CANCEL",
            }:
                try:
                    message = WebSocketRematchMessage.model_validate(payload)
                    current_room = service.get_room(invite_code)
                    if (
                        current_room.capacity > 2
                        and not websocket.app.state.settings.multiplayer_3_4_enabled
                    ):
                        raise PvPActionError(PvPErrorCode.REMATCH_NOT_AVAILABLE)
                    try:
                        websocket.app.state.pvp_action_rate_limiter.check(
                            f"{invite_code}:{participant_id}"
                        )
                    except AuthError:
                        await websocket.send_json(
                            _error_message("REMATCH_REJECTED", PvPErrorCode.RATE_LIMITED)
                        )
                        continue
                    if message.type in {"REMATCH_REQUEST", "REMATCH_ACCEPT"}:
                        room = service.request_rematch(
                            invite_code,
                            reconnect_token,
                            match_id=message.match_id,
                            expected_version=message.version,
                        )
                    elif message.type == "REMATCH_DECLINE":
                        room = service.decline_rematch(
                            invite_code,
                            reconnect_token,
                            match_id=message.match_id,
                            expected_version=message.version,
                        )
                    else:
                        room = service.cancel_rematch(
                            invite_code,
                            reconnect_token,
                            match_id=message.match_id,
                            expected_version=message.version,
                        )
                except ValidationError:
                    await websocket.send_json(
                        _error_message(
                            "REMATCH_REJECTED",
                            PvPErrorCode.REMATCH_NOT_AVAILABLE,
                            "invalid_request",
                        )
                    )
                    continue
                except PvPActionError as error:
                    await websocket.send_json(
                        _error_message("REMATCH_REJECTED", error.code, error.domain_code)
                    )
                    if error.code is PvPErrorCode.STALE_VERSION:
                        latest = service.get_room(invite_code)
                        latest_participant = latest.participant_by_id(participant_id)
                        await _send_state(websocket, latest, latest_participant)
                    continue
                except PvPError as error:
                    await websocket.send_json(_error_message("REMATCH_REJECTED", error.code))
                    continue
                await _broadcast_state(room, hub)
                continue
            if message_type == "HINT_REQUEST":
                message: WebSocketHintRequestMessage | None = None
                try:
                    message = WebSocketHintRequestMessage.model_validate(payload)
                    cards = parse_card_codes(message.selected_card_ids)
                    room, hints = service.get_hints(
                        invite_code,
                        reconnect_token,
                        cards,
                        expected_version=message.version,
                    )
                except ValidationError:
                    await websocket.send_json(
                        _hint_error_message(
                            PvPErrorCode.ILLEGAL_ACTION,
                            "invalid_request",
                        )
                    )
                    continue
                except CardCodeError as error:
                    await websocket.send_json(
                        _hint_error_message(
                            PvPErrorCode.ILLEGAL_ACTION,
                            error.code.value,
                            request_id=message.request_id,
                        )
                    )
                    continue
                except PvPActionError as error:
                    await websocket.send_json(
                        _hint_error_message(
                            error.code,
                            error.domain_code,
                            request_id=message.request_id,
                        )
                    )
                    continue
                await websocket.send_json(
                    {
                        "type": "HINTS",
                        "request_id": message.request_id,
                        "version": room.version,
                        "hints": serialize_move_hints(hints).model_dump(mode="json"),
                    }
                )
                continue
            if message_type != "ACTION":
                await websocket.send_json(
                    _error_message("ERROR", PvPErrorCode.ILLEGAL_ACTION, "invalid_message")
                )
                continue

            try:
                message = WebSocketActionMessage.model_validate(payload)
                try:
                    websocket.app.state.pvp_action_rate_limiter.check(
                        f"{invite_code}:{participant_id}"
                    )
                except AuthError:
                    await websocket.send_json(
                        _error_message("ACTION_REJECTED", PvPErrorCode.RATE_LIMITED)
                    )
                    continue
                cards = parse_card_codes(message.cards)
                room = service.play_action(
                    invite_code,
                    reconnect_token,
                    message.action,
                    cards,
                    expected_version=message.version,
                )
            except ValidationError:
                await websocket.send_json(
                    _error_message(
                        "ACTION_REJECTED",
                        PvPErrorCode.ILLEGAL_ACTION,
                        "invalid_request",
                    )
                )
                continue
            except CardCodeError as error:
                await websocket.send_json(
                    _error_message("ACTION_REJECTED", PvPErrorCode.ILLEGAL_ACTION, error.code.value)
                )
                continue
            except PvPActionError as error:
                await websocket.send_json(
                    _error_message("ACTION_REJECTED", error.code, error.domain_code)
                )
                if error.code is PvPErrorCode.STALE_VERSION:
                    latest = service.get_room(invite_code)
                    latest_participant = latest.participant_by_id(participant_id)
                    await _send_state(websocket, latest, latest_participant)
                continue
            except PvPError as error:
                await websocket.send_json(_error_message("ACTION_REJECTED", error.code))
                continue

            await _broadcast_state(room, hub)
            if room.state is not None and room.state.phase is GamePhase.COMPLETE:
                await _broadcast_complete(room, hub)
    except WebSocketDisconnect:
        pass
    finally:
        if participant_id is not None:
            hub.unregister(invite_code, participant_id, connection_id)
            try:
                room = service.disconnect(invite_code, participant_id, connection_id)
            except PvPError:
                room = None
            if room is not None and room.phase is not PvPRoomPhase.CLOSED:
                participant = room.participant_by_id(participant_id)
                if not participant.connected:
                    await _broadcast_event(
                        room,
                        hub,
                        "OPPONENT_DISCONNECTED",
                        exclude=participant_id,
                        affected=participant,
                    )
                    await _broadcast_state(room, hub, exclude=participant_id)


def _guest_name(nickname: str | None) -> str:
    return normalize_guest_nickname(nickname)


def _websocket_origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if origin is None:
        return not websocket.app.state.settings.is_production
    scheme = "https" if websocket.url.scheme == "wss" else "http"
    request_origin = f"{scheme}://{websocket.headers.get('host', '')}".rstrip("/")
    return is_trusted_origin(origin, request_origin, websocket.app.state.settings)


async def _receive_payload(websocket: WebSocket) -> dict:
    text = await websocket.receive_text()
    if len(text.encode("utf-8")) > websocket.app.state.settings.pvp_max_websocket_message_bytes:
        raise _MessageTooLarge
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TypeError("WebSocket messages must be JSON objects")
    return value


async def _send_state(
    websocket: WebSocket,
    room: PvPRoom,
    participant: PvPParticipant,
) -> None:
    state = serialize_pvp_state(room, participant)
    await websocket.send_json({"type": "STATE", "state": state.model_dump(mode="json")})


async def _broadcast_state(
    room: PvPRoom,
    hub: PvPConnectionHub,
    *,
    exclude: str | None = None,
) -> None:
    for participant_id, websocket in hub.connections(room.invite_code):
        if participant_id == exclude:
            continue
        try:
            participant = room.participant_by_id(participant_id)
            await _send_state(websocket, room, participant)
        except (PvPError, RuntimeError, WebSocketDisconnect):
            continue


async def _broadcast_event(
    room: PvPRoom,
    hub: PvPConnectionHub,
    event_type: str,
    *,
    exclude: str | None = None,
    affected: PvPParticipant | None = None,
) -> None:
    for participant_id, websocket in hub.connections(room.invite_code):
        if participant_id == exclude:
            continue
        try:
            message = {"type": event_type, "version": room.version}
            if affected is not None:
                message.update(
                    {
                        "participant_id": affected.participant_id,
                        "seat": affected.seat.value,
                    }
                )
            await websocket.send_json(message)
        except (RuntimeError, WebSocketDisconnect):
            continue


async def _broadcast_complete(room: PvPRoom, hub: PvPConnectionHub) -> None:
    for participant_id, websocket in hub.connections(room.invite_code):
        try:
            participant = room.participant_by_id(participant_id)
            state = serialize_pvp_state(room, participant)
            await websocket.send_json(
                {"type": "GAME_COMPLETE", "state": state.model_dump(mode="json")}
            )
        except (PvPError, RuntimeError, WebSocketDisconnect):
            continue


async def _broadcast_room_closed(
    room: PvPRoom,
    hub: PvPConnectionHub,
    leaving_participant_id: str,
) -> None:
    """Send one terminal neutral lifecycle event, then close every room socket."""
    for participant_id, websocket in hub.connections(room.invite_code):
        try:
            participant = room.participant_by_id(participant_id)
            state = serialize_pvp_state(room, participant)
            await websocket.send_json(
                {
                    "type": "ROOM_CLOSED",
                    "state": state.model_dump(mode="json"),
                    "left_participant_id": leaving_participant_id,
                }
            )
            await websocket.close(code=4000, reason="room intentionally closed")
        except (PvPError, RuntimeError, WebSocketDisconnect):
            continue


def _error_message(message_type: str, code: PvPErrorCode, domain_code: str | None = None) -> dict:
    return {
        "type": message_type,
        "error": {
            "code": code.value,
            "domain_code": domain_code,
        },
    }


def _hint_error_message(
    code: PvPErrorCode,
    domain_code: str | None = None,
    *,
    request_id: int | None = None,
) -> dict:
    message = _error_message("HINTS_REJECTED", code, domain_code)
    if request_id is not None:
        message["request_id"] = request_id
    return message
