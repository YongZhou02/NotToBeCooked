import pytest
from scorers import concerns as c

ORDER = [
    "blocked_answers",
    "wrong_answers",
    "mechanical_answers",
    "real_wording",
    "unanswerable",
    "weak_citations",
    "lost_content",
    "bad_metadata",
    "wrong_document",
    "slow_answers",
    "metric_trust",
    "follow_ups",
    "clean_pdfs",
    "filtered_search",
]
ITEM_KEYS = {
    "id",
    "title",
    "feels_like",
    "status",
    "severity",
    "headline",
    "metrics",
    "examples",
    "how_measured",
}


def chunk(
    n, doc="d1", page=1, content="alpha beta gamma delta epsilon zeta", heading=None
):
    return {
        "chunk_id": f"c{n}",
        "document_id": doc,
        "page_start": page,
        "page_end": page,
        "content": content,
        "heading": heading,
        "rank": n,
        "filename": f"{doc}.pdf",
    }


def question(qid="q1", **extra):
    return {
        "id": qid,
        "question": "What is alpha?",
        "reference_answer": "Alpha is first.",
        "required_facts": ["Alpha is first."],
        "category": "definition",
        "split": "test",
        "answerable": True,
        "evidence_groups": [
            {
                "id": f"{qid}-e1",
                "alternatives": [
                    {"document_id": "d1", "pdf_page": 1, "quote": "alpha beta"}
                ],
            }
        ],
        **extra,
    }


def row(qid="q1", method="hybrid_rrf", **extra):
    return {
        "question_id": qid,
        "question": "What is alpha?",
        "category": "definition",
        "split": "test",
        "method": method,
        "sources": [chunk(1), chunk(2, page=2, content="other text here")],
        "metrics": {"hit@5": 1.0, "evidence_recall@5": 1.0},
        **extra,
    }


def generated(qid="q1", ok=True, ms=2000, draft="Alpha is first [1].", **extra):
    answer = draft if ok else "An answer was written, but its citations..."
    return row(
        qid,
        generation_ms=ms,
        response={"answer": answer, "citations": [], "grounded": ok},
        generation_trace={
            "draft": {
                "answer": draft,
                "citations": [{"marker": 1, "quote": "alpha beta"}],
            },
            "grounding_ok": ok,
            "grounding_problems": []
            if ok
            else ["citation [1] is listed but never referred to in the answer"],
        },
        **extra,
    )


JUDGED = {"correct": 2, "supported": 2, "useful": 2, "refused": False, "note": "ok"}


def test_parse_judgement_strips_think_and_fences():
    text = '<think>hmm {"correct": 0}</think>\n```json\n{"correct": 2, "supported": "1", "useful": 1, "refused": "false", "note": "fine"}\n```'
    assert c.parse_judgement(text) == {
        "correct": 2,
        "supported": 1,
        "useful": 1,
        "refused": False,
        "note": "fine",
    }


@pytest.mark.parametrize(
    "text",
    [
        "",
        "no json",
        '{"correct": 3, "supported": 1, "useful": 1}',
        '{"correct": 1}',
        "[1, 2]",
        "{bad",
    ],
)
def test_parse_judgement_rejects_bad_replies(text):
    assert c.parse_judgement(text) is None


def test_judge_messages_carry_the_inputs():
    messages = c.judge_messages(question(), "ans", ["quote"])
    assert (
        "Alpha is first." in messages[1]["content"]
        and "quote" in messages[1]["content"]
    )
    assert messages[0]["role"] == "system"


def test_normalise_problem_removes_numbers_and_quotes():
    assert (
        c.normalise_problem(
            "citation [3] is listed but never referred to in the answer"
        )
        == "citation [n] is listed but never referred to in the answer"
    )
    assert (
        c.normalise_problem(
            "the quote on [2] does not appear in the source it points at (a.pdf): 'x y'"
        )
        == "the quote on [n] does not appear in the source it points at"
    )
    assert (
        c.normalise_problem("marker [7] is outside the 1..5 sources")
        == "marker [n] is outside the 1..N sources"
    )


