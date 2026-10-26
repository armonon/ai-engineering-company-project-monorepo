"""Acceptance tests for the 4Geeks Todo List CLI contract."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest

from app import (
    add_one_task,
    delete_task,
    get_todos,
    load_todos,
    print_list,
    save_todos,
)


class TodoListTests(unittest.TestCase):
    def setUp(self) -> None:
        get_todos().clear()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.previous_directory = os.getcwd()
        os.chdir(self.temporary_directory.name)

    def tearDown(self) -> None:
        os.chdir(self.previous_directory)
        self.temporary_directory.cleanup()

    def test_add_one_task_appends_as_many_tasks_as_needed(self) -> None:
        add_one_task("Receive LA delivery")
        add_one_task("Review Zaragoza dispatch")
        add_one_task("Call carrier")

        self.assertEqual(
            get_todos(),
            ["Receive LA delivery", "Review Zaragoza dispatch", "Call carrier"],
        )

    def test_print_list_uses_clear_one_based_positions(self) -> None:
        add_one_task("First task")
        add_one_task("Second task")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            print_list()

        self.assertEqual(output.getvalue(), "1. First task\n2. Second task\n")

    def test_delete_task_removes_the_selected_position_and_reindexes(self) -> None:
        for task in ("Make the bed", "Make lunch", "Clean kitchen"):
            add_one_task(task)

        delete_task("2")

        self.assertEqual(get_todos(), ["Make the bed", "Clean kitchen"])

    def test_delete_task_rejects_invalid_positions_without_mutating(self) -> None:
        add_one_task("Keep me")

        for invalid in (0, 2, "not-a-number"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                delete_task(invalid)

        self.assertEqual(get_todos(), ["Keep me"])

    def test_save_and_load_round_trip_csv_safe_titles(self) -> None:
        expected = ["Book carrier, urgent", 'Check "priority" shipments', "Normal task"]
        for task in expected:
            add_one_task(task)

        save_todos()
        get_todos().clear()
        load_todos()

        self.assertEqual(get_todos(), expected)

    def test_load_supports_the_official_plain_line_fixture(self) -> None:
        with open("todos.csv", "w", encoding="utf-8") as file:
            file.write("jump\nrun\nroll")

        load_todos()

        self.assertEqual(get_todos(), ["jump", "run", "roll"])

    def test_load_without_a_file_produces_an_empty_list(self) -> None:
        add_one_task("Old in-memory task")

        load_todos()

        self.assertEqual(get_todos(), [])

    def test_empty_titles_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            add_one_task("   ")
        self.assertEqual(get_todos(), [])


if __name__ == "__main__":
    unittest.main()
