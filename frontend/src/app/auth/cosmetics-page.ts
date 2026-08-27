import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import {
  CosmeticCategory,
  CosmeticEquipRequest,
  CosmeticItem,
  CosmeticsResponse,
} from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';

@Component({
  selector: 'app-cosmetics-page',
  imports: [RouterLink],
  templateUrl: './cosmetics-page.html',
  styleUrl: './cosmetics-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CosmeticsPageComponent implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly profile = inject(ProfileService);

  protected readonly catalogue = signal<CosmeticsResponse | null>(null);
  protected readonly pending = signal(false);
  protected readonly equipping = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly cardBacks = computed(() => this.byCategory('CARD_BACK'));
  protected readonly tables = computed(() => this.byCategory('TABLE_THEME'));
  protected readonly frames = computed(() => this.byCategory('PROFILE_FRAME'));

  ngOnInit(): void {
    if (this.auth.currentUser() !== null) {
      this.load();
      return;
    }
    this.auth.refresh().subscribe((user) => {
      if (user !== null) {
        this.load();
      }
    });
  }

  protected equip(item: CosmeticItem): void {
    if (!item.unlocked || item.equipped || this.equipping() !== null) {
      return;
    }
    this.error.set(null);
    this.equipping.set(item.code);
    const request: CosmeticEquipRequest =
      item.category === 'CARD_BACK'
        ? { card_back_code: item.code }
        : item.category === 'TABLE_THEME'
          ? { table_theme_code: item.code }
          : { profile_frame_code: item.code };
    this.profile
      .equipCosmetics(request)
      .pipe(finalize(() => this.equipping.set(null)))
      .subscribe({
        next: (catalogue) => this.catalogue.set(catalogue),
        error: (error: unknown) => this.error.set(this.messageFor(error)),
      });
  }

  protected unlockLabel(item: CosmeticItem): string {
    if (item.unlock.type === 'DEFAULT') {
      return 'Доступно всем';
    }
    if (item.unlock.type === 'LEVEL') {
      return `Откроется на уровне ${item.unlock.requirement}`;
    }
    return `Нужно достижение «${item.unlock.achievement_title ?? item.unlock.requirement}»`;
  }

  private byCategory(category: CosmeticCategory): readonly CosmeticItem[] {
    return this.catalogue()?.items.filter((item) => item.category === category) ?? [];
  }

  private load(): void {
    this.pending.set(true);
    this.error.set(null);
    this.profile
      .getCosmetics()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (catalogue) => this.catalogue.set(catalogue),
        error: (error: unknown) => this.error.set(this.messageFor(error)),
      });
  }

  private messageFor(error: unknown): string {
    if (error instanceof HttpErrorResponse && error.status === 409) {
      return 'Это оформление пока недоступно.';
    }
    return 'Не удалось обновить оформление. Попробуйте снова.';
  }
}