def test_copy_ratio_and_markers():
    sources = ["one two three four five six"]
    assert c.copy_ratio("one two three four five six [1]", sources) == 1
    assert c.copy_ratio("one two three four five xx", sources) == 0.5
    assert c.copy_ratio("too short", sources) is None
    assert c.has_marker("see [2]") and not c.has_marker("see 【2】")


def test_percentile_and_rate_text():
    assert c.percentile([1, 2, 3, 4], 50) == 2.5
    assert c.percentile([], 50) is None
    assert "2/4 (50%)" in c.rate_text(2, 4) and "95% range" in c.rate_text(2, 4)


def test_severity_uses_one_table_and_unknown_when_missing():
    high, medium = c.THRESHOLDS["slow_answers"]
    assert c.severity("slow_answers", high) == "high"
    assert c.severity("slow_answers", medium) == "medium"
    assert c.severity("slow_answers", 0) == "low"
    assert c.severity("slow_answers", None) == "unknown"


def test_answer_state():
    assert c.answer_state(generated()) == "shown"
    assert c.answer_state(generated(ok=False)) == "blocked"
    failed = generated()
    failed["generation_trace"]["generation_error"] = "boom"
    assert c.answer_state(failed) == "failed"
    old = row(response={"answer": "An answer was written, but x", "citations": []})
    assert c.answer_state(old) == "blocked"  # old runs have no trace


def test_end_to_end_pass_rules():
    q = {"q1": question(), "u": question("u", answerable=False)}
    shown = c.answer_records(q, [generated("q1")], {"q1": JUDGED})[0]
    assert c.end_to_end_pass(shown) is True
    weak = c.answer_records(q, [generated("q1")], {"q1": {**JUDGED, "supported": 0}})[0]
    assert c.end_to_end_pass(weak) is False
    blocked = c.answer_records(q, [generated("q1", ok=False)], {"q1": JUDGED})[0]
    assert c.end_to_end_pass(blocked) is False
    refusal = c.answer_records(q, [generated("u")], {"u": {**JUDGED, "refused": True}})[
        0
    ]
    assert c.end_to_end_pass(refusal) is True
    assert c.end_to_end_pass(c.answer_records(q, [generated("q1")], {})[0]) is None


def test_blocked_answers_counts_reasons_and_good_drafts():
    q = {"q1": question(), "q2": question("q2")}
    rows = [generated("q1", ok=False), generated("q2", ok=False)]
    records = c.answer_records(q, rows, {"q1": JUDGED, "q2": {**JUDGED, "correct": 1}})
    result = c.blocked_answers(records)
    assert result["status"] == "measured" and result["severity"] == "high"
    labels = {m["label"]: m["value"] for m in result["metrics"]}
    assert (
        labels["Reason: citation [n] is listed but never referred to in the answer"]
        == "2 of 2 blocked"
    )
    assert labels["Drafts with no [n] marker in the text"].startswith("0/2")
    good = next(
        v
        for k, v in labels.items()
        if k.startswith("Blocked drafts that were fully correct")
    )
    assert good == "1 of 2 judged"
    assert all(
        "AI judge, not yet checked by a human" in k
        for k in labels
        if "fully correct" in k
    )


def test_blocked_without_judge_is_partly_measured():
    records = c.answer_records({"q1": question()}, [generated("q1", ok=False)], {})
    assert c.blocked_answers(records)["status"] == "partly_measured"
    assert c.wrong_answers(records)["status"] == "not_measured"


def test_unanswerable_without_rows_still_reports_false_refusals():
    records = c.answer_records(
        {"q1": question()}, [generated("q1", draft=c.REFUSAL)], {}
    )
    result = c.unanswerable(records)
    assert result["status"] == "partly_measured" and result["severity"] == "unknown"
    assert any(
        "refused anyway" in m["label"] and m["value"].startswith("1/1")
        for m in result["metrics"]
    )


def test_unanswerable_handled_with_judge():
    q = {"u": question("u", answerable=False, evidence_groups=[])}
    good = c.answer_records(q, [generated("u")], {"u": JUDGED})
    assert c.unanswerable(good)["severity"] == "low"
    bad = c.answer_records(q, [generated("u")], {"u": {**JUDGED, "correct": 0}})
    assert c.unanswerable(bad)["severity"] == "high"


