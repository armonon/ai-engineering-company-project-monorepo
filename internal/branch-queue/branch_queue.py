"""Standard-library tagged service queues for a bank branch terminal."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

SERVICE_TYPES = ("deposit", "withdrawal", "account_management")


class QueueEmptyError(LookupError):
    """Raised when a selected service has no waiting clients."""


def _validate_service_type(service_type: str) -> str:
    normalized = str(service_type).strip().lower()
    if normalized not in SERVICE_TYPES:
        allowed = ", ".join(SERVICE_TYPES)
        raise ValueError(f"Service type must be one of: {allowed}.")
    return normalized


@dataclass(frozen=True, slots=True)
class Ticket:
    """One globally numbered client ticket."""

    number: int
    client_name: str
    service_type: str
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.number, int) or isinstance(self.number, bool) or self.number < 1:
            raise ValueError("Ticket number must be a positive integer.")
        normalized_name = str(self.client_name).strip()
        if not normalized_name:
            raise ValueError("Client name cannot be empty.")
        normalized_service = _validate_service_type(self.service_type)
        if not isinstance(self.issued_at, datetime):
            raise TypeError("issued_at must be a datetime.")

        normalized_time = self.issued_at
        if normalized_time.tzinfo is None:
            normalized_time = normalized_time.replace(tzinfo=UTC)
        else:
            normalized_time = normalized_time.astimezone(UTC)

        object.__setattr__(self, "client_name", normalized_name)
        object.__setattr__(self, "service_type", normalized_service)
        object.__setattr__(self, "issued_at", normalized_time)


class BranchQueue:
    """Manage one independent FIFO queue per bank service type."""

    def __init__(self) -> None:
        self._queues: dict[str, deque[Ticket]] = {
            service_type: deque() for service_type in SERVICE_TYPES
        }
        self._next_ticket_number = 1
        self._lock = Lock()

    def issue_ticket(
        self,
        client_name: str,
        service_type: str,
        *,
        issued_at: datetime | None = None,
    ) -> Ticket:
        """Create and enqueue a globally numbered ticket atomically."""

        normalized_service = _validate_service_type(service_type)
        normalized_name = str(client_name).strip()
        if not normalized_name:
            raise ValueError("Client name cannot be empty.")

        with self._lock:
            ticket = Ticket(
                number=self._next_ticket_number,
                client_name=normalized_name,
                service_type=normalized_service,
                issued_at=issued_at or datetime.now(UTC),
            )
            self._next_ticket_number += 1
            self._queues[normalized_service].append(ticket)
            return ticket

    def call_next(self, service_type: str) -> Ticket:
        """Atomically remove and return the oldest ticket for one service."""

        normalized_service = _validate_service_type(service_type)
        with self._lock:
            queue = self._queues[normalized_service]
            if not queue:
                raise QueueEmptyError(f"No clients are waiting for {normalized_service}.")
            return queue.popleft()

    def peek_next(self, service_type: str) -> Ticket:
        """Return the next ticket for one service without removing it."""

        normalized_service = _validate_service_type(service_type)
        with self._lock:
            queue = self._queues[normalized_service]
            if not queue:
                raise QueueEmptyError(f"No clients are waiting for {normalized_service}.")
            return queue[0]

    def list_waiting(self) -> dict[str, list[Ticket]]:
        """Return an isolated FIFO snapshot for every service type."""

        with self._lock:
            return {service: list(queue) for service, queue in self._queues.items()}

    def stats(self) -> dict[str, int]:
        """Return per-service and overall waiting counts."""

        with self._lock:
            counts = {service: len(queue) for service, queue in self._queues.items()}
            counts["total"] = sum(counts.values())
            return counts


def _read_service_type() -> str:
    raw = input("Service (deposit, withdrawal, account_management): ")
    return _validate_service_type(raw)


def _print_waiting(branch: BranchQueue) -> None:
    waiting = branch.list_waiting()
    if not any(waiting.values()):
        print("No clients are waiting.")
        return

    for service_type, tickets in waiting.items():
        print(f"{service_type}:")
        if not tickets:
            print("  No clients waiting.")
            continue
        for ticket in tickets:
            print(
                f"  #{ticket.number} {ticket.client_name} | issued {ticket.issued_at.isoformat()}"
            )


def run_cli(branch: BranchQueue | None = None) -> None:
    """Run the branch queue terminal without crashing on invalid input."""

    active_branch = branch or BranchQueue()
    while True:
        print(
            "\nBranch Queue\n"
            "1. Issue ticket\n"
            "2. Call next client\n"
            "3. Peek next client\n"
            "4. List all waiting\n"
            "5. Show statistics\n"
            "6. Exit"
        )
        choice = input("> ").strip()

        if choice == "6":
            print("Goodbye.")
            return
        if choice == "1":
            try:
                client_name = input("Client name: ")
                service_type = _read_service_type()
                ticket = active_branch.issue_ticket(client_name, service_type)
                print(f"Issued ticket #{ticket.number} for {ticket.client_name}.")
            except ValueError as error:
                print(f"Could not issue ticket: {error}")
        elif choice in {"2", "3"}:
            try:
                service_type = _read_service_type()
                ticket = (
                    active_branch.call_next(service_type)
                    if choice == "2"
                    else active_branch.peek_next(service_type)
                )
                verb = "Call" if choice == "2" else "Next"
                print(f"{verb}: #{ticket.number} {ticket.client_name}.")
            except (QueueEmptyError, ValueError) as error:
                print(error)
        elif choice == "4":
            _print_waiting(active_branch)
        elif choice == "5":
            counts = active_branch.stats()
            print(
                "Waiting: "
                f"deposits={counts['deposit']}, withdrawals={counts['withdrawal']}, "
                f"account management={counts['account_management']}, total={counts['total']}"
            )
        else:
            print("Invalid option. Choose 1, 2, 3, 4, 5, or 6.")


if __name__ == "__main__":
    run_cli()
