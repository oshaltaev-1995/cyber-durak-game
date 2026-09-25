# Kiba retention policy

Initial public-beta targets, version 1.0 (2026-09-25). Phase 6B configures per-container log
rotation and a monitored daily local database-backup job; expired-row cleanup remains an
operational follow-up where it is not already performed by application access paths.

| Data | Retention target | End-of-retention action |
| --- | --- | --- |
| Account/profile | Until self-service deletion or a valid manual deletion request | Delete live user row and owned records transactionally |
| Completed matches, statistics source data, XP, achievements, cosmetics/loadout | Until account deletion | Delete user-owned rows; anonymize deleted identity in opponents' retained PvP rows |
| Active bot game | Six hours inactivity; completed presentation 30 minutes; always lost on restart | Remove from process memory |
| Private PvP room | Waiting 30 minutes; completed 15 minutes; disconnected active room two hours; always lost on restart | Remove from process memory |
| Authentication session | 30-day absolute and 14-day idle maximum, or earlier logout/revocation/deletion | Reject after expiry/revocation; operational target to purge expired/revoked rows within 7 days |
| Email verification token | 24 hours or first use | Reject after expiry/use; operational purge target within 7 days |
| Password-reset token | 30 minutes or first use | Reject after expiry/use; operational purge target within 7 days |
| Process-local rate-limit state | Current process lifetime/window | Expire window or restart |
| Security/application/reverse-proxy logs | Initial target 30 days | Automated rotation and deletion; extend only for a documented incident/legal need |
| Database backups | Initial target 30 days | Automated protected rotation and deletion |

Normal deletion removes live account data immediately after a successful transaction. Deleted data
may remain in protected backup copies until the normal 30-day rotation expires. Backups are for
disaster recovery, not ordinary user lookup. A restore procedure must consider deletion requests
made after the restored snapshot.

TAKE-created active game data, hidden hands, and reconnect credentials are not persistent records.
Production containers use bounded local logs. Kiba database dumps are isolated under
`/var/backups/kiba`, protected, verified, and rotated at approximately 30 days. A restore drill is
required before launch. Off-host disaster-recovery copy is explicitly deferred, so total VPS or
storage loss can also destroy the local backups.
