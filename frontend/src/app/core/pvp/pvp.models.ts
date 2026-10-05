import {
  AttackPacket,
  BoutPhase,
  GameCard,
  GamePhase,
  HumanActionType,
  HintResponse,
  LastBoutSummary,
  ProgressionAward,
  Seat,
  TableArithmetic,
  TrumpState,
} from '../api/game-api.models';

export type PvPRoomPhase = 'WAITING_FOR_OPPONENT' | 'GAME_ACTIVE' | 'COMPLETE' | 'CLOSED';
export type PvPRematchStatus = 'NONE' | 'WAITING' | 'INCOMING' | 'DECLINED';

export interface PvPParticipant {
  readonly participant_id: string;
  readonly seat: Seat;
  readonly display_name: string;
  readonly connected: boolean;
  readonly authenticated: boolean;
}

export interface PvPCredential {
  readonly participant_id: string;
  readonly seat: Seat;
  readonly reconnect_token: string;
}

export interface PvPResult {
  readonly outcome: 'WIN' | 'DRAW';
  readonly winner_seat: Seat | null;
  readonly winner_participant_id: string | null;
  readonly winner_display_name: string | null;
}

export interface PvPState {
  readonly invite_code: string;
  readonly match_id: string | null;
  readonly room_phase: PvPRoomPhase;
  readonly version: number;
  readonly rematch_status: PvPRematchStatus;
  readonly you: PvPParticipant;
  readonly opponent: PvPParticipant | null;
  readonly game_phase: GamePhase | null;
  readonly result: PvPResult | null;
  readonly result_saved: boolean;
  readonly progression_award: ProgressionAward | null;
  readonly last_bout_summary: LastBoutSummary | null;
  readonly hand: readonly GameCard[];
  readonly opponent_hand_count: number | null;
  readonly draw_pile_count: number;
  readonly exposed_top_card: GameCard | null;
  readonly trump: TrumpState;
  readonly discard_count: number;
  readonly table_cards: readonly GameCard[];
  readonly table_arithmetic: TableArithmetic;
  readonly bout_starting_attacker: Seat | null;
  readonly attacker: Seat | null;
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
  readonly required_participant_id: string | null;
  readonly required_seat: Seat | null;
  readonly available_actions: readonly HumanActionType[];
}

export interface PvPRoomJoin {
  readonly invite_code: string;
  readonly invite_path: string;
  readonly credential: PvPCredential;
  readonly state: PvPState;
}

export interface PvPRoomStatus {
  readonly invite_code: string;
  readonly room_phase: PvPRoomPhase;
  readonly version: number;
  readonly participants: readonly PvPParticipant[];
}

export interface PvPErrorBody {
  readonly code: string;
  readonly domain_code: string | null;
}

export type PvPConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'offline'
  | 'disconnected'
  | 'expired'
  | 'error';

export type PvPOpponentStatus = 'unknown' | 'connected' | 'disconnected' | 'returned';

export type PvPConnectionNotice =
  'connection_restored' | 'state_updated' | 'action_recovered' | null;

export type PvPRoomClosure = 'you_left' | 'opponent_left' | null;

export type PvPServerMessage =
  | { readonly type: 'STATE'; readonly state: PvPState }
  | { readonly type: 'GAME_COMPLETE'; readonly state: PvPState }
  | { readonly type: 'ACTION_REJECTED'; readonly error: PvPErrorBody }
  | { readonly type: 'REMATCH_REJECTED'; readonly error: PvPErrorBody }
  | {
      readonly type: 'HINTS';
      readonly request_id: number;
      readonly version: number;
      readonly hints: HintResponse;
    }
  | {
      readonly type: 'HINTS_REJECTED';
      readonly request_id?: number;
      readonly error: PvPErrorBody;
    }
  | { readonly type: 'ERROR'; readonly error: PvPErrorBody }
  | {
      readonly type: 'ROOM_CLOSED';
      readonly state: PvPState;
      readonly left_participant_id: string;
    }
  | {
      readonly type: 'OPPONENT_CONNECTED' | 'OPPONENT_DISCONNECTED' | 'PONG';
      readonly version: number;
    };
