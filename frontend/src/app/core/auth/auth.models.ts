export interface CurrentUser {
  readonly id: string;
  readonly email: string;
  readonly display_name: string;
  readonly created_at: string;
}

export interface RegisterRequest {
  readonly email: string;
  readonly display_name: string;
  readonly password: string;
}

export interface LoginRequest {
  readonly email: string;
  readonly password: string;
}
