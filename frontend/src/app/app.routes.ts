import { Routes } from '@angular/router';
import { LoginPageComponent } from './auth/login-page';
import { ProfilePageComponent } from './auth/profile-page';
import { RegisterPageComponent } from './auth/register-page';
import { GamePageComponent } from './game/game-page';
import { LandingPageComponent } from './landing/landing-page';
import { RulesPageComponent } from './rules/rules-page';
import { TutorialPageComponent } from './tutorial/tutorial-page';

export const routes: Routes = [
  { path: '', component: LandingPageComponent, title: 'Kiba — карточная игра с арифметикой' },
  { path: 'play', component: GamePageComponent, title: 'Играть — Kiba' },
  { path: 'tutorial', component: TutorialPageComponent, title: 'Обучение — Kiba' },
  { path: 'rules', component: RulesPageComponent, title: 'Правила — Kiba' },
  { path: 'login', component: LoginPageComponent, title: 'Войти — Kiba' },
  { path: 'register', component: RegisterPageComponent, title: 'Создать аккаунт — Kiba' },
  { path: 'profile', component: ProfilePageComponent, title: 'Профиль — Kiba' },
  { path: '**', redirectTo: '' },
];
