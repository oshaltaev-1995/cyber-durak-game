import { Locale } from '../i18n/locale';

export interface CurrentUser {
  readonly id: string;
  readonly email: string;
  readonly display_name: string;
  readonly created_at: string;
  readonly email_verified?: boolean;
  readonly verification_email_sent?: boolean | null;
  readonly preferred_locale: Locale;
}

export interface RegisterRequest {
  readonly email: string;
  readonly display_name: string;
  readonly password: string;
  readonly preferred_locale: Locale;
}

export interface LoginRequest {
  readonly email: string;
  readonly password: string;
}

export interface AuthMessage {
  readonly message: string;
}
