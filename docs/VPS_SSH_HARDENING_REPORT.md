# VPS SSH hardening report

Date: 2026-09-25. Scope: Phase 6A.9 lockout-safe SSH authentication hardening on the existing
Netherlands VPS. This report contains no client addresses, passwords, key material, fingerprints,
tokens, VPN configuration, or application data.

## Verdict

**HARDENED SUCCESSFULLY.** Root administration remains available with the existing authorized
public key. SSH password and keyboard-interactive authentication are disabled. The SSH port and
public listener surface are unchanged. No reboot occurred.

## Before

| Setting/check | Baseline |
| --- | --- |
| SSH port | 22 |
| `PermitRootLogin` | `yes` |
| `PubkeyAuthentication` | `yes` |
| `PasswordAuthentication` | `yes` |
| `KbdInteractiveAuthentication` | `no` |
| `UsePAM` | `yes` |
| `AuthenticationMethods` | `any` |
| Root authorized keys | One usable Ed25519 entry; directory/file ownership and permissions acceptable |
| Independent key-only login | Succeeded as root before any configuration change |

The active Ubuntu configuration includes `/etc/ssh/sshd_config.d/*.conf` near the start of the main
configuration. The provider/cloud-init drop-in `50-cloud-init.conf` supplied the first effective
`PasswordAuthentication yes` value, while the main file later permitted unrestricted root login.
There were no `Match` blocks affecting root. Because OpenSSH uses the first obtained value for these
directives, an earlier administrator drop-in was required; blindly appending settings or using a
late `99-*` file would not have produced the intended effective configuration.

VDSina control-panel power and out-of-band console/recovery access was confirmed before the change.
The existing working SSH session remained open until the independent post-reload login and all
effective-setting checks had passed.

## Change

A root-owned, mode-600 drop-in was added at:

```text
/etc/ssh/sshd_config.d/00-local-auth-hardening.conf
```

It contains only:

```text
PermitRootLogin prohibit-password
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
```

`UsePAM yes`, `AuthenticationMethods any`, port 22, listeners, forwarding, SFTP, crypto algorithms,
and all unrelated SSH behavior were left unchanged. `/root/.ssh/authorized_keys` was not modified.

## Validation

- `sshd -t` succeeded before reload and again afterward.
- Root-specific `sshd -T` evaluation reported:
  - `permitrootlogin without-password` (OpenSSH's effective-output synonym for
    `prohibit-password`);
  - `pubkeyauthentication yes`;
  - `passwordauthentication no`;
  - `kbdinteractiveauthentication no`;
  - `usepam yes`;
  - `authenticationmethods any`;
  - `port 22`.
- `systemctl reload ssh` completed successfully; SSH was reloaded, not restarted.
- SSH remained active and continued listening on port 22.
- A completely new connection with public-key authentication forced and password/keyboard fallback
  disabled succeeded as root after reload.
- A non-interactive password-only connection with public-key and keyboard-interactive methods
  disabled was rejected with `Permission denied (publickey)`; no password was entered.
- The redacted SSH journal showed the successful public-key logins and a clean service reload, with
  no configuration or authentication-subsystem errors attributable to the change.

## Existing services

| Service | Post-change result |
| --- | --- |
| Kennel Operations | HEALTHY; public page and health endpoint HTTP 200 |
| Husky Tracking | HEALTHY; public page, health, and readiness endpoints HTTP 200 |
| Docker | HEALTHY; active; all nine existing production containers running |
| Caddy | HEALTHY; running with restart count 0 |
| Amnezia | HEALTHY; running with restart count 0 |

No application data was written during these checks.

## Network

The public listener set remained equivalent to the pre-change baseline:

- 22/tcp for SSH;
- 80/tcp and 443/tcp for Caddy;
- 40970/udp for Amnezia.

No PostgreSQL or application backend port became public. Firewall rules and policy were not changed.

## Final posture

```text
SSH root access: public key only
Password SSH authentication: disabled
Keyboard-interactive authentication: disabled
SSH port: unchanged (22)
```

Root access was deliberately not disabled completely, and no new administrator account was added.
No package was installed or upgraded, Docker/containerd/runc were untouched, and no reboot occurred.

## Rollback

The exact pre-change SSH configuration is stored in the root-only server directory:

```text
/root/ssh-pre-hardening-20260925-090540/
```

It contains the prior main configuration and drop-in directory for controlled rollback. The backup
remains only on the VPS and is not part of Git. Rollback was not needed.
