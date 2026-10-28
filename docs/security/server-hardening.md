# TrackFlow server hardening runbook

The repository defines the target state; installation requires console access
to the Linux host. Never close the existing root/console session until a second
`trackflow` key-only SSH session succeeds.

## Apply

```bash
sudo deploy/hardening/bootstrap-host.sh --apply /secure/path/approved_authorized_keys
sudo deploy/hardening/firewall.sh --apply
deploy/hardening/verify-host.sh | tee hardening-proof.txt
```

Target state:

- daily operations use the dedicated `trackflow` account;
- root and password SSH login are disabled; only approved public keys work;
- `/opt/trackflow/app` and `/var/log/trackflow` are `trackflow:trackflow 0750`;
- `/etc/trackflow` is `root:trackflow 0750`; secrets inside must be `0640`;
- only SSH (22), HTTP redirect/ACME (80), and HTTPS (443) are public;
- FastAPI, Next.js, MCP, Flower, Redis, and Qdrant bind to loopback or the
  private Compose network and sit behind the HTTPS reverse proxy;
- backend and MCP containers run as non-root `trackflow` users.

The firewall script deliberately requires `--apply`, preventing an accidental
lockout when someone only intended to inspect it. The repository does not store
private keys, passwords, production IP allowlists, or VPS credentials.
