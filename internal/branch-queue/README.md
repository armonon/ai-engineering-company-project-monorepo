# Branch Queue — Tagged Service Queue Manager

This standard-library Python terminal application implements the 4Geeks
**Branch Queue — Tagged Service Queue** project inside the cumulative
coursework monorepo.

It includes:

- separate FIFO queues for `deposit`, `withdrawal`, and `account_management`;
- one globally sequential ticket counter across all services;
- `issue_ticket`, `call_next`, `peek_next`, `list_waiting`, and `stats`;
- explicit invalid-service and empty-queue handling;
- a resilient interactive terminal menu; and
- atomic ticket issuance and client calling for concurrent agents.

## Run

```bash
cd internal/branch-queue
python3 branch_queue.py
```

## Test

```bash
cd internal/branch-queue
python3 -m unittest -v test_branch_queue.py
```

See [`DESIGN.md`](./DESIGN.md) for the per-service data-structure and
concurrent-mutation reasoning required by the rubric.