def test_weak_citations_checks_gold_pages():
    q = {"q1": question()}
    on_page = c.answer_records(q, [generated("q1")], {})
    assert c.weak_citations(on_page)["severity"] == "low"
    off = generated("q1")
    off["sources"] = [chunk(1, page=2, content="alpha beta elsewhere")]
    result = c.weak_citations(c.answer_records(q, [off], {}))
    assert result["severity"] == "high" and result["examples"][0]["question_id"] == "q1"


def test_old_run_without_extra_fields_does_not_crash():
    bare = {
        "question_id": "q1",
        "question": "?",
        "category": "x",
        "split": "test",
        "method": "hybrid_rrf",
        "sources": [],
        "response": {"answer": "Fine.", "citations": []},
        "generation_ms": 100,
    }
    result = c.build_concerns("r", {"questions": {}, "rows": [bare]})
    assert [i["id"] for i in result["items"]] == ORDER


def test_real_wording_compares_clean_and_stress():
    q = {"q1": question(), "s1": question("s1", split="stress", category="typo")}
    weak = row(
        "s1",
        split="stress",
        category="typo",
        metrics={"hit@5": 0.0, "evidence_recall@5": 0.0},
    )
    result = c.real_wording([row("q1"), weak], [], q)
    assert result["status"] == "measured" and result["severity"] == "high"
    assert any(m["label"] == "Category typo, hybrid" for m in result["metrics"])
    assert c.real_wording([row("q1")], [], q)["status"] == "partly_measured"


def test_lost_content_and_bad_metadata():
    checks = {
        "extraction_evidence_coverage": 1.0,
        "chunk_evidence_coverage": 0.5,
        "required_evidence_groups": 2,
        "not_intact_in_any_chunk": ["q1-e1"],
        "pages": [{"document_id": "d1", "pdf_page": 3, "token_recall": 0.2}],
    }
    lost = c.lost_content(checks, {"q1": question()})
    assert lost["severity"] == "high" and lost["examples"][0]["question_id"] == "q1"
    assert c.lost_content(None, {})["status"] == "not_measured"
    chunks = [
        {**chunk(1, heading="Intro", content="x"), "chunk_index": 0, "token_count": 10},
        {**chunk(2, heading="Missing head"), "chunk_index": 1, "token_count": 100},
        {**chunk(3), "chunk_index": 2, "token_count": 100},
    ]
    pages = [{"document_id": "d1", "page_start": 1, "content": "The Intro is here"}]
    result = c.bad_metadata(chunks, pages)
    labels = {m["label"]: m["value"] for m in result["metrics"]}
    assert labels["Headings not on the chunk's pages"].startswith("1/2")
    assert labels["Chunks with no heading"].startswith("1/3")
    assert result["status"] == "measured"


def test_wrong_document_needs_two_pdfs_and_flags_topic3_swaps():
    q = {"q1": question()}
    assert c.wrong_document([row("q1")], q)["status"] == "not_measured"
    wrong = row("q1", sources=[chunk(1, doc="d2"), chunk(2, doc="d1")])
    result = c.wrong_document([wrong], q)
    assert result["status"] == "measured" and result["severity"] == "high"
    t3 = {
        "q1": question(
            evidence_groups=[
                {
                    "id": "g",
                    "alternatives": [
                        {
                            "document_id": "cpt316-topic3-student",
                            "pdf_page": 1,
                            "quote": "x",
                        }
                    ],
                }
            ]
        )
    }
    swap = row(
        "q1", sources=[chunk(1, doc="cpt316-topic3-updated"), chunk(2, doc="d1")]
    )
    metrics = {m["label"]: m["value"] for m in c.wrong_document([swap], t3)["metrics"]}
    assert metrics["Rank 1 from the other Topic 3 PDF"] == "1"


def test_slow_answers():
    records = c.answer_records(
        {}, [generated("a", ms=1000), generated("b", ms=30000)], {}
    )
    result = c.slow_answers(records)
    assert result["severity"] == "high" and "1/2" in result["metrics"][2]["value"]


