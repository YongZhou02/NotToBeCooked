"""Tests for app/services/embeddings.py.

Most tests replace the model with a fake, so they run in milliseconds and need no
download. The last test loads the real model and only runs with RUN_MODEL_TESTS=1.
"""

import math
import os
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from app.core.config import settings
from app.services import embeddings
from app.services.embeddings import count_token, embed_query, embed_text


def make_fake_model(rows: list[list[float]]) -> MagicMock:
    model = MagicMock()
    model.encode.return_value = np.array(rows, dtype=np.float32)
    return model


def test_embed_query_returns_one_plain_list_of_numbers():
    fake_model = make_fake_model([[0.6, 0.8]])

    with patch("app.services.embeddings._get_model", return_value=fake_model):
        vector = embed_query("How is backpropagation calculated?")

    assert vector == pytest.approx([0.6, 0.8])
    assert isinstance(vector, list)
    assert all(isinstance(x, float) for x in vector)

    fake_model.encode.assert_called_once_with(
        ["How is backpropagation calculated?"],
        show_progress_bar=False,
        normalize_embeddings=True,
        task="retrieval",
        prompt_name="query",
    )


def test_embed_text_returns_one_list_per_input_in_the_same_order():
    fake_model = make_fake_model([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]])
    texts = ["first chunk", "second chunk", "third chunk"]

    with patch("app.services.embeddings._get_model", return_value=fake_model):
        vectors = embed_text(texts)

    assert vectors == [
        pytest.approx([1.0, 0.0]),
        pytest.approx([0.0, 1.0]),
        pytest.approx([0.6, 0.8]),
    ]
    assert all(isinstance(v, list) for v in vectors)

    fake_model.encode.assert_called_once_with(
        texts,
        batch_size=settings.BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
        task="retrieval",
        prompt_name="document",
    )


def test_query_and_document_use_different_prompts():
    # The model is told whether it is reading a question or a stored chunk.
    # Mixing these up still returns numbers, but search quality quietly drops.
    fake_model = make_fake_model([[1.0, 0.0]])

    with patch("app.services.embeddings._get_model", return_value=fake_model):
        embed_query("a question")
        embed_text(["a chunk"])

    first_call, second_call = fake_model.encode.call_args_list
    assert first_call.kwargs["prompt_name"] == "query"
    assert second_call.kwargs["prompt_name"] == "document"


def test_model_is_loaded_once_and_reused(monkeypatch):
    monkeypatch.setattr(embeddings, "_active_model", None)
    loaded = object()

    with patch("app.services.embeddings._load_model", return_value=loaded) as load:
        first = embeddings._get_model()
        second = embeddings._get_model()

    assert first is loaded
    assert second is loaded
    load.assert_called_once()


def test_two_threads_asking_at_once_still_load_the_model_once(monkeypatch):
    """Two uploads that start in the same second both reach `_get_model` from
    worker threads while the model is still None. Loading it twice at once is
    not merely wasteful: measured 24 September 2026, one of two concurrent loads
    came back with 290 of its 310 base weights in float32 instead of bfloat16,
    and every `encode` on it raised "expected m1 and m2 to have the same dtype".
    """
    monkeypatch.setattr(embeddings, "_active_model", None)
    calls: list[int] = []

    def slow_load():
        calls.append(1)
        time.sleep(0.2)  # long enough for the second thread to arrive mid-load
        return object()

    monkeypatch.setattr(embeddings, "_load_model", slow_load)

    with ThreadPoolExecutor(max_workers=2) as pool:
        models = list(pool.map(lambda _: embeddings._get_model(), range(2)))

    assert len(calls) == 1
    assert models[0] is models[1]


def test_load_model_uses_cpu_when_no_gpu():
    with (
        patch.object(torch.cuda, "is_available", return_value=False),
        patch("app.services.embeddings.SentenceTransformer") as sentence_transformer,
    ):
        embeddings._load_model()

    sentence_transformer.assert_called_once_with(
        settings.MODEL_TYPE,
        trust_remote_code=True,
        device="cpu",
        model_kwargs={},
        config_kwargs={},
    )


@pytest.mark.parametrize(
    ("flash_attn_installed", "expected_config_kwargs"),
    [
        (False, {}),
        (True, {"_attn_implementation": "flash_attention_2"}),
    ],
)
def test_load_model_on_gpu(monkeypatch, flash_attn_installed, expected_config_kwargs):
    # A None entry in sys.modules makes `import flash_attn` fail, as if it were not installed.
    fake_module = types.ModuleType("flash_attn") if flash_attn_installed else None
    monkeypatch.setitem(sys.modules, "flash_attn", fake_module)

    with (
        patch.object(torch.cuda, "is_available", return_value=True),
        patch("app.services.embeddings.SentenceTransformer") as sentence_transformer,
    ):
        embeddings._load_model()

    sentence_transformer.assert_called_once_with(
        settings.MODEL_TYPE,
        trust_remote_code=True,
        device="cuda",
        model_kwargs={"dtype": torch.bfloat16},
        config_kwargs=expected_config_kwargs,
    )


def test_count_token_counts_only_the_text_itself():
    fake_model = MagicMock()
    fake_model.tokenizer.encode.return_value = [101, 2054, 2003]

    with patch("app.services.embeddings._get_model", return_value=fake_model):
        count = count_token("what is this")

    assert count == 3
    fake_model.tokenizer.encode.assert_called_once_with("what is this", add_special_tokens=False)


def similarity(a: list[float], b: list[float]) -> float:
    # Both vectors have length 1, so multiplying them position by position and
    # adding up gives a score from -1 (opposite) to 1 (same meaning).
    return sum(x * y for x, y in zip(a, b, strict=True))


@pytest.mark.skipif(
    os.environ.get("RUN_MODEL_TESTS") != "1",
    reason="loads the real embedding model; run with RUN_MODEL_TESTS=1",
)
def test_real_model_places_related_text_closer_than_unrelated_text():
    query_vector = embed_query("How is backpropagation calculated?")

    assert len(query_vector) == settings.EMBEDDINGS_DIM
    length = math.sqrt(sum(x * x for x in query_vector))
    assert math.isclose(length, 1.0, rel_tol=1e-3)

    related, unrelated = embed_text(
        [
            "Backpropagation computes the gradient of the loss with respect to each network weight.",
            "The campus library cafeteria opens at 8am and serves sandwiches on weekdays.",
        ]
    )
    assert len(related) == settings.EMBEDDINGS_DIM
    assert len(unrelated) == settings.EMBEDDINGS_DIM

    related_score = similarity(query_vector, related)
    unrelated_score = similarity(query_vector, unrelated)
    assert related_score > unrelated_score + 0.3, (
        f"related={related_score:.3f}, unrelated={unrelated_score:.3f}"
    )
