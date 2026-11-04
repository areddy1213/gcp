"""Parsing and normalization of Claude's extraction output."""

from __future__ import annotations

import json

import pytest

from iqbank.extract import (
    EXTRACTION_SCHEMA,
    ExtractionParseError,
    merge_results,
    normalize_category,
    normalize_date,
    normalize_round_type,
    normalize_verbatim,
    parse_extraction,
    parse_loop,
    resolve_source_url,
    split_text,
)
from iqbank.models import ROUND_TYPES

DOC = "https://example.com/glean-interview"


def q(**overrides):
    item = {
        "question": "Merge overlapping intervals",
        "round_type": "coding",
        "category": "intervals",
        "date_if_known": "2024-03",
        "source_url": DOC,
        "verbatim_or_paraphrased": "paraphrased",
        "role_if_known": None,
    }
    item.update(overrides)
    return item


def payload(questions, relevant=True, loop=None):
    return json.dumps({"relevant": relevant, "questions": questions, "loop": loop})


# ---- whole-response parsing -------------------------------------------------------------


def test_clean_structured_output():
    r = parse_extraction(payload([q(), q(question="Design a permission-aware enterprise search index",
                                        round_type="system_design", category="search/ranking")]), doc_url=DOC)
    assert r.relevant
    assert [x.question for x in r.questions] == [
        "Merge overlapping intervals",
        "Design a permission-aware enterprise search index",
    ]
    first = r.questions[0]
    assert (first.round_type, first.category, first.date_if_known, first.source_url) == (
        "coding", "intervals", "2024-03", DOC,
    )
    assert first.verbatim_or_paraphrased == "paraphrased"
    assert r.dropped == 0


def test_json_inside_code_fence_with_prose():
    text = "Here is what I found:\n```json\n" + payload([q()]) + "\n```\nLet me know!"
    r = parse_extraction(text, doc_url=DOC)
    assert len(r.questions) == 1


def test_json_after_leading_prose_without_fence():
    r = parse_extraction("Sure. " + payload([q()]) + " Done.", doc_url=DOC)
    assert len(r.questions) == 1


def test_top_level_list_is_accepted():
    r = parse_extraction(json.dumps([q(), q(question="Implement an LRU cache")]), doc_url=DOC)
    assert r.relevant and len(r.questions) == 2 and r.loop is None


def test_single_question_object_is_accepted():
    r = parse_extraction(json.dumps(q()), doc_url=DOC)
    assert len(r.questions) == 1


def test_bare_string_items_become_questions_with_defaults():
    r = parse_extraction(json.dumps({"questions": ["How would you rotate mTLS certificates at scale?"]}), doc_url=DOC)
    (only,) = r.questions
    assert only.round_type == "unknown"
    assert only.category == "other"
    assert only.source_url == DOC
    assert only.verbatim_or_paraphrased == "paraphrased"


@pytest.mark.parametrize("text", ["", "   ", "no json here", "{not valid json"])
def test_unreadable_output_raises(text):
    with pytest.raises(ExtractionParseError):
        parse_extraction(text, doc_url=DOC)


