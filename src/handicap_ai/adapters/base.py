from __future__ import annotations

from typing import Protocol

from handicap_ai.models import NormalizedMatchBundle


class SourceAdapter(Protocol):
    source_name: str

    def load(self) -> list[NormalizedMatchBundle]:
        raise NotImplementedError
