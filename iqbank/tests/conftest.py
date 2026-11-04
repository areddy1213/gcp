from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from iqbank.config import Settings
from iqbank.llm import LLMResult
from iqbank.models import RawDoc
from iqbank.store import Store


class FakeLLM:
    """Stands in for ClaudeJSON. `responder(system, user, schema)` returns a dict, a str, or raises."""

    model = "fake-model"

    def __init__(self, responder: Callable[[str, str, dict[str, Any]], Any]):
        self.responder = responder
        self.calls: list[dict[str, Any]] = []

    def call(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 32_000) -> LLMResult:
        self.calls.append({"system": system, "user": user, "schema": schema})
        out = self.responder(system, user, schema)
        text = out if isinstance(out, str) else json.dumps(out)
        return LLMResult(text=text, model=self.model)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(db_path=tmp_path / "t.db", inbox_dir=tmp_path / "inbox", out_dir=tmp_path / "out")


@pytest.fixture
def store(settings: Settings):
    s = Store(settings.db_path)
    yield s
    s.close()


def add_doc(store: Store, url: str, text: str, source: str = "web", **meta: Any):
    store.upsert_doc(RawDoc(url=url, source=source, title=url.rsplit("/", 1)[-1], raw_text=text, meta=meta))
    return store.get_doc(url)
