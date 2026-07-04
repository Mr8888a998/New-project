from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from handicap_ai.scraping.models import SourceFetchRecord


@dataclass(frozen=True)
class SavedHtmlFetchResult:
    html: str
    record: SourceFetchRecord


def load_saved_html(source: str, html_path: Path) -> SavedHtmlFetchResult:
    path = Path(html_path)
    html = path.read_text(encoding="utf-8")
    content_hash = sha256(html.encode("utf-8")).hexdigest()
    record = SourceFetchRecord(
        source=source,
        url=path.resolve().as_uri(),
        fetched_at=datetime.now(timezone.utc),
        status_code=200,
        cache_path=str(path),
        content_hash=content_hash,
        error_message=None,
    )
    return SavedHtmlFetchResult(html=html, record=record)
