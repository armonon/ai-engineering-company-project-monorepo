"""Acceptance tests for the Branch Queue coursework project."""

from __future__ import annotations

import io
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import UTC, datetime
from unittest.mock import patch

from branch_queue import BranchQueue, QueueEmptyError, Ticket, run_cli


class BranchQueueTests(unittest.TestCase):
    def test_ticket_numbers_are_global_across_services(self) -> None:
        branch = BranchQueue()
        tickets = [
            branch.issue_ticket("Ana", "deposit"),
            branch.issue_ticket("Ben", "withdrawal"),
            branch.issue_ticket("Cara", "account_management"),
        ]
        self.assertEqual([ticket.number for ticket in tickets], [1, 2, 3])

    def test_each_service_preserves_its_own_fifo_order(self) -> None:
        branch = BranchQueue()
        branch.issue_ticket("First deposit", "deposit")
        branch.issue_ticket("Withdrawal", "withdrawal")
        branch.issue_ticket("Second deposit", "deposit")
        self.assertEqual(branch.call_next("deposit").client_name, "First deposit")
        self.assertEqual(branch.call_next("deposit").client_name, "Second deposit")

    def test_agents_cannot_cross_service_queues(self) -> None:
        branch = BranchQueue()
        withdrawal = branch.issue_ticket("Wendy", "withdrawal")
        deposit = branch.issue_ticket("Diego", "deposit")
        self.assertEqual(branch.call_next("deposit"), deposit)
        self.assertEqual(branch.peek_next("withdrawal"), withdrawal)

    def test_peek_does_not_remove_ticket(self) -> None:
        branch = BranchQueue()
        ticket = branch.issue_ticket("Ana", "deposit")
        self.assertEqual(branch.peek_next("deposit"), ticket)
        self.assertEqual(branch.stats()["total"], 1)

    def test_list_waiting_returns_all_services_and_is_isolated(self) -> None:
        branch = BranchQueue()
        branch.issue_ticket("Ana", "deposit")
        snapshot = branch.list_waiting()
        self.assertEqual(set(snapshot), {"deposit", "withdrawal", "account_management"})
        snapshot["deposit"].clear()
        self.assertEqual(branch.stats()["deposit"], 1)

    def test_stats_include_service_counts_and_total(self) -> None:
        branch = BranchQueue()
        branch.issue_ticket("Ana", "deposit")
        branch.issue_ticket("Ben", "withdrawal")
        branch.issue_ticket("Cara", "withdrawal")
        self.assertEqual(
            branch.stats(),
            {"deposit": 1, "withdrawal": 2, "account_management": 0, "total": 3},
        )

    def test_empty_service_operations_raise_clear_error(self) -> None:
        branch = BranchQueue()
        with self.assertRaisesRegex(QueueEmptyError, "No clients"):
            branch.call_next("deposit")
        with self.assertRaisesRegex(QueueEmptyError, "No clients"):
            branch.peek_next("withdrawal")

    def test_invalid_service_is_rejected_consistently(self) -> None:
        branch = BranchQueue()
        with self.assertRaisesRegex(ValueError, "Service type"):
            branch.issue_ticket("Ana", "loan")
        with self.assertRaisesRegex(ValueError, "Service type"):
            branch.call_next("loan")

    def test_client_name_and_timestamp_are_validated(self) -> None:
        branch = BranchQueue()
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            branch.issue_ticket("  ", "deposit")
        ticket = branch.issue_ticket("  Ana  ", "DEPOSIT", issued_at=datetime(2026, 10, 28, 12))
        self.assertEqual(ticket.client_name, "Ana")
        self.assertEqual(ticket.service_type, "deposit")
        self.assertEqual(ticket.issued_at.tzinfo, UTC)

    def test_ticket_rejects_non_positive_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            Ticket(0, "Ana", "deposit")

    def test_concurrent_issuance_keeps_unique_sequential_numbers(self) -> None:
        branch = BranchQueue()
        with ThreadPoolExecutor(max_workers=8) as executor:
            tickets = list(
                executor.map(
                    lambda index: branch.issue_ticket(f"Client {index}", "deposit"),
                    range(100),
                )
            )
        self.assertEqual(sorted(ticket.number for ticket in tickets), list(range(1, 101)))

    def test_concurrent_call_next_never_calls_one_client_twice(self) -> None:
        branch = BranchQueue()
        for index in range(30):
            branch.issue_ticket(f"Client {index}", "withdrawal")
        with ThreadPoolExecutor(max_workers=6) as executor:
            names = list(
                executor.map(
                    lambda _index: branch.call_next("withdrawal").client_name,
                    range(30),
                )
            )
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(branch.stats()["total"], 0)

    def test_cli_handles_invalid_menu_service_and_empty_queue(self) -> None:
        output = io.StringIO()
        answers = ["bad", "2", "loan", "2", "deposit", "6"]
        with patch("builtins.input", side_effect=answers), redirect_stdout(output):
            run_cli()
        rendered = output.getvalue()
        self.assertIn("Invalid option", rendered)
        self.assertIn("Service type", rendered)
        self.assertIn("No clients are waiting", rendered)
        self.assertIn("Goodbye", rendered)


if __name__ == "__main__":
    unittest.main()
