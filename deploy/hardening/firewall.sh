#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root on the target Linux host." >&2
  exit 1
fi
if [[ "${1:-}" != "--apply" ]]; then
  echo "Plan: deny inbound; allow outbound; allow 22/tcp, 80/tcp, and 443/tcp." >&2
  echo "Re-run with --apply after confirming console access." >&2
  exit 2
fi

command -v ufw >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'TrackFlow ops SSH'
ufw allow 80/tcp comment 'HTTP redirect / ACME'
ufw allow 443/tcp comment 'TrackFlow HTTPS'
ufw --force enable
ufw status verbose
