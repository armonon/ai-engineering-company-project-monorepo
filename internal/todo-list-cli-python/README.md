# Todo List CLI with Python

This folder preserves the official 4Geeks `python-hello` project interface for
the **Todo List CLI with Python** assignment while keeping the completed work in
the cumulative TrackFlow monorepo.

The operations tool supports the complete required flow:

- add any number of task titles;
- display tasks with one-based numeric positions;
- delete one task by its displayed position;
- save the current list to `todos.csv`;
- load the list from `todos.csv` after restarting the program.

It uses only Python's standard library.

## Run the CLI

```bash
cd internal/todo-list-cli-python
python3 app.py
```

## Run the acceptance tests

```bash
cd internal/todo-list-cli-python
python3 test.py
```

The evaluator-facing functions remain in `app.py` with their required names:
`add_one_task`, `print_list`, `delete_task`, `save_todos`, and `load_todos`.
The generated `todos.csv` is local runtime data and is intentionally ignored.
