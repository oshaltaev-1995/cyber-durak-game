export type HumanActionType =
  'INITIAL_ATTACK' | 'DEFEND' | 'TRANSFER' | 'THROW_IN' | 'TAKE' | 'BITO';

export type GamePhase = 'ready_for_bout' | 'bout_active' | 'complete';
export type BoutPhase =
  | 'waiting_for_initial_attack'
  | 'waiting_for_defender_response'
  | 'waiting_for_attacker_decision'
  | 'complete';
export type Seat = 'one' | 'two' | 'three' | 'four';
export type Suit = 'clubs' | 'diamonds' | 'hearts' | 'spades';
export type DeckProfile = 'classic' | 'extended';
export type DeckCount = 1 | 2;
export type JokerColor = 'red' | 'black';

export interface DeckConfig {
  readonly deck_profile: DeckProfile;
  readonly deck_count: DeckCount;
}

export interface GameCard {
  /** Exact physical identity. D3 payloads always provide it; optional only for legacy fixtures. */
  readonly id?: string;
  readonly code: string;
  readonly rank: string;
  readonly suit: Suit | null;
  readonly joker_color?: JokerColor | null;
  readonly base_value: number;
  readonly effective_value: number;
  readonly is_trump: boolean;
}

export interface TrumpState {
  readonly active: boolean;
  readonly source_card: GameCard | null;
  readonly trump_rank: string | null;
  readonly trump_suit: Suit | null;
}

export type ThrowInReasonType =
  | 'same_rank'
  | 'latest_defense_ranks'
  | 'existing_value'
  | 'defense_total'
  | 'table_total'
  | 'arithmetic_mean'
  | 'rank_run';

export interface ThrowInReason {
  readonly type: ThrowInReasonType;
  readonly target_value: number | null;
  readonly expression: string | null;
  readonly run_start?: string | null;
  readonly run_end?: string | null;
  readonly run_length?: number | null;
  readonly run_ranks?: readonly string[] | null;
  readonly source_cards?: readonly GameCard[];
}

export interface LastBoutSummary {
  readonly outcome: 'TAKE' | 'BITO';
  readonly actor_seat: Seat;
  readonly table_card_count: number;
}

export interface AttackPacket {
  readonly attack_cards: readonly GameCard[];
  readonly attack_value: number;
  readonly defense_cards: readonly GameCard[];
  readonly defense_value: number | null;
  readonly closed: boolean;
  readonly throw_in_reasons: readonly ThrowInReason[];
}

export interface TableArithmetic {
  readonly total_effective_value: number;
  readonly physical_card_count: number;
  readonly arithmetic_mean: string | null;
}

export interface GameResult {
  readonly outcome: 'WIN' | 'DRAW';
  readonly winner: 'HUMAN' | 'BOT' | null;
  readonly winner_seat: Seat | null;
}

export interface AchievementAward {
  readonly code: string;
  readonly title: string;
  readonly description: string;
  readonly bonus_xp: number;
}

export interface ProgressionAward {
  readonly base_xp: number;
  readonly achievement_bonus_xp: number;
  readonly total_awarded_xp: number;
  readonly new_achievements: readonly AchievementAward[];
  readonly total_xp: number;
  readonly level: number;
  readonly next_level_xp: number;
  readonly xp_needed_for_next_level: number;
  readonly new_cosmetics: readonly CosmeticAward[];
}

export interface CosmeticAward {
  readonly code: string;
  readonly category: 'CARD_BACK' | 'TABLE_THEME' | 'PROFILE_FRAME';
  readonly title: string;
}

export interface GameCosmetics {
  readonly card_back_code: string;
  readonly table_theme_code: string;
  readonly profile_frame_code: string;
}

export type BotPresentationEventType =
  'BOT_INITIAL_ATTACK' | 'BOT_DEFEND' | 'BOT_TRANSFER' | 'BOT_THROW_IN' | 'BOT_TAKE' | 'BOT_BITO';

export interface BotPresentationEvent {
  readonly type: BotPresentationEventType;
  readonly actor: 'BOT';
  readonly card_count: number;
  readonly value: number | null;
  readonly target: number | null;
  readonly actor_seat?: Seat | null;
}

