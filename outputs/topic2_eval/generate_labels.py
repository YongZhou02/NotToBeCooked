import asyncio
import csv
import json
from pathlib import Path

import httpx

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = Path(r"D:\Downloads\NTBC_Topic2_50_Questions_Only.csv")
PAGES = ROOT / "outputs/topic2_eval/topic2_pages.txt"
OUTPUT = ROOT / "outputs/topic2_eval/ai_labels.json"


async def main() -> None:
    questions = list(csv.DictReader(QUESTIONS.open(encoding="utf-8-sig", newline="")))
    source = PAGES.read_text(encoding="utf-8")
    schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "id": {"type": "STRING"},
                "answerable": {"type": "BOOLEAN"},
                "reference_answer": {"type": "STRING"},
                "required_facts": {"type": "ARRAY", "items": {"type": "STRING"}},
                "evidence": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "pdf_page": {"type": "INTEGER"},
                            "quote": {"type": "STRING"},
                        },
                        "required": ["pdf_page", "quote"],
                    },
                },
                "reason": {"type": "STRING"},
            },
            "required": [
                "id",
                "answerable",
                "reference_answer",
                "required_facts",
                "evidence",
                "reason",
            ],
        },
    }
    prompt = f"""You are preparing a frozen RAG evaluation dataset from one supplied lecture PDF.

For every question, decide strictly from the supplied lecture text whether it is answerable.
- Do not use outside knowledge.
- If the lecture does not provide the requested exact algorithm, version, numeric benchmark, address, flags, state count, library, or behavior, mark answerable=false.
- For answerable questions, write a concise answer and 1-3 atomic required facts.
- Evidence quotes must be copied VERBATIM from the supplied page text and must directly support the answer. Keep each quote short but meaningful.
- For unanswerable questions, use this exact reference_answer: "The supplied material does not cover this question." and use an empty evidence array.
- Return exactly one object for every input ID, in the same order.

QUESTIONS:
{json.dumps(questions, ensure_ascii=False)}

LECTURE TEXT WITH PDF PAGE MARKERS:
{source}
"""
    url = f"{settings.GEMINI_API_BASE_URL}/models/{settings.GEMINI_MODEL_NAME}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            url,
            params={"key": settings.GEMINI_API_KEY.get_secret_value()},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    text = body["candidates"][0]["content"]["parts"][0]["text"]
    labels = json.loads(text)
    OUTPUT.write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(labels)} labels to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
