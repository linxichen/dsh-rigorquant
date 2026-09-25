"""The blind roles are tool-denied, not just prompt-asked.

docs/architecture.md Decision 14 (C1, C2), carried onto Agent Teams by
Decision 24: the team plugin (`dsh/team.js`) reads a teammate's role from its
name and denies the blind roles (OffGridThinker, DoubleChecker) web_search,
web_fetch and `skill`, and the web-denied roles (the blind roles plus the
Adversary and Document adversary) web_search and web_fetch. No teammate can
create teammates at all (only the orchestrator holds `spawn_teammate`), so the
per-row delegation deny lists the classic preset carried have nothing left to
deny. The deny tables are pinned here against CONTEXT.md's glossary; what
each role actually SEES is observed through the team probe
(tests/test_team_plugin.py).

Because `skill` is denied, a blind role cannot load the rigorquant skill: its
persona file (`dsh/personas/<role>.md`) has to carry the derivation protocol
and the pinned compute lane itself.
"""

import re

from conftest import REPO, SKILL_DIR, preset_children

TEAM = REPO / "dsh/team.js"
PERSONAS = REPO / "dsh/personas"
BLIND = ("offgrid", "doublechecker")


def _js_set(name):
    m = re.search(r"const %s = new Set\(\[([^\]]*)\]\)" % name, TEAM.read_text())
    assert m, "dsh/team.js no longer declares %s" % name
    return set(re.findall(r"'([a-z-]+)'", m.group(1)))


def _js_list(name):
    m = re.search(r"const %s = \[([^\]]*)\]" % name, TEAM.read_text())
    assert m, "dsh/team.js no longer declares %s" % name
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def test_fetch_is_enabled():
    assert re.search(r"^    fetch: true\s*$", preset_children(), re.MULTILINE), \
        "tool-web fetch must be true so web_fetch exists for the lit roles"


def test_the_deny_tiers_match_the_glossary():
    """CONTEXT.md: blind = OffGridThinker + DoubleChecker; web-denied = the
    blind roles plus the Adversary and Document adversary."""
    assert _js_set("BLIND_ROLES") == set(BLIND)
    assert _js_set("WEB_DENIED_ROLES") == {"adversary", "doc-adversary"}
    assert _js_list("WEB_DENY") == {"web_search", "web_fetch"}
    team = TEAM.read_text()
    assert "[...EVERY_TEAMMATE_DENY, ...WEB_DENY, 'skill']" in team, (
        "the blind tier no longer denies web and skill")
    glossary = " ".join((REPO / "CONTEXT.md").read_text().split())
    assert "no web, no skills and nobody's draft: OffGridThinker, DoubleChecker" in glossary
    assert "the blind roles plus the Adversary and Document adversary" in glossary


def test_every_teammate_is_denied_the_orchestrator_owned_tools():
    """Decision 10: one study-level goal, root-owned; the unattended contract
    keeps ask_user_question and plan mode off every teammate."""
    assert _js_list("EVERY_TEAMMATE_DENY") == {
        "create_goal", "update_goal", "get_goal", "todo_write",
        "ask_user_question", "exit_plan_mode"}


def test_blind_personas_carry_the_protocol_they_cannot_load():
    """`skill` is denied for the blind roles, so they cannot read protocol.md.

    A five-line persona plus a denied `skill` tool is strictly less capable than
    what these roles had before the deny list existed; the derivation protocol
    has to travel in the persona itself.
    """
    for role in BLIND:
        persona = (PERSONAS / ("%s.md" % role)).read_text().lower()
        assert len(persona) > 800, (
            "%s persona is a stub (%d chars); it cannot load a skill, so the "
            "protocol must be in it" % (role, len(persona)))
        for required in ("counterexample",   # elimination rule
                         "cannot load",      # states its own blindness honestly
                         "exact remaining gap",  # terminal honesty
                         "seed"):            # stochastic convention
            assert required in persona, "%s persona never states %r" % (role, required)
        assert "load the `rigorquant` skill" not in persona, (
            "%s is told to load a skill it is denied" % role)


# The study's own lane (issue #36): the declaration is the tracked env/ at
# the study root, the venv and uv cache are scratch under interim/, and a
# teammate runs offline against the venv the orchestrator built at Step 2.
LANE_ENV = ('UV_PROJECT_ENVIRONMENT="$PWD/interim/venv" '
            'UV_CACHE_DIR="$PWD/interim/uv-cache"')
LANE_INVOCATION = "uv run --frozen --offline --project env"


def test_blind_personas_carry_the_pinned_compute_lane():
    """The blind lane's compute leverage must name the sanctioned invocation.

    Blind roles keep bash (C1), so derivation compute reaches them only
    through the study's pinned uv lane. Both blind personas must instruct the
    exact invocation SKILL.md Step 2 sanctions (from the study root, venv and
    cache under interim/, offline), and prohibit installs/fetches (the guard
    refuses the network verbs at the call, but the persona is what tells the
    role why). The shared $DSH_HOME template is not a lane a teammate runs
    against: the sandbox refuses a venv there, and it is not the record.
    """
    for role in BLIND:
        persona = " ".join((PERSONAS / ("%s.md" % role)).read_text().split())
        assert LANE_ENV in persona and LANE_INVOCATION in persona, \
            "%s persona lost the compute-lane invocation" % role
        assert "study root" in persona, "%s persona never says where to run it" % role
        assert "share/rigorquant/env" not in persona, \
            "%s persona still points at the shared template" % role
        assert "pip install" in persona and "uv sync" in persona, \
            "%s persona lost the no-install/no-fetch discipline" % role
    skill = " ".join((SKILL_DIR / "SKILL.md").read_text().split())
    assert LANE_ENV in skill and LANE_INVOCATION in skill, \
        "SKILL.md no longer documents the invocation the personas teach"
