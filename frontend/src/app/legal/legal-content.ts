import { Locale } from '../core/i18n/locale';
import {
  LEGAL_EFFECTIVE_DATE,
  PRIVACY_POLICY_VERSION,
  SUPPORT_EMAIL,
  TERMS_VERSION,
} from './policy-metadata';

export interface LegalSection {
  readonly heading: string;
  readonly paragraphs: readonly string[];
  readonly bullets?: readonly string[];
}

export interface LegalDocument {
  readonly eyebrow: string;
  readonly title: string;
  readonly summary: string;
  readonly versionLabel: string;
  readonly effectiveLabel: string;
  readonly sections: readonly LegalSection[];
}

const privacyEn: LegalDocument = {
  eyebrow: 'Legal · Privacy',
  title: 'Privacy Policy',
  summary:
    'This policy explains the personal data KIBA actually uses during its EU/international public beta and the choices available to you.',
  versionLabel: `Version ${PRIVACY_POLICY_VERSION}`,
  effectiveLabel: `Effective ${LEGAL_EFFECTIVE_DATE}`,
  sections: [
    {
      heading: 'Who is responsible',
      paragraphs: [
        `The data controller is Oleg Shaltaev, Finland. Privacy and data-rights questions can be sent to ${SUPPORT_EMAIL}.`,
      ],
    },
    {
      heading: 'What KIBA is',
      paragraphs: [
        'KIBA is a browser-based card game available against a bot or in a private two-player room. You may play as a guest. Creating an account is optional and is used to save history and progression.',
      ],
    },
    {
      heading: 'Data KIBA uses',
      paragraphs: ['The service processes only the data needed for the current features:'],
      bullets: [
        'Account details: account ID, email, display name, preferred language, verification status, and account timestamps.',
        'Security data: a password hash, hashed session and verification/reset tokens, expiry/revocation times, request IDs, rate-limit metadata, and ordinary server connection metadata contained in infrastructure logs.',
        'Saved play data for authenticated users: compact bot/PvP match summaries, outcomes, opponent display-name snapshots, action counters, statistics, XP entries, achievements, cosmetic unlocks, and equipped cosmetics.',
        'Temporary play data: active game state, hands, draw order, private-room nicknames, invite/reconnect credentials, and connection state. These remain process-local and disappear after their TTL or a backend restart.',
      ],
    },
    {
      heading: 'Why data is processed',
      paragraphs: [
        'Account and gameplay data is processed to provide the requested service and account features. Security, abuse-prevention, diagnostics, and service-reliability processing is based on the controller’s legitimate interests in operating a safe service. Any legal obligation will be applied only when it actually applies; this policy is not blanket consent to all processing.',
      ],
    },
    {
      heading: 'Guests and registered users',
      paragraphs: [
        'Guest play does not create persistent account history, XP, achievements, or cosmetics. Active games and rooms are temporary. A browser may keep a language preference and short-lived private-room reconnect details.',
        'Registered users may save their profile, completed-match history, statistics, XP, achievements, cosmetic unlocks, and loadout. Logging in during a guest match does not retroactively attach that match to the account.',
      ],
    },
    {
      heading: 'Cookies and browser storage',
      paragraphs: [
        'KIBA uses an HTTP-only authentication cookie for signed-in sessions, localStorage for your RU/EN language choice, and sessionStorage for private-room reconnect credentials. These are necessary or functional storage. KIBA currently has no analytics, advertising, behavioural-tracking, or marketing cookies, so no optional-cookie banner is shown.',
      ],
    },
    {
      heading: 'Emails',
      paragraphs: [
        'KIBA sends account verification and password-recovery messages only. It does not currently send newsletters or marketing email. Delivery uses the language saved on the account.',
      ],
    },
    {
      heading: 'Providers and international processing',
      paragraphs: [
        'KIBA uses a VDSina-hosted server in the Netherlands/EEA, Brevo for transactional verification and password-recovery email, and Cloudflare for authoritative DNS and inbound routing of the public support mailbox. These providers process only the categories needed for those functions.',
        'The controller does not promise that every future provider will always be inside the EEA. Any provider that handles personal data must receive an appropriate privacy and transfer review before use.',
      ],
    },
    {
      heading: 'Retention and deletion',
      paragraphs: [
        'Account, profile, match, progression, and cosmetic data is kept until you delete the account. Active games and rooms follow short process-local time limits and are lost on backend restart. Authentication sessions and account tokens expire according to their security lifetimes and are cleaned operationally.',
        'The initial target for security/application logs and database backups is 30 days. Deletion removes live account data immediately; protected backup copies may retain it until normal backup rotation expires and may be used only for disaster recovery.',
      ],
    },
    {
      heading: 'Security',
      paragraphs: [
        'KIBA uses proportionate technical and organizational safeguards for a small public beta, including password hashing, hashed session/token storage, access controls, same-origin protections, and restricted production configuration. No internet service can promise absolute security.',
      ],
    },
    {
      heading: 'Your rights',
      paragraphs: [
        'Depending on the circumstances and legal basis, GDPR rights may include access, correction, deletion, portability, restriction, and objection. The profile provides self-service JSON export and account deletion. You may also contact the controller. You may have the right to complain to a competent supervisory authority, including the authority in your EU/EEA country.',
      ],
    },
    {
      heading: 'Contact and policy changes',
      paragraphs: [
        `Contact ${SUPPORT_EMAIL} for privacy questions. Material changes will be reflected by a new version/effective date on this page. This public-beta policy is compliance-readiness information and not a claim of formal certification.`,
      ],
    },
  ],
};

