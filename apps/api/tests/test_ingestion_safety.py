import asyncio
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services import ingestion, processing


def test_windows_parsing_disables_native_compilation(monkeypatch):
    converter = Mock()
    monkeypatch.setattr(ingestion.sys, "platform", "win32")
    monkeypatch.setattr(ingestion, "DocumentConverter", Mock(return_value=converter))
    monkeypatch.setattr(ingestion.docling_settings.inference, "compile_torch_models", True)
    ingestion.ingest_document("example.pdf")
    assert ingestion.docling_settings.inference.compile_torch_models is False
    converter.convert.assert_called_once_with("example.pdf")


@pytest.mark.asyncio
async def test_heavy_ingestion_is_serialized_and_slot_recovers_after_failure(monkeypatch):
    active = 0
    peak = 0
    calls = 0

    async def work(*args):
        nonlocal active, peak, calls
        active += 1
        calls += 1
        number = calls
        peak = max(peak, active)
        try:
            await asyncio.sleep(0)
            if number == 1:
                raise ValueError("parse failed")
            return 3
        finally:
            active -= 1

    monkeypatch.setattr(processing, "_ingestion_slot", asyncio.Semaphore(1))
    monkeypatch.setattr(processing, "_process_file", work)
    args = (uuid4(), uuid4(), uuid4(), "example.pdf", Mock())
    results = await asyncio.gather(
        *(processing.process_file(*args) for _ in range(3)), return_exceptions=True
    )
    assert isinstance(results[0], ValueError)
    assert results[1:] == [3, 3]
    assert peak == 1
