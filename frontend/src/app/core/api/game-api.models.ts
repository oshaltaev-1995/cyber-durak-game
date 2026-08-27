export type HumanActionType =
  'INITIAL_ATTACK' | 'DEFEND' | 'TRANSFER' | 'THROW_IN' | 'TAKE' | 'BITO';

export type GamePhase = 'ready_for_bout' | 'bout_active' | 'complete';
export type BoutPhase =
  | 'waiting_for_initial_attack'
  | 'waiting_for_defender_response'
  | 'waiting_for_attacker_decision'
  | 'complete';
export type Seat = 'one' | 'two';
export type Suit = 'clubs' | 'diamonds' | 'hearts' | 'spades';

export interface GameCard {
  readonly code: string;
  readonly rank: string;
  readonly suit: Suit;
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

export type ThrowInReasonType = 'same_rank' | 'existing_value' | 'table_total' | 'arithmetic_mean';

export interface ThrowInReason {
  readonly type: ThrowInReasonType;
  readonly target_value: number | null;
  readonly expression: string | null;
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

export interface GameResponse {
  readonly game_id: string;
  readonly account_associated: boolean;
  readonly result_saved: boolean;
  readonly progression_award: ProgressionAward | null;
  readonly cosmetics: GameCosmetics;
  readonly phase: GamePhase;
  readonly result: GameResult | null;
  readonly human_seat: Seat;
  readonly bot_seat: Seat;
  readonly human_hand: readonly GameCard[];
  readonly bot_hand_count: number;
  readonly draw_pile_count: number;
  readonly exposed_top_card: GameCard | null;
  readonly trump: TrumpState;
  readonly discard_count: number;
  readonly table_cards: readonly GameCard[];
  readonly table_arithmetic: TableArithmetic;
  readonly attacker: Seat | null;
  readonly defender: Seat | null;
  readonly bout_phase: BoutPhase | null;
  readonly packets: readonly AttackPacket[];
  readonly active_packet: AttackPacket | null;
  readonly direct_anchor_cards: readonly GameCard[];
  readonly active_attack_value: number | null;
  readonly attack_card_limit: number | null;
  readonly total_attack_card_count: number | null;
  readonly transfer_open: boolean;
  readonly required_actor: 'HUMAN' | 'BOT' | null;
  readonly required_seat: Seat | null;
  readonly available_actions: readonly HumanActionType[];
}

export type CardActionType = 'INITIAL_ATTACK' | 'DEFEND' | 'TRANSFER' | 'THROW_IN';

export interface CardActionRequest {
  readonly action: CardActionType;
  readonly cards: readonly string[];
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

export const ACTION_LABELS: Readonly<Record<HumanActionType, string>> = {
  INITIAL_ATTACK: 'Ходить',
  DEFEND: 'Покрыть',
  TRANSFER: 'Перевести',
  THROW_IN: 'Подкинуть',
  TAKE: 'Взять',
  BITO: 'Бито',
};

export const SUIT_SYMBOLS: Readonly<Record<Suit, string>> = {
  clubs: '♣',
  diamonds: '♦',
  hearts: '♥',
  spades: '♠',
};
