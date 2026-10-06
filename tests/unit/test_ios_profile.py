from copy import deepcopy

import pytest

from scripts.ios_profile import compare_summaries, summarize, validate_profile

RUN_ID = "456EEB81-F801-4F0A-9C3F-9C9AFD9AB123"


def fixture():
    return {"schema_version": 1, "run_id": RUN_ID, "status": "success", "total_ms": 10,
            "failed_categories": [], "events": [
                {"phase": f"{category}.fetch", "duration_ms": 1}
                for category in ("sleep", "vitals", "body", "lifestyle", "activity", "workouts", "ecg")]}


def test_rejects_stale_partial_missing_and_nonfinite_results():
    payload = fixture()
    assert validate_profile(payload, RUN_ID) == payload
    for changes in ({"run_id": "other"}, {"events": []}, {"total_ms": float("nan")},
                    {"failed_categories": ["vitals"]}):
        with pytest.raises(ValueError):
            validate_profile({**payload, **changes}, RUN_ID)
    missing = deepcopy(payload)
    missing["events"].pop()
    with pytest.raises(ValueError):
        validate_profile(missing, RUN_ID)


def test_summarizes_repeated_spans_without_double_counting_categories():
    payload = fixture()
    payload["events"] += [{"phase": "ecg.http", "duration_ms": 2}, {"phase": "ecg.http", "duration_ms": 3}]
    second = {**payload, "total_ms": 20}
    result = summarize([payload, second])
    assert result["total"] == {"p50_ms": 15, "p90_ms": 20}
    assert result["phases"]["ecg.http"]["p50_ms"] == 5


def test_comparison_reports_workload_drift_and_rejects_mixed_modes():
    baseline = {"configuration": "Release", "cold": False, "warmup": 1, "total": {"p50_ms": 12},
                "sample_counts": [{"vitals.encode": 100}]}
    candidate = {**baseline, "total": {"p50_ms": 4}, "sample_counts": [{"vitals.encode": 99}]}
    comparison = compare_summaries(baseline, candidate)
    assert comparison["speedup"] == 3
    assert comparison["time_reduction_percent"] == pytest.approx(200 / 3)
    assert comparison["maximum_relative_sample_count_drift"] == .01
    with pytest.raises(ValueError):
        compare_summaries(baseline, {**candidate, "cold": True})
    with pytest.raises(ValueError):
        compare_summaries(baseline, {**candidate, "warmup": 0})
