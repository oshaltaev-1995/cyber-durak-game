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

export interface TutorialPractical {
  readonly prompt: string;
  readonly cards: readonly GameCard[];
  readonly answerCodes: readonly string[];
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
  readonly practical?: TutorialPractical;
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

export const TUTORIAL_LESSONS_RU: readonly TutorialLesson[] = [
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
    note: 'Не нужно запоминать все связи сразу: во время партии игра проверит выбранные карты.',
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
    id: 'practice-defense',
    title: 'Попробуйте покрыть',
    lead: 'Соперник атакует Королём стоимостью 18. Соберите защиту строго дороже.',
    points: [
      'Нажмите на карты J и 7: вместе они дают 19.',
      'Проверьте сумму выбора и нажмите «Покрыть».',
    ],
    cards: [card('KH', 'K', 'hearts', 18)],
    cardCaption: 'Атака соперника: K = 18.',
    equations: ['J(12) + 7 = 19', '19 > 18 ✓'],
    note: 'Это учебный пример: он не создаёт настоящую партию и не влияет на прогресс.',
    exercise: null,
    practical: {
      prompt: 'Выберите защиту и выполните действие.',
      cards: [
        card('JC', 'J', 'clubs', 12),
        card('7D', '7', 'diamonds', 7),
        card('6S', '6', 'spades', 6),
      ],
      answerCodes: ['JC', '7D'],
      success: 'Верно: вы выбрали J + 7 = 19 и покрыли атаку 18.',
      retry: 'Нужны именно J и 7: их сумма 19 строго больше атаки 18.',
    },
  },
  {
    id: 'throw-in',
    title: 'Как подкидывать',
    lead: 'После покрытия прямые подсказки дают карты последней защиты.',
    points: [
      'J(12), покрытый K(18), больше не даёт прямую цель 12; K даёт ранг K и значение 18.',
      'Старые карты всё равно остаются в сумме и среднем стола.',
      'Если отбились 7 + J, одним действием можно подкинуть 7 + J: оба ранга есть в последней защите.',
      'Сумма карт последней защиты тоже доступна: после J(12) + 8(8) = 20 можно подкинуть A = 20.',
      'Продвинутый приём: карты стола и выбора могут собрать непрерывный ряд минимум из пяти рангов.',
    ],
    cards: [
      card('JC', 'J', 'clubs', 12),
      card('KD', 'K', 'diamonds', 18),
      card('7S', '7', 'spades', 7),
      card('JH', 'J', 'hearts', 12),
    ],
    cardCaption: 'Атака J покрыта K. В следующем примере последняя защита — 7 и J.',
    equations: [
      '10 + 8 = 18 = K',
      'защита J + 8 = 20 → A = 20',
      'защита 7 + J → можно подкинуть 7 + J',
      '10, J, K, A + Q → ряд 10–A',
    ],
    note: null,
    exercise: {
      prompt: 'Последняя защита — 7 и J. Что подходит по рангам?',
      choices: [
        { id: 'anchored', label: '7 + J' },
        { id: 'foreign', label: '7 + 9' },
        { id: 'old', label: '6' },
      ],
      answer: 'anchored',
      success: 'Верно: каждый выбранный ранг есть среди карт последней защиты.',
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
      'Активная атака — отдельная величина: покрывать нужно только текущую незакрытую атаку.',
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
    lead: 'Обычный перевод точно совпадает с текущей атакой.',
    points: [
      'При атаке 18 карты 9 + 9 переводят ровно 18.',
      'Перевод расширяет ту же незакрытую атаку: следующая цель становится 36, затем 72.',
      'После первой успешной защиты переводы закрыты до конца кона.',
      'Если вся незакрытая атака одного ранга, точную часть перевода можно дополнить картами того же ранга.',
      'Число атакующих карт ограничено рукой текущего защитника; после перевода лимит пересчитывается по руке нового защитника.',
      '«Атака 2 / лимит 4» означает: две атакующие карты уже сыграны, максимум — четыре.',
    ],
    cards: [
      card('9C', '9', 'clubs', 9),
      card('9D', '9', 'diamonds', 9),
      card('KC', 'K', 'clubs', 18),
    ],
    cardCaption: null,
    equations: ['18 → 36 → 72', '9 + 9 = 18 ✓', '7 → 7 + 7 → 21', '19 ≠ 18 ✕'],
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
      'Бито: защитник начинает следующий кон. Если он успешно отбился последней картой или картами из руки, кон завершается автоматически и подкидывать больше нельзя.',
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

export const TUTORIAL_LESSONS_EN: readonly TutorialLesson[] = [
  {
    id: 'goal',
    title: 'Goal and cards',
    lead: 'Get rid of every card before your opponent.',
    points: [
      'Each player starts with 7 cards.',
      'A match consists of bouts: attack, response, then refill toward seven.',
      'The exposed top card of the deck defines trumps for the current bout.',
    ],
    cards: [
      card('6C', '6', 'clubs', 6),
      card('10D', '10', 'diamonds', 10),
      card('JH', 'J', 'hearts', 12),
      card('QS', 'Q', 'spades', 15),
      card('KC', 'K', 'clubs', 18),
      card('AD', 'A', 'diamonds', 20),
    ],
    cardCaption: '6–10 use their face value; J = 12, Q = 15, K = 18, A = 20.',
    equations: ['6 · 7 · 8 · 9 · 10 · 12 · 15 · 18 · 20'],
    note: 'Cards on the table either go to discard or to the player who takes.',
    exercise: null,
  },
  {
    id: 'trump',
    title: 'Dual trump',
    lead: 'If 7♥ is exposed, every Heart and every Seven is trump.',
    points: [
      'A trump card has double value.',
      'The owner of the lowest trump makes the first attack of the match.',
    ],
    cards: [
      card('7S', '7', 'spades', 7, 14, true),
      card('8H', '8', 'hearts', 8, 16, true),
      card('KH', 'K', 'hearts', 18, 36, true),
      card('8C', '8', 'clubs', 8),
      card('6H', '6', 'hearts', 6, 12, true),
    ],
    cardCaption: 'Exposed card: 7♥. The bottom number is the effective value.',
    equations: ['7♠ = 14', '8♥ = 16', 'K♥ = 36', '8♣ = 8'],
    note: null,
    exercise: {
      prompt: 'Which of these trumps is the lowest?',
      choices: [
        { id: '7S', label: '7♠ = 14' },
        { id: '8H', label: '8♥ = 16' },
        { id: '6H', label: '6♥ = 12' },
      ],
      answer: '6H',
      success: 'Correct: 6♥ is worth 12, below the trumps worth 14 and 16.',
      retry: 'Compare doubled effective values, not only ranks.',
    },
  },
  {
    id: 'attack',
    title: 'Initial attack',
    lead: 'A single card is always allowed. Multiple cards must be connected.',
    points: [
      'Cards of the same rank may be played together.',
      'Groups with equal effective totals form an arithmetic connection.',
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
    note: 'You do not need to memorize every connection at once: the game checks selected cards during play.',
    exercise: {
      prompt: 'Which set is connected to K = 18?',
      choices: [
        { id: 'nines', label: '9 + 9 + K' },
        { id: 'mixed', label: '9 + 7 + K' },
        { id: 'unrelated', label: '8 + 7 + K' },
      ],
      answer: 'nines',
      success: 'Yes: two Nines total 18, the same as a King.',
      retry: 'Find two non-empty groups with equal totals.',
    },
  },
  {
    id: 'defense',
    title: 'How to defend',
    lead: 'Defense must be strictly more valuable than the active attack.',
    points: [
      'Any cards may be selected: only their total effective value matters.',
      'Equality is not enough — the defense must be strictly greater.',
    ],
    cards: [
      card('QH', 'Q', 'hearts', 15),
      card('QD', 'Q', 'diamonds', 15),
      card('10C', '10', 'clubs', 10),
    ],
    cardCaption: 'Defense Q + Q + 10 totals 40.',
    equations: ['Attack: J + J + 6 + 6 = 36', '40 > 36 ✓', '36 = 36 ✕'],
    note: null,
    exercise: {
      prompt: 'Which defense covers an attack of 36?',
      choices: [
        { id: 'equal', label: 'Cards totaling 36' },
        { id: 'greater', label: 'Q + Q + 10 = 40' },
        { id: 'lower', label: 'Cards totaling 35' },
      ],
      answer: 'greater',
      success: 'Correct: 40 is strictly greater than 36.',
      retry: 'Equality does not defend. The total must be greater than 36.',
    },
  },
  {
    id: 'practice-defense',
    title: 'Try a defense',
    lead: 'Your opponent attacks with a King worth 18. Build a defense worth strictly more.',
    points: [
      'Select J and 7: together they total 19.',
      'Check the selected total, then press Defend.',
    ],
    cards: [card('KH', 'K', 'hearts', 18)],
    cardCaption: 'Opponent attack: K = 18.',
    equations: ['J(12) + 7 = 19', '19 > 18 ✓'],
    note: 'This is a tutorial example: it creates no match and awards no progression.',
    exercise: null,
    practical: {
      prompt: 'Select a defense and perform the action.',
      cards: [
        card('JC', 'J', 'clubs', 12),
        card('7D', '7', 'diamonds', 7),
        card('6S', '6', 'spades', 6),
      ],
      answerCodes: ['JC', '7D'],
      success: 'Correct: J + 7 = 19 defends against the attack of 18.',
      retry: 'Select J and 7: their total of 19 is strictly greater than the attack of 18.',
    },
  },
  {
    id: 'throw-in',
    title: 'How to throw in',
    lead: 'After defense, the latest defense cards provide the direct ranks and values.',
    points: [
      'A J(12) covered by K(18) no longer exposes 12; K exposes rank K and value 18.',
      'Older cards still contribute to table total and arithmetic mean.',
      'After defending with 7 + J, 7 + J may be thrown in together because both ranks appear in the latest defense.',
      'The latest defense total is also available: after J(12) + 8(8) = 20, A = 20 may be thrown in.',
      'Advanced: table and selected cards may form a continuous run of at least five ranks.',
    ],
    cards: [
      card('JC', 'J', 'clubs', 12),
      card('KD', 'K', 'diamonds', 18),
      card('7S', '7', 'spades', 7),
      card('JH', 'J', 'hearts', 12),
    ],
    cardCaption: 'Attack J is covered by K. In the next example, the latest defense is 7 and J.',
    equations: [
      '10 + 8 = 18 = K',
      'defense J + 8 = 20 → A = 20',
      'defense 7 + J → throw in 7 + J',
      '10, J, K, A + Q → run 10–A',
    ],
    note: null,
    exercise: {
      prompt: 'The latest defense is 7 and J. Which ranks fit?',
      choices: [
        { id: 'anchored', label: '7 + J' },
        { id: 'foreign', label: '7 + 9' },
        { id: 'old', label: '6' },
      ],
      answer: 'anchored',
      success: 'Correct: every selected rank is present among the latest defense cards.',
      retry: 'Every selected rank must be present among the latest defense cards.',
    },
  },
  {
    id: 'arithmetic',
    title: 'Total and mean',
    lead: 'All physical table cards create two additional targets.',
    points: [
      'The table total may become a throw-in target.',
      'The mean is exact and is never rounded.',
      'The active attack is separate: only the current unresolved attack must be defended.',
    ],
    cards: [
      card('JC', 'J', 'clubs', 12),
      card('KD', 'K', 'diamonds', 18),
      card('QS', 'Q', 'spades', 15),
    ],
    cardCaption: 'J and K are on the table. Q or 7 + 8 matches their mean.',
    equations: ['12 + 18 = 30', '(12 + 18) / 2 = 15', 'Q = 15', '7 + 8 = 15'],
    note: 'The total 30 is also available as its own target.',
    exercise: {
      prompt: 'What matches the mean of 15?',
      choices: [
        { id: 'queen', label: 'Q = 15' },
        { id: 'king', label: 'K = 18' },
        { id: 'ten', label: '10 = 10' },
      ],
      answer: 'queen',
      success: 'Exactly: (12 + 18) / 2 = 15 = Q.',
      retry: 'The mean is 15. It must be matched exactly, without rounding.',
    },
  },
  {
    id: 'transfer',
    title: 'Transfer',
    lead: 'A normal transfer exactly matches the current attack.',
    points: [
      'Against 18, cards 9 + 9 transfer exactly 18.',
      'A transfer extends the same unresolved attack: the next target becomes 36, then 72.',
      'Transfers close for the rest of the bout after the first successful defense.',
      'If the entire unresolved attack has one rank, the exact-value part may be extended with more cards of that rank.',
      'Attack-card count is limited by the current defender’s hand; after a transfer, the limit is recalculated from the new defender’s remaining hand.',
      '“Attack 2 / limit 4” means two attack cards are already in play and four is the maximum.',
    ],
    cards: [
      card('9C', '9', 'clubs', 9),
      card('9D', '9', 'diamonds', 9),
      card('KC', 'K', 'clubs', 18),
    ],
    cardCaption: null,
    equations: ['18 → 36 → 72', '9 + 9 = 18 ✓', '7 → 7 + 7 → 21', '19 ≠ 18 ✕'],
    note: null,
    exercise: {
      prompt: 'What can transfer an attack of 18?',
      choices: [
        { id: 'exact', label: '9 + 9 = 18' },
        { id: 'above', label: '10 + 9 = 19' },
        { id: 'below', label: '10 + 7 = 17' },
      ],
      answer: 'exact',
      success: 'Yes: a transfer requires exact equality.',
      retry: 'Being greater is not enough for a transfer — the total must be exactly 18.',
    },
  },
  {
    id: 'endgame',
    title: 'End bout, take and game end',
    lead: 'After each bout, the table is resolved and hands refill.',
    points: [
      'Discard: the defender starts the next bout. If they defend successfully with their final card or cards from hand, the bout ends automatically and no more cards may be thrown in.',
      'Take: the defender takes the whole table and the previous attacker keeps initiative.',
      'If the deck is short, refill balances the hands as closely as possible.',
      'An empty deck means play continues without trumps.',
    ],
    cards: [],
    cardCaption: null,
    equations: ['one empty hand → win', 'both empty → Draw 🤝'],
    note: 'The result is checked only after bout resolution, table movement and refill.',
    exercise: null,
  },
];
