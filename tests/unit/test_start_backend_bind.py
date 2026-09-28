from __future__ import annotations

import subprocess
from pathlib import Path


def test_start_backend_bind_policy() -> None:
    script = Path(__file__).with_name("test_start_backend_bind.sh")
    completed = subprocess.run(
        ["bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