def test_random_baseline_is_seeded_and_low():
    chunks = [chunk(n, content=f"filler {n}") for n in range(50)]
    chunks[7] = chunk(7, content="alpha beta here")
    one = c.random_retriever_baseline(chunks, [question()])
    assert one == c.random_retriever_baseline(chunks, [question()])
    assert 0.05 < one["hit@5"] < 0.2  # about 5 in 50
    assert c.random_retriever_baseline(chunks[:3], [question()]) is None


def test_metric_trust_reports_interval_controls_and_unit_value():
    q = {f"q{i}": question(f"q{i}") for i in range(4)}
    rows = [generated(f"q{i}") for i in range(4)]
    judged = {f"q{i}": JUDGED for i in range(4)}
    controls = [{"passed": True}, {"passed": False}]
    records = c.answer_records(q, rows, judged)
    result = c.metric_trust(records, q, [chunk(n) for n in range(6)], controls, set(q))
    labels = {m["label"]: m["value"] for m in result["metrics"]}
    assert labels["One question is worth"] == "25.0 points"
    assert "4/4" in next(
        v for k, v in labels.items() if k.startswith("End-to-end pass")
    )
    assert "1/2" in next(v for k, v in labels.items() if k.startswith("Judge control"))
    assert result["status"] == "measured"


def test_build_concerns_shape_and_unmeasured_items():
    q = {"q1": question()}
    result = c.build_concerns(
        "run-1",
        {
            "questions": q,
            "rows": [generated("q1")],
            "judgements": {"q1": JUDGED},
            "chunks": [],
            "pages": [],
            "checks": None,
        },
    )
    assert set(result) == {"run_id", "items"} and result["run_id"] == "run-1"
    assert [i["id"] for i in result["items"]] == ORDER
    for entry in result["items"]:
        assert set(entry) == ITEM_KEYS
        assert entry["status"] in {"measured", "partly_measured", "not_measured"}
        assert entry["severity"] in {"high", "medium", "low", "unknown"}
        for m in entry["metrics"]:
            assert set(m) == {"label", "value", "note"}
        for e in entry["examples"]:
            assert set(e) == {"question_id", "note"}
        if entry["status"] == "not_measured":
            assert entry["severity"] == "unknown"
    by_id = {i["id"]: i for i in result["items"]}
    assert all(
        by_id[k]["status"] == "not_measured"
        for k in ("follow_ups", "clean_pdfs", "filtered_search")
    )


def test_control_plan_is_half_true_half_other_and_stable():
    import run_concerns as rc

    q = {
        f"q{i}": {**question(f"q{i}"), "reference_answer": f"Answer {i}"}
        for i in range(6)
    }
    plan = rc.control_plan(q, set(q), 4)
    assert plan == rc.control_plan(q, set(q), 4)
    assert [p["kind"] for p in plan] == ["true_answer", "other_answer"] * 2
    assert all(
        p["from"] != p["question_id"] for p in plan if p["kind"] == "other_answer"
    )
    assert rc.control_plan(q, set(q), 0) == []


def test_judge_waits_on_429_then_parses(monkeypatch):
    import run_concerns as rc

    class Reply:
        def __init__(self, status, headers=None, body=None):
            self.status_code, self.headers, self.body = status, headers or {}, body

        def raise_for_status(self):
            assert self.status_code < 400

        def json(self):
            return {"choices": [{"message": {"content": self.body}}]}

    good = '{"correct": 1, "supported": 1, "useful": 1, "refused": false, "note": "x"}'
    replies = [Reply(429, {"retry-after": "500"}), Reply(200, body=good)]
    waits = []
    judge = rc.Judge.__new__(rc.Judge)
    judge.url, judge.headers, judge.calls = "u", {}, 0
    judge.client = type("C", (), {"post": lambda self, *a, **k: replies.pop(0)})()
    monkeypatch.setattr(rc.time, "sleep", waits.append)
    assert judge.ask([])["correct"] == 1
    assert waits == [60] and judge.calls == 2  # wait is capped at 60 s
