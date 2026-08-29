import { ChangeDetectionStrategy, Component, OnInit, effect, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from './core/auth/auth.service';
import { ProfileService } from './core/profile/profile.service';
import { Locale } from './core/i18n/locale';
import { TranslationService } from './core/i18n/translation.service';
import { TranslationKey } from './core/i18n/translations/ru';

const TITLE_KEYS: readonly [string, TranslationKey][] = [
  ['/profile/achievements', 'meta.achievements'],
  ['/profile/cosmetics', 'meta.cosmetics'],
  ['/profile/history', 'meta.history'],
  ['/profile', 'meta.profile'],
  ['/pvp/room/', 'meta.pvpRoom'],
  ['/pvp', 'meta.pvp'],
  ['/join/', 'meta.pvpJoin'],
  ['/tutorial', 'meta.tutorial'],
  ['/rules', 'meta.rules'],
  ['/play', 'meta.play'],
  ['/login', 'meta.login'],
  ['/register', 'meta.register'],
  ['/forgot-password', 'meta.forgot'],
  ['/reset-password', 'meta.reset'],
  ['/verify-email', 'meta.verify'],
];

@Component({
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App implements OnInit {
  protected readonly auth = inject(AuthService);
  protected readonly profile = inject(ProfileService);
  protected readonly i18n = inject(TranslationService);
  private readonly router = inject(Router);
  private readonly currentUrl = signal(this.router.url);
  protected localeSaveError = '';

  constructor() {
    this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe((event) => {
        this.currentUrl.set(event.urlAfterRedirects);
      });
    effect(() => {
      this.i18n.locale();
      const match = TITLE_KEYS.find(([path]) => this.currentUrl().startsWith(path));
      this.i18n.setTitle(match?.[1] ?? 'meta.default');
    });
    effect(() => {
      const user = this.auth.currentUser();
      if (user === null) {
        this.profile.resetCosmetics();
        return;
      }
      this.profile.getCosmetics().subscribe({ error: () => undefined });
    });
  }

  ngOnInit(): void {
    this.auth.refresh().subscribe();
  }

  protected chooseLocale(locale: Locale): void {
    if (locale === this.i18n.locale()) return;
    this.localeSaveError = '';
    this.i18n.setLocale(locale);
    if (this.auth.currentUser() !== null) {
      this.auth.updatePreferredLocale(locale).subscribe({
        error: () => (this.localeSaveError = this.i18n.t('locale.saveError')),
      });
    }
  }
}
