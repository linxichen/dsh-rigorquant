"""Per-role tool budgets: the invariants a static deny list must keep.

Under Decision 24 every role's budget is a `tools.restrict({ deny })` the team
plugin (`dsh/team.js`) applies on the teammate's own scope, keyed by its name.
What each role then SEES is observed through the team probe
(tests/test_team_plugin.py); the tier tables are pinned against the glossary
in tests/test_blind_deny_list.py. This module keeps the two invariants that
are about the composition around them:

1. SPAWN SAFETY — a static deny list may only name tools the preset or the
   dsh-base host mounts in EVERY deployment. tools.restrict() throws on an
   unknown name ("names unknown global tool"), so a plugin-optional name in a
   shipped deny list (ssh_*, import_*, third-party image tools) would break
   composition for every teammate on any machine without that plugin. The
   scoped Team tools (`send_message`, `list_agents`, `team_task_*`,
   `spawn_teammate`, …) are not global and cannot be restricted at all —
   that is the guard's job — so they may not appear either.
2. NO UNSCOPED SPAWNERS — fork, workflow and ralph mint children the team
   plugin never composes (no name, no persona, no budget), so their rows stay
   disabled.

Parser caveat: the composition is read by structural convention (see
conftest), not with a yaml parser — the test venv has no yaml module and the
file embeds `!!js` runtime expressions.
"""

import re

from conftest import REPO, composition_rows, is_disabled, preset_children

# Global tools mounted for EVERY deployment that runs this preset: the
# preset's own rows plus the dsh-base host composition. Deliberately NOT here:
# pwsh (win32-gated), structured_output (child-scoped), everything
# plugin-optional, and the Team tools (registered per member scope, never
# global, so `tools.restrict` cannot name them).
GUARANTEED = frozenset({
    # shell + filesystem (preset tool-bash/tool-fs/tool-fs-search rows)
    "bash", "read", "write", "edit", "glob", "grep",
    # retrieval + procedure (preset tool-web row with fetch: true, tool-skill)
    "web_search", "web_fetch", "skill",
    # background compute (preset tool-jobs row; bash run_in_background needs them)
    "job_output", "job_kill", "job_list",
    # orchestrator-owned state (goal rows, tool-todo, tool-ask-user, plan mode)
    "create_goal", "update_goal", "get_goal", "todo_write",
    "ask_user_question", "exit_plan_mode",
})


def _team_deny_names():
    team = (REPO / "dsh/team.js").read_text()
    names = set()
    for const in ("EVERY_TEAMMATE_DENY", "WEB_DENY"):
        m = re.search(r"const %s = \[([^\]]*)\]" % const, team)
        assert m, "dsh/team.js no longer declares %s" % const
        names |= set(re.findall(r"'([a-z_]+)'", m.group(1)))
    # The blind tier appends `skill` inline.
    names |= set(re.findall(r"\.\.\.WEB_DENY, '([a-z_]+)'", team))
    return names


def test_every_static_deny_name_is_guaranteed_mounted():
    """Spawn safety: no shipped deny list may name a plugin-optional tool."""
    names = _team_deny_names()
    assert "skill" in names, "the blind tier's inline `skill` deny was not found"
    unknown = sorted(names - GUARANTEED)
    assert not unknown, (
        "dsh/team.js denies tools outside the guaranteed-mounted global "
        "universe: %r. A static deny of a plugin-optional tool throws at "
        "composition; a scoped Team tool belongs to the guard." % unknown)


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
