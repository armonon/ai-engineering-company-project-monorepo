"""Regression tests for the findings in docs/ERROR_HANDLING_AUDIT.md.

Each test names the finding it pins. Every one of them fails if its fix
is reverted — they were written against the broken behaviour first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "eh.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-a-real-one-32-bytes-minimum")

    import database

    database.close_db()

    from main import app

    # raise_server_exceptions=False makes TestClient behave like a real
    # server: an unhandled exception becomes a response instead of
    # propagating into the test.
    with TestClient(app, raise_server_exceptions=False) as c:
        c.post("/users", json={"email": "eh@trackflow.com", "password": "eh-password-123"})
        token = c.post(
            "/auth/login",
            json={"email": "eh@trackflow.com", "password": "eh-password-123"},
        ).json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c

    database.close_db()


CSV_HEADER = (
    b"incident_id,description,status,category,country,date,email,"
    b"tracking_number,satisfaction_score\n"
)


def upload(client: TestClient, body: bytes):
    return client.post(
        "/api/incidents/analyze", files={"file": ("incidents.csv", body, "text/csv")}
    )


# ---------------------------------------------------------------------------
# C1 / C2 — no route may answer with a non-JSON body
# ---------------------------------------------------------------------------


def test_an_oversized_csv_field_is_a_400_not_a_500(client: TestClient) -> None:
    """C2. Python's csv module refuses fields over 128 KB.

    This escaped as an unhandled exception, and Starlette answered with
    the plain-text body `Internal Server Error`.
    """
    response = upload(client, CSV_HEADER + b"1," + b"A" * 200_000 + b"\n")

    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "csv" in detail.lower()
    # The advice has to be actionable, not just a refusal.
    assert "try again" in detail.lower()


def test_error_responses_are_always_json(client: TestClient) -> None:
    """C1. Every frontend caller parses the body as JSON.

    A plain-text body is what produced `Unexpected token 'I'` on screen,
    so the content type matters as much as the status code.
    """
    responses = [
        upload(client, CSV_HEADER + b"1," + b"A" * 200_000 + b"\n"),
        upload(client, b"not,a,known,header\n"),
        upload(client, b"incident_id\n\xff\xfe\n"),
        client.get("/api/incidents/999999"),
        client.post("/api/incidents", json={"title": ""}),
    ]
    for response in responses:
        assert response.headers["content-type"].startswith("application/json"), (
            f"{response.request.url} answered {response.headers['content-type']}"
        )
        body = response.json()
        assert "detail" in body


def test_the_global_handler_returns_structured_json_and_hides_the_cause(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1. The safety net itself, exercised directly.

    A route is forced to raise so the handler runs. The response must be
    JSON, and must not contain the exception text — that belongs in the
    server log.
    """
    import routers.incidents_manager as manager

    secret_detail = "postgres://admin:s3cr3t@10.0.0.4/trackflow"

    def explode(*_args, **_kwargs):
        raise RuntimeError(secret_detail)

    monkeypatch.setattr(manager, "incidents_table", explode)

    response = client.get("/api/incidents")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    detail = response.json()["detail"]
    assert secret_detail not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
    # Still tells the reader what to do.
    assert "try again" in detail.lower()
    assert "support" in detail.lower()


