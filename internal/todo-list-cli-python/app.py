"""TrackFlow's small, standard-library-only task list CLI.

The public functions intentionally keep the names from the official 4Geeks
``python-hello`` project contract so the course evaluator can import them.
"""

from __future__ import annotations

import csv
from pathlib import Path


TODOS_FILE = Path("todos.csv")
todos: list[str] = []


def get_todos() -> list[str]:
    """Return the active in-memory task list."""

    return todos


def add_one_task(title: str) -> None:
    """Append one non-empty task title to the active list."""

    normalized_title = str(title).strip()
    if not normalized_title:
        raise ValueError("Task title cannot be empty.")
    todos.append(normalized_title)


def print_list() -> None:
    """Print pending tasks in their current one-based list positions."""

    if not todos:
        print("No pending tasks.")
        return

    for position, task in enumerate(todos, start=1):
        print(f"{position}. {task}")


def delete_task(number_to_delete: int | str) -> None:
    """Delete the task at a one-based position.

    The CLI accepts text input, while the course tests call the same function
    with integers, so both representations are supported deliberately.
    """

    try:
        position = int(number_to_delete)
    except (TypeError, ValueError) as error:
        raise ValueError("Task position must be a whole number.") from error

    if position < 1 or position > len(todos):
        raise ValueError(f"Task position must be between 1 and {len(todos)}.")

    del todos[position - 1]


def save_todos() -> None:
    """Persist every active task to ``todos.csv``."""

    with TODOS_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows((task,) for task in todos)


def load_todos() -> None:
    """Replace the active list with tasks read from ``todos.csv``."""

    if not TODOS_FILE.exists():
        todos.clear()
        return

    with TODOS_FILE.open("r", newline="", encoding="utf-8") as file:
        loaded = [row[0] for row in csv.reader(file) if row]

    todos[:] = loaded


def main() -> None:
    """Run the interactive command-line menu."""

    while True:
        print(
            """
Choose an option:
    1. Add one task
    2. Delete a task
    3. Print the current list of tasks
    4. Save todos to todos.csv
    5. Load todos from todos.csv
    6. Exit
"""
        )
        response = input("> ").strip()

        if response == "6":
            return
        if response == "3":
            print_list()
        elif response == "2":
            print_list()
            try:
                delete_task(input("What task number do you want to delete? "))
                print("Task deleted.")
            except ValueError as error:
                print(error)
        elif response == "1":
            try:
                add_one_task(input("What is your task title? "))
                print("Task added.")
            except ValueError as error:
                print(error)
        elif response == "4":
            save_todos()
            print("Tasks saved.")
        elif response == "5":
            load_todos()
            print("Tasks loaded.")
        else:
            print("Invalid response, asking again...")


if __name__ == "__main__":
    main()
