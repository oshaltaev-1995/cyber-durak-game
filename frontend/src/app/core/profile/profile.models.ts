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
}

export type MatchOutcome = 'WIN' | 'LOSS' | 'DRAW';

export interface MatchHistoryItem {
  readonly id: string;
  readonly outcome: MatchOutcome;
  readonly opponent_type: 'BOT';
  readonly started_at: string;
  readonly completed_at: string;
  readonly duration_seconds: number;
  readonly initial_attacker: 'HUMAN' | 'BOT';
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