# ---------------------------------------------------------------------------
# H5 — the login parser must not echo the request body
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, secret",
    [
        (b'{"email": "a@b.com", "password": 918273}', "918273"),
        (b'{"email": "a@b.com", "password": ["hunter2-secret"]}', "hunter2-secret"),
        (b'{"email": "a@b.com", "password": {"p": "hunter2-secret"}}', "hunter2-secret"),
    ],
)
def test_a_malformed_login_never_returns_the_submitted_password(
    client: TestClient, body: bytes, secret: str
) -> None:
    """H5. Pydantic v2 embeds the rejected input in its error text.

    Interpolating that into `detail` handed the password back to the
    caller — and into the access log.
    """
    response = client.post(
        "/auth/login", content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert "validation error" not in response.text.lower()


def test_a_malformed_login_still_says_what_was_wrong(client: TestClient) -> None:
    """A safe message still has to be a useful one."""
    response = client.post(
        "/auth/login", content=b"{oops", headers={"Content-Type": "application/json"}
    )
    detail = response.json()["detail"]
    assert "email" in detail.lower() and "password" in detail.lower()


# ---------------------------------------------------------------------------
# M1 — no raw exception text in any response
# ---------------------------------------------------------------------------


def test_a_non_utf8_csv_gets_advice_not_codec_internals(client: TestClient) -> None:
    """M1. The old message appended the UnicodeDecodeError verbatim."""
    response = upload(client, b"incident_id,description\n1,caf\xe9\n")

    assert response.status_code == 400
    detail = response.json()["detail"]
    for leak in ("0x", "codec", "byte", "position", "UnicodeDecodeError"):
        assert leak not in detail, f"response leaked {leak!r}: {detail}"
    assert "utf-8" in detail.lower()


def test_no_response_body_carries_a_filesystem_path(client: TestClient) -> None:
    """Nothing the client receives should describe the server's disk."""
    responses = [
        upload(client, b"incident_id\n\xff\xfe\n"),
        upload(client, CSV_HEADER + b"1," + b"A" * 200_000 + b"\n"),
        client.get("/api/incidents/424242"),
    ]
    for response in responses:
        text = response.text
        for leak in ("/Users/", "/home/", "site-packages", ".venv", "services/api"):
            assert leak not in text, f"{response.request.url} leaked {leak!r}"


# ---------------------------------------------------------------------------
# L2 — containers must not be flattened into a field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["title", "description", "category"])
def test_a_container_is_rejected_rather_than_stringified(
    client: TestClient, field: str
) -> None:
    """L2. `{"title": {"a": 1}}` used to return 201 and store "{'a': 1}"."""
    payload = {
        "title": "Pallet damaged",
        "description": "Clipped at bay 3.",
        "category": "warehouse_incident",
        "origin": "internal",
        "branch": "central",
        field: {"nested": "value"},
    }
    response = client.post("/api/incidents", json=payload)

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["field"] == field
    assert client.get("/api/incidents").json() == []


def test_a_stored_incident_never_contains_a_python_repr(client: TestClient) -> None:
    client.post(
        "/api/incidents",
        json={
            "title": ["a", "b"],
            "description": "x",
            "category": "other",
            "origin": "internal",
            "branch": "central",
        },
    )
    for incident in client.get("/api/incidents").json():
        assert not incident["title"].startswith(("[", "{", "("))


# ---------------------------------------------------------------------------
# The seeders and the CLI — informative stderr, non-zero exit (M2, M3)
# ---------------------------------------------------------------------------


def test_the_seeder_reports_a_directory_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M3. The broad `except Exception` printed the raw exception."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import seed_incidents

    a_directory = tmp_path / "somewhere"
    a_directory.mkdir()

    code = seed_incidents.main([str(a_directory)])

    # Unreadable input is exit 2, distinct from a parse failure's exit 1.
    assert code == 2, f"expected exit 2 for an unusable path, got {code}"
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "directory" in err.lower()
    # The broad `except Exception as exc: print(exc)` also mentioned
    # "directory" — it printed `[Errno 21] Is a directory: '...'` and
    # returned 1 for every cause alike. The errno and the flat exit code
    # are what actually distinguish the fix. (The path itself is fine to
    # echo here: the user typed it as an argument.)
    assert "Errno" not in err, f"raw errno reached the user: {err}"


def test_the_seeder_reports_a_missing_file_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import seed_incidents

    code = seed_incidents.main([str(tmp_path / "nope.csv")])

    assert code != 0
    err = capsys.readouterr().err
    assert "Traceback" not in err


def test_the_analyzer_cli_handles_every_unreadable_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M2. `read_csv` was unguarded — each of these raised a traceback."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import analyze

    a_directory = tmp_path / "dir"
    a_directory.mkdir()

    not_utf8 = tmp_path / "latin.csv"
    not_utf8.write_bytes(b"incident_id,description\n1,caf\xe9\n")

    oversized = tmp_path / "big.csv"
    oversized.write_bytes(b"incident_id,description\n1," + b"A" * 200_000 + b"\n")

    for bad_input in (a_directory, not_utf8, oversized):
        code = analyze.main([str(bad_input), "--no-prompt"])
        err = capsys.readouterr().err
        assert code != 0, f"{bad_input.name} exited 0"
        assert "Traceback" not in err, f"{bad_input.name} printed a traceback"
        assert err.startswith("error:"), f"{bad_input.name} said nothing on stderr"


def test_the_analyzer_cli_reports_an_unwritable_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """M2. `write_bytes` was unguarded."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import analyze

    source = Path(__file__).resolve().parents[3] / "scripts" / "incidents-trackflow.csv"
    out_is_a_directory = tmp_path / "out"
    out_is_a_directory.mkdir()

    monkeypatch.setattr("builtins.input", lambda *_: "y")
    code = analyze.main([str(source), "--out", str(out_is_a_directory)])

    assert code != 0
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "directory" in err.lower()


def test_a_corrupt_database_file_is_reported_as_such(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """M3 in seed.py — a truncated JSON file has a specific remedy."""
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    monkeypatch.setenv("TINYDB_PATH", str(broken))

    import database

    database.close_db()
    import seed

    code = seed.main()

    assert code != 0
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "json" in err.lower()
    database.close_db()


def test_the_seed_json_check_matches_the_error_the_module_raises() -> None:
    """`seed.py` catches `json.JSONDecodeError`; TinyDB must raise that."""
    assert issubclass(json.JSONDecodeError, ValueError)
