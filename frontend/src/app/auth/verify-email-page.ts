import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth/auth.service';

@Component({
  selector: 'app-verify-email-page',
  imports: [RouterLink],
  templateUrl: './verify-email-page.html',
  styleUrl: './auth-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VerifyEmailPageComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly token = this.route.snapshot.queryParamMap.get('token') ?? '';
  protected readonly pending = signal(true);
  protected readonly verified = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {},
      replaceUrl: true,
    });
    if (!this.token) {
      this.pending.set(false);
      this.error.set('Ссылка подтверждения недействительна.');
      return;
    }
    this.auth.confirmVerification(this.token).subscribe({
      next: () => {
        this.pending.set(false);
        this.verified.set(true);
      },
      error: () => {
        this.pending.set(false);
        this.error.set('Ссылка истекла или уже использована. Запросите новое письмо в профиле.');
      },
    });
  }
}
