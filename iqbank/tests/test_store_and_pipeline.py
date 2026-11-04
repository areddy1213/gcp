"""Incremental storage and the extract pipeline, with a fake model."""

from __future__ import annotations

import pytest

from iqbank.extract import extract_pending
from iqbank.llm import FatalLLMError, LLMRefusal
from iqbank.models import RawDoc
from iqbank.store import Store

from .conftest import FakeLLM, add_doc


def ok_response(*questions, loop=None):
    return {
        "relevant": True,
        "questions": [
            {"question": t, "round_type": "coding", "category": "graphs", "date_if_known": None,
             "source_url": "https://made.up/url", "verbatim_or_paraphrased": "paraphrased", "role_if_known": None}
            for t in questions
        ],
        "loop": loop or {"reported": False, "role": None, "interview_date": None, "total_rounds": None,
                         "rounds": [], "timeline": None},
    }


def test_upsert_is_incremental(store: Store):
    doc = RawDoc(url="https://x.example/a", source="web", title="a", raw_text="Glean v1")
    assert store.upsert_doc(doc) == "new"
    assert store.upsert_doc(doc) == "unchanged"
    doc.raw_text = "Glean v2"
    assert store.upsert_doc(doc) == "updated"
    assert store.get_doc(doc.url).raw_text == "Glean v2"


def test_skipped_urls_expire(store: Store):
    store.mark_skipped("https://x.example/robots", "web", "disallowed by robots.txt")
    assert store.is_skipped("https://x.example/robots", ttl_days=30)
    assert not store.is_skipped("https://x.example/robots", ttl_days=0)
    assert not store.is_skipped("https://x.example/other")


def test_readonly_store_without_db_file_writes_nothing(tmp_path):
    path = tmp_path / "missing.db"
    with Store(path, readonly=True) as s:
        assert s.stats()["questions"] == 0
    assert not path.exists()


def test_extract_pending_end_to_end_and_incremental(store, settings):
    d1 = add_doc(store, "https://a.example/1", "Glean onsite: course schedule with topological sort")
    add_doc(store, "https://a.example/2", "I like to glean insights from books")  # mentions "glean" as a verb
    add_doc(store, "https://a.example/3", "Nothing about the company at all")  # prefiltered, no call
    add_doc(store, "inbox://pasted.md", "Onsite: number of islands", source="inbox")  # inbox skips prefilter

    def responder(system, user, schema):
        if "a.example/2" in user:
            return {"relevant": False, "questions": [], "loop": ok_response()["loop"]}
        if "a.example/1" in user:
            return ok_response("Course schedule (topological sort)", loop={
                "reported": True, "role": None, "interview_date": None, "total_rounds": 4,
                "rounds": [], "timeline": "3 weeks"})
        return ok_response("Number of islands")

    llm = FakeLLM(responder)
    stats = extract_pending(store, llm, settings)
    assert (stats.pending, stats.ok, stats.irrelevant, stats.questions) == (4, 2, 2, 2)
    assert len(llm.calls) == 3  # doc 3 never reached the model
    assert "Glean" in llm.calls[0]["system"] and "untrusted" in llm.calls[0]["system"]

    qs = {q.question: q for q in store.questions()}
    assert set(qs) == {"Course schedule (topological sort)", "Number of islands"}
    assert qs["Course schedule (topological sort)"].source_url == d1.url  # invented URL replaced
    loops = store.loops()
    assert len(loops) == 1 and loops[0][1].total_rounds == 4

    # second run: nothing pending, no calls
    again = extract_pending(store, llm, settings)
    assert again.pending == 0 and len(llm.calls) == 3

    # changing a doc makes only that doc pending again, and replaces its questions
    store.upsert_doc(RawDoc(url=d1.url, source="web", title="1", raw_text="Glean onsite: alien dictionary"))
    llm2 = FakeLLM(lambda s, u, sc: ok_response("Alien dictionary"))
    extract_pending(store, llm2, settings)
    assert len(llm2.calls) == 1
    assert {q.question for q in store.questions()} == {"Alien dictionary", "Number of islands"}


def test_refusals_and_errors_are_recorded(store, settings):
    add_doc(store, "https://a.example/refused", "Glean security round")
    add_doc(store, "https://a.example/garbled", "Glean coding round")

    def responder(system, user, schema):
        if "refused" in user:
            raise LLMRefusal("cyber")
        return "this is not json"

    stats = extract_pending(store, FakeLLM(responder), settings)
    assert (stats.refused, stats.errors) == (1, 1)
    pending = [d.url for d in store.docs_pending_extraction()]
    assert pending == ["https://a.example/garbled"]  # errors retry next run; refusals need --reextract
    assert len(store.docs_pending_extraction(reextract=True)) == 2


def test_fatal_errors_stop_the_run(store, settings):
    add_doc(store, "https://a.example/1", "Glean")

    def responder(system, user, schema):
        raise FatalLLMError("bad key")

    with pytest.raises(FatalLLMError):
        extract_pending(store, FakeLLM(responder), settings)


def test_long_docs_are_chunked_not_truncated(store, settings):
    settings.max_chunk_chars = 200
    text = "\n\n".join(f"Glean paragraph {i}: " + "z" * 80 for i in range(10))
    add_doc(store, "https://a.example/long", text)
    llm = FakeLLM(lambda s, u, sc: ok_response("Same question every chunk"))
    extract_pending(store, llm, settings)
    assert len(llm.calls) > 1
    assert all("<part>" in c["user"] for c in llm.calls)
    sent = "".join(c["user"] for c in llm.calls)
    for i in range(10):
        assert f"Glean paragraph {i}:" in sent
    assert len(store.questions()) == 1  # merged across chunks


def test_dry_run_makes_no_calls(store, settings):
    add_doc(store, "https://a.example/1", "Glean")
    out = []
    stats = extract_pending(store, None, settings, dry_run=True, echo=out.append)
    assert stats.pending == 1 and "would extract 1 document" in out[0]
    assert store.docs_pending_extraction()  # still pending


def test_inbox_doc_with_original_url_is_cited_by_that_url(store, settings):
    original = "https://www.teamblind.com/post/glean-xyz"
    add_doc(store, "inbox://blind.txt", f"{original}\nGlean onsite: merge intervals", source="inbox",
            original_url=original)
    extract_pending(store, FakeLLM(lambda s, u, sc: ok_response("Merge intervals", "LRU cache")), settings)
    assert {q.source_url for q in store.questions()} == {original}
