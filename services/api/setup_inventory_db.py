#!/usr/bin/env python3
"""One-command setup for the Supabase inventory database.

Does everything except supply the connection string, which only you
have:

  1. prompts for the Supabase URI without echoing it or putting it in
     your shell history
  2. sanity-checks it before trying anything
  3. writes it to .env (gitignored) without disturbing the other keys
  4. opens the connection and reports the server version
  5. creates the tables and runs the seeder

Run it:
    uv run python setup_inventory_db.py        # from services/api/
"""

from __future__ import annotations

import getpass
import re
from pathlib import Path

ENV = Path(__file__).resolve().parent / ".env"


def prompt_for_uri() -> str | None:
    print("Paste your Supabase connection string.")
    print("  Supabase dashboard -> Connect -> Transaction pooler -> URI")
    print("  It is hidden as you type, and never enters your shell history.\n")
    try:
        uri = getpass.getpass("DATABASE_URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return None
    return uri or None


def check(uri: str) -> list[str]:
    """Catch the mistakes that produce confusing driver errors later."""
    problems: list[str] = []

    if not uri.startswith(("postgresql://", "postgres://")):
        problems.append(
            "It should start with postgresql:// — check you copied the URI, "
            "not the psql command."
        )
    if "[YOUR-PASSWORD]" in uri or "[your-password]" in uri.lower():
        problems.append(
            "The [YOUR-PASSWORD] placeholder is still there. Replace it with "
            "your real database password."
        )
    if uri.endswith(("@", ":")) or "@" not in uri:
        problems.append(
            "The string looks truncated — it should end with :6543/postgres "
            "or :5432/postgres."
        )

    # The direct-connection host is IPv6-only. Most home and cafe networks
    # have no IPv6 route, so it fails with "No route to host" — which reads
    # like a firewall problem and is really the wrong connection mode. The
    # milestone specifies the Transaction pooler because it answers on IPv4.
    if re.search(r"@db\.[a-z0-9]+\.supabase\.co", uri):
        problems.append(
            "That is the Direct connection host (db.<ref>.supabase.co), which "
            "is IPv6-only and will fail on most networks. Use the Transaction "
            "pooler URI instead — its host looks like "
            "aws-0-<region>.pooler.supabase.com."
        )
    elif ":5432/" in uri and "supabase" in uri:
        problems.append(
            "Port 5432 is the direct connection. The Transaction pooler uses "
            "6543 — re-copy the URI with the pooler selected."
        )

    # A raw @ or # inside the password breaks URI parsing.
    match = re.match(r"^postgres(?:ql)?://[^:]+:([^@]*)@", uri)
    if match:
        password = match.group(1)
        for char, encoded in (("#", "%23"), ("/", "%2F"), ("?", "%3F")):
            if char in password:
                problems.append(
                    f"Your password contains '{char}', which must be URL-encoded as '{encoded}'."
                )
    return problems


def write_env(uri: str) -> None:
    """Replace DATABASE_URL in .env, leaving every other key alone."""
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    out, replaced = [], False
    for line in lines:
        if line.startswith("DATABASE_URL="):
            out.append(f"DATABASE_URL={uri}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out += ["", "# Supabase inventory database (Milestone 5).", f"DATABASE_URL={uri}"]
    ENV.write_text("\n".join(out) + "\n")
    print(f"\n  written to {ENV.name} (gitignored — it will never be committed)")


def main() -> int:
    print("TrackFlow — inventory database setup\n")

    uri = prompt_for_uri()
    if uri is None:
        return 1

    problems = check(uri)
    if problems:
        print("\n  That string does not look usable:\n")
        for problem in problems:
            print(f"    - {problem}")
        print("\n  Nothing was written. Fix it and run this again.")
        return 1

    write_env(uri)

    import os

    os.environ["DATABASE_URL"] = uri

    print("\n  connecting...")
    try:
        from sqlalchemy import text

        from database import dispose_inventory_engine, inventory_engine

        dispose_inventory_engine()
        with inventory_engine().connect() as connection:
            version = connection.execute(text("SELECT version()")).scalar()
        print(f"  connected: {str(version).split(',')[0]}")
    except Exception as exc:
        message = str(exc).splitlines()[0]
        print(f"\n  FAILED to connect: {message}\n")
        if "password authentication" in message.lower():
            print("  The password in the string is wrong. Supabase dashboard ->")
            print("  Settings -> Database -> Reset database password.")
        elif "could not translate host" in message.lower():
            print("  The host is wrong or the string was truncated on copy.")
        elif "timeout" in message.lower():
            print("  Could not reach Supabase. Check the project is not paused.")
        print("\n  The string was saved, so fix it in .env and re-run the seeder.")
        return 1

    print("\n  creating tables and seeding...\n")
    from seed_inventory import main as seed_main

    return seed_main()


if __name__ == "__main__":
    raise SystemExit(main())
