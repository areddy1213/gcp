"""Source interface: discover candidates cheaply, then fetch the ones we don't already have."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from iqbank.config import Settings
from iqbank.models import RawDoc

if TYPE_CHECKING:
    from iqbank.store import Store


@dataclass
class Candidate:
    url: str  # canonical URL: the store's key for this document
    title: str = ""
    data: Any = None  # source-specific payload handed from discover() to fetch()


class SkipDoc(Exception):
    """Deliberately not storing this candidate (robots.txt, irrelevant, empty, ...).

    remember=True records the URL so later runs don't refetch it (for skip_ttl_days).
    Use remember=False for reasons that can change between runs, like the blocklist.
    """

    def __init__(self, reason: str, *, remember: bool = True):
        super().__init__(reason)
        self.reason = reason
        self.remember = remember


class SourceUnavailable(Exception):
    """The whole source can't run right now (bad credentials, quota exhausted)."""


class Source(ABC):
    name: ClassVar[str]
    # False: skip candidates already in the store (network sources: never refetch).
    # True: always fetch and let the store keep only changed content (cheap local sources).
    refetch_known: ClassVar[bool] = False

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def check_config(self) -> str | None:
        """Return why this source can't run (missing credentials, ...), or None if it can."""

    @abstractmethod
    def plan(self, store: "Store") -> list[str]:
        """Human-readable description of what a real run would do. Must not touch the network."""

    @abstractmethod
    def discover(self) -> Iterator[Candidate]:
        """Yield candidates. May call search APIs but should not download documents."""

    @abstractmethod
    def fetch(self, candidate: Candidate) -> RawDoc:
        """Download and build the document, or raise SkipDoc."""
