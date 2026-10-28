# Triage Queue design

## Data structure

`TriageQueue` uses Python's `heapq` with entries shaped as
`(triage_level, arrived_at, sequence, patient)`. Lower triage levels sort first,
so a newly arrived critical patient automatically moves ahead of urgent and
standard patients. The arrival timestamp preserves FIFO order inside one
level, while the monotonically increasing sequence number gives deterministic
FIFO behavior when two timestamps are identical.

This is preferable to a single `deque`, which cannot insert a new critical
patient in priority order efficiently, and to a fully sorted list, which must
shift entries on insertion. A heap provides `O(log n)` enqueue/dequeue and
`O(1)` peek without re-sorting the full queue after each arrival.

## Concurrent mutation

All heap reads and mutations are protected by one `threading.Lock`. A worker
must acquire that lock and remove (`heappop`) the next patient before releasing
it or starting treatment. This mutation-first order transfers ownership of the
patient atomically, so a second worker cannot call the same person. An
incoming critical patient waits briefly for the same lock, then enters the
remaining queue; it cannot invalidate the patient already claimed by another
worker.

In a multi-process deployment, the same invariant would move to a database
transaction using row-level locking or an atomic queue broker operation. The
in-memory lock is correct for this single-process terminal assignment.
