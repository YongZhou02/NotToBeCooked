import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playground.toolkit.trace import Trace, traced


@traced("demo.sync")
def add(a, b=1):
    return a + b


@traced("demo.async")
async def boom(x):
    raise ValueError(x)


def test_calls_are_recorded_inside_a_trace_only():
    assert add(1) == 2
    with Trace() as trace:
        add(2, b=3)
        try:
            asyncio.run(boom("bad"))
        except ValueError:
            pass
    assert [s["step"] for s in trace.steps] == ["demo.sync", "demo.async"]
    assert trace.steps[0]["input"] == {"a": 2, "b": 3} and trace.steps[0]["output"] == 5
    assert "bad" in trace.steps[1]["error"]


def test_long_values_are_capped():
    with Trace() as trace:
        add("x" * 1000, b="y")
    assert len(trace.steps[0]["input"]["a"]) < 400
