from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from health_quantification import ecg_plot
from health_quantification.ecg_plot import (
    MATPLOTLIB_HELP,
    assess_export,
    display_scale,
    main,
    resolve_private_path,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ID = "synthetic-plot-id"
SENTINEL_VOLTS = 0.001337
NEGATIVE_VOLTS = -0.00042
SYNTHETIC_START = "2026-01-15T18:00:00Z"


def _export(*, hz: float = 10.0, count: int = 300) -> dict[str, object]:
    voltage = []
    for index in range(count):
        volts = 0.0
        if index == min(10, count - 1):
            volts = SENTINEL_VOLTS
        elif index == min(20, count - 1):
            volts = NEGATIVE_VOLTS
        voltage.append({"time_offset_seconds": index / hz, "voltage_volts": volts})
    return {
        "source_id": SOURCE_ID,
        "start_at": SYNTHETIC_START,
        "end_at": "2026-01-15T18:00:30Z",
        "algorithm_classification": "sinus_rhythm",
        "average_heart_rate_bpm": 72,
        "sampling_frequency_hz": hz,
        "number_of_voltage_measurements": count,
        "voltage_count": count,
        "returned_points": count,
        "truncated": False,
        "voltage_status": "complete",
        "voltage_unit": "V",
        "lead": "apple_watch_similar_to_lead_i",
        "not_a_diagnosis": True,
        "voltage": voltage,
    }


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")


def _run(tmp_path: Path, payload: object) -> tuple[int, str, Path, Path]:
    source = tmp_path / "synthetic_ecg.json"
    output = tmp_path / "synthetic_ecg.png"
    integrity = tmp_path / "synthetic_ecg_integrity.json"
    _write(source, payload)
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(output),
            "--integrity-output",
            str(integrity),
        ]
    )
    return code, source.read_text(encoding="utf-8"), output, integrity


def _assert_no_staging(directory: Path) -> None:
    assert list(directory.glob(ecg_plot._STAGING_PREFIX + "*")) == []
    assert list(directory.glob("*.partial.png")) == []


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_assess_accepts_consistent_synthetic_grid() -> None:
    report, times, volts = assess_export(_export(hz=512.0, count=512))
    assert report["overall_pass"] is True
    assert times[1] == pytest.approx(1 / 512)
    assert volts[10] == SENTINEL_VOLTS
    assert "voltage" not in report


def test_display_scale_keeps_full_range_when_standard_gain_does_not_fit() -> None:
    scale = display_scale([0.0, 80.0])
    assert scale.y_lo <= 0.0
    assert scale.y_hi >= 80.0
    assert scale.scale_reduced is True
    assert "未裁剪" in scale.scale_note
    assert "不保证打印比例" in scale.scale_note


