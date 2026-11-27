"""The literature lane's arXiv fetch helper: identifiers and query encoding.

It is the only shipped script that had no test (issue #50). The Atom feed is
faked; nothing here touches the network.
"""

import importlib.util

import pytest

from conftest import REPO

SCRIPT = REPO / "agent-presets/rigorquant/skills/arxiv/scripts/search_arxiv.py"

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/solv-int/9901001v2</id>
    <title>An old-style identifier</title>
    <published>1999-01-01T00:00:00Z</published>
    <updated>1999-02-01T00:00:00Z</updated>
    <author><name>A. Author</name></author>
    <summary>Abstract.</summary>
    <category term="math.AP"/>
  </entry>
</feed>
"""


class _Reply:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return ATOM.encode()


def load(monkeypatch, calls):
    spec = importlib.util.spec_from_file_location("search_arxiv", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def urlopen(request, timeout=None):
        calls.append(request.full_url)
        return _Reply()

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    return module


def test_an_old_style_id_keeps_its_whole_base(monkeypatch, capsys):
    """`solv-int/9901001v2` used to split at the "v" in "solv" (abs/sol)."""
    load(monkeypatch, []).search(ids="solv-int/9901001v2")
    out = capsys.readouterr().out
    assert "https://arxiv.org/abs/solv-int/9901001 |" in out
    assert "ID: solv-int/9901001v2" in out


def test_a_multi_word_query_is_encoded(monkeypatch, capsys):
    calls = []
    load(monkeypatch, calls).search(query="portfolio selection")
    assert "all:portfolio%20selection" in calls[0]
    assert " " not in calls[0]


def test_the_id_list_is_url_quoted(monkeypatch, capsys):
    """An unquoted `&` in --id used to inject a second query parameter."""
    calls = []
    load(monkeypatch, calls).search(ids="2402.03300&max_results=99")
    assert "id_list=2402.03300%26max_results%3D99" in calls[0]


def test_the_category_is_url_quoted(monkeypatch, capsys):
    """An unquoted `&` in --category used to inject a second query parameter."""
    calls = []
    load(monkeypatch, calls).search(category="cs.AI&max_results=99")
    assert "cat:cs.AI%26max_results%3D99" in calls[0]
    assert calls[0].count("max_results=") == 1


def test_an_unknown_sort_is_rejected(monkeypatch, capsys):
    """An unknown --sort used to be passed straight into sortBy."""
    calls = []
    module = load(monkeypatch, calls)
    with pytest.raises(SystemExit):
        module.search(query="GRPO", sort="newest")
    assert calls == []
    assert "unsupported --sort 'newest'" in capsys.readouterr().out
