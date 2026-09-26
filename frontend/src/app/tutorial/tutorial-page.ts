import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslationService } from '../core/i18n/translation.service';
import { formatCardShort } from '../game/card-presentation';
import { PlayingCardComponent } from '../game/components/playing-card/playing-card';
import { TUTORIAL_LESSONS_EN, TUTORIAL_LESSONS_RU } from './tutorial-data';

@Component({
  selector: 'app-tutorial-page',
  imports: [PlayingCardComponent, RouterLink],
  templateUrl: './tutorial-page.html',
  styleUrl: './tutorial-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TutorialPageComponent {
  protected readonly i18n = inject(TranslationService);
  protected readonly lessons = computed(() =>
    this.i18n.locale() === 'ru' ? TUTORIAL_LESSONS_RU : TUTORIAL_LESSONS_EN,
  );
  protected readonly stepIndex = signal(0);
  protected readonly selectedChoice = signal<string | null>(null);
  protected readonly selectedPracticalCodes = signal<ReadonlySet<string>>(new Set());
  protected readonly practicalAttempted = signal(false);
  protected readonly complete = signal(false);
  protected readonly lesson = computed(() => this.lessons()[this.stepIndex()]);
  protected readonly choiceIsCorrect = computed(() => {
    const exercise = this.lesson().exercise;
    return exercise !== null && this.selectedChoice() === exercise.answer;
  });
  protected readonly selectedPracticalCards = computed(() => {
    const practical = this.lesson().practical;
    if (practical === undefined) return [];
    const selected = this.selectedPracticalCodes();
    return practical.cards.filter((card) => selected.has(card.code));
  });
  protected readonly practicalTotal = computed(() =>
    this.selectedPracticalCards().reduce((total, card) => total + card.effective_value, 0),
  );
  protected readonly practicalIsCorrect = computed(() => {
    const practical = this.lesson().practical;
    if (practical === undefined) return false;
    const selected = this.selectedPracticalCodes();
    return (
      selected.size === practical.answerCodes.length &&
      practical.answerCodes.every((code) => selected.has(code))
    );
  });
  protected readonly canContinue = computed(() => {
    const lesson = this.lesson();
    const quizReady = lesson.exercise === null || this.choiceIsCorrect();
    const practicalReady =
      lesson.practical === undefined || (this.practicalAttempted() && this.practicalIsCorrect());
    return quizReady && practicalReady;
  });

  protected choose(choiceId: string): void {
    this.selectedChoice.set(choiceId);
  }

  protected togglePracticalCard(code: string): void {
    this.selectedPracticalCodes.update((current) => {
      const next = new Set(current);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
    this.practicalAttempted.set(false);
  }

  protected submitPractical(): void {
    if (this.selectedPracticalCodes().size === 0) return;
    this.practicalAttempted.set(true);
  }

  protected practicalSelectionText(): string {
    const cards = this.selectedPracticalCards();
    if (cards.length === 0) return this.i18n.t('tutorial.practiceEmpty');
    return this.i18n.t('tutorial.practiceSelected', {
      cards: cards.map(formatCardShort).join(' + '),
      total: this.practicalTotal(),
    });
  }

  protected previous(): void {
    if (this.stepIndex() === 0) {
      return;
    }
    this.stepIndex.update((step) => step - 1);
    this.resetResponse();
  }

  protected next(): void {
    if (!this.canContinue()) {
      return;
    }
    if (this.stepIndex() === this.lessons().length - 1) {
      this.complete.set(true);
      return;
    }
    this.stepIndex.update((step) => step + 1);
    this.resetResponse();
  }

  protected restart(): void {
    this.stepIndex.set(0);
    this.resetResponse();
    this.complete.set(false);
  }

  private resetResponse(): void {
    this.selectedChoice.set(null);
    this.selectedPracticalCodes.set(new Set());
    this.practicalAttempted.set(false);
  }
}