def test_plot_writes_private_png_without_printing_samples(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _text, output, integrity = _run(tmp_path, _export())
    captured = capsys.readouterr()
    assert code == 0
    assert output.read_bytes().startswith(b"\x89PNG")
    status = json.loads(captured.out)
    assert status["status"] == "plotted"
    assert "不保证打印比例" in status["scale_note"]
    assert "25 mm/s" in status["scale_note"]
    assert SOURCE_ID not in captured.out
    assert SOURCE_ID not in captured.err
    assert "0.001337" not in captured.out
    assert SYNTHETIC_START not in captured.out
    report = json.loads(integrity.read_text(encoding="utf-8"))
    assert report["overall_pass"] is True
    assert report["plot"]["clipped"] is False
    assert report["plot"]["filtered"] is False
    assert report["plot"]["samples_excluded"] == 0
    assert report["plot"]["samples_drawn"] == 300
    y_lo, y_hi = report["plot"]["y_limits_mv"]
    assert y_lo <= NEGATIVE_VOLTS * 1000
    assert y_hi >= SENTINEL_VOLTS * 1000
    assert report["record"]["source_id"] == SOURCE_ID
    assert not (tmp_path / "synthetic_ecg.partial.png").exists()
    _assert_no_staging(tmp_path)


@pytest.mark.parametrize(
    ("mutate", "failed"),
    [
        (lambda payload: payload["voltage"].__setitem__(3, {"time_offset_seconds": 0.3, "voltage_volts": None}), "finite_non_null"),
        (lambda payload: payload["voltage"].__setitem__(4, {"time_offset_seconds": 0.4, "voltage_volts": float("nan")}), "finite_non_null"),
        (lambda payload: payload["voltage"].__setitem__(5, {"time_offset_seconds": 0.5, "voltage_volts": float("inf")}), "finite_non_null"),
        (lambda payload: payload["voltage"].__setitem__(6, {"time_offset_seconds": payload["voltage"][5]["time_offset_seconds"], "voltage_volts": 0.0}), "time_strictly_monotonic"),
        (lambda payload: payload.__setitem__("sampling_frequency_hz", 20.0), "sampling_frequency"),
        (lambda payload: payload.__setitem__("voltage_count", 301), "point_count"),
        (lambda payload: payload.__setitem__("truncated", True), "point_count"),
        (lambda payload: payload.__setitem__("voltage_status", "partial"), "point_count"),
        (lambda payload: payload.__setitem__("voltage_unit", "mV"), "voltage_unit"),
    ],
)
def test_integrity_failures_do_not_write_png(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutate,
    failed: str,
) -> None:
    payload = _export()
    mutate(payload)
    code, _text, output, integrity = _run(tmp_path, payload)
    captured = capsys.readouterr()
    assert code == 2
    assert not output.exists()
    status = json.loads(captured.out)
    assert failed in status["failed_checks"]
    assert "0.001337" not in captured.out
    assert SOURCE_ID not in captured.out
    report = json.loads(integrity.read_text(encoding="utf-8"))
    assert report["overall_pass"] is False
    assert report["plot"]["written"] is False
    _assert_no_staging(tmp_path)


def test_samples_outside_six_strips_are_not_clipped(tmp_path: Path) -> None:
    count = 32
    payload = _export(hz=1.0, count=count)
    code, _text, output, integrity = _run(tmp_path, payload)
    assert code == 2
    assert not output.exists()
    report = json.loads(integrity.read_text(encoding="utf-8"))
    assert report["checks"]["plot_window"]["pass"] is False
    assert report["checks"]["sampling_frequency"]["pass"] is True


def test_invalid_json_and_missing_voltage_are_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "bad.json"
    output = tmp_path / "bad.png"
    integrity = tmp_path / "bad_integrity.json"
    source.write_text("{", encoding="utf-8")
    assert main(["--input", str(source), "--output", str(output), "--integrity-output", str(integrity)]) == 2
    assert not output.exists()
    first_report = integrity.read_bytes()
    assert "voltage" not in capsys.readouterr().out

    source.write_text("[]", encoding="utf-8")
    assert main(["--input", str(source), "--output", str(output), "--integrity-output", str(integrity)]) == 2
    assert integrity.read_bytes() == first_report
    assert not output.exists()
    assert "new output filename" in capsys.readouterr().out

    output2 = tmp_path / "bad2.png"
    integrity2 = tmp_path / "bad2_integrity.json"
    assert main(["--input", str(source), "--output", str(output2), "--integrity-output", str(integrity2)]) == 2
    report = json.loads(integrity2.read_text(encoding="utf-8"))
    assert report["overall_pass"] is False
    assert not output2.exists()


def test_repo_paths_must_stay_under_private_data(tmp_path: Path) -> None:
    allowed = ROOT / "data" / "exports" / "synthetic_ecg_plot.png"
    assert resolve_private_path(allowed, write=True) == allowed.resolve()
    assert not allowed.exists()

    with pytest.raises(ecg_plot.EcgPlotError, match="data/"):
        resolve_private_path(ROOT / "README.md", write=True)
    with pytest.raises(ecg_plot.EcgPlotError, match="private"):
        resolve_private_path(ROOT / "data" / "exports" / ".gitkeep", write=True)
    with pytest.raises(ecg_plot.EcgPlotError, match="private"):
        resolve_private_path(ROOT / "data" / "not_ignored.png", write=True)

    source = tmp_path / "synthetic_ecg.json"
    _write(source, _export(hz=10.0, count=4))
    gitkeep = ROOT / "data" / "exports" / ".gitkeep"
    before = gitkeep.read_bytes()
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(gitkeep),
            "--integrity-output",
            str(tmp_path / "integrity.json"),
        ]
    )
    assert code == 2
    assert gitkeep.read_bytes() == before
    tracked = ROOT / "tests" / "unit" / "ecg_plot_should_not_exist.png"
    code = main(
        [
            "--input",
            str(ROOT / "README.md"),
            "--output",
            str(tracked),
            "--integrity-output",
            str(tmp_path / "integrity.json"),
        ]
    )
    assert code == 2
    assert not tracked.exists()


def test_missing_matplotlib_is_a_friendly_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def blocked(name: str, package: str | None = None) -> object:
        raise ImportError(name)

    monkeypatch.setattr(ecg_plot.importlib, "import_module", blocked)
    code, _text, output, integrity = _run(tmp_path, _export(hz=10.0, count=20))
    captured = capsys.readouterr()
    assert code == 2
    assert not output.exists()
    assert "matplotlib is not installed" in captured.out
    assert MATPLOTLIB_HELP in captured.out
    assert "0.001337" not in captured.out
    assert SOURCE_ID not in captured.out
    report = json.loads(integrity.read_text(encoding="utf-8"))
    assert report["overall_pass"] is True
    assert report["plot"]["written"] is False
    _assert_no_staging(tmp_path)


