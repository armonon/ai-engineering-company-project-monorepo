#!/usr/bin/env bash
set -euo pipefail

id trackflow
sshd -T | grep -E '^(permitrootlogin no|passwordauthentication no)$'
stat -c '%U:%G %a %n' /opt/trackflow/app /var/log/trackflow /etc/trackflow
ufw status verbose
ss -lntup

# Containers with an explicit non-root user print a nonzero uid.
docker compose run --rm --no-deps backend id
docker compose run --rm --no-deps company-tools-mcp id
