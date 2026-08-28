import { Routes } from '@angular/router';
import { LoginPageComponent } from './auth/login-page';
import { AchievementsPageComponent } from './auth/achievements-page';
import { CosmeticsPageComponent } from './auth/cosmetics-page';
import { HistoryPageComponent } from './auth/history-page';
import { ProfilePageComponent } from './auth/profile-page';
import { RegisterPageComponent } from './auth/register-page';
import { ForgotPasswordPageComponent } from './auth/forgot-password-page';
import { ResetPasswordPageComponent } from './auth/reset-password-page';
import { VerifyEmailPageComponent } from './auth/verify-email-page';
import { GamePageComponent } from './game/game-page';
import { LandingPageComponent } from './landing/landing-page';
import { PvPJoinPageComponent } from './pvp/pvp-join-page';
import { PvPLobbyPageComponent } from './pvp/pvp-lobby-page';
import { PvPRoomPageComponent } from './pvp/pvp-room-page';
import { RulesPageComponent } from './rules/rules-page';
import { TutorialPageComponent } from './tutorial/tutorial-page';

export const routes: Routes = [
  { path: '', component: LandingPageComponent, title: 'Kiba — карточная игра с арифметикой' },
  { path: 'play', component: GamePageComponent, title: 'Играть — Kiba' },
  { path: 'pvp', component: PvPLobbyPageComponent, title: 'Играть с другом — Kiba' },
  { path: 'pvp/room/:inviteCode', component: PvPRoomPageComponent, title: 'Приватная игра — Kiba' },
  { path: 'join/:inviteCode', component: PvPJoinPageComponent, title: 'Присоединиться — Kiba' },
  { path: 'tutorial', component: TutorialPageComponent, title: 'Обучение — Kiba' },
  { path: 'rules', component: RulesPageComponent, title: 'Правила — Kiba' },
  { path: 'login', component: LoginPageComponent, title: 'Войти — Kiba' },
  { path: 'register', component: RegisterPageComponent, title: 'Создать аккаунт — Kiba' },
  { path: 'forgot-password', component: ForgotPasswordPageComponent, title: 'Сброс пароля — Kiba' },
  { path: 'reset-password', component: ResetPasswordPageComponent, title: 'Новый пароль — Kiba' },
  { path: 'verify-email', component: VerifyEmailPageComponent, title: 'Подтвердить email — Kiba' },
  { path: 'profile', component: ProfilePageComponent, title: 'Профиль — Kiba' },
  { path: 'profile/history', component: HistoryPageComponent, title: 'История партий — Kiba' },
  {
    path: 'profile/achievements',
    component: AchievementsPageComponent,
    title: 'Достижения — Kiba',
  },
  { path: 'profile/cosmetics', component: CosmeticsPageComponent, title: 'Оформление — Kiba' },
  { path: '**', redirectTo: '' },
];