def test_truncated_json_raises():
    full = payload([q(), q(question="Implement an LRU cache")])
    with pytest.raises(ExtractionParseError):
        parse_extraction(full[: len(full) // 2], doc_url=DOC)


def test_questions_not_a_list_raises():
    with pytest.raises(ExtractionParseError):
        parse_extraction(json.dumps({"questions": "Merge intervals"}), doc_url=DOC)


def test_scalar_json_raises():
    with pytest.raises(ExtractionParseError):
        parse_extraction("42", doc_url=DOC)


def test_bad_items_are_dropped_not_fatal():
    items = [q(), {"question": ""}, {"question": "ok?"}, 17, None, {"round_type": "coding"}, q(question="Two sum")]
    r = parse_extraction(payload(items), doc_url=DOC)
    assert [x.question for x in r.questions] == ["Merge overlapping intervals", "Two sum"]
    assert r.dropped == 5


def test_duplicates_within_a_doc_collapse():
    items = [q(), q(question="  merge overlapping   intervals. "), q(question="Merge Overlapping Intervals!")]
    r = parse_extraction(payload(items), doc_url=DOC)
    assert len(r.questions) == 1


def test_irrelevant_doc_returns_no_questions_even_if_listed():
    r = parse_extraction(payload([q()], relevant=False), doc_url=DOC)
    assert not r.relevant and r.questions == [] and r.loop is None


def test_relevant_defaults_from_questions_when_missing():
    assert parse_extraction(json.dumps({"questions": [q()]}), doc_url=DOC).relevant is True
    assert parse_extraction(json.dumps({"questions": []}), doc_url=DOC).relevant is False


def test_relevant_as_string():
    assert parse_extraction(json.dumps({"relevant": "false", "questions": [q()]}), doc_url=DOC).questions == []


def test_question_text_cleanup():
    items = [
        q(question="1. Implement a rate limiter"),
        q(question="Q2: Design a webhook delivery system"),
        q(question='"Explain the TLS 1.3 handshake"'),
        q(question="- Find the kth largest element"),
        q(question="Question: how do you store refresh tokens?"),
    ]
    r = parse_extraction(payload(items), doc_url=DOC)
    assert [x.question for x in r.questions] == [
        "Implement a rate limiter",
        "Design a webhook delivery system",
        "Explain the TLS 1.3 handshake",
        "Find the kth largest element",
        "how do you store refresh tokens?",
    ]


def test_alternate_field_names_are_tolerated():
    r = parse_extraction(
        json.dumps({"questions": [{"text": "Design a URL shortener", "round": "Systems Design", "topic": "API",
                                   "date": "Jan 2025", "role": "Software Engineer"}]}),
        doc_url=DOC,
    )
    (only,) = r.questions
    assert (only.round_type, only.category, only.date_if_known, only.role_if_known) == (
        "system_design", "api design", "2025-01", "Software Engineer",
    )


# ---- field normalizers ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("coding", "coding"),
        ("phone_screen", "phone_screen"),
        ("Phone Screen", "phone_screen"),
        ("phone-screen", "phone_screen"),
        ("Technical phone interview", "phone_screen"),
        ("tech screen", "phone_screen"),
        ("Recruiter call", "phone_screen"),
        ("Onsite - Coding", "coding"),
        ("Onsite #2: coding round", "coding"),
        ("OA", "coding"),
        ("Live coding (CoderPad)", "coding"),
        ("System Design", "system_design"),
        ("Architecture round", "system_design"),
        ("Security design", "security_deep_dive"),
        ("Threat modeling", "security_deep_dive"),
        ("security_deep_dive", "security_deep_dive"),
        ("Behavioural", "behavioral"),
        ("Culture fit", "behavioral"),
        ("AI exercise", "ai_exercise"),
        ("LLM round", "ai_exercise"),
        ("HM", "hiring_manager"),
        ("Hiring Manager chat", "hiring_manager"),
        ("n/a", "unknown"),
        ("", "unknown"),
        ("lunch", "unknown"),
        (None, "unknown"),
        (3, "unknown"),
    ],
)
def test_normalize_round_type(raw, expected):
    assert normalize_round_type(raw) == expected


def test_every_round_type_maps_to_itself():
    for rt in ROUND_TYPES:
        assert normalize_round_type(rt) == rt


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("graphs", "graphs"),
        ("Graph", "graphs"),
        ("BFS", "graphs"),
        ("Intervals", "intervals"),
        ("authn/authz", "authn/authz"),
        ("OAuth", "authn/authz"),
        ("Authorization", "authn/authz"),
        ("mTLS", "TLS/mTLS"),
        ("TLS", "TLS/mTLS"),
        ("Kubernetes security", "k8s security"),
        ("K8s", "k8s security"),
        ("search", "search/ranking"),
        ("RAG", "LLM/RAG"),
        ("Distributed Systems", "distributed systems"),
        ("graphs, BFS", "graphs"),
        ("bfs and dfs", "graphs"),
        ("Supply chain security", "supply chain security"),
        ("", "other"),
        (None, "other"),
    ],
)
def test_normalize_category(raw, expected):
    assert normalize_category(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("verbatim", "verbatim"),
        ("Verbatim", "verbatim"),
        ("exact quote", "verbatim"),
        ("paraphrased", "paraphrased"),
        ("Paraphrase", "paraphrased"),
        ("", "paraphrased"),
        (None, "paraphrased"),
        (True, "verbatim"),
        (False, "paraphrased"),
    ],
)
def test_normalize_verbatim(raw, expected):
    assert normalize_verbatim(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2024-03-15", "2024-03-15"),
        ("2024-3-5", "2024-03-05"),
        ("2024/03/15", "2024-03-15"),
        ("2024-03", "2024-03"),
        ("2024", "2024"),
        (2024, "2024"),
        ("2024-03-15T10:22:00Z", "2024-03-15"),
        ("March 2024", "2024-03"),
        ("Mar 2024", "2024-03"),
        ("March 15, 2024", "2024-03-15"),
        ("15th March 2024", "2024-03-15"),
        ("Sept. 2023", "2023-09"),
        ("Q1 2024", "2024-Q1"),
        ("2024 q3", "2024-Q3"),
        ("early 2024", "early 2024"),
        ("unknown", None),
        ("N/A", None),
        ("", None),
        (None, None),
        ("last week", None),
        ("1850", None),
    ],
)
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


