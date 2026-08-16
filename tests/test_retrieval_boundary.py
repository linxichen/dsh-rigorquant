"""The literature lane's external boundary, marked rather than assumed.

docs/literature-lane.md A8: arXiv / Semantic Scholar / Crossref access is a real
network boundary. Where the sandbox or CI cannot reach it, these tests SKIP with
an explicit "unverified boundary" message -- they never translate "not run" into
"passed", which is the failure mode the whole repository exists to prevent.
"""

import json
import urllib.error
import urllib.request

import pytest

TIMEOUT = 10


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dsh-rigorquant-tests/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # A throttled service is still an unverified boundary; any other HTTP
        # status means the service answered and the contract really is broken.
        if e.code in (429, 503):
            pytest.skip("UNVERIFIED BOUNDARY: %s rate-limited (%s); the retrieval "
                        "path is NOT confirmed by this run." % (url, e.code))
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        pytest.skip("UNVERIFIED BOUNDARY: %s unreachable from this environment (%s). "
                    "The retrieval path is NOT confirmed by this run." % (url, e))


def test_arxiv_api_returns_the_requested_paper():
    """The arxiv skill's whole contract: id_list returns that id's Atom entry."""
    body = _get("http://export.arxiv.org/api/query?id_list=1706.03762&max_results=1")
    assert "1706.03762" in body
    assert "Attention Is All You Need" in body


def test_crossref_resolves_a_doi_to_its_title():
    """The freshness check (retraction/venue) rides on Crossref resolving DOIs."""
    body = _get("https://api.crossref.org/works/10.2307/2975974"
                "?mailto=dsh-rigorquant@example.com")
    data = json.loads(body)
    assert data["message"]["DOI"].lower() == "10.2307/2975974"
    assert "Portfolio Selection" in " ".join(data["message"]["title"])


def test_semantic_scholar_resolves_an_arxiv_id_to_its_title():
    """Forward-citation / version checks ride on Semantic Scholar resolving IDs."""
    body = _get("https://api.semanticscholar.org/graph/v1/paper/arXiv:1706.03762"
                "?fields=title")
    data = json.loads(body)
    assert "attention is all you need" in data.get("title", "").lower()
