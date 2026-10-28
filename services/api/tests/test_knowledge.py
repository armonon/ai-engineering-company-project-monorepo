from unittest.mock import patch


def test_knowledge_query_requires_auth(api):
    response = api.post("/knowledge/query", json={"question": "What is the return window?"})
    assert response.status_code == 401


def test_knowledge_query_returns_only_answer(signed_in):
    with patch(
        "routers.knowledge.query", return_value="Returns are normally accepted for 30 days."
    ):
        response = signed_in.post(
            "/knowledge/query", json={"question": "What is the return window?"}
        )
    assert response.status_code == 200
    assert response.json() == {"answer": "Returns are normally accepted for 30 days."}


def test_knowledge_provider_failure_is_safe(signed_in):
    with patch("routers.knowledge.query", side_effect=RuntimeError("secret provider detail")):
        response = signed_in.post("/knowledge/query", json={"question": "Can we discount storage?"})
    assert response.status_code == 503
    assert "secret provider detail" not in response.text
