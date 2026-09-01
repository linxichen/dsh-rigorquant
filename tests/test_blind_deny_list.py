"""Delegation-denial is tool-denied, not just prompt-asked.

docs/architecture.md Decision 14 (C1, C2): the blind roles (ground-truth oracle,
novel explorer) must deny web_search, web_fetch, skill, and every delegation
tool in the composition itself, and every other role that denies delegation
(literature line/adversary, document adversary) must deny the same delegation
set. This is the one piece of the lane's isolation that IS enforceable; the
residual bash-curl and filesystem holes are documented as procedural, and named
as such under Decision 14.

`BLIND_TOOLS` must name every delegation tool the composition can mount — a
new delegation row whose toolName is absent here silently re-opens C2 for every
previously blind child. The self-name is included on purpose (each row denies
its own toolName too), mirroring the shipped deny lists.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORDIS = REPO / "agent-presets/rigorquant/agent.cordis.yml"

BLIND_TOOLS = {
    "web_search", "web_fetch", "skill",
    "subagent", "subagent_ground_truth", "subagent_adversary",
    "subagent_novel", "subagent_lit_line", "subagent_lit_adversary",
    "subagent_document_adversary",
    "subagent_fork", "workflow", "ralph",
}
DELEGATION = BLIND_TOOLS - {"web_search", "web_fetch", "skill"}

# Tools only the root orchestrator may touch. Children get them mounted by the
# shared composition, so each role's deny list must name them explicitly.
ORCHESTRATOR_TOOLS = {
    "workflow", "ralph",                                # fan-out loops
    "send_message", "interrupt_agent", "list_agents",   # child-control
    "create_goal", "update_goal", "get_goal",           # Decision 10: one task-level goal
    "todo_write",                                       # Decision 10
    "ask_user_question",                                # unattended contract
    "exit_plan_mode",                                   # children are never in plan mode
}


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
    has to travel in the persona itself.
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


def test_document_adversary_is_delegation_denied():
    """The document adversary audits local deliverables: no web, no delegation."""
    text = CORDIS.read_text()
    doc_rows = {rn: _deny(b) for rn, b in _rows(text)
                if _tool_name(b) == "subagent_document_adversary"}
    assert set(doc_rows) == {"tool-subagent-doc-adversary"}, \
        "the document-adversary row must exist"
    for row_id, denied in doc_rows.items():
        missing = sorted(DELEGATION - denied)
        assert not missing, "%s is missing from its delegation deny list: %s" % (row_id, missing)
        assert "web_search" in denied and "web_fetch" in denied, \
            "%s must keep web_search/web_fetch denied" % row_id


def test_explorer_is_delegation_denied_and_child_scoped():
    """The open-track explorer keeps web and `skill`, and nothing orchestrator-owned.

    The method track is open (web stays for known-result checks; the novelty
    toggle lives on the separate subagent_novel row), and `skill` stays because
    the rigorquant skill carries the working procedure. Everything else the
    root owns is denied: delegation, orchestration loops, child-control, task
    state, ask_user_question, plan mode.
    """
    text = CORDIS.read_text()
    explorer_rows = {rn: _deny(b) for rn, b in _rows(text) if _tool_name(b) == "subagent"}
    assert set(explorer_rows) == {"tool-subagent"}, "the explorer row must exist"
    for row_id, denied in explorer_rows.items():
        missing = sorted(DELEGATION - denied)
        assert not missing, "%s is missing from its delegation deny list: %s" % (row_id, missing)
        missing = sorted(ORCHESTRATOR_TOOLS - denied)
        assert not missing, "%s is missing from its child-scope deny list: %s" % (row_id, missing)
        for kept in ("web_search", "web_fetch", "skill"):
            assert kept not in denied, "%s must keep %s (open track)" % (row_id, kept)


def test_blind_deny_sets_carry_every_delegation_row():
    """BLIND_TOOLS must name every delegation toolName the composition mounts.

    A new delegation row that forgets to extend this set (and the shipped deny
    lists with it) silently re-opens Decision 14's C2 for every previously
    blind child: the tool stays in the catalog at depth 1.
    """
    text = CORDIS.read_text()
    mounted = {_tool_name(b) for _, b in _rows(text)
               if _tool_name(b) is not None and "provider: spawn" in b}
    delegation_rows = {name for name in mounted if name.startswith("subagent")}
    missing_from_set = sorted(delegation_rows - DELEGATION)
    assert not missing_from_set, (
        "delegation toolName(s) %r are mounted by the composition but absent "
        "from BLIND_TOOLS/DELEGATION; extend the set and every delegation "
        "deny list" % missing_from_set)