def test_source_url_invented_by_model_falls_back_to_doc_url():
    assert resolve_source_url("https://leetcode.com/problems/merge-intervals/", DOC) == DOC
    assert resolve_source_url("", DOC) == DOC
    assert resolve_source_url(None, DOC) == DOC


def test_source_url_declared_by_inbox_file_is_kept():
    original = "https://www.glassdoor.com/Interview/Glean-Interview-Questions-E123.htm"
    doc_url = "inbox://glassdoor-1.md"
    assert resolve_source_url(original + "?utm_source=x", doc_url, (original,)) == original
    r = parse_extraction(payload([q(source_url=original)]), doc_url=doc_url, alt_urls=(original,))
    assert r.questions[0].source_url == original


# ---- interview loop ---------------------------------------------------------------------------


def test_loop_parsing_normalizes_rounds():
    loop = {
        "reported": True,
        "role": "Security Engineer",
        "interview_date": "Feb 2025",
        "total_rounds": "5",
        "rounds": [
            {"round_type": "phone_screen", "name": "Tech screen", "format": "CoderPad", "duration_minutes": 45,
             "notes": None},
            {"round_type": "Security", "name": "Security deep dive", "format": None, "duration_minutes": "1 hour",
             "notes": ""},
            "Hiring manager",
        ],
        "timeline": "Recruiter call to offer in about 3 weeks",
    }
    r = parse_extraction(payload([q()], loop=loop), doc_url=DOC)
    lp = r.loop
    assert lp is not None and lp.reported
    assert (lp.role, lp.interview_date, lp.total_rounds) == ("Security Engineer", "2025-02", 5)
    assert [(x.round_type, x.duration_minutes) for x in lp.rounds] == [
        ("phone_screen", 45), ("security_deep_dive", 60), ("hiring_manager", None),
    ]
    assert lp.rounds[1].notes is None
    assert lp.round_count == 5


def test_loop_not_reported_is_none():
    empty = {"reported": False, "role": None, "interview_date": None, "total_rounds": None, "rounds": [],
             "timeline": None}
    assert parse_extraction(payload([q()], loop=empty), doc_url=DOC).loop is None
    assert parse_loop(None) is None
    assert parse_loop("five rounds") is None


def test_loop_with_content_but_reported_false_is_kept():
    lp = parse_loop({"reported": False, "rounds": [{"name": "System design", "round_type": "system_design"}]})
    assert lp is not None and lp.reported and lp.round_count == 1


@pytest.mark.parametrize("value,expected", [(0, None), (-1, None), (99, None), ("four", None), (True, None), (4.0, 4)])
def test_loop_total_rounds_sanity(value, expected):
    assert parse_loop({"reported": True, "total_rounds": value}).total_rounds == expected


# ---- chunking & merging -------------------------------------------------------------------------


def test_split_text_never_drops_content():
    paras = [f"paragraph {i} " + "x" * 50 for i in range(40)]
    text = "\n\n".join(paras)
    chunks = split_text(text, 300)
    assert all(len(c) <= 300 for c in chunks)
    assert "\n\n".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_split_text_hard_splits_a_single_huge_line():
    text = "y" * 1000
    chunks = split_text(text, 300)
    assert "".join(chunks) == text and all(len(c) <= 300 for c in chunks)


def test_split_text_short_text_is_one_chunk():
    assert split_text("short", 300) == ["short"]


def test_merge_results_dedupes_across_chunks_and_keeps_richest_loop():
    a = parse_extraction(payload([q()], loop={"reported": True, "rounds": [{"name": "Coding"}]}), doc_url=DOC)
    b = parse_extraction(
        payload([q(question="merge overlapping intervals"), q(question="Implement an LRU cache")],
                loop={"reported": True, "rounds": [{"name": "Coding"}, {"name": "System design"}]}),
        doc_url=DOC,
    )
    merged = merge_results([a, b])
    assert [x.question for x in merged.questions] == ["Merge overlapping intervals", "Implement an LRU cache"]
    assert len(merged.loop.rounds) == 2


# ---- schema sanity -------------------------------------------------------------------------------


def test_schema_objects_disallow_additional_properties_and_require_all_fields():
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(EXTRACTION_SCHEMA)
    rt_enum = EXTRACTION_SCHEMA["properties"]["questions"]["items"]["properties"]["round_type"]["enum"]
    assert rt_enum == list(ROUND_TYPES)