def test_existing_success_is_kept_when_same_path_is_retried(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, first_text, output, integrity = _run(tmp_path, _export())
    assert code == 0
    previous_png = output.read_bytes()
    previous_report = integrity.read_bytes()
    assert previous_png.startswith(b"\x89PNG")
    assert json.loads(previous_report)["source_sha256"] == _sha256(first_text)
    capsys.readouterr()

    bad = _export()
    bad["voltage_unit"] = "mV"
    source = tmp_path / "synthetic_ecg.json"
    _write(source, bad)
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(output),
            "--integrity-output",
            str(integrity),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert output.read_bytes() == previous_png
    assert integrity.read_bytes() == previous_report
    status = json.loads(captured.out)
    assert status["status"] == "rejected"
    assert status["overall_pass"] is False
    assert "output" not in status
    assert "new output filename" in status["detail"]
    assert "0.001337" not in captured.out
    assert SOURCE_ID not in captured.out

    new_output = tmp_path / "synthetic_ecg_retry.png"
    new_integrity = tmp_path / "synthetic_ecg_retry_integrity.json"
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(new_output),
            "--integrity-output",
            str(new_integrity),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert not new_output.exists()
    assert output.read_bytes() == previous_png
    assert integrity.read_bytes() == previous_report
    report = json.loads(new_integrity.read_text(encoding="utf-8"))
    assert report["overall_pass"] is False
    assert report["plot"]["written"] is False
    assert "voltage_unit" in captured.out
    _assert_no_staging(tmp_path)


def test_plot_failure_on_new_path_does_not_publish_or_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _, output, integrity = _run(tmp_path, _export())
    assert code == 0
    previous_png = output.read_bytes()
    previous_report = integrity.read_bytes()
    capsys.readouterr()

    def boom(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise ecg_plot.EcgPlotError("synthetic plot failure")

    monkeypatch.setattr(ecg_plot, "render_png", boom)
    payload = _export()
    payload["average_heart_rate_bpm"] = 81
    source = tmp_path / "fresh.json"
    fresh_output = tmp_path / "fresh.png"
    fresh_integrity = tmp_path / "fresh_integrity.json"
    _write(source, payload)
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(fresh_output),
            "--integrity-output",
            str(fresh_integrity),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert not fresh_output.exists()
    assert output.read_bytes() == previous_png
    assert integrity.read_bytes() == previous_report
    status = json.loads(captured.out)
    assert status["status"] == "rejected"
    assert status["overall_pass"] is False
    assert "output" not in status
    report = json.loads(fresh_integrity.read_text(encoding="utf-8"))
    assert report["plot"]["written"] is False
    assert report["source_sha256"] == _sha256(source.read_text(encoding="utf-8"))
    assert "synthetic plot failure" in captured.out
    _assert_no_staging(tmp_path)


def test_integrity_write_failure_does_not_publish_png(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, first_text, output, integrity = _run(tmp_path, _export())
    assert code == 0
    previous_png = output.read_bytes()
    previous_report = integrity.read_bytes()
    assert json.loads(previous_report)["source_sha256"] == _sha256(first_text)
    capsys.readouterr()

    real_write = ecg_plot._write_json

    def flaky(path: Path, payload: dict[str, object]) -> None:
        plot = payload.get("plot")
        if isinstance(plot, dict) and plot.get("written"):
            raise OSError("synthetic integrity write failure")
        real_write(path, payload)

    monkeypatch.setattr(ecg_plot, "_write_json", flaky)
    payload = _export()
    payload["average_heart_rate_bpm"] = 83
    source = tmp_path / "fresh.json"
    fresh_output = tmp_path / "fresh.png"
    fresh_integrity = tmp_path / "fresh_integrity.json"
    _write(source, payload)
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(fresh_output),
            "--integrity-output",
            str(fresh_integrity),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert not fresh_output.exists()
    assert output.read_bytes() == previous_png
    assert integrity.read_bytes() == previous_report
    status = json.loads(captured.out)
    assert status["status"] == "rejected"
    assert status["overall_pass"] is False
    assert "output" not in status
    assert "0.001337" not in captured.out
    report = json.loads(fresh_integrity.read_text(encoding="utf-8"))
    assert report["plot"]["written"] is False
    assert report["source_sha256"] == _sha256(source.read_text(encoding="utf-8"))
    _assert_no_staging(tmp_path)


def test_unwritable_integrity_does_not_publish_or_delete_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code, _, output, integrity = _run(tmp_path, _export())
    assert code == 0
    previous_png = output.read_bytes()
    previous_report = integrity.read_bytes()
    source = tmp_path / "fresh.json"
    _write(source, _export())
    before = source.read_bytes()
    fresh_output = tmp_path / "fresh.png"
    fresh_integrity = tmp_path / "fresh_integrity.json"

    def blocked(_path: Path, _payload: dict[str, object]) -> None:
        raise OSError("synthetic integrity write failure")

    monkeypatch.setattr(ecg_plot, "_write_json", blocked)
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(fresh_output),
            "--integrity-output",
            str(fresh_integrity),
        ]
    )
    assert code == 2
    assert not fresh_output.exists()
    assert not fresh_integrity.exists()
    assert output.read_bytes() == previous_png
    assert integrity.read_bytes() == previous_report
    assert source.read_bytes() == before
    _assert_no_staging(tmp_path)


def test_coincident_paths_do_not_overwrite_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "synthetic_ecg.json"
    _write(source, _export())
    before = source.read_bytes()
    other = tmp_path / "other.png"
    other.write_bytes(b"prior-output")
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(source),
            "--integrity-output",
            str(tmp_path / "integrity.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert source.read_bytes() == before
    assert not (tmp_path / "integrity.json").exists()
    assert "different" in captured.out
    assert "0.001337" not in captured.out

    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(other),
            "--integrity-output",
            str(source),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert source.read_bytes() == before
    assert other.read_bytes() == b"prior-output"
    assert "different" in captured.out
    _assert_no_staging(tmp_path)

    linked = tmp_path / "linked.json"
    os.link(source, linked)
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(linked),
            "--integrity-output",
            str(tmp_path / "integrity.json"),
        ]
    )
    assert code == 2
    assert source.read_bytes() == before
    assert linked.read_bytes() == before
    assert not (tmp_path / "integrity.json").exists()