export interface BotSessionParticipant {
  readonly participant_id: string;
  readonly seat: Seat;
  readonly display_name: string;
  readonly is_bot: boolean;
  readonly active: boolean;
  readonly finished: boolean;
  readonly hand_count: number;
}

export interface KibaCapabilities {
  readonly multiplayer_3_4_enabled: boolean;
  readonly deck_variants_enabled?: boolean;
}

export interface GameResponse {
  readonly game_id: string;
  readonly account_associated: boolean;
  readonly result_saved: boolean;
  readonly progression_award: ProgressionAward | null;
  readonly cosmetics: GameCosmetics;
  readonly recent_events: readonly BotPresentationEvent[];
  readonly last_bout_summary: LastBoutSummary | null;
  readonly phase: GamePhase;
  readonly result: GameResult | null;
  readonly human_seat: Seat;
  readonly bot_seat: Seat;
  readonly total_players: 2 | 3 | 4;
  readonly deck_profile: DeckProfile;
  readonly deck_count: DeckCount;
  readonly participants: readonly BotSessionParticipant[];
  readonly active_seats: readonly Seat[];
  readonly finished_seats: readonly Seat[];
  readonly finish_groups: readonly (readonly Seat[])[];
  readonly human_hand: readonly GameCard[];
  readonly bot_hand_count: number;
  readonly draw_pile_count: number;
  readonly exposed_top_card: GameCard | null;
  readonly trump: TrumpState;
  readonly discard_count: number;
  readonly table_cards: readonly GameCard[];
  readonly table_arithmetic: TableArithmetic;
  readonly bout_starting_attacker: Seat | null;
  readonly attacker: Seat | null;
  readonly lead_attacker: Seat | null;
  readonly defender: Seat | null;
  readonly bout_phase: BoutPhase | null;
  readonly packets: readonly AttackPacket[];
  readonly active_packet: AttackPacket | null;
  readonly direct_anchor_cards: readonly GameCard[];
  readonly active_attack_value: number | null;
  readonly attack_card_limit: number | null;
  readonly max_attack_card_addition: number | null;
  readonly total_attack_card_count: number | null;
  readonly transfer_open: boolean;
  readonly required_actor: 'HUMAN' | 'BOT' | null;
  readonly required_seat: Seat | null;
  readonly available_actions: readonly HumanActionType[];
}

export type HintReasonType =
  | 'single_card'
  | 'same_rank'
  | 'latest_defense_ranks'
  | 'arithmetic_equality'
  | 'defense_total'
  | 'transfer_exact'
  | 'same_rank_transfer'
  | 'existing_value'
  | 'table_total'
  | 'arithmetic_mean'
  | 'rank_run';

export interface HintCombination {
  readonly action: HumanActionType;
  readonly card_ids: readonly string[];
  readonly added_card_ids: readonly string[];
  readonly physical_card_ids?: readonly string[];
  readonly added_physical_card_ids?: readonly string[];
  readonly reason: HintReasonType;
  readonly selected_value: number;
  readonly target_value: number | null;
}

export interface HintResponse {
  readonly selected_card_ids: readonly string[];
  readonly suggested_card_ids: readonly string[];
  readonly selected_physical_ids?: readonly string[];
  readonly suggested_physical_ids?: readonly string[];
  readonly suggested_action_types: readonly HumanActionType[];
  readonly combinations: readonly HintCombination[];
}

export type CardActionType = 'INITIAL_ATTACK' | 'DEFEND' | 'TRANSFER' | 'THROW_IN';

export interface CardActionRequest {
  readonly action: CardActionType;
  readonly card_ids: readonly string[];
}

export interface TerminalActionRequest {
  readonly action: 'TAKE' | 'BITO';
}

export type HumanActionRequest = CardActionRequest | TerminalActionRequest;

export const CARD_ACTIONS: ReadonlySet<HumanActionType> = new Set([
  'INITIAL_ATTACK',
  'DEFEND',
  'TRANSFER',
  'THROW_IN',
]);

export const SUIT_SYMBOLS: Readonly<Record<Suit, string>> = {
  clubs: '♣',
  diamonds: '♦',
  hearts: '♥',
  spades: '♠',
};
