# Kiba incident-response runbook

Owner/contact: **Oleg Shaltaev — support@cyberdurak.com**. This is an operational checklist for a
one-person public beta. It does not automate or prejudge legal notification duties.

1. **Open an incident record.** Record discovery time, reporter, systems, symptoms, request IDs and
   known timeline. Avoid copying unnecessary personal data into notes.
2. **Contain.** Disable affected credentials, endpoints, accounts or deployment components with the
   least destructive action that stops further exposure. Preserve opponent/user safety.
3. **Preserve evidence.** Secure relevant logs and configuration snapshots with access controls.
   Do not alter original evidence; record every collection/action.
4. **Rotate exposure.** Rotate database, SMTP, deployment, cookie/signing or other credentials that
   may be affected. Revoke sessions/tokens where needed.
5. **Assess scope.** Identify systems, time range, data categories, number/type of users, access or
   exfiltration evidence, likely consequences, and whether backups/providers are involved.
6. **Assess risk.** Document confidentiality, integrity, availability and user-harm analysis.
   Obtain legal advice where the threshold is uncertain.
7. **Decide notifications.** Determine whether notification to a competent supervisory authority is
   required and, where applicable, work against the GDPR notification timeline (including the
   72-hour framework from awareness). Record reasons for notifying or not notifying.
8. **Notify affected people** without undue delay where legally required, using plain language and
   safe contact channels. Do not reveal another person's data.
9. **Remediate and recover.** Patch the cause, validate clean configuration/data, restore carefully,
   and increase monitoring proportionately.
10. **Close and review.** Record final facts, decisions, actions, notifications, residual risk and
    prevention work. Update this runbook and processor/security controls.

If `support@cyberdurak.com` itself is unavailable, use a pre-established private emergency contact
document outside this repository. Public beta must not launch until the support mailbox is working
and monitored.
