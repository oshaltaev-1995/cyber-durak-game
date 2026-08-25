"""Pydantic request and public-state response schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from kiba_api.sessions import HumanActionType


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InitialAttackRequest(_StrictRequest):
    action: Literal[HumanActionType.INITIAL_ATTACK]
    cards: list[str] = Field(min_length=1)


class DefenseRequest(_StrictRequest):
    action: Literal[HumanActionType.DEFEND]
    cards: list[str] = Field(min_length=1)


class TransferRequest(_StrictRequest):
    action: Literal[HumanActionType.TRANSFER]
    cards: list[str] = Field(min_length=1)


class ThrowInRequest(_StrictRequest):
    action: Literal[HumanActionType.THROW_IN]
    cards: list[str] = Field(min_length=1)


class TakeRequest(_StrictRequest):
    action: Literal[HumanActionType.TAKE]


class BitoRequest(_StrictRequest):
    action: Literal[HumanActionType.BITO]


HumanActionRequest = Annotated[
    InitialAttackRequest
    | DefenseRequest
    | TransferRequest
    | ThrowInRequest
    | TakeRequest
    | BitoRequest,
    Field(discriminator="action"),
]


class CardResponse(BaseModel):
    code: str
    rank: str
    suit: str
    base_value: int
    effective_value: int
    is_trump: bool


class TrumpResponse(BaseModel):
    active: bool
    source_card: CardResponse | None
    trump_rank: str | None
    trump_suit: str | None


class PacketResponse(BaseModel):
    attack_cards: list[CardResponse]
    attack_value: int
    defense_cards: list[CardResponse]
    defense_value: int | None
    closed: bool


class TableArithmeticResponse(BaseModel):
    total_effective_value: int
    physical_card_count: int
    arithmetic_mean: str | None


class ResultResponse(BaseModel):
    outcome: Literal["WIN", "DRAW"]
    winner: Literal["HUMAN", "BOT"] | None
    winner_seat: str | None


class GameResponse(BaseModel):
    game_id: str
    phase: str
    result: ResultResponse | None
    human_seat: str
    bot_seat: str
    human_hand: list[CardResponse]
    bot_hand_count: int
    draw_pile_count: int
    exposed_top_card: CardResponse | None
    trump: TrumpResponse
    discard_count: int
    table_cards: list[CardResponse]
    table_arithmetic: TableArithmeticResponse
    attacker: str | None
    defender: str | None
    bout_phase: str | None
    packets: list[PacketResponse]
    active_packet: PacketResponse | None
    direct_anchor_cards: list[CardResponse]
    active_attack_value: int | None
    attack_card_limit: int | None
    total_attack_card_count: int | None
    transfer_open: bool
    required_actor: Literal["HUMAN", "BOT"] | None
    required_seat: str | None
    available_actions: list[HumanActionType]
