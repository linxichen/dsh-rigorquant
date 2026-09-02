"""Per-role tool budgets, asserted as the VISIBLE catalog each child sees.

test_blind_deny_list.py pins what each delegation row DENIES. This module pins
the other half and the more meaningful one: what a spawn child of each role
actually SEES in its request. The child catalog is simulated the way
applyChildComposition composes it (packages/subagent/src/child-agent.ts): the
mounted universe restricted by the row's toolFilter deny list.

Three invariants are asserted, in descending order of importance:

1. SPAWN SAFETY — a static deny list may only name tools the preset or the
   dsh-base host mounts in EVERY deployment. tools.restrict() throws on an
   unknown name at child creation (core/tools restrict(): "names unknown
   global tool"), so a plugin-optional name in a shipped deny list (ssh_*,
   import_*, third-party image tools) would break every delegation on any
   machine without that plugin. Plugin-optional noise is the barebone
   assembly filter's job, never a static list's.
2. EXACT BUDGETS — each landed role's visible set is asserted EQUAL to the
   budget table below, over the guaranteed universe. Adding a deny name,
   dropping one, or mounting a new guaranteed tool surfaces as a test diff
   instead of a silent catalog change. Roles are pinned here as their budgets
   land on the feature branch; unlanded roles are covered only by the
   universal invariants.
3. UNIVERSAL CHILD SCOPE — every delegation child, landed or not: no
   delegation tools, and report + bash visible (report is the delivery
   channel; bash is C1's kept capability for the blind lane and the compute
   lane for everyone else). The orchestrator-owned set joins this floor when
   the last persona's budget lands.

Parser caveat: like test_blind_deny_list.py this module reads the composition
by structural convention (see conftest), not with a yaml parser — the test
venv has no yaml module and the file embeds `!!js` runtime expressions.
"""

from conftest import (CORDIS, DELEGATION, ORCHESTRATOR_TOOLS, composition_rows,
                      deny_of, tool_name_of)

# Tools mounted for EVERY deployment that runs this preset: the preset's own
# rows plus the dsh-base host composition (fs, jobs, web, skill registry,
# goals, todo, ask-user, plan mode, subagent control, subagent report).
# Deliberately NOT here: pwsh (win32-gated), structured_output (child-scoped,
# structured workflow runs only), and everything plugin-optional.
GUARANTEED = frozenset({
    # shell + filesystem (preset tool-bash/tool-fs/tool-fs-search rows)
    "bash", "read", "write", "edit", "glob", "grep",
    # delivery (host tool-subagent-report)
    "report",
    # retrieval + procedure (preset tool-web row with fetch: true, tool-skill)
    "web_search", "web_fetch", "skill",
    # background compute (preset tool-jobs row; bash run_in_background needs them)
    "job_output", "job_kill", "job_list",
    # orchestrator-owned state and channels
    "create_goal", "update_goal", "get_goal", "todo_write",
    "ask_user_question", "exit_plan_mode",
    "send_message", "interrupt_agent", "list_agents",
    # orchestration loops (preset tool-workflow / tool-ralph rows)
    "workflow", "ralph",
    # delegation (the preset's own spawn rows)
    "subagent", "subagent_ground_truth", "subagent_adversary",
    "subagent_novel", "subagent_lit_line", "subagent_lit_adversary",
    "subagent_document_adversary", "subagent_fork",
})

# toolName -> the exact visible set a spawned child of that role must see.
# Kept sets, not deny sets: a budget change is a reviewable diff in this table.
# A role enters this table only when its budget lands through persona review;
# until then it is covered by the universal invariants below. (Oracle/novel
# are next: their proposal is the blind lane minus the orchestrator-owned set.)
BUDGETS = {
    # explorer: open track — web for known-result checks; skill carries the
    # working procedure.
    "subagent": GUARANTEED - (DELEGATION | ORCHESTRATOR_TOOLS),
    # adversary: web-blind verdict (a cited page would enter the PASS gate
    # unaudited); skill stays (the check battery lives there).
    "subagent_adversary": GUARANTEED - (DELEGATION | ORCHESTRATOR_TOOLS
                                        | {"web_search", "web_fetch"}),
}

