"""Plain data records shared by the sources, the store, extraction, dedupe and reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ROUND_TYPES: tuple[str, ...] = (
    "phone_screen",
    "coding",
    "system_design",
    "security_deep_dive",
    "behavioral",
    "ai_exercise",
    "hiring_manager",
    "unknown",
)

VERBATIM_VALUES: tuple[str, ...] = ("verbatim", "paraphrased")


@dataclass
class RawDoc:
    """A document as produced by a source, before it is stored."""

    url: str
    source: str  # reddit | web | github | inbox
    title: str
    raw_text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Doc:
    """A stored document."""

    id: int
    url: str
    source: str
    title: str
    fetched_at: str
    raw_text: str
    content_hash: str
    meta: dict[str, Any]

    @property
    def original_url(self) -> str | None:
        return self.meta.get("original_url")


@dataclass
class Question:
    question: str
    round_type: str
    category: str
    date_if_known: str | None
    source_url: str
    verbatim_or_paraphrased: str
    role_if_known: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LoopRound:
    round_type: str
    name: str
    format: str | None = None
    duration_minutes: int | None = None
    notes: str | None = None


@dataclass
class LoopInfo:
    """What one source says about the interview process."""

    reported: bool
    role: str | None = None
    interview_date: str | None = None
    total_rounds: int | None = None
    rounds: list[LoopRound] = field(default_factory=list)
    timeline: str | None = None

    @property
    def round_count(self) -> int | None:
        if self.total_rounds:
            return self.total_rounds
        return len(self.rounds) or None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopInfo":
        rounds = [LoopRound(**r) for r in data.get("rounds", [])]
        return cls(
            reported=bool(data.get("reported")),
            role=data.get("role"),
            interview_date=data.get("interview_date"),
            total_rounds=data.get("total_rounds"),
            rounds=rounds,
            timeline=data.get("timeline"),
        )


@dataclass
class ExtractionResult:
    relevant: bool
    questions: list[Question] = field(default_factory=list)
    loop: LoopInfo | None = None
    dropped: int = 0  # items the model returned that failed validation


@dataclass
class QuestionRow:
    """A stored question joined with the document it came from."""

    id: int
    doc_id: int
    question: str
    round_type: str
    category: str
    date_if_known: str | None
    source_url: str
    verbatim_or_paraphrased: str
    role_if_known: str | None
    cluster_id: int | None
    doc_url: str
    doc_source: str
    doc_content_hash: str
    doc_meta: dict[str, Any]

    @property
    def independence_key(self) -> str:
        """Two rows with the same key come from the same underlying source."""
        return self.doc_meta.get("original_url") or self.doc_url


@dataclass
class ClusterRecord:
    canonical_question: str
    round_type: str
    category: str
    member_ids: list[int]
    source_count: int
    mention_count: int
