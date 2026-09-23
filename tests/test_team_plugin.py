"""Team composition (dsh/team.js) — Agent Teams composition AND per-call guard.

DSH 0.1.6 ships native Agent Teams. This host half applies each teammate's
role composition — persona, tool-tier budget, and (on the Lead) a runtime
fact that the guard is armed — purely from the teammate's NAME
(`<role>-<n>`, e.g. `doublechecker-1`), resolved through the harness's
`agentTeams` service. It is purely additive: the classic `[[rq:role=...]]`
tag mechanism (dsh/index.js) and the seven classic delegation rows
(agent-presets/rigorquant/agent.cordis.yml) are untouched and coexist with
this module until a later issue removes them.

`tools.restrict` cannot mask the scoped Team tools (`send_message`,
`list_agents`, `team_task_list`, `team_task_get`, `team_task_update`,
`spawn_teammate`), so topology-by-guard (docs/architecture.md, Decision 24)
is `tools.guard`, registered per-agent alongside the restriction: hub-and-
spoke messaging (a teammate may message only the Lead), roster/board
blindness (`list_agents`/`team_task_list` denied outright), own-task-only
board access (`team_task_get`/`team_task_update` read live ownership
through the service), the bash network-verb denial for web-denied roles,
and the orchestrator's `spawn_teammate` name/fork refusal.

These checks pin the load-bearing properties against a real execution of the
module (via tests/team_probe.cjs, not by re-implementing it in Python):

1. persona composition — a teammate's role persona lands at the harness's
   own `deployment:persona-prefix` slot, first, and its tool catalog is
   restricted by tier;
2. the Lead gets a distinct "RigorQuant team guard: armed" runtime CONTEXT
   (not a persona section — see dsh/team.js's module header for why);
3. an unparseable teammate name, and a non-RigorQuant team, are both
   silently untouched (no section, no restriction, no guard);
4. every `agent/created` source re-applies composition from scratch (proven
   via a resume-sourced re-creation: the first registration is disposed and
   a fresh one takes its place, not skipped as a no-op);
5. `agentTeams` absent -> one warning, no armed context anywhere;
6. the module never imports the experimental Agent Teams packages and never
   declares `agentTeams` a hard dependency;
7. the per-call guard table, driven with fake calls through every rule:
   sibling `send_message` denied / Lead allowed; `list_agents`/
   `team_task_list` denied; a foreign task's `team_task_get`/
   `team_task_update` denied, an unowned or own task allowed; a bash
   network verb denied for a web-denied role and allowed for an open role;
   a bad `spawn_teammate` name or `context: 'fork'` denied on the Lead.
8. a session composed as rigorquant only AFTER its own `agent/created`
   already ran (found live against the installed 0.1.6-alpha.2 harness,
   docs/upgrade-0.1.6.md §3.11 — a "New Session" switched to the RigorQuant
   preset in the picker, rather than created with it already selected)
   still gets the Lead's guard-armed context and `spawn_teammate` guard,
   via a second trigger on `agent-preset/selected`.
"""

import json
import re
import shutil
import subprocess

import pytest

from conftest import REPO

PROBE = REPO / "tests/team_probe.cjs"


def manifest():
    return json.loads((REPO / "package.json").read_text())


