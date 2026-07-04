from pathlib import Path

from handicap_ai.scraping.fetcher import SavedHtmlFetchResult, load_saved_html


def test_load_saved_html_returns_hash_and_text(tmp_path):
    html_path = tmp_path / "match.html"
    html_path.write_text("<html>match</html>", encoding="utf-8")

    result = load_saved_html(source="betexplorer", html_path=html_path)

    assert isinstance(result, SavedHtmlFetchResult)
    assert result.html == "<html>match</html>"
    assert result.record.source == "betexplorer"
    assert result.record.status_code == 200
    assert result.record.cache_path == str(html_path)
    assert len(result.record.content_hash) == 64
