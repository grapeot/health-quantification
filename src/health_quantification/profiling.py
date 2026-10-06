"""Opt-in, request-local aggregate timings; contains no health payload fields."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

current_timings: ContextVar[dict[str, float] | None] = ContextVar("ingest_timings", default=None)


@contextmanager
def timed(phase: str):
    timings = current_timings.get()
    if timings is None:
        yield
        return
    start = perf_counter()
    try:
        yield
    finally:
        timings[phase] = timings.get(phase, 0.0) + (perf_counter() - start) * 1000
