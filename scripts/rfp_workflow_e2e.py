"""Reproducible RFP Parts 1-3 run with simulated named-owner approvals."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from rfp_intake import (
    ApprovalCoordinator,
    generate_response,
    process_rfp,
    synthesize_final_document,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--ticket-id", default="rfp-e2e-demo")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    intake = process_rfp(str(args.pdf), args.ticket_id)
    if intake.status != "intake_complete":
        raise SystemExit(f"Document did not pass intake: {intake.classification.reason}")
    response = generate_response(intake.handoff_payload)

    with tempfile.TemporaryDirectory(prefix="trackflow-rfp-checkpoints-") as directory:
        coordinator = ApprovalCoordinator(Path(directory) / "approvals.sqlite3")
        try:
            pending = coordinator.start(response.handoff_payload)
            approved = {
                department_id: coordinator.resume(
                    args.ticket_id,
                    department_id,
                    "approve",
                    state["contact"],
                    "Simulated named-owner approval for reproducible E2E verification.",
                )
                for department_id, state in pending.items()
            }
        finally:
            coordinator.close()

    document = synthesize_final_document(
        args.ticket_id,
        response.handoff_payload["metadata"],
        list(approved.values()),
    )
    output = args.output or Path(tempfile.gettempdir()) / f"{args.ticket_id}-proposal.md"
    output.write_text(document, encoding="utf-8")
    print(
        json.dumps(
            {
                "ticket_id": args.ticket_id,
                "states": [
                    "analyzing",
                    "intake_complete",
                    "drafting",
                    "under_evaluation",
                    "waiting_for_approval",
                    "done",
                ],
                "departments": {
                    department_id: state["approval_status"]
                    for department_id, state in approved.items()
                },
                "checkpoint_threads": {
                    department_id: state["thread_id"]
                    for department_id, state in approved.items()
                },
                "final_document": str(output),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