def test_existing_hardlink_or_symlink_is_not_replaced(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "synthetic_ecg.json"
    _write(source, _export())
    prior = tmp_path / "prior.png"
    prior.write_bytes(b"private-prior-png")
    hard = tmp_path / "hard.png"
    os.link(prior, hard)
    integrity = tmp_path / "hard_integrity.json"
    code = main(
        ["--input", str(source), "--output", str(hard), "--integrity-output", str(integrity)]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert hard.read_bytes() == b"private-prior-png"
    assert prior.read_bytes() == b"private-prior-png"
    assert not integrity.exists()
    assert "new output filename" in captured.out

    target = tmp_path / "target.png"
    target.write_bytes(b"symlink-target")
    link = tmp_path / "link.png"
    link.symlink_to(target)
    integrity2 = tmp_path / "link_integrity.json"
    code = main(
        ["--input", str(source), "--output", str(link), "--integrity-output", str(integrity2)]
    )
    assert code == 2
    assert target.read_bytes() == b"symlink-target"
    assert link.is_symlink()
    assert link.read_bytes() == b"symlink-target"
    assert not integrity2.exists()

    broken = tmp_path / "broken.png"
    broken.symlink_to(tmp_path / "missing-target.png")
    integrity3 = tmp_path / "broken_integrity.json"
    code = main(
        ["--input", str(source), "--output", str(broken), "--integrity-output", str(integrity3)]
    )
    assert code == 2
    assert broken.is_symlink()
    assert not (tmp_path / "missing-target.png").exists()
    assert not integrity3.exists()

    only_integrity = tmp_path / "only_integrity.json"
    only_integrity.write_bytes(b'{"kept":true}\n')
    only_output = tmp_path / "only_output.png"
    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(only_output),
            "--integrity-output",
            str(only_integrity),
        ]
    )
    assert code == 2
    assert only_integrity.read_bytes() == b'{"kept":true}\n'
    assert not only_output.exists()


def test_output_appearing_during_plot_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "synthetic_ecg.json"
    output = tmp_path / "concurrent.png"
    integrity = tmp_path / "concurrent_integrity.json"
    _write(source, _export())
    marker = b"concurrent-existing-png"
    real_scale = ecg_plot.display_scale

    def sneak(values: list[float]) -> object:
        output.write_bytes(marker)
        return real_scale(values)

    monkeypatch.setattr(ecg_plot, "display_scale", sneak)
    code = main(
        ["--input", str(source), "--output", str(output), "--integrity-output", str(integrity)]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert output.read_bytes() == marker
    status = json.loads(captured.out)
    assert status["status"] == "rejected"
    assert "0.001337" not in captured.out
    _assert_no_staging(tmp_path)