const privacyRu: LegalDocument = {
  eyebrow: 'Правовая информация · Конфиденциальность',
  title: 'Политика конфиденциальности',
  summary:
    'Здесь описаны персональные данные, которые KIBA действительно использует в международной публичной бета-версии для ЕС, и доступные вам действия.',
  versionLabel: `Версия ${PRIVACY_POLICY_VERSION}`,
  effectiveLabel: `Действует с ${LEGAL_EFFECTIVE_DATE}`,
  sections: [
    {
      heading: 'Кто отвечает за данные',
      paragraphs: [
        `Контролёр данных — Oleg Shaltaev, Finland. Вопросы о конфиденциальности и правах на данные: ${SUPPORT_EMAIL}.`,
      ],
    },
    {
      heading: 'Что такое KIBA',
      paragraphs: [
        'KIBA — браузерная карточная игра против бота или в приватной комнате для двух игроков. Можно играть как гость. Необязательный аккаунт сохраняет историю и прогресс.',
      ],
    },
    {
      heading: 'Какие данные используются',
      paragraphs: ['Сервис обрабатывает только данные, необходимые текущим функциям:'],
      bullets: [
        'Аккаунт: UUID, email, отображаемое имя, выбранный язык, состояние подтверждения email и временные метки.',
        'Безопасность: хеш пароля, хеши сессий и токенов подтверждения/сброса, сроки действия и отзыва, ID запросов, метаданные ограничения частоты и обычные сетевые сведения в инфраструктурных журналах.',
        'Сохранённая игра зарегистрированных пользователей: краткие итоги BOT/PvP, результаты, снимок имени соперника, счётчики действий, статистика, XP, достижения и оформление.',
        'Временная игра: активное состояние, руки, порядок колоды, гостевые имена, приглашения, данные переподключения и состояние соединения. Они хранятся в процессе и исчезают по TTL или при перезапуске backend.',
      ],
    },
    {
      heading: 'Зачем данные обрабатываются',
      paragraphs: [
        'Данные аккаунта и игры нужны для предоставления запрошенного сервиса. Безопасность, предотвращение злоупотреблений, диагностика и надёжность основаны на законном интересе контролёра поддерживать безопасный сервис. Юридическая обязанность применяется только когда она действительно существует; эта политика не является общим согласием на любую обработку.',
      ],
    },
    {
      heading: 'Гости и зарегистрированные пользователи',
      paragraphs: [
        'Гостевая игра не создаёт постоянную историю аккаунта, XP, достижения или оформление. Активные игры и комнаты временны. Браузер может хранить выбор языка и кратковременные данные переподключения к комнате.',
        'Для аккаунта могут сохраняться профиль, завершённые партии, статистика, XP, достижения и оформление. Вход во время гостевой партии не привязывает её к аккаунту задним числом.',
      ],
    },
    {
      heading: 'Cookie и хранилища браузера',
      paragraphs: [
        'KIBA использует HTTP-only cookie для входа, localStorage для выбора RU/EN и sessionStorage для переподключения к приватной комнате. Это необходимое или функциональное хранение. Сейчас нет аналитики, рекламы, поведенческого отслеживания или маркетинговых cookie, поэтому баннер необязательных cookie не показывается.',
      ],
    },
    {
      heading: 'Письма',
      paragraphs: [
        'KIBA отправляет только письма подтверждения аккаунта и восстановления пароля. Рассылок и маркетинговых писем сейчас нет. Язык письма берётся из настроек аккаунта.',
      ],
    },
    {
      heading: 'Провайдеры и международная обработка',
      paragraphs: [
        'KIBA использует сервер VDSina в Нидерландах/ЕЭЗ, Brevo для транзакционных писем подтверждения и восстановления пароля, а Cloudflare — для авторитетного DNS и входящей маршрутизации публичного адреса поддержки. Эти провайдеры получают только категории данных, необходимые для соответствующей функции.',
        'Контролёр не обещает, что каждый будущий провайдер всегда будет находиться в ЕЭЗ. До подключения провайдера, работающего с персональными данными, проводится проверка конфиденциальности и передачи данных.',
      ],
    },
    {
      heading: 'Хранение и удаление',
      paragraphs: [
        'Профиль, история, прогресс и оформление хранятся до удаления аккаунта. Активные игры и комнаты имеют короткие процессные TTL и теряются при перезапуске backend. Сессии и токены истекают по установленным срокам безопасности и удаляются операционно.',
        'Начальный целевой срок журналов безопасности и резервных копий — 30 дней. Удаление сразу убирает данные из рабочей базы; защищённые копии могут хранить их до обычной ротации и используются только для аварийного восстановления.',
      ],
    },
    {
      heading: 'Безопасность',
      paragraphs: [
        'KIBA применяет соразмерные небольшой публичной бета-версии меры: хеширование паролей, хранение хешей сессий/токенов, контроль доступа, защита одного источника и строгую производственную конфигурацию. Абсолютную безопасность интернет-сервиса гарантировать нельзя.',
      ],
    },
    {
      heading: 'Ваши права',
      paragraphs: [
        'В зависимости от обстоятельств и правового основания права GDPR могут включать доступ, исправление, удаление, переносимость, ограничение и возражение. В профиле доступны JSON-экспорт и удаление аккаунта. Также можно обратиться к контролёру и, при наличии права, подать жалобу в компетентный надзорный орган страны ЕС/ЕЭЗ.',
      ],
    },
    {
      heading: 'Контакт и изменения',
      paragraphs: [
        `По вопросам конфиденциальности пишите на ${SUPPORT_EMAIL}. Существенные изменения будут отмечены новой версией и датой. Эта политика описывает готовность бета-версии и не заявляет о формальной сертификации.`,
      ],
    },
  ],
};

