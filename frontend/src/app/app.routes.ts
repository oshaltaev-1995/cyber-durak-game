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
  { path: '', component: LandingPageComponent },
  { path: 'play', component: GamePageComponent },
  { path: 'pvp', component: PvPLobbyPageComponent },
  { path: 'pvp/room/:inviteCode', component: PvPRoomPageComponent },
  { path: 'join/:inviteCode', component: PvPJoinPageComponent },
  { path: 'tutorial', component: TutorialPageComponent },
  { path: 'rules', component: RulesPageComponent },
  { path: 'login', component: LoginPageComponent },
  { path: 'register', component: RegisterPageComponent },
  { path: 'forgot-password', component: ForgotPasswordPageComponent },
  { path: 'reset-password', component: ResetPasswordPageComponent },
  { path: 'verify-email', component: VerifyEmailPageComponent },
  { path: 'profile', component: ProfilePageComponent },
  { path: 'profile/history', component: HistoryPageComponent },
  {
    path: 'profile/achievements',
    component: AchievementsPageComponent,
  },
  { path: 'profile/cosmetics', component: CosmeticsPageComponent },
  { path: '**', redirectTo: '' },
];
