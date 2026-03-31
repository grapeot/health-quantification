from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(slots=True)
class SnapshotEnvelope:
    source: str
    exported_at: str
    schema_version: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