const termsEn: LegalDocument = {
  eyebrow: 'Legal · Terms',
  title: 'Terms of Use',
  summary: 'Short, practical terms for using the free KIBA public beta.',
  versionLabel: `Version ${TERMS_VERSION}`,
  effectiveLabel: `Effective ${LEGAL_EFFECTIVE_DATE}`,
  sections: [
    {
      heading: 'Service provider',
      paragraphs: [`KIBA is provided by Oleg Shaltaev, Finland. Contact: ${SUPPORT_EMAIL}.`],
    },
    {
      heading: 'The service',
      paragraphs: [
        'KIBA is a free browser-game public beta. You may play against a bot or in a private room as a guest. An optional account saves completed-match history and cosmetic progression.',
      ],
    },
    {
      heading: 'Accounts',
      paragraphs: [
        'You are responsible for protecting your credentials and should not share account access. Use an email you control if you want verification and password recovery. Information you provide, including display names, must not impersonate or abuse others.',
      ],
    },
    {
      heading: 'Acceptable use',
      paragraphs: ['You must not:'],
      bullets: [
        'seek unauthorized access to accounts, systems, rooms, or data;',
        'attack, disrupt, overload, probe, or circumvent service security;',
        'deliberately exploit or cheat, distribute harmful automation, or generate abusive traffic;',
        'use KIBA unlawfully or impersonate another person.',
      ],
    },
    {
      heading: 'Availability and public-beta changes',
      paragraphs: [
        'This is a small public beta. Features may change and maintenance or downtime may occur. Active games and private rooms are process-local: a backend restart or maintenance event can end an unfinished match. Persistent accounts and completed summaries are separate from active game state.',
      ],
    },
    {
      heading: 'Progression and cosmetics',
      paragraphs: [
        'XP, levels, achievements, and cosmetics have no monetary or cash value, give no gameplay advantage, and are not transferable. KIBA currently has no purchases, paid currency, or prize system.',
      ],
    },
    {
      heading: 'Intellectual property',
      paragraphs: [
        'Applicable rights in KIBA software, text, artwork, and branding are reserved by their respective owners. These terms do not claim exclusive ownership over abstract card-game ideas, mathematical concepts, or rules beyond rights recognized by law.',
      ],
    },
    {
      heading: 'Restriction or termination',
      paragraphs: [
        'Access may be restricted or terminated where reasonably necessary to address abuse, security threats, illegal use, or material violations of these terms. You may stop using KIBA or delete your account at any time.',
      ],
    },
    {
      heading: 'Responsibility and liability',
      paragraphs: [
        'KIBA is provided as a beta and may contain defects. Nothing in these terms excludes or limits liability, remedies, or consumer rights that cannot lawfully be excluded. To the extent permitted by applicable law, the provider is not responsible for indirect losses caused by ordinary beta downtime or loss of unfinished process-local games.',
      ],
    },
    {
      heading: 'Governing context and changes',
      paragraphs: [
        `These terms are intended to operate under Finnish law, subject to mandatory consumer and other rules that apply to you. Material changes will be shown through a new version/effective date. Questions: ${SUPPORT_EMAIL}.`,
      ],
    },
  ],
};

