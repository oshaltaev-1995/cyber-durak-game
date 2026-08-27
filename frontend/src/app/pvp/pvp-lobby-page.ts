import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { PvPApiService } from '../core/pvp/pvp-api.service';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';

@Component({
  selector: 'app-pvp-lobby-page',
  imports: [FormsModule, RouterLink],
  templateUrl: './pvp-lobby-page.html',
  styleUrl: './pvp-lobby-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PvPLobbyPageComponent {
  private readonly api = inject(PvPApiService);
  private readonly credentials = inject(PvPCredentialStore);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthService);
  protected readonly nickname = signal('');
  protected readonly inviteCode = signal('');
  protected readonly pending = signal(false);
  protected readonly error = signal<string | null>(null);

  protected createRoom(): void {
    if (this.pending()) return;
    this.pending.set(true);
    this.error.set(null);
    this.api
      .createRoom(this.auth.currentUser() === null ? this.nickname().trim() : null)
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
    if (code !== '') void this.router.navigate(['/join', code]);
  }

  private errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse && error.status === 422) {
      return 'Введите имя длиной от 1 до 24 символов.';
    }
    return 'Не удалось создать комнату. Попробуйте ещё раз.';
  }
}
