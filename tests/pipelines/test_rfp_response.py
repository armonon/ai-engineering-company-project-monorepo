from __future__ import annotations

from rfp_intake import (
    build_response_graph,
    evaluate_compliance,
    evaluate_section,
    generate_reverse_section,
    generate_warehouse_section,
)


def handoff(*departments: str, country: str = "Spain", currency: str = "EUR") -> dict:
    return {
        "ticket_id": "ticket-123",
        "metadata": {
            "client_name": "ModaViva",
            "client_country": country,
            "currency": currency,
            "monthly_volume": 5_000,
        },
        "workstreams": [
            {
                "department_id": department,
                "contact": "Owner",
                "key_aspects": ["Confirm scope and pricing inputs."],
            }
            for department in departments
        ],
    }


def test_warehouse_generator_uses_part1_metadata_and_trackflow_rules() -> None:
    content = generate_warehouse_section(
        handoff("warehouse")["metadata"], ["Confirm storage capacity."], "", 1
    )
    assert "EUR" in content
    assert "storage capacity" in content.lower()
    assert "98.5% on-time delivery SLA" in content
    assert "Monthly volume | Discount" in content


def test_three_structured_evaluators_pass_a_compliant_section() -> None:
    payload = handoff("reverse")
    content = generate_reverse_section(
        payload["metadata"], payload["workstreams"][0]["key_aspects"], "", 1
    )
    result = evaluate_section("reverse", payload["metadata"], content)
    assert result["overall_pass"] is True
    assert set(result) == {
        "department_id",
        "readability",
        "relevance",
        "compliance",
        "overall_pass",
        "feedback_for_generator",
    }


def test_briefing_returns_rule_rejects_under_48_hour_promise() -> None:
    draft = "We promise returns processing within 24 hours. EUR."
    result = evaluate_compliance(handoff("reverse")["metadata"], draft)
    assert result["pass"] is False
    assert any("TF-RETURNS-MIN-48H" in violation for violation in result["violations"])


def test_failed_generator_retries_then_hands_last_draft_to_part3() -> None:
    attempts: list[int] = []

    def bad_generator(metadata: dict, aspects: list[str], feedback: str, iteration: int) -> str:
        attempts.append(iteration)
        return "Too short and unrelated. Returns within 12 hours."

    statuses: list[str] = []
    runtime = build_response_graph(
        {"reverse": bad_generator}, max_iterations=2, on_status=statuses.append
    )
    result = runtime.invoke(handoff("reverse"))
    section = result.sections[0]

    assert attempts == [1, 2]
    assert result.status == "needs_human_review"
    assert section["draft_content"] == "Too short and unrelated. Returns within 12 hours."
    assert section["evaluation_result"]["overall_pass"] is False
    assert section["needs_human_review"] is True
    assert result.handoff_payload["sections"][0]["draft_content"] == section["draft_content"]
    assert statuses == [
        "drafting",
        "drafting",
        "under_evaluation",
        "drafting",
        "under_evaluation",
        "needs_human_review",
    ]


def test_successful_departments_generate_independently() -> None:
    result = build_response_graph().invoke(handoff("warehouse", "reverse"))
    assert result.status == "under_evaluation"
    assert {section["department_id"] for section in result.sections} == {
        "warehouse",
        "reverse",
    }
    assert all(section["evaluation_result"]["overall_pass"] for section in result.sections)
