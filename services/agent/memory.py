"""Consent-gated episodic memory for the TrackFlow support agent.

This store is intentionally separate from the read-only company knowledge
collection. It persists only user-approved operational corrections/preferences
and keeps a complete proposal decision log.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

DecisionLabel = Literal["approve", "reject", "edit", "ambiguous"]
ProposalStatus = Literal[
    "pending",
    "approved",
    "edited",
    "rejected",
    "ambiguous_rejected",
    "silence_rejected",
]


@dataclass(frozen=True)
class MemoryCandidate:
    category: Literal["carrier_rule", "recurring_incident", "b2b_report_preference"]
    scope_key: str
    fact: str
    rationale: str


@dataclass(frozen=True)
class Decision:
    label: DecisionLabel
    edited_fact: str | None = None
    remaining_message: str = ""
    confidence: float = 1.0


@dataclass(frozen=True)
class PendingProposal:
    proposal_id: str
    user_id: str
    run_id: str
    originating_message: str
    candidate: MemoryCandidate
    proposed_at: str


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    user_id: str
    category: str
    scope_key: str
    fact: str
    approved_at: str
    expires_at: str


_FORBIDDEN_PATTERNS = [
    re.compile(
        r"\b\d{1,5}\s+[\w.-]+(?:\s+[\w.-]+){0,3}\s+"
        r"(?:street|st|avenue|ave|road|rd)\b",
        re.I,
    ),
    re.compile(r"\b(?:calle|avenida)\s+[\w.-]+(?:\s+[\w.-]+){0,3}\s+\d+\b", re.I),
    re.compile(r"\b(?:warehouse|almac[eé]n)\s+(?:route|ruta|bay|dock)\b", re.I),
    re.compile(r"\b(?:contract|commercial)\s+negotiat", re.I),
    re.compile(r"\btracking\s+(?:number|id|#)?\s*[A-Z0-9-]{5,}\b", re.I),
]


def contains_forbidden_memory(text: str) -> bool:
    """TrackFlow briefing deny-list: locations, one-offs, and negotiations."""
    return any(pattern.search(text) for pattern in _FORBIDDEN_PATTERNS)


def evaluate_memory_candidate(message: str) -> MemoryCandidate | None:
    """Return a proposal only for the three briefing-approved memory classes."""
    cleaned = " ".join(message.split()).strip()
    lowered = cleaned.lower()
    if not cleaned or contains_forbidden_memory(cleaned):
        return None

    carrier_change = any(
        phrase in lowered
        for phrase in (
            "no longer covers",
            "stopped operating",
            "changed its coverage",
            "have to use the local carrier",
            "must use the local carrier",
        )
    )
    carrier_word = any(
        word in lowered for word in ("carrier", "seur", "dhl", "ups", "fedex", "correos")
    )
    if carrier_change and carrier_word:
        country = "spain" if "zaragoza" in lowered or "spain" in lowered else "usa"
        carrier = next(
            (name for name in ("seur", "dhl", "ups", "fedex", "correos") if name in lowered),
            "carrier",
        )
        return MemoryCandidate(
            category="carrier_rule",
            scope_key=f"{country}:{carrier}",
            fact=cleaned,
            rationale=(
                "A corrected carrier assignment or coverage rule can prevent "
                "repeated routing errors."
            ),
        )

    recurring_signal = any(
        phrase in lowered
        for phrase in ("third ticket", "several tickets", "repeated incidents", "this week")
    )
    incident_signal = any(word in lowered for word in ("delay", "incident", "ticket"))
    cause_signal = any(phrase in lowered for phrase in ("due to", "caused by", "are from"))
    if recurring_signal and incident_signal and cause_signal:
        location = "zaragoza" if "zaragoza" in lowered else "los-angeles"
        return MemoryCandidate(
            category="recurring_incident",
            scope_key=location,
            fact=cleaned,
            rationale="A known recurring incident cause prevents duplicate escalations.",
        )

    report_signal = "monthly report" in lowered and any(
        phrase in lowered for phrase in ("always wants", "prefers", "preference")
    )
    b2b_signal = any(word in lowered for word in ("client", "brand", "b2b"))
    if report_signal and b2b_signal:
        client_match = re.search(r"(?:the\s+)?([\w-]+)\s+(?:b2b\s+)?(?:client|brand)", lowered)
        client = client_match.group(1) if client_match else "b2b-client"
        return MemoryCandidate(
            category="b2b_report_preference",
            scope_key=client,
            fact=cleaned,
            rationale="A recurring B2B report preference improves future monthly reporting.",
        )
    return None


def classify_decision(message: str) -> Decision:
    """Explicitly classify a response; ambiguity always means rejection."""
    cleaned = " ".join(message.split()).strip()
    lowered = cleaned.lower()
    edit_match = re.match(r"^(?:edit|remember this instead)\s*:\s*(.+)$", cleaned, re.I)
    if edit_match:
        return Decision(label="edit", edited_fact=edit_match.group(1).strip())

    approve_match = re.match(
        r"^(?:yes(?:,?\s+(?:please\s+)?remember (?:it|that))?|approve|approved|"
        r"please remember (?:it|that)|remember it)"
        r"(?:[.!])?(?:\s+(?:also|and)\s+(.+))?$",
        cleaned,
        re.I,
    )
    if approve_match:
        return Decision(label="approve", remaining_message=approve_match.group(1) or "")

    reject_match = re.match(
        r"^(?:no|reject|do not remember (?:it|that)|don't remember (?:it|that)|forget it)"
        r"(?:[.!])?(?:\s+(?:also|and)\s+(.+))?$",
        cleaned,
        re.I,
    )
    if reject_match:
        return Decision(label="reject", remaining_message=reject_match.group(1) or "")
    is_question = "?" in cleaned or bool(
        re.match(r"^(?:what|why|how|when|where|who|can|could|should|is|are|do|does)\b", lowered)
    )
    return Decision(
        label="ambiguous",
        confidence=0.0,
        remaining_message=message if is_question else "",
    )


class MemoryStore:
    """SQLite read/write interface with one pending proposal per user."""

    def __init__(self, path: str | Path | None = None, max_per_user: int = 100):
        default = Path(__file__).resolve().parents[1] / "api" / "data" / "agent_memory.db"
        self.path = Path(path or os.getenv("AGENT_MEMORY_DB") or default)
        self.max_per_user = max_per_user
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    originating_message TEXT NOT NULL,
                    category TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    proposed_fact TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision_message TEXT,
                    final_fact TEXT,
                    proposed_at TEXT NOT NULL,
                    decided_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_proposal_per_user
                    ON memory_proposals(user_id) WHERE status = 'pending';
                CREATE TABLE IF NOT EXISTS agent_memories (
                    memory_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    originating_proposal_id TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    UNIQUE(user_id, category, scope_key)
                );
                """
            )

    def propose(
        self,
        *,
        user_id: str,
        run_id: str,
        originating_message: str,
        candidate: MemoryCandidate,
    ) -> PendingProposal:
        now = datetime.now(UTC).isoformat()
        proposal = PendingProposal(
            proposal_id=str(uuid4()),
            user_id=user_id,
            run_id=run_id,
            originating_message=originating_message,
            candidate=candidate,
            proposed_at=now,
        )
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM memory_proposals
                WHERE user_id = ? AND status = 'pending' LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if existing:
                return self._proposal_from_row(existing)
            connection.execute(
                """
                INSERT INTO memory_proposals
                    (proposal_id, user_id, run_id, originating_message, category,
                     scope_key, proposed_fact, rationale, status, proposed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    proposal.proposal_id,
                    user_id,
                    run_id,
                    originating_message,
                    candidate.category,
                    candidate.scope_key,
                    candidate.fact,
                    candidate.rationale,
                    now,
                ),
            )
        return proposal

    def pending(self, user_id: str) -> PendingProposal | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM memory_proposals
                WHERE user_id = ? AND status = 'pending'
                ORDER BY proposed_at DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return self._proposal_from_row(row) if row else None

    def resolve(
        self,
        proposal: PendingProposal,
        decision: Decision,
        _decision_message: str,
    ) -> MemoryRecord | None:
        final_fact = proposal.candidate.fact
        status: ProposalStatus
        if decision.label == "approve":
            status = "approved"
        elif decision.label == "edit" and decision.edited_fact:
            edited_candidate = evaluate_memory_candidate(decision.edited_fact)
            if edited_candidate is None or edited_candidate.category != proposal.candidate.category:
                status = "rejected"
                final_fact = ""
            else:
                status = "edited"
                final_fact = decision.edited_fact
        elif decision.label == "reject":
            status = "rejected"
            final_fact = ""
        else:
            status = "ambiguous_rejected"
            final_fact = ""

        now = datetime.now(UTC)
        record = None
        with self._lock, self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE memory_proposals
                SET status = ?, decision_message = ?, final_fact = ?, decided_at = ?
                WHERE proposal_id = ? AND status = 'pending'
                """,
                (
                    status,
                    decision.label,
                    final_fact or None,
                    now.isoformat(),
                    proposal.proposal_id,
                ),
            )
            if updated.rowcount != 1:
                return None
            if final_fact:
                ttl_days = {
                    "recurring_incident": 14,
                    "carrier_rule": 180,
                    "b2b_report_preference": 365,
                }[proposal.candidate.category]
                memory_id = str(uuid4())
                expires_at = (now + timedelta(days=ttl_days)).isoformat()
                connection.execute(
                    """
                    INSERT INTO agent_memories
                        (memory_id, user_id, category, scope_key, fact,
                         originating_proposal_id, approved_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, category, scope_key) DO UPDATE SET
                        fact = excluded.fact,
                        originating_proposal_id = excluded.originating_proposal_id,
                        approved_at = excluded.approved_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        memory_id,
                        proposal.user_id,
                        proposal.candidate.category,
                        proposal.candidate.scope_key,
                        final_fact,
                        proposal.proposal_id,
                        now.isoformat(),
                        expires_at,
                    ),
                )
                saved = connection.execute(
                    """
                    SELECT * FROM agent_memories
                    WHERE user_id = ? AND category = ? AND scope_key = ?
                    """,
                    (
                        proposal.user_id,
                        proposal.candidate.category,
                        proposal.candidate.scope_key,
                    ),
                ).fetchone()
                record = self._memory_from_row(saved)
            self._consolidate(connection, proposal.user_id, now)
        return record

    def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryRecord]:
        self.cleanup()
        terms = {term for term in re.findall(r"[a-z0-9-]+", query.lower()) if len(term) >= 3}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_memories
                WHERE user_id = ? AND expires_at > ?
                ORDER BY approved_at DESC
                """,
                (user_id, datetime.now(UTC).isoformat()),
            ).fetchall()
        scored = [
            (sum(term in f"{row['scope_key']} {row['fact']}".lower() for term in terms), row)
            for row in rows
        ]
        return [
            self._memory_from_row(row)
            for score, row in sorted(scored, key=lambda pair: pair[0], reverse=True)
            if score > 0
        ][:limit]

    def list_memories(self, user_id: str) -> list[MemoryRecord]:
        self.cleanup()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_memories WHERE user_id = ? ORDER BY approved_at",
                (user_id,),
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def proposal_log(self, user_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memory_proposals WHERE user_id = ? ORDER BY proposed_at",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def cleanup(self) -> None:
        now = datetime.now(UTC)
        pending_cutoff = (now - timedelta(hours=24)).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM agent_memories WHERE expires_at <= ?", (now.isoformat(),)
            )
            connection.execute(
                """
                UPDATE memory_proposals
                SET status = 'silence_rejected', decided_at = ?
                WHERE status = 'pending' AND proposed_at <= ?
                """,
                (now.isoformat(), pending_cutoff),
            )

    def _consolidate(self, connection: sqlite3.Connection, user_id: str, now: datetime) -> None:
        connection.execute("DELETE FROM agent_memories WHERE expires_at <= ?", (now.isoformat(),))
        connection.execute(
            """
            DELETE FROM agent_memories WHERE memory_id IN (
                SELECT memory_id FROM agent_memories
                WHERE user_id = ? ORDER BY approved_at DESC LIMIT -1 OFFSET ?
            )
            """,
            (user_id, self.max_per_user),
        )

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> PendingProposal:
        return PendingProposal(
            proposal_id=row["proposal_id"],
            user_id=row["user_id"],
            run_id=row["run_id"],
            originating_message=row["originating_message"],
            candidate=MemoryCandidate(
                category=row["category"],
                scope_key=row["scope_key"],
                fact=row["proposed_fact"],
                rationale=row["rationale"],
            ),
            proposed_at=row["proposed_at"],
        )

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            user_id=row["user_id"],
            category=row["category"],
            scope_key=row["scope_key"],
            fact=row["fact"],
            approved_at=row["approved_at"],
            expires_at=row["expires_at"],
        )
