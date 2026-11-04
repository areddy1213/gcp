from __future__ import annotations

import json

from iqbank.dedupe import (
    Item,
    count_sources,
    lexical_groups,
    majority,
    run_dedupe,
    similar,
    validate_clusters,
)
from iqbank.extract import parse_extraction
from iqbank.models import ROUND_TYPES

from .conftest import FakeLLM, add_doc


def test_validate_clusters_assigns_every_id_exactly_once():
    data = {
        "clusters": [
            {"canonical_question": "Merge intervals", "ids": [1, 2, 2, 99]},  # dup and unknown id
            {"canonical_question": "LRU cache", "ids": [2, 3]},  # 2 already taken
            {"canonical_question": "  ", "ids": ["4"]},  # string id, blank canonical
            {"canonical_question": "nothing valid", "ids": [100]},
            "garbage",
        ]
    }
    out = validate_clusters(data, [1, 2, 3, 4, 5])
    assert out == [("Merge intervals", [1, 2]), ("LRU cache", [3]), (None, [4]), (None, [5])]


def test_validate_clusters_handles_unusable_output():
    assert validate_clusters({"clusters": "nope"}, [1, 2]) == [(None, [1]), (None, [2])]
    assert validate_clusters(None, [7]) == [(None, [7])]


def test_majority_ignores_unknown_and_breaks_ties_deterministically():
    assert majority(["unknown", "coding", "unknown"], ignore=("unknown",), order=ROUND_TYPES) == "coding"
    assert majority(["unknown", "unknown"], ignore=("unknown",)) == "unknown"
    assert majority(["system_design", "coding"], order=ROUND_TYPES) == "coding"  # earlier in ROUND_TYPES


def test_similar_and_lexical_groups():
    assert similar("Design a rate limiter for an API", "Design an API rate limiter")
    assert not similar("Design a rate limiter", "Design a URL shortener")
    items = [
        Item(1, "Merge overlapping intervals"),
        Item(2, "merge overlapping intervals in a list"),
        Item(3, "Explain the TLS handshake"),
    ]
    groups = sorted(sorted(g) for g in lexical_groups(items))
    assert groups == [[1, 2], [3]]


def _extract_into(store, doc, questions):
    result = parse_extraction(json.dumps({"relevant": True, "questions": questions, "loop": None}), doc_url=doc.url)
    store.save_extraction(doc, model="fake", status="ok", questions=result.questions)


def _q(text, rt="coding", cat="intervals"):
    return {"question": text, "round_type": rt, "category": cat, "date_if_known": None, "source_url": "",
            "verbatim_or_paraphrased": "paraphrased", "role_if_known": None}


def test_source_counting_treats_copies_as_one_source(store, settings):
    a = add_doc(store, "https://a.example/post", "Glean onsite: merge intervals")
    b = add_doc(store, "https://b.example/mirror", "Glean onsite: merge intervals")  # identical text
    c = add_doc(store, "inbox://gd.md", "Source: https://c.example/review\nGlean: merge intervals", source="inbox",
                original_url="https://c.example/review")
    d = add_doc(store, "https://c.example/review", "Glean review page: merge intervals!")  # same as inbox origin
    e = add_doc(store, "https://e.example/blog", "Glean phone screen: merge overlapping intervals")
    for doc in (a, b, c, d, e):
        _extract_into(store, doc, [_q("Merge overlapping intervals")])
    rows = store.questions()
    assert count_sources(rows) == 3  # {a/b same text}, {c, d same origin}, {e}


def test_run_dedupe_with_claude_clusters_and_counts(store, settings):
    d1 = add_doc(store, "https://a.example/1", "Glean report one")
    d2 = add_doc(store, "https://b.example/2", "Glean report two")
    _extract_into(store, d1, [_q("Merge intervals"), _q("Design enterprise search with ACLs", "system_design", "search/ranking")])
    _extract_into(store, d2, [_q("merge intervals."), _q("Merge overlapping meeting intervals", "unknown"),
                              _q("Explain mTLS", "security_deep_dive", "TLS/mTLS")])

    seen_inputs = []

    def responder(system, user, schema):
        seen_inputs.append(user)
        ids = [int(line.split("]")[0].lstrip("[")) for line in user.splitlines()[1:]]
        texts = {int(line.split("]")[0].lstrip("[")): line for line in user.splitlines()[1:]}
        merge = [i for i in ids if "intervals" in texts[i].lower()]
        return {"clusters": [{"canonical_question": "Merge overlapping intervals", "ids": merge}]}  # rest omitted

    llm = FakeLLM(responder)
    stats = run_dedupe(store, llm, settings, method="claude")
    assert stats.questions == 5 and stats.clusters == 3
    # exact duplicates ("Merge intervals" / "merge intervals.") were collapsed before the call
    assert len(seen_inputs[0].splitlines()) - 1 == 4

    clusters = {c["canonical_question"]: c for c in store.clusters()}
    merged = clusters["Merge overlapping intervals"]
    assert (merged["round_type"], merged["source_count"], merged["mention_count"]) == ("coding", 2, 3)
    assert {"Design enterprise search with ACLs", "Explain mTLS"} <= set(clusters)
    assert store.stats()["unclustered_questions"] == 0

    # unchanged questions -> no new Claude call
    again = run_dedupe(store, llm, settings, method="claude")
    assert again.unchanged and len(llm.calls) == 1


def test_run_dedupe_batches_then_merges_across_batches(store, settings):
    settings.dedupe_batch_size = 2
    doc = add_doc(store, "https://a.example/1", "Glean")
    _extract_into(store, doc, [_q("Alpha problem one"), _q("Beta problem"), _q("Alpha problem two"), _q("Gamma problem")])

    def responder(system, user, schema):
        lines = user.splitlines()[1:]
        ids = [int(line.split("]")[0].lstrip("[")) for line in lines]
        alpha = [i for i, line in zip(ids, lines) if "Alpha" in line]
        return {"clusters": [{"canonical_question": "Alpha problem", "ids": alpha}] if alpha else []}

    stats = run_dedupe(store, FakeLLM(responder), settings, method="claude")
    names = sorted(c["canonical_question"] for c in store.clusters())
    assert stats.clusters == 3
    assert names == ["Alpha problem", "Beta problem", "Gamma problem"]


def test_run_dedupe_falls_back_to_lexical_when_a_batch_fails(store, settings):
    from iqbank.llm import LLMError

    doc = add_doc(store, "https://a.example/1", "Glean")
    _extract_into(store, doc, [_q("Merge overlapping intervals"), _q("merge overlapping intervals in a list")])

    def responder(system, user, schema):
        raise LLMError("boom")

    stats = run_dedupe(store, FakeLLM(responder), settings, method="claude")
    assert stats.clusters == 1


def test_run_dedupe_dry_run_writes_nothing(store, settings):
    doc = add_doc(store, "https://a.example/1", "Glean")
    _extract_into(store, doc, [_q("Merge intervals")])
    lines = []
    run_dedupe(store, None, settings, method="claude", dry_run=True, echo=lines.append)
    assert store.clusters() == [] and lines and "would dedupe 1 questions" in lines[0]
