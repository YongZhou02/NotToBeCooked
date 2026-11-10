import json

import pytest
from builder.merge_team_questions import Pdfs, main, merge

SOURCES = {
    "documents": [{"id": "d1", "path": "d1.pdf"}, {"id": "d2", "path": "d2.pdf"}]
}
PAGES = {"d1.pdf": ["page one text", "page two has the quote"], "d2.pdf": ["other doc"]}


def pdfs(reads=None):
    def reader(path):
        if reads is not None:
            reads.append(path.name)
        return PAGES[path.name]

    from pathlib import Path

    return Pdfs(Path("."), SOURCES, reader)


def original(row_id="t1-001", **extra):
    return {
        "id": row_id,
        "category": "definition",
        "split": "test",
        "generation_review": False,
        "question": f"Question {row_id}?",
        "reference_answer": "A",
        "required_facts": ["A"],
        "evidence_groups": [
            {
                "id": f"{row_id}-e1",
                "alternatives": [
                    {"document_id": "d1", "pdf_page": 1, "quote": "page one"}
                ],
            }
        ],
        **extra,
    }


def team(row_id="human-001", **extra):
    return {
        "id": row_id,
        "question": "How do I study?",
        "reference_answer": "Read.",
        "category": "explain",
        "evidence_groups": [
            {
                "alternatives": [
                    {"document_id": "d1", "pdf_page": 2, "quote": "the quote"}
                ]
            }
        ],
        **extra,
    }


def run(rows, files, reads=None):
    return merge(rows, files, pdfs(reads))


def test_new_row_gets_prefixed_id_defaults_and_group_ids():
    rows, report = run([original()], [("aisha", {"questions": [team()]})])
    new = rows[-1]
    assert new["id"] == "aisha-human-001"
    assert (new["origin"], new["split"], new["author"], new["verified"]) == (
        "human",
        "test",
        "aisha",
        False,
    )
    assert new["generation_review"] is True
    assert new["label_review"] == {"status": "team", "strict_retrieval_eligible": True}
    assert new["evidence_groups"][0]["id"] == "aisha-human-001-e1"
    assert new["required_facts"] == ["Read."]
    assert report["team_files"][0]["added"] == 1 and not report["skipped"]


def test_same_local_id_from_two_people_does_not_clash():
    rows, _ = run([], [("a", [team()]), ("b", [team()])])
    assert [r["id"] for r in rows] == ["a-human-001", "b-human-001"]


def test_already_prefixed_id_is_kept():
    rows, _ = run([], [("a", [team("a-human-001")])])
    assert rows[0]["id"] == "a-human-001"


def test_edit_replaces_original_and_is_listed():
    edit = team("t1-001", question="Reworded?", verified=True)
    rows, report = run([original()], [("aisha", [edit])])
    assert len(rows) == 1 and rows[0]["question"] == "Reworded?"
    assert rows[0]["verified"] is True and rows[0]["edited_by"] == "aisha"
    assert report["edited_originals"][0]["id"] == "t1-001"
    assert "question" in report["edited_originals"][0]["fields"]


def test_edit_with_no_change_is_not_an_edit():
    same = {**original(), "verified": False}
    rows, report = run([original()], [("a", [same])])
    assert rows[0]["question"] == "Question t1-001?"
    assert report["edited_originals"] == [] and report["unchanged_edits"] == 1


def test_two_people_editing_same_original_is_a_conflict():
    rows, report = run(
        [original()],
        [
            ("a", [team("t1-001", question="One?")]),
            ("b", [team("t1-001", question="Two?")]),
        ],
    )
    assert rows[0]["question"] == "Question t1-001?"
    assert report["conflicts"] == [
        {"id": "t1-001", "authors": ["a", "b"], "kept": "original"}
    ]
    assert report["edited_originals"] == []


