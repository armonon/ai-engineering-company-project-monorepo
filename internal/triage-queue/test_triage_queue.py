"""Acceptance tests for the Triage Queue coursework project."""

from __future__ import annotations

import io
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from triage_queue import Patient, QueueEmptyError, TriageQueue, run_cli

BASE_TIME = datetime(2026, 10, 28, 12, tzinfo=UTC)


class TriageQueueTests(unittest.TestCase):
    def patient(self, name: str, level: int, minutes: int) -> Patient:
        return Patient(name, level, BASE_TIME + timedelta(minutes=minutes))

    def test_critical_patient_moves_ahead_of_lower_priorities(self) -> None:
        queue = TriageQueue()
        queue.enqueue(self.patient("Standard", 3, 0))
        queue.enqueue(self.patient("Urgent", 2, 1))
        queue.enqueue(self.patient("Critical", 1, 2))

        self.assertEqual(
            [patient.name for patient in queue.list_queue()],
            ["Critical", "Urgent", "Standard"],
        )

    def test_fifo_is_preserved_inside_the_same_level(self) -> None:
        queue = TriageQueue([self.patient("First", 2, 0), self.patient("Second", 2, 1)])
        self.assertEqual(queue.dequeue().name, "First")
        self.assertEqual(queue.dequeue().name, "Second")

    def test_exact_timestamp_ties_preserve_enqueue_order(self) -> None:
        queue = TriageQueue()
        queue.enqueue(self.patient("First", 1, 0))
        queue.enqueue(self.patient("Second", 1, 0))
        self.assertEqual([patient.name for patient in queue.list_queue()], ["First", "Second"])

    def test_peek_and_list_do_not_remove_patients(self) -> None:
        queue = TriageQueue([self.patient("Next", 1, 0), self.patient("Later", 3, 1)])
        self.assertEqual(queue.peek().name, "Next")
        self.assertEqual([patient.name for patient in queue.list_queue()], ["Next", "Later"])
        self.assertEqual(len(queue), 2)

    def test_stats_include_all_levels(self) -> None:
        queue = TriageQueue(
            [self.patient("One", 1, 0), self.patient("Two", 1, 1), self.patient("Three", 3, 2)]
        )
        self.assertEqual(queue.stats(), {1: 2, 2: 0, 3: 1})

    def test_empty_queue_operations_raise_clear_error(self) -> None:
        queue = TriageQueue()
        with self.assertRaisesRegex(QueueEmptyError, "No patients"):
            queue.dequeue()
        with self.assertRaisesRegex(QueueEmptyError, "No patients"):
            queue.peek()

    def test_patient_validation_rejects_invalid_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            Patient("  ", 1)
        with self.assertRaisesRegex(ValueError, "1, 2, or 3"):
            Patient("Alex", 4)

    def test_naive_timestamp_is_normalized_to_utc(self) -> None:
        patient = Patient("Alex", 2, datetime(2026, 10, 28, 12))
        self.assertEqual(patient.arrived_at.tzinfo, UTC)

    def test_enqueue_requires_a_patient(self) -> None:
        with self.assertRaisesRegex(TypeError, "Patient"):
            TriageQueue().enqueue("not a patient")  # type: ignore[arg-type]

    def test_concurrent_dequeues_never_return_the_same_patient(self) -> None:
        queue = TriageQueue(self.patient(f"Patient {index}", 2, index) for index in range(20))
        with ThreadPoolExecutor(max_workers=4) as executor:
            names = list(executor.map(lambda _index: queue.dequeue().name, range(20)))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(queue), 0)

    def test_cli_handles_invalid_menu_and_empty_queue(self) -> None:
        output = io.StringIO()
        with patch("builtins.input", side_effect=["nope", "2", "5"]), redirect_stdout(output):
            run_cli()
        rendered = output.getvalue()
        self.assertIn("Invalid option", rendered)
        self.assertIn("No patients are waiting", rendered)
        self.assertIn("Goodbye", rendered)

    def test_cli_rejects_invalid_patient_then_continues(self) -> None:
        output = io.StringIO()
        with patch("builtins.input", side_effect=["1", "Alex", "9", "5"]), redirect_stdout(output):
            run_cli()
        self.assertIn("Could not add patient", output.getvalue())


if __name__ == "__main__":
    unittest.main()
