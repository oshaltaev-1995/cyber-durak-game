import {
  ChangeDetectionStrategy,
  Component,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { TranslationService } from '../../../core/i18n/translation.service';

export const TURN_REMINDER_DELAY_MS = 30_000;

@Component({
  selector: 'app-turn-reminder',
  templateUrl: './turn-reminder.html',
  styleUrl: './turn-reminder.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TurnReminderComponent implements OnInit, OnChanges, OnDestroy {
  @Input() contextKey = '';
  protected readonly i18n = inject(TranslationService);
  protected readonly reminderVisible = signal(false);
  private startedAt = 0;
  private reminderTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.startCycle();
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
  }

  ngOnChanges(): void {
    if (this.startedAt !== 0) this.startCycle();
  }

  private startCycle(): void {
    if (this.reminderTimer !== null) clearTimeout(this.reminderTimer);
    this.startedAt = Date.now();
    this.reminderVisible.set(false);
    this.reminderTimer = setTimeout(() => this.showReminder(), TURN_REMINDER_DELAY_MS);
  }

  ngOnDestroy(): void {
    if (this.reminderTimer !== null) clearTimeout(this.reminderTimer);
    document.removeEventListener('visibilitychange', this.handleVisibilityChange);
  }

  private readonly handleVisibilityChange = (): void => {
    if (
      document.visibilityState === 'visible' &&
      !this.reminderVisible() &&
      Date.now() - this.startedAt >= TURN_REMINDER_DELAY_MS
    ) {
      this.showReminder();
    }
  };

  private showReminder(): void {
    if (this.reminderVisible()) return;
    this.reminderVisible.set(true);
    if (this.reminderTimer !== null) {
      clearTimeout(this.reminderTimer);
      this.reminderTimer = null;
    }
  }
}
