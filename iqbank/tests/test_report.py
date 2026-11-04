from __future__ import annotations

import csv
import json

from iqbank.dedupe import run_dedupe
from iqbank.extract import parse_extraction
from iqbank.models import LoopInfo, LoopRound
from iqbank.report import CSV_COLUMNS, generate_report, loop_stats, md

from .conftest import FakeLLM, add_doc


def _save(store, doc, questions, loop=None):
    items = [
        {"question": t, "round_type": rt, "category": cat, "date_if_known": date, "source_url": "",
         "verbatim_or_paraphrased": vb, "role_if_known": None}
        for t, rt, cat, date, vb in questions
    ]
    r = parse_extraction(json.dumps({"relevant": True, "questions": items, "loop": loop}),
                         doc_url=doc.url, alt_urls=tuple(u for u in (doc.original_url,) if u))
    store.save_extraction(doc, model="fake", status="ok", questions=r.questions, loop=r.loop)


def test_report_groups_by_round_and_sorts_by_frequency(store, settings, tmp_path):
    loop = {"reported": True, "role": "Software Engineer", "interview_date": "2024-05", "total_rounds": 5,
            "rounds": [{"round_type": "coding", "name": "Coding", "format": "CoderPad", "duration_minutes": 60,
                        "notes": None}],
            "timeline": "about 4 weeks end to end"}
    a = add_doc(store, "https://www.reddit.com/comments/abc/", "Glean", source="reddit", subreddit="cscareerquestions")
    b = add_doc(store, "https://blog.example/glean", "Glean blog")
    c = add_doc(store, "inbox://glassdoor/one.md", "Glean pasted", source="inbox")
    _save(store, a, [("Merge intervals", "coding", "intervals", "2024-05", "paraphrased"),
                     ("Design a permission-aware search index", "system_design", "search/ranking", None, "verbatim")],
          loop=loop)
    _save(store, b, [("merge intervals", "coding", "intervals", "2025-01", "paraphrased"),
                     ("Number of islands", "coding", "graphs", None, "paraphrased")])
    _save(store, c, [("Merge intervals", "coding", "intervals", None, "paraphrased"),
                     ("Tell me about a conflict", "behavioral", "behavioral", None, "paraphrased")])
    run_dedupe(store, None, settings, method="lexical")

    llm = FakeLLM(lambda s, u, sc: {"summary_markdown": "Most candidates report five rounds [1]."})
    out = tmp_path / "out"
    paths = generate_report(store, settings, llm, out)
    assert [p.name for p in paths] == ["questions.csv", "questions.md", "loop_summary.md"]

    rows = list(csv.DictReader(open(out / "questions.csv", encoding="utf-8")))
    assert list(rows[0].keys()) == CSV_COLUMNS
    assert [(r["round_type"], r["rank"], r["question"], r["source_count"]) for r in rows] == [
        ("coding", "1", "Merge intervals", "3"),
        ("coding", "2", "Number of islands", "1"),
        ("system_design", "1", "Design a permission-aware search index", "1"),
        ("behavioral", "1", "Tell me about a conflict", "1"),
    ]
    assert rows[0]["first_reported"] == "2024-05" and rows[0]["last_reported"] == "2025-01"
    assert rows[2]["verbatim"] == "yes"

    text = (out / "questions.md").read_text()
    assert text.index("## Coding") < text.index("## System design") < text.index("## Behavioral")
    assert "[r/cscareerquestions](https://www.reddit.com/comments/abc/)" in text
    assert "[inbox: glassdoor/one.md](../inbox/glassdoor/one.md)" in text
    assert "Based on **1** reported experience" in text
    assert "Most candidates report five rounds [1]." in text
    assert "about 4 weeks end to end" in (out / "loop_summary.md").read_text()

    # the narrative is cached: a second report makes no new Claude call
    generate_report(store, settings, llm, out)
    assert len(llm.calls) == 1


def test_report_without_dedupe_falls_back_to_lexical(store, settings, tmp_path):
    a = add_doc(store, "https://a.example/1", "Glean one")
    b = add_doc(store, "https://b.example/2", "Glean two")
    _save(store, a, [("Merge intervals", "coding", "intervals", None, "paraphrased")])
    _save(store, b, [("Merge intervals!", "unknown", "intervals", None, "paraphrased")])
    generate_report(store, settings, None, tmp_path)
    rows = list(csv.DictReader(open(tmp_path / "questions.csv", encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["round_type"] == "coding" and rows[0]["mention_count"] == "2"


def test_loop_stats():
    loops = [
        (None, LoopInfo(reported=True, total_rounds=5, rounds=[LoopRound("coding", "c", "CoderPad", 60)])),
        (None, LoopInfo(reported=True, rounds=[LoopRound("coding", "c", None, 45), LoopRound("system_design", "sd")])),
        (None, LoopInfo(reported=True, timeline="2 weeks")),
    ]
    st = loop_stats(loops)
    assert st["experiences"] == 3
    assert st["round_counts"] == [5, 2] and st["median_rounds"] == 3.5
    assert st["per_type"]["coding"]["experiences"] == 2
    assert sorted(st["per_type"]["coding"]["durations"]) == [45, 60]


def test_md_escaping():
    assert md("a_b*c <script> [x](y) |") == r"a\_b\*c \<script\> \[x\](y) \|"
