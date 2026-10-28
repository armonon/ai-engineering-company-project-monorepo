# Branch Queue design

## One queue per service

`BranchQueue` stores three independent `collections.deque` instances keyed by
`deposit`, `withdrawal`, and `account_management`. An agent can locate its
service queue with one dictionary lookup and call the oldest client with an
`O(1)` `popleft`. A single shared list would either require scanning past
unrelated tickets on every call or repeatedly filtering and rebuilding the
list. Separate queues make the service boundary explicit and keep every
service FIFO by construction.

Ticket numbering remains global rather than per queue. The next number and
the chosen queue are updated in one critical section, so concurrent issuers
cannot receive the same number even when they request different services.

## Concurrent `call_next`

All queue operations share one `threading.Lock`. An agent acquires it and
removes the ticket with `popleft` before the method returns or service work
begins. That mutation-first order atomically transfers ownership: a second
agent of the same service cannot observe or remove the same client. Peek,
snapshot, and statistics operations also hold the lock so they never read a
half-completed issuance or call.

For a future multi-process branch system, this invariant would move to a queue
broker acknowledgement or a database transaction with row-level locking. The
in-memory lock is the correct boundary for this single-process terminal model.
