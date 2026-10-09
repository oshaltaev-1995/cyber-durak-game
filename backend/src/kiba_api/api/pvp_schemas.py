"""HTTP and WebSocket schemas for private 2–4 participant rooms."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiba_api.api.schemas import (
    CardResponse,
    LastBoutSummaryResponse,
    PacketResponse,
    ProgressionAwardResponse,
    TableArithmeticResponse,
    TrumpResponse,
)
from kiba_api.sessions import HumanActionType


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoomIdentityRequest(_StrictModel):
    nickname: str | None = None


class RoomCreateRequest(RoomIdentityRequest):
    capacity: int = Field(default=2, ge=2, le=4)


class ParticipantResponse(BaseModel):
    participant_id: str
    seat: str
    display_name: str
    connected: bool
    authenticated: bool


class PlayerStateResponse(ParticipantResponse):
    is_self: bool
    hand_count: int | None
    active: bool
    finished: bool


class ParticipantCredentialResponse(BaseModel):
    participant_id: str
    seat: str
    reconnect_token: str


class PvPResultResponse(BaseModel):
    outcome: Literal["WIN", "DRAW"]
    winner_seat: str | None
    winner_participant_id: str | None
    winner_display_name: str | None


class PvPStateResponse(BaseModel):
    invite_code: str
    match_id: str | None
    room_phase: str
    version: int
    capacity: int
    joined_count: int
    seat_order: list[str]
    players: list[PlayerStateResponse]
    active_seats: list[str]
    finished_seats: list[str]
    finish_groups: list[list[str]]
    rematch_status: Literal["NONE", "WAITING", "INCOMING", "DECLINED"]
    rematch_ready_count: int
    rematch_total_count: int
    rematch_requester_participant_id: str | None
    rematch_ready_participant_ids: list[str]
    you: ParticipantResponse
    opponent: ParticipantResponse | None
    game_phase: str | None
    result: PvPResultResponse | None
    result_saved: bool
    progression_award: ProgressionAwardResponse | None
    last_bout_summary: LastBoutSummaryResponse | None
    hand: list[CardResponse]
    opponent_hand_count: int | None
    draw_pile_count: int
    exposed_top_card: CardResponse | None
    trump: TrumpResponse
    discard_count: int
    table_cards: list[CardResponse]
    table_arithmetic: TableArithmeticResponse
    bout_starting_attacker: str | None
    attacker: str | None
    lead_attacker: str | None
    defender: str | None
    bout_phase: str | None
    packets: list[PacketResponse]
    active_packet: PacketResponse | None
    direct_anchor_cards: list[CardResponse]
    active_attack_value: int | None
    attack_card_limit: int | None
    max_attack_card_addition: int | None
    total_attack_card_count: int | None
    transfer_open: bool
    required_participant_id: str | None
    required_seat: str | None
    available_actions: list[HumanActionType]


class RoomJoinResponse(BaseModel):
    invite_code: str
    invite_path: str
    credential: ParticipantCredentialResponse
    state: PvPStateResponse


class RoomStatusResponse(BaseModel):
    invite_code: str
    room_phase: str
    version: int
    capacity: int
    joined_count: int
    participants: list[ParticipantResponse]


class WebSocketAuthMessage(_StrictModel):
    type: Literal["AUTH"]
    credential: str = Field(min_length=1)


class WebSocketPingMessage(_StrictModel):
    type: Literal["PING"]


class WebSocketLeaveMessage(_StrictModel):
    type: Literal["LEAVE"]


class WebSocketRematchMessage(_StrictModel):
    type: Literal["REMATCH_REQUEST", "REMATCH_ACCEPT", "REMATCH_DECLINE", "REMATCH_CANCEL"]
    match_id: str = Field(min_length=1)
    version: int = Field(ge=0)


class WebSocketHintRequestMessage(_StrictModel):
    type: Literal["HINT_REQUEST"]
    request_id: int = Field(ge=0)
    version: int = Field(ge=0)
    selected_card_ids: list[str] = Field(default_factory=list)


class WebSocketActionMessage(_StrictModel):
    type: Literal["ACTION"]
    version: int = Field(ge=0)
    action: HumanActionType
    cards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def card_shape_matches_action(self) -> "WebSocketActionMessage":
        card_actions = {
            HumanActionType.INITIAL_ATTACK,
            HumanActionType.DEFEND,
            HumanActionType.TRANSFER,
            HumanActionType.THROW_IN,
        }
        if self.action in card_actions and not self.cards:
            raise ValueError("card actions require cards")
        if self.action not in card_actions and self.cards:
            raise ValueError("this action does not accept cards")
        return self
