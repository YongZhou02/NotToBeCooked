"""Records every toolkit call made while answering one question.

    with Trace() as trace:          # one per question, opened by the runner
        await pipeline.answer(q, tk)
    trace.steps                     # [{"step", "input", "output", "ms", "error"}, ...]

    @traced("retrieval.keyword")    # on any toolkit function, sync or async
    def keyword(query, k=5): ...

Calls made outside a Trace are not recorded and behave normally.
"""

from __future__ import annotations

import functools
import inspect
from contextvars import ContextVar
from time import perf_counter
from typing import Any, Callable

_current: ContextVar["Trace | None"] = ContextVar("playground_trace", default=None)

MAX_TEXT = 300
MAX_ITEMS = 10


def summarise(value: Any, depth: int = 0) -> Any:
    """A JSON-safe, size-capped copy, so a trace line stays readable."""
    if depth > 4:
        return "..."
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + "..."
    if isinstance(value, dict):
        return {str(k): summarise(v, depth + 1) for k, v in list(value.items())[:30]}
    if isinstance(value, (list, tuple, set)):
        items = [summarise(v, depth + 1) for v in list(value)[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            items.append(f"... {len(value) - MAX_ITEMS} more")
        return items
    if hasattr(value, "model_dump"):
        return summarise(value.model_dump(mode="json"), depth + 1)
    return summarise(repr(value), depth + 1)


class Trace:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self._token = None

    def __enter__(self) -> "Trace":
        self._token = _current.set(self)
        return self

    def __exit__(self, *exc: Any) -> None:
        _current.reset(self._token)

    def record(self, step: str, input: Any = None, output: Any = None,
               ms: float | None = None, error: str | None = None) -> None:
        self.steps.append({
            "step": step,
            "input": summarise(input),
            "output": summarise(output),
            "ms": None if ms is None else round(ms, 2),
            "error": error,
        })


def csv_cell(value: Any) -> Any:
    """How every results table writes a value: 1/0 for booleans, empty for
    not measured, so playground and run_eval tables load together."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    return value


def current() -> Trace | None:
    return _current.get()


def traced(step: str) -> Callable:
    """Record each call of the wrapped function in the current Trace."""

    def wrap(function: Callable) -> Callable:
        signature = inspect.signature(function)

        def arguments(args: tuple, kwargs: dict) -> dict:
            try:
                bound = signature.bind_partial(*args, **kwargs)
                return {k: v for k, v in bound.arguments.items() if k not in ("self", "tk")}
            except TypeError:
                return {"args": args, "kwargs": kwargs}

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def run_async(*args: Any, **kwargs: Any) -> Any:
                trace, start = current(), perf_counter()
                try:
                    result = await function(*args, **kwargs)
                except Exception as error:
                    if trace:
                        trace.record(step, arguments(args, kwargs), None,
                                     (perf_counter() - start) * 1000, repr(error)[:500])
                    raise
                if trace:
                    trace.record(step, arguments(args, kwargs), result,
                                 (perf_counter() - start) * 1000)
                return result

            return run_async

        @functools.wraps(function)
        def run_sync(*args: Any, **kwargs: Any) -> Any:
            trace, start = current(), perf_counter()
            try:
                result = function(*args, **kwargs)
            except Exception as error:
                if trace:
                    trace.record(step, arguments(args, kwargs), None,
                                 (perf_counter() - start) * 1000, repr(error)[:500])
                raise
            if trace:
                trace.record(step, arguments(args, kwargs), result,
                             (perf_counter() - start) * 1000)
            return result

        return run_sync

    return wrap
