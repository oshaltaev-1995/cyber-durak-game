# Kiba processor register

Pre-launch register, reviewed 2026-09-25. `PLANNED` means the provider is not currently processing
live Kiba production-user data.

| Provider | Purpose | Data categories | Location | DPA/legal status | Status |
| --- | --- | --- | --- | --- | --- |
| Netherlands VPS provider (not selected) | App, PostgreSQL, logs, encrypted backups | All production service data | Planned Netherlands/EEA | Provider, subprocessor list, DPA, security and transfer review required | PLANNED |
| Transactional email provider (not selected) | Verification and password recovery | Email, display name, locale, one-use link and delivery metadata | Not selected | DPA, processing region, retention and transfer review required | PLANNED |
| Domain/DNS provider (not selected) | Domain resolution and edge DNS logs | DNS queries and ordinary network metadata | Not selected | Privacy terms and any processor role must be reviewed | PLANNED |
| Analytics/advertising/marketing provider | None | None | N/A | Must trigger cookie/privacy assessment before addition | NOT USED |

Development Docker/PostgreSQL and the process-local development email outbox are local developer
tools, not production processors.

## Production gates

- Final processor and Privacy Policy review after Phase 6B provider configuration.
- Record provider legal name, contact, countries, subprocessors, DPA date, transfer mechanism, and
  retention before production data flows.
- Confirm `support@cyberdurak.com` can receive mail and is monitored before public beta launch.
- Reassess this register before any analytics, advertising, monitoring with personal data, payment,
  or deliberate non-EEA processing is introduced.
