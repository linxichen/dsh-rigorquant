"""Per-role tool budgets: the invariants the explicit classification must keep.

Under Decision 24 every role's budget is a `tools.restrict({ allow })` the team
plugin (`dsh/team.js`) applies on the teammate's own scope, keyed by its name.
What each role then SEES is observed through the team probe
(tests/test_team_plugin.py); the tier tables are pinned against the glossary
in tests/test_blind_deny_list.py. This module keeps the invariants that are
about the composition around them:

1. SPAWN SAFETY — an allow list may only name tools the preset or the
   dsh-base host mounts in EVERY deployment (or the one platform-gated row,
   `pwsh`, which `allowListFor` filters out where it is not mounted).
   `tools.restrict()` throws on an unknown name ("names unknown global
   tool"), so a plugin-optional name in a shipped allow set would break
   composition for every teammate on any machine without that plugin. The
   classification is the only source of a teammate's visible catalog, so a
   typo must fail here rather than silently narrow a role.
2. ONE SOURCE OF SCOPE — the per-tier allow sets are the whole classification.
   There is no second, exported every-teammate deny list that a reader or a
   test could mistake for the enforcement; the module's exported surface is
   pinned so a retired list cannot come back beside the tiers.
3. NO UNSCOPED SPAWNERS — fork, workflow and ralph mint children the team
   plugin never composes (no name, no persona, no budget), so their rows stay
   disabled.

Parser caveat: the composition is read by structural convention (see
conftest), not with a yaml parser — the test venv has no yaml module and the
file embeds `!!js` runtime expressions.
"""

import json
import shutil
import subprocess

import pytest

from conftest import REPO, composition_rows, is_disabled, preset_children

# Global tools mounted for EVERY deployment that runs this preset: the
# preset's own rows plus the dsh-base host composition. Deliberately NOT here:
# pwsh (win32-gated; `allowListFor` filters it where absent), structured_output
# (child-scoped), everything plugin-optional, and the Team tools registered
# per member scope.
GUARANTEED = frozenset({
    # shell + filesystem (preset tool-bash/tool-fs/tool-fs-search rows, also
    # base-mounted: read_image comes from tool-fs)
    "bash", "read", "write", "edit", "read_image", "glob", "grep",
    # 0.2.1's dsh-base host plane mounts `working_directory` for every
    # deployment; a teammate is denied it by Decision 27 (seam S7).
    "working_directory",
    # retrieval + procedure (preset tool-web row with fetch: true, tool-skill)
    "web_search", "web_fetch", "skill",
    # background compute (preset tool-jobs row; bash run_in_background needs them)
    "job_output", "job_kill", "job_list",
    # messaging + shared board: base tool-subagent-control and tool-agent-team
    "send_message", "wait_agent",
    "team_task_create", "team_task_get", "team_task_update",
    # deliverables: only this preset mounts tool-present
    "present",
    # orchestrator-owned state (goal rows, tool-todo, tool-ask-user, plan mode)
    "create_goal", "update_goal", "get_goal", "todo_write",
    "ask_user_question", "exit_plan_mode",
})

# The one platform-gated allow name: mounted on win32 (and only there), so
# the classification carries it and `allowListFor` drops it elsewhere.
PLATFORM_GATED = frozenset({"pwsh"})


def _classification():
    """The module's own classification data, through a real import."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to import dsh/team.js")
    module = REPO / "dsh/team.js"
    code = (
        "import(process.argv[1]).then((m) => process.stdout.write(JSON.stringify({"
        "keys: Object.keys(m).sort(), tiers: m.TEAMMATE_ALLOW_BY_TIER})))"
        ".catch((error) => { process.stderr.write(String(error)); process.exit(1) })"
    )
    out = subprocess.run([node, "-e", code, module.as_uri()],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_every_classified_allow_name_is_guaranteed_mounted():
    """Spawn safety: no shipped allow set may name a plugin-optional tool."""
    tiers = _classification()["tiers"]
    assert set(tiers) == {"open", "webDenied", "blind"}, tiers
    names = set()
    for tier, allow in tiers.items():
        assert allow, "the %s tier is empty" % tier
        names |= set(allow)
    assert "skill" in names, "the classification lost the skill tool"
    unknown = sorted(names - GUARANTEED - PLATFORM_GATED)
    assert not unknown, (
        "dsh/team.js allows tools outside the guaranteed-mounted global "
        "universe: %r. A static allow of a plugin-optional tool throws at "
        "composition; a scoped Team tool belongs to the guard/denial list."
        % unknown)


def test_the_module_exports_no_second_scope_source():
    """The tier tables are the only classification this module exposes.

    0.8.0 shipped an exported every-teammate deny list next to the composition
    even though a global deny mask cannot reach the scope-registered Team
    tools; 0.8.1 deleted it and made the allow classification the only source
    of a teammate's visible catalog. The export set is pinned so a second list
    cannot reappear as an "audit list" a reader or a test would treat as the
    enforcement.
    """
    keys = _classification()["keys"]
    assert keys == [
        "TEAMMATE_ALLOW_BY_TIER", "TEAMMATE_ROLES", "apply",
        "classificationFor", "inject", "name", "roleFromName", "tierOf",
    ], keys


def test_the_orchestrator_owned_tools_are_absent_from_every_tier():
    """Decision 10/24/27 tools are denied by not being classified at all.

    working_directory (Decision 27 S7), the study goal and todo (Decision 10),
    the unattended contract, the roster and board listings (Decision 24),
    interruption (the shipped configs leave it off) and delegation itself are
    absent from every allow set. Absence is the enforcement; nothing has to
    name them as denied.
    """
    tiers = _classification()["tiers"]
    for required in ("working_directory", "create_goal", "update_goal", "get_goal",
                     "todo_write", "ask_user_question", "exit_plan_mode",
                     "list_agents", "team_task_list", "interrupt_agent",
                     "subagent", "subagent_fork"):
        assert all(required not in allow for allow in tiers.values()), (
            "a tier still allows the orchestrator-owned tool %r" % required)


def test_the_tiers_narrow_from_open_to_blind():
    tiers = {tier: set(allow) for tier, allow in _classification()["tiers"].items()}
    assert tiers["blind"] < tiers["webDenied"] < tiers["open"]
    assert "skill" in tiers["webDenied"] and "skill" not in tiers["blind"]
    assert {"web_search", "web_fetch"} <= tiers["open"]
    assert not {"web_search", "web_fetch"} & tiers["webDenied"]


def test_untagged_spawner_rows_are_disabled():
    """fork/workflow/ralph cannot mint uncomposed children in this preset.

    Their children carry no `<role>-<n>` name (the team plugin never composes
    them, the router never routes them), and for workflow `agent()` calls
    neither a persona nor a per-child budget is expressible. 74 of the 162
    children in the 0.4.x study logs were untagged workers wearing the root
    persona with the full catalog. The fork row is gone entirely under
    Decision 24; the others stay disabled.
    """
    rows = dict(composition_rows(preset_children()))
    assert "tool-subagent-fork" not in rows
    for row_id in ("workflow-ptc", "tool-workflow", "tool-ralph"):
        assert row_id in rows, "the preset lost the disabled %s row" % row_id
        assert is_disabled(rows[row_id]), (
            "%s must stay disabled: it mints uncomposed children" % row_id)
