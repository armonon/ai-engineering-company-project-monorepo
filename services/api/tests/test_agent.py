from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_agent_query_requires_auth(api):
    assert api.post("/agent/query", json={"question": "What is the SLA?"}).status_code == 401


def test_agent_query_invokes_compiled_runtime(signed_in):
    result = SimpleNamespace(answer="Grounded answer", run_id="run-123")
    mock_runtime = SimpleNamespace(invoke=lambda _question, user_id: result)
    with (
        patch("routers.agent.runtime", mock_runtime),
        patch.object(mock_runtime, "invoke", return_value=result) as invoke,
    ):
        response = signed_in.post("/agent/query", json={"question": "What is the SLA?"})
    assert response.status_code == 200
    assert response.json() == {"answer": "Grounded answer", "run_id": "run-123"}
    invoke.assert_called_once_with("What is the SLA?", user_id="user:1")


def test_agent_failure_does_not_expose_internal_details(signed_in):
    mock_runtime = SimpleNamespace(invoke=lambda _question, user_id: None)
    with (
        patch("routers.agent.runtime", mock_runtime),
        patch.object(mock_runtime, "invoke", side_effect=RuntimeError("provider-secret")),
    ):
        response = signed_in.post("/agent/query", json={"question": "What is the SLA?"})
    assert response.status_code == 503
    assert "provider-secret" not in response.text


def test_agent_trace_is_queryable(signed_in):
    events = [{"sequence": 1, "node": "receive", "created_at": "now", "output": {}}]
    with (
        patch("routers.agent.runtime.traces.is_owner", return_value=True),
        patch("routers.agent.runtime.traces.get", return_value=events),
    ):
        response = signed_in.get("/agent/traces/run-123")
    assert response.status_code == 200
    assert response.json() == {"run_id": "run-123", "events": events}


def test_agent_trace_hides_another_users_run(signed_in):
    with (
        patch("routers.agent.runtime.traces.is_owner", return_value=False),
        patch("routers.agent.runtime.traces.get") as get_trace,
    ):
        response = signed_in.get("/agent/traces/another-users-run")
    assert response.status_code == 404
    get_trace.assert_not_called()


def test_guardrail_summary_requires_auth(api):
    assert api.get("/agent/guardrails/summary").status_code == 401


def test_guardrail_summary_is_queryable(signed_in):
    summary = {
        "total": 2,
        "by_failure_type": {"security": 1, "content": 1},
        "by_action": {"block": 1, "redirect": 1},
        "by_reason": {"instruction_change": 1, "casual_or_general": 1},
    }
    with patch("routers.agent.runtime.traces.guardrail_summary", return_value=summary):
        response = signed_in.get("/agent/guardrails/summary")
    assert response.status_code == 200
    assert response.json() == summary


def test_agent_runtime_is_wired_to_company_tools_mcp():
    from trackflow_agent import CompanyToolsMCPClient

    from routers import agent

    assert isinstance(agent.company_tools, CompanyToolsMCPClient)


def test_ticket_authorization_is_deny_by_default(monkeypatch: pytest.MonkeyPatch):
    from routers.agent import authorize_ticket

    monkeypatch.delenv("AGENT_TICKET_ACCESS_JSON", raising=False)
    assert authorize_ticket("user:7", 45821) is False
    assert authorize_ticket("admin:7", 45821) is True


def test_ticket_authorization_uses_explicit_user_allowlist(
    monkeypatch: pytest.MonkeyPatch,
):
    from routers.agent import authorize_ticket

    monkeypatch.setenv("AGENT_TICKET_ACCESS_JSON", '{"7":[482]}')
    assert authorize_ticket("user:7", 482) is True
    assert authorize_ticket("user:7", 483) is False
    assert authorize_ticket("user:8", 482) is False