# Roles whose budgets are landed and therefore pinned EXACTLY by this module.
LANDED_BUDGETS = frozenset(BUDGETS)

BLIND_LANED = {"subagent_ground_truth", "subagent_novel"}


def _spawn_rows(text):
    """(row_id, toolName, visible) for every spawn delegation row with a filter."""
    for row_id, body in composition_rows(text):
        name = tool_name_of(body)
        if name is None or name not in DELEGATION or "provider: spawn" not in body:
            continue
        visible = GUARANTEED - deny_of(body)
        yield row_id, name, visible


def _composition():
    return CORDIS.read_text()


def test_every_static_deny_name_is_guaranteed_mounted():
    """Spawn safety: no shipped deny list may name a plugin-optional tool.

    tools.restrict() throws on unknown names at child creation, so one
    plugin-optional name (ssh_exec, import_chatgpt, ...) in a shipped deny
    list breaks EVERY delegation on machines without that plugin. This is the
    invariant that forces the static/dynamic split the budgets rely on.
    """
    unknown = {}
    for row_id, body in composition_rows(_composition()):
        denied = deny_of(body)
        if not denied:
            continue
        missing = sorted(denied - GUARANTEED)
        if missing:
            unknown[row_id] = missing
    assert not unknown, (
        "deny list(s) name tools outside the guaranteed-mounted universe: %r. "
        "A static deny of a plugin-optional tool throws at child spawn; move "
        "it to the barebone assembly filter." % unknown)


def test_landed_roles_see_exactly_their_budget():
    """Each landed role's visible catalog equals its budget, name by name."""
    text = _composition()
    seen = {}
    for row_id, name, visible in _spawn_rows(text):
        if name not in BUDGETS:
            continue
        budget = BUDGETS[name]
        extra = sorted(visible - budget)
        lacked = sorted(budget - visible)
        assert not extra and not lacked, (
            "%s (%s) visible catalog drifted: sees %r, missing %r "
            "(expected the pinned budget; update BUDGETS only through review)"
            % (row_id, name, extra, lacked))
        seen[name] = row_id
    assert set(seen) == set(BUDGETS), (
        "budgeted role(s) %r have no spawn row (or no toolFilter) in the "
        "composition" % sorted(set(BUDGETS) - set(seen)))


def test_every_delegation_child_is_child_scoped():
    """Universal floor for every spawn child, landed or not.

    Delegation must be catalog-invisible everywhere (C2 is not depth-only),
    and every child keeps its delivery channel (report) and its compute lane
    (bash, C1). The orchestrator-owned set is asserted per role as each
    budget lands; it becomes part of this universal floor when the last
    persona lands.
    """
    text = _composition()
    leaked = {}
    for row_id, name, visible in _spawn_rows(text):
        forbidden = DELEGATION & visible
        if forbidden:
            leaked[row_id] = sorted(forbidden)
        assert "report" in visible, "%s lost the report channel" % row_id
        assert "bash" in visible, "%s lost bash (C1 compute lane)" % row_id
    assert not leaked, (
        "spawn child(ren) still see delegation tools: %r" % leaked)
    rows = {name for _, name, _ in _spawn_rows(text)}
    assert LANDED_BUDGETS <= rows, (
        "landed role(s) %r missing from the composition" % sorted(LANDED_BUDGETS - rows))


def test_blind_lane_sees_no_web_and_no_skill():
    """C1/C2 for the visible catalog: the blind lane is blind in its request."""
    for row_id, name, visible in _spawn_rows(_composition()):
        if name not in BLIND_LANED:
            continue
        leaked = sorted({"web_search", "web_fetch", "skill"} & visible)
        assert not leaked, "%s (%s) leaks blind-lane capabilities: %r" % (row_id, name, leaked)
