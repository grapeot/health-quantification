from health_quantification.analysis.daily_summary import build_default_daily_summary


def test_default_daily_summary_has_expected_shape() -> None:
    summary = build_default_daily_summary("2026-03-30", "America/Los_Angeles")

    assert summary.date == "2026-03-30"
    assert summary.timezone == "America/Los_Angeles"
    assert "phase_1_placeholder" in summary.notes
