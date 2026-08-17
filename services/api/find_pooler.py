#!/usr/bin/env python3
"""Find the Supabase Transaction pooler for this project and configure it.

The only thing you supply is your database password, typed locally and
never echoed. Everything else — the project ref, the region, the pooler
host, the port — is worked out here.

Why this exists: Supabase's Direct connection host is IPv6-only, and on
a network without IPv6 it fails with "No route to host", which reads
like a firewall problem. The Transaction pooler answers on IPv4 and is
what the milestone specifies, but its hostname embeds an AWS region that
is only visible in the dashboard. So this tries each region until one
authenticates.

Run it:
    uv run python find_pooler.py        # from services/api/
"""

from __future__ import annotations

import getpass
import re
import urllib.parse
from pathlib import Path

ENV = Path(__file__).resolve().parent / ".env"

# Every AWS region Supabase runs poolers in, commonest first.
REGIONS = [
    "us-east-1", "us-west-1", "us-east-2", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1", "eu-central-2",
    "eu-north-1", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
    "ap-northeast-2", "ap-south-1", "ca-central-1", "sa-east-1",
]
# Supabase has used both prefixes for pooler hostnames.
PREFIXES = ["aws-0", "aws-1"]
PORT = 6543


def project_ref() -> str | None:
    """Read the project ref out of whatever is already in .env."""
    if not ENV.exists():
        return None
    for line in ENV.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            value = line.split("=", 1)[1]
            match = re.search(r"db\.([a-z0-9]{20})\.supabase\.co", value)
            if match:
                return match.group(1)
            match = re.search(r"postgres\.([a-z0-9]{20})", value)
            if match:
                return match.group(1)
    return None


def build(ref: str, password: str, prefix: str, region: str) -> str:
    quoted = urllib.parse.quote(password, safe="")
    return f"postgresql://postgres.{ref}:{quoted}@{prefix}-{region}.pooler.supabase.com:{PORT}/postgres"


def try_connect(uri: str) -> tuple[bool, str]:
    import psycopg2

    try:
        conn = psycopg2.connect(uri, connect_timeout=6)
        conn.close()
        return True, "ok"
    except Exception as exc:
        return False, str(exc).strip().splitlines()[0]


def write_env(uri: str) -> None:
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    out, replaced = [], False
    for line in lines:
        if line.startswith("DATABASE_URL="):
            out.append(f"DATABASE_URL={uri}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out += ["", f"DATABASE_URL={uri}"]
    ENV.write_text("\n".join(out) + "\n")


def main() -> int:
    print("TrackFlow — find the Supabase Transaction pooler\n")

    ref = project_ref()
    if ref is None:
        print("  Could not find a project ref in .env.")
        print("  Paste your project ref (the 20-character id in your Supabase URL):")
        ref = input("  ref: ").strip()
        if not re.fullmatch(r"[a-z0-9]{20}", ref):
            print("  That does not look like a project ref.")
            return 1
    print(f"  project ref: {ref}")

    print("\n  Enter your Supabase DATABASE password.")
    print("  (Dashboard -> Settings -> Database. Not your Supabase login;")
    print("   not the anon key. Hidden as you type, never stored in history.)\n")
    try:
        password = getpass.getpass("  password: ")
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return 1
    if not password:
        print("  No password entered.")
        return 1

    print(f"\n  trying {len(REGIONS)} regions...\n")
    wrong_password = False

    for prefix in PREFIXES:
        for region in REGIONS:
            uri = build(ref, password, prefix, region)
            ok, message = try_connect(uri)
            if ok:
                print(f"  FOUND: {prefix}-{region}.pooler.supabase.com:{PORT}")
                write_env(uri)
                print(f"  written to {ENV.name} (gitignored)\n")

                import os

                os.environ["DATABASE_URL"] = uri
                from database import dispose_inventory_engine

                dispose_inventory_engine()

                print("  creating tables and seeding...\n")
                from seed_inventory import main as seed_main

                return seed_main()

            lowered = message.lower()
            if "password authentication failed" in lowered:
                # Right region, wrong secret. No point trying the rest.
                wrong_password = True
                print(f"  {prefix}-{region}: reached the pooler, password REJECTED")
                break
            if "enotfound" in lowered or "tenant" in lowered:
                # The pooler answered and does not host this project.
                # This is the expected miss, and it is fast.
                print(f"  {prefix}-{region}: not this region")
            else:
                print(f"  {prefix}-{region}: {message[:60]}")
        if wrong_password:
            break

    print()
    if wrong_password:
        print("  The pooler was reached but the password is wrong.")
        print("  Supabase dashboard -> Settings -> Database -> Reset database")
        print("  password, then run this again.")
    else:
        print("  No region accepted the connection.")
        print("  Most likely the project is paused — open the Supabase")
        print("  dashboard and resume it, then run this again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