const termsRu: LegalDocument = {
  eyebrow: 'Правовая информация · Условия',
  title: 'Условия использования',
  summary: 'Краткие практические условия бесплатной публичной бета-версии KIBA.',
  versionLabel: `Версия ${TERMS_VERSION}`,
  effectiveLabel: `Действует с ${LEGAL_EFFECTIVE_DATE}`,
  sections: [
    {
      heading: 'Поставщик сервиса',
      paragraphs: [`KIBA предоставляет Oleg Shaltaev, Finland. Контакт: ${SUPPORT_EMAIL}.`],
    },
    {
      heading: 'Сервис',
      paragraphs: [
        'KIBA — бесплатная публичная бета-версия браузерной игры. Можно играть против бота или в приватной комнате как гость. Необязательный аккаунт сохраняет завершённые партии и визуальный прогресс.',
      ],
    },
    {
      heading: 'Аккаунты',
      paragraphs: [
        'Вы отвечаете за сохранность учётных данных и не должны передавать доступ. Для подтверждения и восстановления используйте email, который контролируете. Отображаемое имя не должно выдавать вас за другого человека или использоваться для оскорблений.',
      ],
    },
    {
      heading: 'Допустимое использование',
      paragraphs: ['Запрещено:'],
      bullets: [
        'получать несанкционированный доступ к аккаунтам, системам, комнатам или данным;',
        'атаковать, нарушать работу, перегружать, сканировать или обходить защиту сервиса;',
        'намеренно эксплуатировать ошибки, мошенничать, распространять вредную автоматизацию или создавать злоупотребляющий трафик;',
        'использовать KIBA незаконно или выдавать себя за другого человека.',
      ],
    },
    {
      heading: 'Доступность и изменения бета-версии',
      paragraphs: [
        'Это небольшая публичная бета-версия. Функции могут меняться, возможны обслуживание и простои. Активные игры и комнаты хранятся в процессе: перезапуск backend или обслуживание могут завершить незаконченную партию. Постоянный аккаунт и итоги завершённых игр отделены от активного состояния.',
      ],
    },
    {
      heading: 'Прогресс и оформление',
      paragraphs: [
        'XP, уровни, достижения и оформление не имеют денежной стоимости, не дают игрового преимущества и не передаются. Сейчас в KIBA нет покупок, платной валюты или призовой системы.',
      ],
    },
    {
      heading: 'Интеллектуальная собственность',
      paragraphs: [
        'Применимые права на код, тексты, графику и бренд KIBA принадлежат их правообладателям. Эти условия не заявляют исключительных прав на абстрактные идеи карточных игр, математические концепции или правила сверх признаваемого законом.',
      ],
    },
    {
      heading: 'Ограничение или прекращение доступа',
      paragraphs: [
        'Доступ может быть разумно ограничен для пресечения злоупотреблений, угроз безопасности, незаконного использования или существенных нарушений. Вы можете прекратить использование или удалить аккаунт в любое время.',
      ],
    },
    {
      heading: 'Ответственность',
      paragraphs: [
        'KIBA предоставляется как бета-версия и может содержать ошибки. Условия не исключают ответственность, средства защиты или обязательные права потребителя, которые нельзя исключить законом. В разрешённых законом пределах поставщик не отвечает за косвенные потери из-за обычного простоя бета-версии или потери незавершённых процессных игр.',
      ],
    },
    {
      heading: 'Правовой контекст и изменения',
      paragraphs: [
        `Условия предполагают применение права Финляндии с учётом обязательных потребительских и иных норм, применимых к пользователю. Существенные изменения отмечаются новой версией и датой. Вопросы: ${SUPPORT_EMAIL}.`,
      ],
    },
  ],
};

export const PRIVACY_DOCUMENTS: Readonly<Record<Locale, LegalDocument>> = {
  en: privacyEn,
  ru: privacyRu,
};

export const TERMS_DOCUMENTS: Readonly<Record<Locale, LegalDocument>> = {
  en: termsEn,
  ru: termsRu,
};
