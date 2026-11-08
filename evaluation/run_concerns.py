"""Judge a finished run and write judgements.json and concerns.json beside it.

Run from the repository root:
uv run --project apps/api python evaluation/run_concerns.py [--run RUN_DIR] [--no-judge]
"""

import argparse
import hashlib
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "apps/api"))
sys.path.insert(0, str(EVALUATION))

import httpx
from scorers.concerns import JUDGE, build_concerns, judge_messages, parse_judgement
from scorers.retrieval import normalize

JUDGE_MODEL = "qwen/qwen3.8-27b"
DATASETS = EVALUATION / "datasets/cpt316"
LEDGER = Path(
    r"C:\Users\calvi\AppData\Local\Temp\claude\ecb0aa2ce4b2753f"
    r"\537c5a50-925e-4cb5-936e-71db48befdee\scratchpad\groq_ledger.txt"
)
MAX_RETRIES = 5
MAX_WAIT_SECONDS = 60


def read(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def latest_finished_run() -> Path:
    runs = sorted(
        (p for p in (EVALUATION / "runs").iterdir() if (p / "summary.json").exists()),
        key=lambda p: p.name,
    )
    if not runs:
        raise SystemExit("No finished run found in evaluation/runs")
    return runs[-1]


def load_questions(run: Path, config: dict) -> dict[str, dict]:
    """The run does not store its questions, so find the dataset that matches its hash."""
    wanted = config.get("dataset_hashes", {}).get("questions.jsonl")
    folders = [DATASETS / name for name in ("all", "topic1", "topic1_stress")]
    found: dict[str, dict] = {}
    exact = None
    for folder in folders:
        path = folder / "questions.jsonl"
        if not path.exists():
            continue
        if wanted and hashlib.sha256(path.read_bytes()).hexdigest() == wanted:
            exact = folder
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in rows:
            found.setdefault(row["id"], row)
    if exact:
        found = {
            row["id"]: row
            for row in map(
                json.loads,
                (exact / "questions.jsonl").read_text(encoding="utf-8").splitlines(),
            )
        }
    return {i: {**q, "answerable": q.get("answerable", True)} for i, q in found.items()}


def load_rows(run: Path) -> list[dict]:
    path = run / "results.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def quotes_of(question: dict) -> list[str]:
    return [
        g["alternatives"][0]["quote"]
        for g in question.get("evidence_groups", [])
        if g["alternatives"]
    ]


def control_plan(questions: dict, rows_ids: set[str], count: int) -> list[dict]:
    """Half the controls give the true answer, half another question's answer."""
    pool = sorted(
        i
        for i in rows_ids
        if i in questions
        and questions[i]["answerable"]
        and questions[i].get("evidence_groups")
    )
    if len(pool) < 2 or count < 1:
        return []
    rng = random.Random(37)
    chosen = rng.sample(pool, min(count, len(pool)))
    plan = []
    for n, qid in enumerate(chosen):
        if n % 2 == 0:
            plan.append(
                {
                    "id": f"true:{qid}",
                    "kind": "true_answer",
                    "question_id": qid,
                    "from": qid,
                }
            )
        else:
            own = normalize(questions[qid]["reference_answer"])
            others = [
                o for o in pool if normalize(questions[o]["reference_answer"]) != own
            ]
            plan.append(
                {
                    "id": f"other:{qid}",
                    "kind": "other_answer",
                    "question_id": qid,
                    "from": rng.choice(others),
                }
            )
    return plan


class Judge:
    def __init__(self) -> None:
        from app.core.config import settings

        key = settings.GROQ_API_KEY.get_secret_value()
        if not key:
            raise SystemExit(
                "GROQ_API_KEY is not set; use --no-judge to skip the judge"
            )
        self.url = settings.GROQ_API_BASE_URL.rstrip("/") + "/chat/completions"
        self.headers = {"Authorization": f"Bearer {key}"}
        self.client = httpx.Client(timeout=120)
        self.calls = 0

    def ask(self, messages: list[dict]) -> dict | None:
        """One judged answer, or None. Waits out 429 replies, at most MAX_RETRIES times."""
        body = {
            "model": JUDGE_MODEL,
            "temperature": 0,
            "messages": messages,
            "max_completion_tokens": 4096,
        }
        for attempt in range(MAX_RETRIES + 1):
            self.calls += 1
            response = self.client.post(self.url, headers=self.headers, json=body)
            if (response.status_code == 429 or response.status_code >= 500) and (
                attempt < MAX_RETRIES
            ):
                # 429 says how long to wait; a 5xx gets a short pause.
                wait = min(
                    float(response.headers.get("retry-after", 5)), MAX_WAIT_SECONDS
                )
                print(f"  got {response.status_code}, waiting {wait:.0f}s", flush=True)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return parse_judgement(response.json()["choices"][0]["message"]["content"])
        return None


def judge_run(run: Path, questions: dict, rows: list[dict], args) -> dict:
    saved = read(run / "judgements.json", {})
    state = {
        "run_id": run.name,
        "model": JUDGE_MODEL,
        "label": JUDGE,
        "answers": saved.get("answers", {}),
        "controls": saved.get("controls", []),
        "failed": [],
    }
    if args.no_judge:
        return state
    todo = [
        r
        for r in rows
        if "response" in r
        and r["question_id"] in questions
        and r["question_id"] not in state["answers"]
        and ((r.get("generation_trace") or {}).get("draft") or r["response"])
    ]
    done_controls = {c["id"] for c in state["controls"]}
    plan = [
        c
        for c in control_plan(
            questions, {r["question_id"] for r in rows}, args.controls
        )
        if c["id"] not in done_controls
    ]
    budget = max(0, args.max_judge_calls - len(plan))
    judge = Judge()
    try:
        for row in todo[:budget]:
            q = questions[row["question_id"]]
            draft = (row.get("generation_trace") or {}).get("draft") or row["response"]
            quotes = [c.get("quote", "") for c in draft.get("citations", [])]
            result = judge.ask(judge_messages(q, draft.get("answer", ""), quotes))
            if result is None:
                state["failed"].append(
                    {"question_id": q["id"], "reason": "reply was not valid judge JSON"}
                )
            else:
                state["answers"][q["id"]] = {**result, "method": row["method"]}
            write(run / "judgements.json", state)
            print(f"Judged {q['id']} ({judge.calls} calls)", flush=True)
        for control in plan[: max(0, args.max_judge_calls - judge.calls)]:
            q, source = questions[control["question_id"]], questions[control["from"]]
            result = judge.ask(
                judge_messages(q, source["reference_answer"], quotes_of(source))
            )
            if result is not None:
                expect_ok = control["kind"] == "true_answer"
                passed = result["correct"] >= 1 if expect_ok else result["correct"] == 0
                state["controls"].append(
                    {**control, "correct": result["correct"], "passed": passed}
                )
            write(run / "judgements.json", state)
            print(f"Control {control['id']} ({judge.calls} calls)", flush=True)
    except httpx.HTTPError as error:
        print(f"Stopped early: {error!r}", flush=True)
    finally:
        write(run / "judgements.json", state)
        if judge.calls:
            try:
                with LEDGER.open("a", encoding="utf-8") as handle:
                    handle.write(f"{judge.calls} judge calls {run.name}\n")
            except OSError:
                print("Could not write the ledger file", flush=True)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", type=Path, help="run folder; default is the latest finished run"
    )
    parser.add_argument(
        "--no-judge", action="store_true", help="skip the judge, reuse judgements.json"
    )
    parser.add_argument("--max-judge-calls", type=int, default=120)
    parser.add_argument("--controls", type=int, default=20)
    args = parser.parse_args()
    run = (args.run or latest_finished_run()).resolve()
    config = read(run / "config.json", {})
    questions = load_questions(run, config)
    rows = load_rows(run)
    judgements = judge_run(run, questions, rows, args)
    concerns = build_concerns(
        run.name,
        {
            "questions": questions,
            "rows": rows,
            "judgements": judgements["answers"],
            "controls": judgements["controls"],
            "chunks": read(run / "chunks.json", []),
            "pages": read(run / "reference_pages.json", []),
            "checks": read(run / "checks.json"),
            "filtered_search": read(run / "filtered_search.json"),
        },
    )
    write(run / "concerns.json", concerns)
    print(f"Wrote {run / 'concerns.json'} at {datetime.now(UTC):%H:%M:%S}Z")
    for entry in concerns["items"]:
        print(f"  {entry['id']:<20} {entry['status']:<15} {entry['severity']}")


if __name__ == "__main__":
    main()
