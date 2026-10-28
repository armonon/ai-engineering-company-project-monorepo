#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root on the target Linux host." >&2
  exit 1
fi
if [[ "${1:-}" != "--apply" || -z "${2:-}" ]]; then
  echo "Usage: sudo $0 --apply /path/to/approved_trackflow_authorized_keys" >&2
  exit 2
fi

approved_keys="$2"
test -f "$approved_keys"
id trackflow >/dev/null 2>&1 || useradd --create-home --shell /bin/bash trackflow
install -d -o trackflow -g trackflow -m 0700 /home/trackflow/.ssh
install -o trackflow -g trackflow -m 0600 "$approved_keys" /home/trackflow/.ssh/authorized_keys

install -d -o trackflow -g trackflow -m 0750 /opt/trackflow/app /var/log/trackflow
install -d -o root -g trackflow -m 0750 /etc/trackflow
install -o root -g root -m 0644 \
  "$(dirname "$0")/60-trackflow.conf" \
  /etc/ssh/sshd_config.d/60-trackflow.conf

sshd -t
systemctl reload sshd 2>/dev/null || systemctl reload ssh
echo "Host user and SSH policy installed. Verify a new trackflow key-only session before logout."
