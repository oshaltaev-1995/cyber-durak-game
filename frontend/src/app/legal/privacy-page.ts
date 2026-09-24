import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../core/i18n/translation.service';
import { PRIVACY_DOCUMENTS } from './legal-content';
import { SUPPORT_EMAIL } from './policy-metadata';

@Component({
  selector: 'app-privacy-page',
  imports: [RouterLink],
  templateUrl: './privacy-page.html',
  styleUrl: './legal-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrivacyPageComponent {
  protected readonly i18n = inject(TranslationService);
  protected readonly document = computed(() => PRIVACY_DOCUMENTS[this.i18n.locale()]);
  protected readonly supportEmail = SUPPORT_EMAIL;
}
