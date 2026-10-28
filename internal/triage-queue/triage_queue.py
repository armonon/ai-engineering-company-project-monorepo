"""Standard-library priority queue for a hospital triage terminal."""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from threading import Lock

TRIAGE_LEVELS = (1, 2, 3)


class QueueEmptyError(LookupError):
    """Raised when an operation needs a patient but the queue is empty."""


@dataclass(frozen=True, slots=True)
class Patient:
    """A patient waiting for attention in the emergency unit."""

    name: str
    triage_level: int
    arrived_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        normalized_name = str(self.name).strip()
        if not normalized_name:
            raise ValueError("Patient name cannot be empty.")
        if self.triage_level not in TRIAGE_LEVELS:
            raise ValueError("Triage level must be 1, 2, or 3.")
        if not isinstance(self.arrived_at, datetime):
            raise TypeError("arrived_at must be a datetime.")

        normalized_time = self.arrived_at
        if normalized_time.tzinfo is None:
            normalized_time = normalized_time.replace(tzinfo=UTC)
        else:
            normalized_time = normalized_time.astimezone(UTC)

        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "arrived_at", normalized_time)


class TriageQueue:
    """Thread-safe priority queue with FIFO ordering inside each level.

    Each heap entry is ``(triage_level, arrived_at, sequence, patient)``.
    The level makes critical patients sort first, the UTC timestamp preserves
    arrival order, and the sequence number makes exact timestamp ties stable.
    """

    def __init__(self, patients: Iterable[Patient] = ()) -> None:
        self._queue: list[tuple[int, datetime, int, Patient]] = []
        self._sequence = count()
        self._lock = Lock()
        for patient in patients:
            self.enqueue(patient)

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)

    def enqueue(self, patient: Patient) -> Patient:
        """Add and return a patient without re-sorting the full queue."""

        if not isinstance(patient, Patient):
            raise TypeError("enqueue expects a Patient instance.")
        with self._lock:
            heapq.heappush(
                self._queue,
                (
                    patient.triage_level,
                    patient.arrived_at,
                    next(self._sequence),
                    patient,
                ),
            )
        return patient

    def dequeue(self) -> Patient:
        """Atomically remove and return the next patient for attention."""

        with self._lock:
            if not self._queue:
                raise QueueEmptyError("No patients are waiting.")
            return heapq.heappop(self._queue)[3]

    def peek(self) -> Patient:
        """Return the next patient without changing the queue."""

        with self._lock:
            if not self._queue:
                raise QueueEmptyError("No patients are waiting.")
            return self._queue[0][3]

    def list_queue(self) -> list[Patient]:
        """Return a non-mutating snapshot in exact attention order."""

        with self._lock:
            return [entry[3] for entry in sorted(self._queue)]

    def stats(self) -> dict[int, int]:
        """Return the current waiting count for every triage level."""

        with self._lock:
            counts = {level: 0 for level in TRIAGE_LEVELS}
            for triage_level, _arrived_at, _sequence, _patient in self._queue:
                counts[triage_level] += 1
            return counts


def _read_triage_level() -> int:
    raw_level = input("Triage level (1=critical, 2=urgent, 3=standard): ").strip()
    try:
        level = int(raw_level)
    except ValueError as error:
        raise ValueError("Triage level must be a whole number from 1 to 3.") from error
    if level not in TRIAGE_LEVELS:
        raise ValueError("Triage level must be 1, 2, or 3.")
    return level


def _print_queue(queue: TriageQueue) -> None:
    patients = queue.list_queue()
    if not patients:
        print("No patients are waiting.")
        return
    for position, patient in enumerate(patients, start=1):
        print(
            f"{position}. {patient.name} | level {patient.triage_level} | "
            f"arrived {patient.arrived_at.isoformat()}"
        )


def run_cli(queue: TriageQueue | None = None) -> None:
    """Run the resilient interactive terminal menu."""

    active_queue = queue or TriageQueue()
    while True:
        print(
            "\nTriage Queue\n"
            "1. Add patient\n"
            "2. Call next patient\n"
            "3. View queue\n"
            "4. View statistics\n"
            "5. Exit"
        )
        choice = input("> ").strip()

        if choice == "5":
            print("Goodbye.")
            return
        if choice == "1":
            try:
                patient = Patient(input("Patient name: "), _read_triage_level())
                active_queue.enqueue(patient)
                print(f"Added {patient.name} at triage level {patient.triage_level}.")
            except (TypeError, ValueError) as error:
                print(f"Could not add patient: {error}")
        elif choice == "2":
            try:
                patient = active_queue.dequeue()
                print(f"Call {patient.name} (triage level {patient.triage_level}).")
            except QueueEmptyError as error:
                print(error)
        elif choice == "3":
            _print_queue(active_queue)
        elif choice == "4":
            counts = active_queue.stats()
            print(
                "Waiting: "
                f"level 1={counts[1]}, level 2={counts[2]}, level 3={counts[3]}, "
                f"total={sum(counts.values())}"
            )
        else:
            print("Invalid option. Choose 1, 2, 3, 4, or 5.")


if __name__ == "__main__":
    run_cli()
