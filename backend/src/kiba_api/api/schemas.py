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


class ThrowInReasonResponse(BaseModel):
    type: Literal[
        "same_rank",
        "existing_value",
        "defense_total",
        "table_total",
        "arithmetic_mean",
        "rank_run",
    ]
    target_value: int | None
    expression: str | None
    run_start: str | None = Field(default=None, exclude_if=lambda value: value is None)
    run_end: str | None = Field(default=None, exclude_if=lambda value: value is None)
    run_length: int | None = Field(default=None, exclude_if=lambda value: value is None)
    run_ranks: list[str] | None = Field(default=None, exclude_if=lambda value: value is None)
    source_cards: list[CardResponse] = Field(
        default_factory=list,
        exclude_if=lambda value: not value,
    )


class PacketResponse(BaseModel):
    attack_cards: list[CardResponse]
    attack_value: int
    defense_cards: list[CardResponse]
    defense_value: int | None
    closed: bool
    throw_in_reasons: list[ThrowInReasonResponse]


class TableArithmeticResponse(BaseModel):
    total_effective_value: int
    physical_card_count: int
    arithmetic_mean: str | None


class ResultResponse(BaseModel):
    outcome: Literal["WIN", "DRAW"]
    winner: Literal["HUMAN", "BOT"] | None
    winner_seat: str | None


class AchievementAwardResponse(BaseModel):
    code: str
    title: str
    description: str
    bonus_xp: int


class CosmeticAwardResponse(BaseModel):
    code: str
    category: str
    title: str


class ProgressionAwardResponse(BaseModel):
    base_xp: int
    achievement_bonus_xp: int
    total_awarded_xp: int
    new_achievements: list[AchievementAwardResponse]
    total_xp: int
    level: int
    next_level_xp: int
    xp_needed_for_next_level: int
    new_cosmetics: list[CosmeticAwardResponse]


class CosmeticLoadoutResponse(BaseModel):
    card_back_code: str
    table_theme_code: str
    profile_frame_code: str


class BotPresentationEventResponse(BaseModel):
    type: Literal[
        "BOT_INITIAL_ATTACK",
        "BOT_DEFEND",
        "BOT_TRANSFER",
        "BOT_THROW_IN",
        "BOT_TAKE",
        "BOT_BITO",
    ]
    actor: Literal["BOT"] = "BOT"
    card_count: int
    value: int | None
    target: int | None


class LastBoutSummaryResponse(BaseModel):
    outcome: Literal["TAKE", "BITO"]
    actor_seat: str
    table_card_count: int


class GameResponse(BaseModel):
    game_id: str
    account_associated: bool
    result_saved: bool
    progression_award: ProgressionAwardResponse | None
    cosmetics: CosmeticLoadoutResponse
    recent_events: list[BotPresentationEventResponse]
    last_bout_summary: LastBoutSummaryResponse | None
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
    bout_starting_attacker: str | None
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
