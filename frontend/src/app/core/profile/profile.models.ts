export interface MatchStatistics {
  readonly games_played: number;
  readonly wins: number;
  readonly losses: number;
  readonly draws: number;
  readonly win_rate: number;
  readonly current_win_streak: number;
  readonly best_win_streak: number;
  readonly total_transfers: number;
  readonly total_takes: number;
  readonly total_throw_ins: number;
  readonly highest_transfer_target: number;
  readonly arithmetic_mean_throw_ins: number;
  readonly bot_games: number;
  readonly bot_wins: number;
  readonly pvp_games: number;
  readonly pvp_wins: number;
}

export type MatchOutcome = 'WIN' | 'LOSS' | 'DRAW';

export interface MatchHistoryItem {
  readonly id: string;
  readonly outcome: MatchOutcome;
  readonly opponent_type: 'BOT' | 'PVP';
  readonly opponent_display_name: string | null;
  readonly started_at: string;
  readonly completed_at: string;
  readonly duration_seconds: number;
  readonly initial_attacker: 'HUMAN' | 'BOT' | 'YOU' | 'OPPONENT';
  readonly final_human_card_count: number;
  readonly final_bot_card_count: number;
  readonly human_action_count: number;
  readonly human_transfer_count: number;
  readonly human_take_count: number;
  readonly human_throw_in_count: number;
  readonly max_transfer_target: number;
  readonly arithmetic_mean_throw_in_count: number;
}

export interface MatchHistoryResponse {
  readonly items: readonly MatchHistoryItem[];
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

export interface ProgressionSummary {
  readonly total_xp: number;
  readonly level: number;
  readonly level_start_xp: number;
  readonly next_level_xp: number;
  readonly xp_into_level: number;
  readonly xp_needed_for_next_level: number;
  readonly progress_fraction: number;
  readonly achievements_unlocked: number;
  readonly achievements_total: number;
}

export interface Achievement {
  readonly code: string;
  readonly title: string;
  readonly description: string;
  readonly bonus_xp: number;
  readonly unlocked: boolean;
  readonly unlocked_at: string | null;
}

export type CosmeticCategory = 'CARD_BACK' | 'TABLE_THEME' | 'PROFILE_FRAME';
export type CosmeticUnlockType = 'DEFAULT' | 'LEVEL' | 'ACHIEVEMENT';

export interface CosmeticLoadout {
  readonly card_back_code: string;
  readonly table_theme_code: string;
  readonly profile_frame_code: string;
}

export const DEFAULT_COSMETIC_LOADOUT: CosmeticLoadout = {
  card_back_code: 'CLASSIC',
  table_theme_code: 'CLASSIC_TABLE',
  profile_frame_code: 'NO_FRAME',
};

export interface CosmeticUnlock {
  readonly type: CosmeticUnlockType;
  readonly requirement: number | string | null;
  readonly achievement_title: string | null;
}

export interface CosmeticItem {
  readonly code: string;
  readonly category: CosmeticCategory;
  readonly title: string;
  readonly description: string;
  readonly unlocked: boolean;
  readonly equipped: boolean;
  readonly unlock: CosmeticUnlock;
  readonly unlocked_at: string | null;
}

export interface CosmeticsResponse {
  readonly items: readonly CosmeticItem[];
  readonly loadout: CosmeticLoadout;
}

export interface CosmeticEquipRequest {
  readonly card_back_code?: string;
  readonly table_theme_code?: string;
  readonly profile_frame_code?: string;
}
