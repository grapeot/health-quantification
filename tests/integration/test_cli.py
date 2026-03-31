from health_quantification.cli import main


def test_doctor_config_runs() -> None:
    exit_code = main(["doctor", "config"])
    assert exit_code == 0