def test_unanswerable_needs_no_evidence_but_keeps_explicit_answerable():
    unanswerable = team("u", category="unanswerable", evidence_groups=[])
    rows, report = run(
        [], [("a", [unanswerable, team("v", answerable=True, evidence_groups=[])])]
    )
    assert rows[0]["answerable"] is False and rows[0]["evidence_groups"] == []
    assert len(rows) == 1
    assert "needs at least one evidence group" in report["skipped"][0]["reason"]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"question": " "}, "missing question"),
        ({"reference_answer": None}, "missing reference_answer"),
        ({"split": "train"}, "split"),
        (
            {
                "evidence_groups": [
                    {
                        "alternatives": [
                            {"document_id": "zz", "pdf_page": 1, "quote": "x"}
                        ]
                    }
                ]
            },
            "not in sources.json",
        ),
        (
            {
                "evidence_groups": [
                    {
                        "alternatives": [
                            {"document_id": "d1", "pdf_page": 9, "quote": "x"}
                        ]
                    }
                ]
            },
            "no page 9",
        ),
        (
            {
                "evidence_groups": [
                    {
                        "alternatives": [
                            {"document_id": "d1", "pdf_page": 1, "quote": "the quote"}
                        ]
                    }
                ]
            },
            "quote not found on d1 page 1",
        ),
        ({"evidence_groups": [{"alternatives": []}]}, "no alternatives"),
    ],
)
def test_bad_rows_are_skipped_with_a_reason(change, reason):
    rows, report = run([], [("a", [team(**change)])])
    assert rows == []
    assert reason in report["skipped"][0]["reason"]
    assert report["skipped"][0]["id"] == "a-human-001"


def test_quote_match_ignores_case_and_spacing():
    rows, _ = run([], [("a", [team()])])
    assert len(rows) == 1  # "page two has the quote" contains "the quote"
    quote = "PAGE two  HAS the quote"
    ok = team(
        evidence_groups=[
            {"alternatives": [{"document_id": "d1", "pdf_page": 2, "quote": quote}]}
        ]
    )
    assert len(run([], [("a", [ok])])[0]) == 1


def test_file_level_problems_are_reported_not_dropped():
    rows, report = run(
        [],
        [
            ("bad", {"oops": 1}),
            ("worse", "unreadable JSON: x"),
            ("c", [{"question": "no id"}]),
        ],
    )
    assert rows == []
    assert [s["file"] for s in report["skipped"]] == [
        "bad.json",
        "worse.json",
        "c.json",
    ]


def test_duplicate_id_in_one_file_and_duplicate_text_warning():
    rows, report = run([], [("a", [team(), team()]), ("b", [team()])])
    assert report["skipped"][0]["reason"] == "id appears twice in this file"
    assert report["warnings"] == [
        {"kind": "duplicate_question", "ids": ["a-human-001", "b-human-001"]}
    ]
    assert len(rows) == 2


def test_each_pdf_is_read_once():
    reads = []
    run([], [("a", [team("x"), team("y"), team("z")])], reads)
    assert reads == ["d1.pdf"]


def test_output_is_stable():
    files = [("a", [team("x"), team("y")]), ("b", [team("x")])]
    assert run([original()], files)[0] == run([original()], files)[0]


def make_corpus(tmp_path, bad_row=False):
    out = tmp_path / "all"
    (tmp_path / "topic1").mkdir(exist_ok=True)
    (tmp_path / "team").mkdir(exist_ok=True)
    out.mkdir(exist_ok=True)
    (tmp_path / "topic1/questions.jsonl").write_text(
        json.dumps(original()) + "\n", encoding="utf-8"
    )
    (out / "sources.json").write_text(json.dumps(SOURCES), encoding="utf-8")
    row = team(split="nope") if bad_row else team()
    (tmp_path / "team/aisha.json").write_text(
        json.dumps({"questions": [row]}), encoding="utf-8"
    )
    return out


def test_main_writes_files_and_strict_fails_on_skips(tmp_path, monkeypatch):
    import builder.merge_team_questions as module

    monkeypatch.setattr(module, "read_pdf_pages", lambda path: PAGES[path.name])
    out = make_corpus(tmp_path)
    monkeypatch.setattr("sys.argv", ["merge", "--corpus", str(tmp_path)])
    main()
    lines = (out / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["id"] for line in lines] == ["t1-001", "aisha-human-001"]
    assert (
        json.loads((out / "merge_report.json").read_text(encoding="utf-8"))["skipped"]
        == []
    )

    make_corpus(tmp_path, bad_row=True)
    monkeypatch.setattr("sys.argv", ["merge", "--corpus", str(tmp_path), "--strict"])
    with pytest.raises(SystemExit) as stop:
        main()
    assert stop.value.code == 1
