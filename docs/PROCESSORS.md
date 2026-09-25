# Kiba processor register

Production-launch register, reviewed 2026-09-25. `ACTIVE AT LAUNCH` means the provider is part of
the approved Phase 6B production path once the public service begins accepting users; Kiba was not
publicly deployed when this register was written.

| Provider | Purpose | Data categories | Location | DPA/legal status | Status |
| --- | --- | --- | --- | --- | --- |
| VDSina | Netherlands VPS hosting for app, PostgreSQL, logs and local backups | All production service data | Netherlands/EEA host region | Legal entity, DPA, subprocessors and transfer safeguards require final owner/legal review | ACTIVE AT LAUNCH |
| Brevo | Transactional verification and password-recovery email | Email, display name, locale, one-use link and delivery metadata | Provider-controlled email infrastructure | DPA, processing locations, subprocessors, retention and transfer safeguards require final owner/legal review | ACTIVE AT LAUNCH |
| Cloudflare | Authoritative DNS and inbound routing for the public support mailbox | DNS queries, ordinary network metadata, inbound support-message routing metadata | Provider-controlled infrastructure | Terms, DPA/processor role, subprocessors and transfer safeguards require final owner/legal review | ACTIVE AT LAUNCH |
| Analytics/advertising/marketing provider | None | None | N/A | Must trigger cookie/privacy assessment before addition | NOT USED |

Development Docker/PostgreSQL and the process-local development email outbox are local developer
tools, not production processors.

## Production gates

- Complete the owner/legal review of provider legal entities, locations, subprocessors, DPAs,
  transfer safeguards and provider retention. Technical provider selection is final, but this
  register does not claim that legal review is complete.
- `support@cyberdurak.com` passed an external receipt test and is monitored.
- Off-host disaster-recovery storage is deliberately deferred for the initial portfolio beta. Kiba
  uses isolated local daily backups with approximately 30-day retention; total VPS/storage loss can
  therefore also destroy those backups.
- Reassess this register before any analytics, advertising, monitoring with personal data, payment,
  or deliberate non-EEA processing is introduced.
