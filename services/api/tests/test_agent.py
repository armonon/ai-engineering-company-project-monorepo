from types import SimpleNamespace
from unittest.mock import patch


def test_agent_query_requires_auth(api):
    assert api.post("/agent/query", json={"question": "What is the SLA?"}).status_code == 401


def test_agent_query_invokes_compiled_runtime(signed_in):
    result = SimpleNamespace(answer="Grounded answer", run_id="run-123")
    mock_runtime = SimpleNamespace(invoke=lambda _question: result)
    with (
        patch("routers.agent.runtime", mock_runtime),
        patch.object(mock_runtime, "invoke", return_value=result) as invoke,
    ):
        response = signed_in.post("/agent/query", json={"question": "What is the SLA?"})
    assert response.status_code == 200
    assert response.json() == {"answer": "Grounded answer", "run_id": "run-123"}
    invoke.assert_called_once_with("What is the SLA?")


def test_agent_failure_does_not_expose_internal_details(signed_in):
    mock_runtime = SimpleNamespace(invoke=lambda _question: None)
    with (
        patch("routers.agent.runtime", mock_runtime),
        patch.object(mock_runtime, "invoke", side_effect=RuntimeError("provider-secret")),
    ):
        response = signed_in.post("/agent/query", json={"question": "What is the SLA?"})
    assert response.status_code == 503
    assert "provider-secret" not in response.text


def test_agent_trace_is_queryable(signed_in):
    events = [{"sequence": 1, "node": "receive", "created_at": "now", "output": {}}]
    with patch("routers.agent.runtime.traces.get", return_value=events):
        response = signed_in.get("/agent/traces/run-123")
    assert response.status_code == 200
    assert response.json() == {"run_id": "run-123", "events": events}


def test_agent_ticket_tool_reads_existing_incident_manager(signed_in):
    created = signed_in.post(
        "/api/incidents",
        json={
            "title": "Parcel missing from the Zaragoza outbound bay",
            "description": "Scanned in but absent from the loading dock.",
            "category": "lost_parcel",
            "origin": "branch",
            "branch": "zaragoza_warehouse",
        },
    )
    assert created.status_code == 201
    incident = created.json()

    response = signed_in.post(
        "/agent/query",
        json={"question": f"What is the status of ticket {incident['id']}?"},
    )

    assert response.status_code == 200
    assert f"Incident {incident['id']}: status=open" in response.json()["answer"]
