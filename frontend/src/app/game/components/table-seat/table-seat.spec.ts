import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TableSeatComponent } from './table-seat';
import { HiddenTableSeat } from '../../presentation/table-seat.models';
import { TableSeatMapComponent } from '../table-seat-map/table-seat-map';

@Component({
  imports: [TableSeatMapComponent],
  template: `
    <div class="seat-prototype">
      <app-table-seat-map [seats]="seats()" />
      <div class="local-seat" data-position="bottom">Local face-up hand</div>
    </div>
  `,
})
class SeatPrototypeHost {
  readonly seats = signal<readonly HiddenTableSeat[]>([]);
}

const topSeat: HiddenTableSeat = {
  id: 'top',
  position: 'top',
  displayName: 'Opponent',
  cardCount: 7,
  badge: 'P2',
};

describe('TableSeatComponent', () => {
  let fixture: ComponentFixture<TableSeatComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [TableSeatComponent] }).compileComponents();
    fixture = TestBed.createComponent(TableSeatComponent);
    fixture.componentRef.setInput('seat', topSeat);
    fixture.detectChanges();
  });

  it('renders one accessible facedown card for every hidden card', () => {
    const element = fixture.nativeElement as HTMLElement;
    const cards = [...element.querySelectorAll<HTMLElement>('.hidden-card')];

    expect(cards).toHaveLength(7);
    expect(cards[0].getAttribute('aria-label')).toContain('1');
    expect(cards[6].getAttribute('aria-label')).toContain('7');
    expect(element.textContent).toContain('Opponent');
    expect(element.textContent).toContain('7');
  });

  it('never requires or exposes hidden card identities', () => {
    const markup = (fixture.nativeElement as HTMLElement).innerHTML;

    expect(markup).not.toContain('6C');
    expect(markup).not.toContain('QD');
    expect(markup).not.toContain('10H');
    expect(markup).not.toContain('card.code');
  });

  it('updates count and uses stronger compression for large TAKE hands', () => {
    fixture.componentRef.setInput('seat', { ...topSeat, cardCount: 16 });
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.hidden-card')).toHaveLength(16);
    expect(element.querySelector('.hidden-hand')?.classList).toContain('hand-huge');
  });
});

describe('table seat presentation fixtures', () => {
  it('represents three seats as top, side, and local bottom positions', async () => {
    await TestBed.configureTestingModule({ imports: [SeatPrototypeHost] }).compileComponents();
    const fixture = TestBed.createComponent(SeatPrototypeHost);
    fixture.componentInstance.seats.set([
      topSeat,
      { ...topSeat, id: 'left', position: 'left', displayName: 'Left' },
    ]);
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.position-top')).not.toBeNull();
    expect(element.querySelector('.position-left')).not.toBeNull();
    expect(element.querySelector('[data-position="bottom"]')).not.toBeNull();
  });

  it('represents four seats without enabling a four-player game mode', async () => {
    await TestBed.configureTestingModule({ imports: [SeatPrototypeHost] }).compileComponents();
    const fixture = TestBed.createComponent(SeatPrototypeHost);
    fixture.componentInstance.seats.set([
      topSeat,
      { ...topSeat, id: 'left', position: 'left', displayName: 'Left' },
      { ...topSeat, id: 'right', position: 'right', displayName: 'Right' },
    ]);
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('app-table-seat')).toHaveLength(3);
    expect(element.querySelector('.seat-map')?.classList).toContain('has-side-seats');
    expect(element.querySelector('.position-right')).not.toBeNull();
    expect(element.querySelector('[data-position="bottom"]')).not.toBeNull();
  });
});
