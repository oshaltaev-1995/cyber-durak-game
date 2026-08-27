import { GameCard } from '../core/api/game-api.models';

export interface TutorialChoice {
  readonly id: string;
  readonly label: string;
}

export interface TutorialExercise {
  readonly prompt: string;
  readonly choices: readonly TutorialChoice[];
  readonly answer: string;
  readonly success: string;
  readonly retry: string;
}

export interface TutorialLesson {
  readonly id: string;
  readonly title: string;
  readonly lead: string;
  readonly points: readonly string[];
  readonly cards: readonly GameCard[];
  readonly cardCaption: string | null;
  readonly equations: readonly string[];
  readonly note: string | null;
  readonly exercise: TutorialExercise | null;
}

const card = (
  code: string,
  rank: string,
  suit: GameCard['suit'],
  baseValue: number,
  effectiveValue = baseValue,
  isTrump = false,
): GameCard => ({
  code,
  rank,
  suit,
  base_value: baseValue,
  effective_value: effectiveValue,
  is_trump: isTrump,
});

export const TUTORIAL_LESSONS: readonly TutorialLesson[] = [
  {
    id: 'goal',
    title: 'Цель и карты',
    lead: 'Избавьтесь от всех карт раньше соперника.',
    points: [
      'Каждый начинает с 7 карт.',
      'Партия состоит из конов: атака, ответ и добор до семи.',
      'Открытая верхняя карта колоды задаёт козыри текущего кона.',
    ],
    cards: [
      card('6C', '6', 'clubs', 6),
      card('10D', '10', 'diamonds', 10),
      card('JH', 'J', 'hearts', 12),
      card('QS', 'Q', 'spades', 15),
      card('KC', 'K', 'clubs', 18),
      card('AD', 'A', 'diamonds', 20),
    ],
    cardCaption: '6–10 стоят по номиналу; J = 12, Q = 15, K = 18, A = 20.',
    equations: ['6 · 7 · 8 · 9 · 10 · 12 · 15 · 18 · 20'],
    note: 'Карты на столе уходят в бито или к тому, кто решил взять.',
    exercise: null,
  },
  {
    id: 'trump',
    title: 'Двойной козырь',
    lead: 'Если открыта 7♥, козыри — все червы и все семёрки.',
    points: [
      'Козырь удваивает стоимость карты.',
      'В начале матча ходит владелец самого младшего козыря.',
    ],
    cards: [
      card('7S', '7', 'spades', 7, 14, true),
      card('8H', '8', 'hearts', 8, 16, true),
      card('KH', 'K', 'hearts', 18, 36, true),
      card('8C', '8', 'clubs', 8),
      card('6H', '6', 'hearts', 6, 12, true),
    ],
    cardCaption: 'Открытая карта: 7♥. Число внизу — эффективная стоимость.',
    equations: ['7♠ = 14', '8♥ = 16', 'K♥ = 36', '8♣ = 8'],
    note: null,
    exercise: {
      prompt: 'Кто младше среди этих козырей?',
      choices: [
        { id: '7S', label: '7♠ = 14' },
        { id: '8H', label: '8♥ = 16' },
        { id: '6H', label: '6♥ = 12' },
      ],
      answer: '6H',
      success: 'Верно: 6♥ стоит 12 и начинает раньше козырей стоимостью 14 и 16.',
      retry: 'Смотрите на удвоенную стоимость, а не только на ранг.',
    },
  },
  {
    id: 'attack',
    title: 'Первый ход',
    lead: 'Одной картой можно ходить всегда. Несколько карт должны быть связаны.',
    points: [
      'Карты одного ранга можно играть вместе.',
      'Группы с одинаковой эффективной суммой образуют арифметическую связь.',
    ],
    cards: [
      card('9C', '9', 'clubs', 9),
      card('9D', '9', 'diamonds', 9),
      card('KC', 'K', 'clubs', 18),
      card('JH', 'J', 'hearts', 12),
      card('6S', '6', 'spades', 6),
    ],
    cardCaption: null,
    equations: ['9 + 9 = 18 = K', 'J + 6 = 12 + 6 = 18 = K', '9 + 7 ✕'],
    note: 'Не нужно изучать алгоритм: во время настоящей игры сервер проверит выбранные карты.',
    exercise: {
      prompt: 'Какой набор связан с K = 18?',
      choices: [
        { id: 'nines', label: '9 + 9 + K' },
        { id: 'mixed', label: '9 + 7 + K' },
        { id: 'unrelated', label: '8 + 7 + K' },
      ],
      answer: 'nines',
      success: 'Да: две девятки дают 18 — столько же, сколько Король.',
      retry: 'Найдите две непустые группы с одинаковой суммой.',
    },
  },
  {
    id: 'defense',
    title: 'Как покрывать',
    lead: 'Защита должна быть строго дороже активной атаки.',
    points: [
      'Можно выбрать любые карты: важна только сумма эффективных значений.',
      'Равенства недостаточно — нужно строго больше.',
    ],
    cards: [
      card('QH', 'Q', 'hearts', 15),
      card('QD', 'Q', 'diamonds', 15),
      card('10C', '10', 'clubs', 10),
    ],
    cardCaption: 'Защита Q + Q + 10 даёт 40.',
    equations: ['Атака: J + J + 6 + 6 = 36', '40 > 36 ✓', '36 = 36 ✕'],
    note: null,
    exercise: {
      prompt: 'Что покроет атаку 36?',
      choices: [
        { id: 'equal', label: 'Карты на 36' },
        { id: 'greater', label: 'Q + Q + 10 = 40' },
        { id: 'lower', label: 'Карты на 35' },
      ],
      answer: 'greater',
      success: 'Верно: 40 строго больше 36.',
      retry: 'Равенство не покрывает. Нужна сумма строго больше 36.',
    },
  },
  {
    id: 'throw-in',
    title: 'Как подкидывать',
    lead: 'После покрытия прямыми опорами становятся карты, которыми только что отбились.',
    points: [
      'J(12), покрытый K(18), больше не даёт прямую цель 12; K даёт ранг K и значение 18.',
      'Старые карты всё равно остаются в сумме и среднем стола.',
      'Если отбились 7 + J, одним действием можно подкинуть 7 + J: оба ранга есть в опоре.',
    ],
    cards: [
      card('JC', 'J', 'clubs', 12),
      card('KD', 'K', 'diamonds', 18),
      card('7S', '7', 'spades', 7),
      card('JH', 'J', 'hearts', 12),
    ],
    cardCaption: 'Атака J покрыта K. В следующем примере опоры защиты — 7 и J.',
    equations: ['10 + 8 = 18 = K', 'опоры 7 + J → можно подкинуть 7 + J'],
    note: null,
    exercise: {
      prompt: 'Опоры — 7 и J. Что подходит по рангам?',
      choices: [
        { id: 'anchored', label: '7 + J' },
        { id: 'foreign', label: '7 + 9' },
        { id: 'old', label: '6' },
      ],
      answer: 'anchored',
      success: 'Верно: каждый выбранный ранг уже есть среди текущих опор.',
      retry: 'Все выбранные ранги должны присутствовать среди карт последней защиты.',
    },
  },
  {
    id: 'arithmetic',
    title: 'Сумма и среднее',
    lead: 'Все физические карты на столе создают две дополнительные цели.',
    points: [
      'Сумма стола может стать целью для подкидывания.',
      'Среднее считается точно и никогда не округляется.',
      'Активная атака — отдельная величина: покрывать нужно только текущий пакет.',
    ],
    cards: [
      card('JC', 'J', 'clubs', 12),
      card('KD', 'K', 'diamonds', 18),
      card('QS', 'Q', 'spades', 15),
    ],
    cardCaption: 'J и K лежат на столе. Q или 7 + 8 совпадают со средним.',
    equations: ['12 + 18 = 30', '(12 + 18) / 2 = 15', 'Q = 15', '7 + 8 = 15'],
    note: 'Сумма 30 также доступна как самостоятельная цель.',
    exercise: {
      prompt: 'Что совпадает со средним 15?',
      choices: [
        { id: 'queen', label: 'Q = 15' },
        { id: 'king', label: 'K = 18' },
        { id: 'ten', label: '10 = 10' },
      ],
      answer: 'queen',
      success: 'Точно: (12 + 18) / 2 = 15 = Q.',
      retry: 'Среднее здесь равно 15. Нужна точная сумма без округления.',
    },
  },
  {
    id: 'transfer',
    title: 'Перевод',
    lead: 'Перевод должен точно совпасть с текущей атакой.',
    points: [
      'При атаке 18 карты 9 + 9 переводят ровно 18.',
      'Перевод расширяет тот же пакет: следующая цель становится 36, затем 72.',
      'После первой успешной защиты переводы закрыты до конца кона.',
    ],
    cards: [
      card('9C', '9', 'clubs', 9),
      card('9D', '9', 'diamonds', 9),
      card('KC', 'K', 'clubs', 18),
    ],
    cardCaption: null,
    equations: ['18 → 36 → 72', '9 + 9 = 18 ✓', '19 ≠ 18 ✕'],
    note: null,
    exercise: {
      prompt: 'Чем перевести атаку 18?',
      choices: [
        { id: 'exact', label: '9 + 9 = 18' },
        { id: 'above', label: '10 + 9 = 19' },
        { id: 'below', label: '10 + 7 = 17' },
      ],
      answer: 'exact',
      success: 'Да: перевод требует точного равенства.',
      retry: 'Для перевода недостаточно быть больше — нужна точная сумма 18.',
    },
  },
  {
    id: 'endgame',
    title: 'Бито, взять и конец игры',
    lead: 'После каждого кона стол разрешается, затем игроки добирают карты.',
    points: [
      'Бито: защитник начинает следующий кон. Последняя успешная защита завершает кон автоматически.',
      'Взять: защитник забирает весь стол, а прежний атакующий сохраняет ход.',
      'Если карт в колоде мало, добор выравнивает руки насколько возможно.',
      'Пустая колода означает игру без козырей.',
    ],
    cards: [],
    cardCaption: null,
    equations: ['один без карт → победа', 'оба без карт → Ничья 🤝'],
    note: 'Победа проверяется только после завершения кона, движения стола и добора.',
    exercise: null,
  },
];
