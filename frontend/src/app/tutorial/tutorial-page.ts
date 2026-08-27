import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PlayingCardComponent } from '../game/components/playing-card/playing-card';
import { TUTORIAL_LESSONS } from './tutorial-data';

@Component({
  selector: 'app-tutorial-page',
  imports: [PlayingCardComponent, RouterLink],
  templateUrl: './tutorial-page.html',
  styleUrl: './tutorial-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TutorialPageComponent {
  protected readonly lessons = TUTORIAL_LESSONS;
  protected readonly stepIndex = signal(0);
  protected readonly selectedChoice = signal<string | null>(null);
  protected readonly complete = signal(false);
  protected readonly lesson = computed(() => this.lessons[this.stepIndex()]);
  protected readonly choiceIsCorrect = computed(() => {
    const exercise = this.lesson().exercise;
    return exercise !== null && this.selectedChoice() === exercise.answer;
  });
  protected readonly canContinue = computed(
    () => this.lesson().exercise === null || this.choiceIsCorrect(),
  );

  protected choose(choiceId: string): void {
    this.selectedChoice.set(choiceId);
  }

  protected previous(): void {
    if (this.stepIndex() === 0) {
      return;
    }
    this.stepIndex.update((step) => step - 1);
    this.selectedChoice.set(null);
  }

  protected next(): void {
    if (!this.canContinue()) {
      return;
    }
    if (this.stepIndex() === this.lessons.length - 1) {
      this.complete.set(true);
      return;
    }
    this.stepIndex.update((step) => step + 1);
    this.selectedChoice.set(null);
  }

  protected restart(): void {
    this.stepIndex.set(0);
    this.selectedChoice.set(null);
    this.complete.set(false);
  }
}