@pytest.fixture(scope="module")
def probe():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the team plugin")
    module = REPO / manifest()["exports"]["./team"]
    if not module.exists():
        pytest.fail(f"package.json exports ./team but {module} is missing")
    out = subprocess.run([node, str(PROBE), str(module)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_team_export_points_at_a_shipped_file():
    assert (REPO / manifest()["exports"]["./team"]).is_file()


def test_the_plugin_mounts_without_error(probe):
    assert probe["mountError"] is None, probe.get("mountError")


def test_doublechecker_gets_its_persona_under_the_persona_prefix_section(probe):
    sections = probe["present"]["doublechecker1"]["sections"]
    assert len(sections) == 1
    assert sections[0]["name"] == "deployment:persona-prefix"
    assert sections[0]["order"] == 0
    assert "DoubleChecker" in sections[0]["text"]


def test_doublechecker_loses_web_skill_and_every_teammate_tools(probe):
    restricts = probe["present"]["doublechecker1"]["restricts"]
    assert len(restricts) == 1
    deny = set(restricts[0]["deny"])
    assert deny == {
        "create_goal", "update_goal", "get_goal", "todo_write",
        "ask_user_question", "exit_plan_mode", "web_search", "web_fetch", "skill",
    }


def test_explorer_keeps_web_and_skill_but_loses_the_every_teammate_tools(probe):
    restricts = probe["present"]["explorer1"]["restricts"]
    assert len(restricts) == 1
    deny = set(restricts[0]["deny"])
    assert deny == {
        "create_goal", "update_goal", "get_goal", "todo_write",
        "ask_user_question", "exit_plan_mode",
    }
    assert "web_search" not in deny and "skill" not in deny


def test_adversary_is_web_denied_but_keeps_skill(probe):
    restricts = probe["present"]["adversary1"]["restricts"]
    assert len(restricts) == 1
    deny = set(restricts[0]["deny"])
    assert "web_search" in deny and "web_fetch" in deny
    assert "skill" not in deny


def test_an_unparseable_teammate_name_is_skipped_silently(probe):
    entry = probe["present"]["unparseableName"]
    assert entry == {"sections": [], "contexts": [], "restricts": [], "guardCount": 0}


def test_a_non_rigorquant_team_is_never_touched(probe):
    entry = probe["present"]["nonRigorQuantTeammate"]
    assert entry == {"sections": [], "contexts": [], "restricts": [], "guardCount": 0}


def test_the_lead_gets_the_armed_guard_line_as_a_context_not_a_section(probe):
    lead = probe["present"]["lead"]
    assert lead["sections"] == []
    assert len(lead["contexts"]) == 1
    context = lead["contexts"][0]
    assert context["name"] == "rq-team:guard-armed"
    assert context["text"] == "RigorQuant team guard: armed"


def test_reapplication_on_a_resume_sourced_creation(probe):
    resume = probe["resume"]
    assert len(resume["firstSections"]) == 1
    assert resume["disposedAfterResume"] == ["deployment:persona-prefix"]
    assert len(resume["secondSections"]) == 1


def test_when_agent_teams_is_absent_a_warning_is_logged_and_no_armed_context_appears(probe):
    absent = probe["absent"]
    assert len(absent["warnings"]) == 1
    assert "agentTeams" in absent["warnings"][0]
    assert absent["leadContexts"] == []


def test_every_composed_member_registers_exactly_one_guard(probe):
    """Restriction alone cannot reach the scoped Team tools; every composed
    member (teammate or Lead) must also register a `tools.guard`."""
    present = probe["present"]
    for member in ("lead", "doublechecker1", "explorer1", "adversary1"):
        assert present[member]["guardCount"] == 1, f"{member} did not register a guard"


# ── topology by guard: a fake call driven through every per-call rule ──────


def test_hub_and_spoke_denies_a_sibling_and_allows_the_lead(probe):
    checks = probe["guardChecks"]
    assert isinstance(checks["siblingMessageDenied"], str)
    assert checks["leadMessageAllowed"] is None


def test_every_teammate_is_roster_and_board_blind(probe):
    checks = probe["guardChecks"]
    assert isinstance(checks["listAgentsDenied"], str)
    assert isinstance(checks["taskListDenied"], str)


def test_a_teammate_touches_only_its_own_task(probe):
    checks = probe["guardChecks"]
    assert checks["ownTaskGetAllowed"] is None
    assert isinstance(checks["foreignTaskGetDenied"], str)
    assert checks["unownedTaskClaimAllowed"] is None, (
        "an unclaimed task must stay reachable, or team_task_update(action: "
        "'claim') could never succeed")
    assert isinstance(checks["foreignTaskUpdateDenied"], str)


def test_bash_network_verbs_are_denied_for_web_denied_roles_and_allowed_for_open_roles(probe):
    checks = probe["guardChecks"]
    assert isinstance(checks["blindBashCurlDenied"], str)
    assert isinstance(checks["webDeniedBashWgetDenied"], str)
    assert checks["openRoleBashCurlAllowed"] is None
    assert checks["blindBashPlainAllowed"] is None, (
        "the guard must gate on the network verb, not deny bash outright")


def test_the_orchestrator_spawn_teammate_guard_refuses_bad_names_and_fork(probe):
    checks = probe["guardChecks"]
    assert isinstance(checks["spawnBadNameDenied"], str)
    assert isinstance(checks["spawnForkDenied"], str)
    assert checks["spawnFreshRoleAllowed"] is None


# ── a session composed as rigorquant only after its own agent/created ──────


def test_a_late_preset_switch_gets_no_composition_until_the_switch_lands(probe):
    """Before `agent-preset/selected` fires, the session was still on its
    original (non-rigorquant) preset when `agent/created` ran — this module
    correctly stayed silent, matching every other non-rigorquant agent."""
    before = probe["latePresetSelection"]["beforeSwitch"]
    assert before == {"sections": [], "contexts": [], "restricts": [], "guardCount": 0}


def test_a_late_preset_switch_to_rigorquant_installs_the_lead_composition(probe):
    """Once `agent-preset/selected` announces the switch (after the harness's
    own recompose already landed on agent.ctx), the Lead gets exactly what it
    would have gotten from a same-preset agent/created: the armed context and
    its spawn_teammate guard — found missing live on the installed harness
    (docs/upgrade-0.1.6.md §3.11) before this second trigger existed."""
    after = probe["latePresetSelection"]["afterSwitch"]
    assert after["sections"] == []
    assert after["guardCount"] == 1
    assert len(after["contexts"]) == 1
    context = after["contexts"][0]
    assert context["name"] == "rq-team:guard-armed"
    assert context["text"] == "RigorQuant team guard: armed"


def test_the_patch_registers_the_team_row():
    """The bundle patch must actually mount dsh/team.js — a row that exists
    only in package.json exports never runs."""
    patch = (REPO / "cordis.patch.yml").read_text()
    assert "rq-team" in patch
    assert "dsh-rigorquant/team" in patch


def test_the_team_module_declares_agent_teams_optional():
    """agentTeams must never be a hard dependency, and the module must never
    import any of the experimental Agent Teams packages directly (prose
    comments may still name them, explaining what not to import)."""
    source = (REPO / "dsh" / "team.js").read_text()
    match = re.search(r"const inject = \[([^\]]*)\]", source)
    assert match, "dsh/team.js no longer exports a plain `inject` array"
    injected = set(re.findall(r"'([a-zA-Z]+)'", match.group(1)))
    assert "agentTeams" not in injected
    imports = re.findall(r"^\s*import .*from\s+'([^']+)'", source, re.M)
    imports += re.findall(r"require\(\s*'([^']+)'\s*\)", source)
    assert not any("dsh-experimental" in spec for spec in imports), imports
