import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth/auth.service';
import { TranslationService } from '../core/i18n/translation.service';
import { FirstRunStore } from '../core/onboarding/first-run.store';

@Component({
  selector: 'app-landing-page',
  imports: [RouterLink],
  templateUrl: './landing-page.html',
  styleUrl: './landing-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LandingPageComponent {
  protected readonly auth = inject(AuthService);
  protected readonly i18n = inject(TranslationService);
  private readonly firstRun = inject(FirstRunStore);
  private readonly router = inject(Router);
  protected readonly showWelcome = signal(!this.firstRun.hasSeenWelcome());

  protected startTutorial(): void {
    this.continueTo('/tutorial');
  }

  protected playNow(): void {
    this.continueTo('/play');
  }

  private continueTo(route: string): void {
    this.firstRun.markWelcomeSeen();
    this.showWelcome.set(false);
    void this.router.navigateByUrl(route);
  }
}
