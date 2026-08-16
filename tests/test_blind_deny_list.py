"""The blind novel lane is tool-denied, not just prompt-asked.

Decision 14 / docs/literature-lane.md §5: the ground-truth oracle and the novel
explorer must deny web_search, web_fetch, skill, and every delegation tool in
the composition itself. This is the one piece of the lane's isolation that IS
enforceable; the residual bash-curl and filesystem holes are documented as
procedural (docs/literature-lane.md §13).
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORDIS = REPO / "agent-presets/rigorquant/agent.cordis.yml"

BLIND_TOOLS = {
    "web_search", "web_fetch", "skill",
    "subagent", "subagent_ground_truth", "subagent_adversary",
    "subagent_novel", "subagent_lit_line", "subagent_lit_adversary",
    "subagent_fork", "workflow", "ralph",
}
DELEGATION = BLIND_TOOLS - {"web_search", "web_fetch", "skill"}


def _rows(text):
    """Yield (row_id, body) for every 4-space-indented composition row."""
    for part in re.split(r"\n    - id: ", text)[1:]:
        row_id = part.split("\n", 1)[0].strip()
        yield row_id, part


def _tool_name(body):
    m = re.search(r"toolName:\s*(\S+)", body)
    return m.group(1) if m else None


def _deny(body):
    m = re.search(r"deny:\s*\[([^\]]*)\]", body)
    if not m:
        return set()
    return {t.strip() for t in m.group(1).split(",") if t.strip()}


def test_fetch_is_enabled():
    assert re.search(r"^    fetch: true\s*$", CORDIS.read_text(), re.MULTILINE), \
        "tool-web fetch must be true so web_fetch exists for the lit roles"


def test_blind_roles_deny_web_skill_and_delegation():
    text = CORDIS.read_text()
    blind_rows = {rn: _deny(b) for rn, b in _rows(text)
                  if _tool_name(b) in ("subagent_ground_truth", "subagent_novel")}
    assert set(blind_rows) == {"tool-subagent-ground-truth", "tool-subagent-novel"}, \
        "both blind rows must exist"
    for row_id, denied in blind_rows.items():
        missing = sorted(BLIND_TOOLS - denied)
        assert not missing, "%s is missing from its deny list: %s" % (row_id, missing)


def _persona(body):
    m = re.search(r"persona: >-\n(.*?)\n(?=\s{8}\S|\s{4}- id:)", body, re.DOTALL)
    return m.group(1) if m else ""


def test_blind_personas_carry_the_protocol_they_cannot_load():
    """`skill` is denied for the blind roles, so they cannot read protocol.md.

    A five-line persona plus a denied `skill` tool is strictly less capable than
    what these roles had before the deny list existed; the derivation protocol
    has to travel in the persona itself (docs/literature-lane.md §5).
    """
    text = CORDIS.read_text()
    for row_id, body in _rows(text):
        if _tool_name(body) not in ("subagent_ground_truth", "subagent_novel"):
            continue
        persona = _persona(body).lower()
        assert len(persona) > 800, (
            "%s persona is a stub (%d chars); it cannot load a skill, so the "
            "protocol must be in it" % (row_id, len(persona)))
        for required in ("counterexample",   # elimination rule
                         "cannot load",      # states its own blindness honestly
                         "exact remaining gap",  # terminal honesty
                         "seed"):            # stochastic convention
            assert required in persona, "%s persona never states %r" % (row_id, required)
        assert "load the `rigorquant` skill" not in persona, (
            "%s is told to load a skill it is denied" % row_id)


def test_lit_roles_are_delegation_denied_leaves_that_keep_web():
    text = CORDIS.read_text()
    lit_rows = {rn: _deny(b) for rn, b in _rows(text)
                if _tool_name(b) in ("subagent_lit_line", "subagent_lit_adversary")}
    assert set(lit_rows) == {"tool-subagent-lit-line", "tool-subagent-lit-adversary"}, \
        "both literature rows must exist"
    for row_id, denied in lit_rows.items():
        missing = sorted(DELEGATION - denied)
        assert not missing, "%s is missing from its delegation deny list: %s" % (row_id, missing)
        assert "web_search" not in denied and "web_fetch" not in denied, \
            "%s must keep web_search/web_fetch for retrieval" % row_id
