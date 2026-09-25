# Controlled VPS maintenance report

Maintenance date: 2026-09-25. Scope: Phase 6A.8 low-risk OS/security maintenance on the existing
Netherlands VPS. Kiba was not deployed. This report is deliberately sanitized and contains no
credentials, tokens, private keys, database contents, VPN configuration, or application user data.

## Final verdict

**HEALTHY WITH FOLLOW-UP.** The reviewed OS/security update and one controlled reboot completed
successfully. The host booted the new Ubuntu kernel, SSH returned, and Docker, Caddy, Kennel
Operations, Husky Tracking, and Amnezia recovered through their existing startup policies. Public
sites and health endpoints returned HTTP 200 after the reboot. Docker, containerd, and runc were
intentionally not upgraded and need a separate runtime-maintenance window.

## Pre-maintenance state

| Item | Baseline |
| --- | --- |
| OS/kernel | Ubuntu 24.04.3 LTS; `6.8.0-90-generic` |
| Uptime/load | About 80 days; low load |
| CPU | 2 vCPU |
| RAM | 3.8 GiB total; about 1.9 GiB available |
| Swap | 2.0 GiB `/swapfile`; about 88 MiB used; `vm.swappiness=10` |
| Root filesystem | 79 GiB total; about 48 GiB free; 13% inode use |
| Docker runtime | Engine 28.2.2; containerd 1.7.28; runc 1.3.3 |
| Package state | Package manager healthy; no pre-existing package holds; about 233 refreshed candidates |
| Public listeners | 22/tcp, 80/tcp, 443/tcp, and 40970/udp only |

The root filesystem was read/write, package checks passed, and no filesystem or storage errors were
found. The existing firewall allowed the documented SSH, HTTP/HTTPS, and Amnezia listener set; no
database or application backend port was public.

### Production container baseline

| Workload | Existing containers | Pre-maintenance state |
| --- | --- | --- |
| Kennel Operations | frontend, backend, portrait worker, PostgreSQL | Running; checked containers healthy; restart count 0 |
| Husky Tracking | frontend, backend, PostgreSQL | Running and healthy; restart count 0 |
| Shared edge | Caddy | Running; restart count 0; active configuration valid |
| VPN | Amnezia/WireGuard | Running; restart count 0; UDP listener and `awg0` present |

All public pages and available health/readiness endpoints returned HTTP 200 with valid HTTPS before
maintenance. The active Caddy configuration checksum was recorded as
`5a327e2000d9f9ee6fdd2cb56385c6a34da9bd0a280fc7b15495b6a5100372db` and validated without a reload.

## Safety backups and recovery gates

- The established Kennel Operations backup service completed at approximately 08:26 MSK. Its
  timestamped PostgreSQL archive was non-empty (about 1.1 MB) and passed `pg_restore --list`; its
  media archive was non-empty (about 34.5 MB) and passed non-destructive archive inspection.
- The established Husky Tracking backup service completed at approximately 08:26 MSK. Its
  timestamped PostgreSQL archive was non-empty (about 111 KB) and passed `pg_restore --list`.
- No backup was restored into a production database and no production records were intentionally
  changed. Kennel's established backup mechanism briefly stopped and restarted its writers as
  designed to obtain a consistent snapshot.
- A root-only, mode-700 safety directory was created on the VPS with the active Caddyfile, relevant
  Compose YAML, package/kernel/container inventory, firewall snapshots, and transaction records.
  No `.env` files or secrets were copied into the repository or this report.
- The owner confirmed access to VDSina power/reboot controls and out-of-band console/recovery before
  the reboot was authorized.

## Package update

APT metadata was refreshed and the transaction was simulated before installation. The applied
transaction upgraded 168 reviewed security/OS packages and installed seven new kernel-related
packages, with zero removals. It used a conservative keep-existing-configuration policy.

Updated families included the Ubuntu kernel, libc, systemd, OpenSSH, OpenSSL, certificate and curl
libraries, DNS/security libraries, and Python security updates. Kernel `6.8.0-142-generic` plus its
modules, headers, tools, and initramfs were installed. GRUB contained entries for both the new kernel
and the previous known-good `6.8.0-90-generic` kernel before reboot.

