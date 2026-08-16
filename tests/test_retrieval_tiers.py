"""The tiered retrieval order is executable, not just prose.

docs/literature-lane.md §9 fixes the resolution order (author page → open
repos/Unpaywall → preprint → OpenAlex/CORE → user-supplied mirrors) and makes
the mirror tier user-supplied and empty by default. A prose contract cannot be
checked; the resolver script can.
"""

import json
import subprocess
import sys

from conftest import REPO, SKILL_DIR

RESOLVER = (REPO / "agent-presets/rigorquant/skills/academic-paper-search"
            / "scripts/resolve_tiers.py")


def plan(*args, mirrors=None):
    env = {"PATH": "/usr/bin:/bin"}
    if mirrors is not None:
        env["DSH_LIT_MIRRORS"] = mirrors
    out = subprocess.run([sys.executable, str(RESOLVER), *args],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_author_page_is_the_first_tier():
    tiers = plan("--doi", "10.2307/2975974", "--author-page", "https://example.edu/~h/pub")
    assert tiers[0]["retrieval_method"] == "author-page"


def test_the_mirror_tier_is_empty_unless_the_user_supplies_endpoints():
    """C6: mirrors are user-supplied and never hardcoded in-repo."""
    tiers = plan("--doi", "10.2307/2975974")
    assert not [t for t in tiers if t["retrieval_method"] == "user-mirror"]
    assert "sci-hub" not in RESOLVER.read_text().lower()


def test_a_supplied_mirror_becomes_the_last_tier():
    tiers = plan("--doi", "10.2307/2975974", mirrors="https://mirror.example/\n")
    assert tiers[-1]["retrieval_method"] == "user-mirror"
    assert "https://mirror.example/" in json.dumps(tiers[-1])


def test_every_tier_label_is_a_retrieval_method_the_schema_accepts():
    """A label the map cannot record is a label that cannot be provenance."""
    schema = json.loads((SKILL_DIR / "schemas/known-results.schema.json").read_text())
    allowed = set(schema["definitions"]["source"]["properties"]["retrieval_method"]["enum"])
    tiers = plan("--arxiv", "1706.03762", mirrors="https://mirror.example/")
    labels = {t["retrieval_method"] for t in tiers}
    assert labels <= allowed, sorted(labels - allowed)


def test_an_arxiv_id_resolves_through_the_preprint_tier():
    tiers = plan("--arxiv", "1706.03762")
    preprint = [t for t in tiers if t["retrieval_method"] == "preprint"]
    assert preprint and "1706.03762" in json.dumps(preprint)
