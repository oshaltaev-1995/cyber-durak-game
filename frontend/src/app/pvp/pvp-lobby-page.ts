import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { PvPApiService } from '../core/pvp/pvp-api.service';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { TranslationService } from '../core/i18n/translation.service';
import { DeckCount, DeckProfile } from '../core/api/game-api.models';
import { DeckConfigSelectorComponent } from '../core/deck/deck-config-selector';
import {
  RoomPlayerCount,
  humanPlayerOptions,
  nextHumanPlayerCount,
} from './mixed-room-composition';

@Component({
  selector: 'app-pvp-lobby-page',
  imports: [DeckConfigSelectorComponent, FormsModule, RouterLink],
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
  protected readonly capabilityState = signal<'loading' | 'ready' | 'failed'>('loading');
  protected readonly multiplayerEnabled = signal(false);
  protected readonly deckVariantsEnabled = signal(false);
  protected readonly mixedRoomsEnabled = signal(false);
  protected readonly selectedPlayers = signal<2 | 3 | 4>(2);
  protected readonly selectedHumanPlayers = signal<2 | 3 | 4>(2);
  protected readonly selectedDeckProfile = signal<DeckProfile>('classic');
  protected readonly selectedDeckCount = signal<DeckCount>(1);
  protected readonly playerCounts = [2, 3, 4] as const;
  protected readonly error = signal<string | null>(null);
  protected readonly roomCodeTouched = signal(false);

  ngOnInit(): void {
    this.loadCapabilities();
  }

  protected retryCapabilities(): void {
    if (this.capabilityState() === 'loading') return;
    this.loadCapabilities();
  }

  private loadCapabilities(): void {
    this.capabilityState.set('loading');
    this.api.getCapabilities().subscribe({
      next: (capabilities) => {
        this.multiplayerEnabled.set(capabilities.multiplayer_3_4_enabled);
        this.deckVariantsEnabled.set(capabilities.deck_variants_enabled ?? false);
        this.mixedRoomsEnabled.set(capabilities.mixed_rooms_enabled ?? false);
        this.capabilityState.set('ready');
      },
      error: () => {
        this.multiplayerEnabled.set(false);
        this.deckVariantsEnabled.set(false);
        this.mixedRoomsEnabled.set(false);
        this.capabilityState.set('failed');
      },
    });
  }

  protected createRoom(): void {
    if (this.pending() || this.capabilityState() !== 'ready') return;
    this.pending.set(true);
    this.error.set(null);
    const nickname = this.auth.currentUser() === null ? this.nickname().trim() : null;
    const capacity = this.selectedPlayers();
    const deckConfig = {
      deck_profile: this.selectedDeckProfile(),
      deck_count: this.selectedDeckCount(),
    } as const;
    const request =
      this.mixedRoomsEnabled() && this.selectedHumanPlayers() < capacity
        ? this.api.createRoom(nickname, capacity, deckConfig, this.selectedHumanPlayers())
        : this.api.createRoom(nickname, capacity, deckConfig);
    request.pipe(finalize(() => this.pending.set(false))).subscribe({
      next: (response) => {
        this.credentials.save(response.invite_code, response.credential);
        void this.router.navigate(['/pvp/room', response.invite_code]);
      },
      error: (error: unknown) => this.error.set(this.errorMessage(error)),
    });
  }

  protected selectPlayerCount(count: RoomPlayerCount): void {
    this.selectedHumanPlayers.set(
      nextHumanPlayerCount(this.selectedPlayers(), this.selectedHumanPlayers(), count),
    );
    this.selectedPlayers.set(count);
  }

  protected humanPlayerCounts(): readonly RoomPlayerCount[] {
    return humanPlayerOptions(this.selectedPlayers());
  }

  protected botCount(): number {
    return this.selectedPlayers() - this.selectedHumanPlayers();
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
      if (code === 'FEATURE_NOT_AVAILABLE') return this.i18n.t('game.featureUnavailable');
      if (error.status === 422) return this.i18n.t('pvp.invalidNickname');
    }
    return this.i18n.t('pvp.createFailed');
  }
}
