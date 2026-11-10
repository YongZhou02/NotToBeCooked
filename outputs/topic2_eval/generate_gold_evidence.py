import asyncio
import json
from pathlib import Path

import httpx

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[2]
ROWS = ROOT / "outputs/topic2_eval/workbook_gold_rows.json"
PAGES = ROOT / "outputs/topic2_eval/topic2_pages.txt"
OUTPUT = ROOT / "outputs/topic2_eval/workbook_gold_evidence.json"


async def main() -> None:
    rows = json.loads(ROWS.read_text(encoding="utf-8"))
    source = PAGES.read_text(encoding="utf-8")
    schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "id": {"type": "STRING"},
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
            },
            "required": ["id", "evidence"],
        },
    }
    prompt = f"""Extract exact evidence spans for a frozen RAG benchmark.

The supplied rows already define the authoritative question, answer, supported/unsupported status, source pages, and evidence basis. Do not rewrite them.

For each Supported row:
- Return 1 to 3 short quotes copied VERBATIM from the lecture page text.
- Use only pages listed in Source Pages.
- Together the quotes must support the Gold Answer and Evidence Basis.
- Preserve exact characters and wording. Do not correct grammar, join column text, paraphrase, or replace symbols.

For each Unsupported row:
- Return an empty evidence array. The source page only explains why the requested detail is absent and is not positive answer evidence.

Return exactly one object per ID, in input order.

GOLD ROWS:
{json.dumps(rows, ensure_ascii=False)}

LECTURE TEXT WITH PAGE MARKERS:
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
    evidence = json.loads(text)
    OUTPUT.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(evidence)} evidence records to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