Docker-related packages were temporarily held only while applying the reviewed transaction. The
temporary holds were removed after reboot, restoring the original state of no package holds.
Docker Engine/CLI, containerd, runc, Compose, and buildx were not upgraded, restarted, or replaced
by the package transaction.

## Controlled reboot

Exactly one normal reboot was issued at approximately 08:45:25 MSK. SSH returned at approximately
08:45:54 MSK, for an observed interruption of about 29 seconds. The host booted
`6.8.0-142-generic`; the old `6.8.0-90-generic` image and modules remain installed as a recovery
fallback. No hard reset, repeated reboot, or provider-console recovery was needed.

## Post-maintenance validation

| Area | Result |
| --- | --- |
| SSH | Fresh independent key-based login succeeded before reboot and again after reboot |
| Kernel | Running `6.8.0-142-generic`; no reboot-required marker remains |
| Docker | Active/enabled; Engine remains 28.2.2; all nine production containers auto-started |
| Kennel Operations | Containers running; DB and worker healthy; public page and health endpoint HTTP 200 |
| Husky Tracking | All three containers healthy; page, health, and readiness endpoints HTTP 200 |
| Caddy | Running with restart count 0; same config checksum; config valid; 80/443 listening; HTTPS valid |
| Amnezia | Running with restart count 0; userspace `awg0` interface present; 40970/udp listening |
| Package manager | `dpkg --audit` clean; `apt-get check` successful; original hold state restored |
| Failed units/logs | No failed systemd units or host error-level journal entries after reboot |

The orderly reboot produced expected PostgreSQL connection-termination messages during shutdown
and non-fatal Caddy OCSP-stapling warnings after startup; no restart loop or persistent service
failure was observed. No container required a manual start.

### Network and firewall comparison

The public listener surface after reboot remains:

- 22/tcp for SSH;
- 80/tcp and 443/tcp for Caddy;
- 40970/udp for Amnezia.

No PostgreSQL or application backend port became public. Docker regenerated its managed nftables
rule ordering and the private Caddy container address changed during normal container restart;
published destinations, custom host/ingress policy, and effective public exposure remained the
same. No firewall rule was edited or regenerated manually.

### Resource comparison

| Resource | Before | Stabilized after reboot |
| --- | --- | --- |
| RAM available | about 1.9 GiB | about 2.3 GiB |
| Swap | about 88-120 MiB used | 0 B used; 2.0 GiB active |
| Root disk | about 48 GiB free | about 48 GiB free |
| Inodes | 13% used | 14% used |
| Load | low | below 1 after startup stabilization |

No resource warning threshold was crossed.

## Deferred follow-up

- **Container runtime:** 65 package upgrades remain. They include Docker 29.1.3, containerd 2.2.1,
  and runc 1.3.4. These were intentionally deferred because the upgrade can restart Docker and
  rebuild firewall/network state for every production stack. Review them in a dedicated,
  backup-protected runtime-maintenance window.
- **Other updates:** the remaining list also includes networking/firewall-adjacent and ordinary
  Ubuntu update-pocket packages. Review and batch them in a later controlled window rather than
  treating this maintenance as an obligation to install every candidate.
- **Old kernel:** retain `6.8.0-90-generic` until the new kernel has demonstrated stability. Do not
  run automatic old-kernel cleanup yet.
- **SSH hardening:** the effective configuration still allows root login and password
  authentication; public-key authentication is enabled and fail2ban is not installed. In a
  separate lockout-safe task, establish/test a non-root sudo or recovery path before considering
  key-only access and password-login disablement. No SSH setting changed here.
- **Phase 6B:** Kiba remains undeployed and the domain/DNS, monitored support mailbox, SMTP,
  processor/legal review, production secrets, off-host backup destination, and Kiba ingress
  contract remain separate deployment prerequisites.

## Scope confirmation

- Kiba was not deployed and no Kiba server files, containers, networks, or volumes were created.
- No application source, application environment, Compose configuration, Caddy configuration,
  firewall policy, SSH configuration, or Amnezia configuration was changed.
- No production database contents were intentionally modified.
- No Docker image, volume, network, container, or old kernel was deleted.
- Docker/containerd/runc were not upgraded.
