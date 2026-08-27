import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { PvPApiService } from '../core/pvp/pvp-api.service';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { PvPRoomStatus } from '../core/pvp/pvp.models';

@Component({
  selector: 'app-pvp-join-page',
  imports: [FormsModule, RouterLink],
  templateUrl: './pvp-join-page.html',
  styleUrl: './pvp-lobby-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PvPJoinPageComponent implements OnInit {
  private readonly api = inject(PvPApiService);
  private readonly credentials = inject(PvPCredentialStore);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthService);
  protected readonly status = signal<PvPRoomStatus | null>(null);
  protected readonly nickname = signal('');
  protected readonly pending = signal(true);
  protected readonly error = signal<string | null>(null);
  protected inviteCode = '';

  ngOnInit(): void {
    this.inviteCode = this.route.snapshot.paramMap.get('inviteCode') ?? '';
    if (this.credentials.get(this.inviteCode) !== null) {
      void this.router.navigate(['/pvp/room', this.inviteCode]);
      return;
    }
    this.loadStatus();
  }

  protected joinRoom(): void {
    if (this.pending()) return;
    this.pending.set(true);
    this.error.set(null);
    this.api
      .joinRoom(this.inviteCode, this.auth.currentUser() === null ? this.nickname().trim() : null)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (response) => {
          this.credentials.save(response.invite_code, response.credential);
          void this.router.navigate(['/pvp/room', response.invite_code]);
        },
        error: (error: unknown) => this.error.set(this.errorMessage(error)),
      });
  }

  private loadStatus(): void {
    this.pending.set(true);
    this.api
      .getRoom(this.inviteCode)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (status) => this.status.set(status),
        error: () => this.error.set('Комната не найдена или уже закрыта.'),
      });
  }

  private errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const code = (error.error as { detail?: { code?: string } })?.detail?.code;
      if (code === 'ROOM_FULL') return 'Комната уже заполнена.';
      if (code === 'ROOM_NOT_FOUND' || code === 'INVITE_EXPIRED') {
        return 'Комната не найдена или уже закрыта.';
      }
      if (code === 'INVALID_NICKNAME' || error.status === 422) {
        return 'Введите имя длиной от 1 до 24 символов.';
      }
    }
    return 'Не удалось присоединиться. Попробуйте ещё раз.';
  }
}
