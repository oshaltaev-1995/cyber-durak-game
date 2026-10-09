import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { PvPApiService } from '../core/pvp/pvp-api.service';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { TranslationService } from '../core/i18n/translation.service';

@Component({
  selector: 'app-pvp-lobby-page',
  imports: [FormsModule, RouterLink],
  templateUrl: './pvp-lobby-page.html',
  styleUrl: './pvp-lobby-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PvPLobbyPageComponent implements OnInit {
  private readonly api = inject(PvPApiService);
  private readonly credentials = inject(PvPCredentialStore);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthService);
  protected readonly i18n = inject(TranslationService);
  protected readonly nickname = signal('');
  protected readonly inviteCode = signal('');
  protected readonly pending = signal(false);
  protected readonly multiplayerEnabled = signal(false);
  protected readonly selectedPlayers = signal<2 | 3 | 4>(2);
  protected readonly playerCounts = [2, 3, 4] as const;
  protected readonly error = signal<string | null>(null);
  protected readonly roomCodeTouched = signal(false);

  ngOnInit(): void {
    this.api.getCapabilities().subscribe({
      next: (capabilities) => this.multiplayerEnabled.set(capabilities.multiplayer_3_4_enabled),
      error: () => this.multiplayerEnabled.set(false),
    });
  }

  protected createRoom(): void {
    if (this.pending()) return;
    this.pending.set(true);
    this.error.set(null);
    this.api
      .createRoom(
        this.auth.currentUser() === null ? this.nickname().trim() : null,
        this.selectedPlayers(),
      )
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (response) => {
          this.credentials.save(response.invite_code, response.credential);
          void this.router.navigate(['/pvp/room', response.invite_code]);
        },
        error: (error: unknown) => this.error.set(this.errorMessage(error)),
      });
  }

  protected openInvite(): void {
    const code = this.inviteCode().trim();
    this.roomCodeTouched.set(true);
    if (code !== '') void this.router.navigate(['/join', code]);
  }

  protected roomCodeInvalid(): boolean {
    return this.roomCodeTouched() && this.inviteCode().trim() === '';
  }

  private errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const code = (error.error as { detail?: { code?: string } })?.detail?.code;
      if (code === 'FEATURE_NOT_AVAILABLE') return this.i18n.t('pvp.multiplayerUnavailable');
      if (error.status === 422) return this.i18n.t('pvp.invalidNickname');
    }
    return this.i18n.t('pvp.createFailed');
  }
}
