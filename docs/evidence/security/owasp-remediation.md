# OWASP remediation proof index

## Critical access-control fix

- Enforcement: `services/api/routers/agent.py::authorize_ticket`
- Proof: `services/api/tests/test_agent.py::test_ticket_authorization_is_deny_by_default`
- Expected: normal users receive no incident data unless the order/ticket id is
  explicitly assigned; admins remain authorized.

## Critical network-exposure fix

- Enforcement: loopback bindings in `docker-compose.yml` and default-deny UFW
  policy in `deploy/hardening/firewall.sh`.
- Proof: `docker compose config` shows `host_ip: 127.0.0.1`; host verification
  lists only 22/80/443 as public listeners.

## High vulnerable-component fix

- GitHub alert: #38, `dnspython` crafted DNS-name excessive CPU.
- Before: lockfile 2.8.0.
- After: direct minimum and lockfile 2.9.0.
- Proof: `rg -n 'dnspython>=2.9.0|version = "2.9.0"' services/api`.

## High root-runtime fix

- Enforcement: `USER trackflow` in both Python service images.
- Proof: `docker compose run --rm --no-deps <service> id` returns a nonzero uid.

Full findings, residual risks, and all ten categories are in
`docs/security/owasp-top-10-audit.md`.

## Supply-chain and secret checks

- `npm audit --omit=dev`: 0 production vulnerabilities.
- Tracked-file scan for common OpenAI, Supabase, GitHub, and private-key
  signatures: 0 matching files. The scan reports paths/count only and never
  prints a suspected credential.
