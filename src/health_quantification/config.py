from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(slots=True)
class Settings:
    db_path: Path
    export_dir: Path
    timezone: str
    live_tests_enabled: bool
    server_host: str
    server_port: int

    def to_public_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["db_path"] = str(self.db_path)
        data["export_dir"] = str(self.export_dir)
        return data


def _project_root() -> Path:
    """Resolve to the project root (one level above this package directory)."""
    return Path(__file__).resolve().parent.parent.parent


def load_settings() -> Settings:
    project_root = _project_root()
    db_path = Path(os.getenv("HEALTH_QUANT_DB_PATH", str(project_root / "data" / "health_quantification.db")))
    export_dir = Path(os.getenv("HEALTH_QUANT_EXPORT_DIR", str(project_root / "data" / "exports")))
    timezone = os.getenv("HEALTH_QUANT_TIMEZONE", "America/Los_Angeles")
    live_tests_enabled = os.getenv("HEALTH_QUANT_ENABLE_LIVE_TESTS", "0") == "1"
    server_host = os.getenv("HEALTH_QUANT_SERVER_HOST", "0.0.0.0")
    server_port = int(os.getenv("HEALTH_QUANT_SERVER_PORT", "7996"))
    return Settings(
        db_path=db_path,
        export_dir=export_dir,
        timezone=timezone,
        live_tests_enabled=live_tests_enabled,
        server_host=server_host,
        server_port=server_port,
    )
