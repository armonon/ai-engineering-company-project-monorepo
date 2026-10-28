# Triage Queue — Priority Queue Manager

This standard-library Python terminal application implements the 4Geeks
**Triage Queue — Priority Queue Manager** project inside the cumulative
coursework monorepo.

It provides:

- triage priority `1 → 2 → 3` regardless of arrival order;
- strict FIFO ordering inside the same triage level;
- `enqueue`, `dequeue`, `peek`, `list_queue`, and per-level `stats`;
- safe empty-queue and invalid-input handling;
- a functional interactive menu; and
- atomic in-process queue mutations for concurrent workers.

## Run

```bash
cd internal/triage-queue
python3 triage_queue.py
```

## Test

```bash
cd internal/triage-queue
python3 -m unittest -v test_triage_queue.py
```

See [`DESIGN.md`](./DESIGN.md) for the data-structure and concurrent-mutation
decisions required by the rubric.
