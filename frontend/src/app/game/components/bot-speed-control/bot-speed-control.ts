import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { TranslationService } from '../../../core/i18n/translation.service';
import { BotPresentationSpeed } from '../../presentation/bot-presentation-queue';

@Component({
  selector: 'app-bot-speed-control',
  templateUrl: './bot-speed-control.html',
  styleUrl: './bot-speed-control.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BotSpeedControlComponent {
  protected readonly i18n = inject(TranslationService);
  readonly speed = input.required<BotPresentationSpeed>();
  readonly compact = input(false);
  readonly speedChange = output<BotPresentationSpeed>();
  protected readonly speeds = ['fast', 'normal', 'relaxed'] as const;

  protected label(speed: BotPresentationSpeed): string {
    return this.i18n.t(`game.botSpeed${speed[0].toUpperCase()}${speed.slice(1)}` as never);
  }
}
