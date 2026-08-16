import pytest
import json
from unittest.mock import MagicMock
import tools.web_search as web_search

def test_duckduckgo_provider_abstract(mocker):
    provider = web_search.DuckDuckGoSearchProvider()

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "AbstractText": "Python is a programming language.",
        "Heading": "Python",
        "AbstractURL": "https://python.org"
    }).encode("utf-8")

    mock_urlopen = mocker.patch("urllib.request.urlopen")

    # Needs to be a context manager
    mock_urlopen.return_value.__enter__.return_value = mock_response

    results = provider.perform_search("python")

    assert len(results) == 1
    assert results[0]["title"] == "Python"
    assert results[0]["snippet"] == "Python is a programming language."
    assert results[0]["url"] == "https://python.org"

    mock_urlopen.assert_called_once()

def test_duckduckgo_provider_related_topics(mocker):
    provider = web_search.DuckDuckGoSearchProvider()

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "RelatedTopics": [
            {"Text": "Apple - A fruit", "FirstURL": "https://apple.com/fruit"},
            {"Text": "Apple - A tech company", "FirstURL": "https://apple.com"}
        ]
    }).encode("utf-8")

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    results = provider.perform_search("apple")

    assert len(results) == 2
    assert results[0]["title"] == "Apple"
    assert results[0]["snippet"] == "Apple - A fruit"
    assert results[0]["url"] == "https://apple.com/fruit"

    assert results[1]["title"] == "Apple"
    assert results[1]["snippet"] == "Apple - A tech company"
    assert results[1]["url"] == "https://apple.com"

def test_duckduckgo_provider_error(mocker):
    provider = web_search.DuckDuckGoSearchProvider()

    mock_urlopen = mocker.patch("urllib.request.urlopen")
    mock_urlopen.side_effect = Exception("Network error")

    results = provider.perform_search("error")

    assert results == []

def test_perform_search_wrapper(mocker):
    mock_provider = MagicMock()
    mock_provider.perform_search.return_value = [{"title": "Test", "url": "url", "snippet": "snippet"}]

    mocker.patch("tools.web_search._default_provider", mock_provider)

    results = web_search.perform_search("test")

    assert results == [{"title": "Test", "url": "url", "snippet": "snippet"}]
    mock_provider.perform_search.assert_called_once_with("test")
