"""Team composition (dsh/team.js) — Agent Teams composition AND per-call guard.

DSH 0.1.6 ships native Agent Teams. This host half applies each teammate's
role composition — persona, tool-tier budget, and (on the Lead) a runtime
fact that the guard is armed — purely from the teammate's NAME
(`<role>-<n>`, e.g. `doublechecker-1`), resolved through the harness's
`subagents` identity service (`rootOf`/`namesOf`; 0.2.2 removed the Team
service's membership/roster API). It is purely additive: the classic
`[[rq:role=...]]`
tag mechanism (dsh/index.js) and the seven classic delegation rows
(agent-presets/rigorquant/agent.cordis.yml) are untouched and coexist with
this module until a later issue removes them.

`tools.restrict` cannot mask the scoped Team tools (`send_message`,
`list_agents`, `team_task_list`, `team_task_get`, `team_task_update`,
`team_task_create`), so topology-by-guard (docs/architecture.md, Decision
24) is `tools.guard`, registered per-agent alongside the restriction:
hub-and-spoke messaging (a teammate may message only the Lead), roster/board
blindness (`list_agents`/`team_task_list` denied outright), own-task-only
board access (`team_task_get`/`team_task_update` read live ownership
through the service), the bash network-verb denial for web-denied roles,
and the orchestrator's `subagent` name / `subagent_fork` refusal.

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
   already ran (found live on the harness 0.5.0 ran on, Decision 24 — a "New Session" switched to the RigorQuant
   preset in the picker, rather than created with it already selected)
   still gets the Lead's guard-armed context and `subagent` guard,
   via a second trigger on `agent-preset/selected`.
11. Team is armed per RigorQuant ROOT Session through `setEnabled`, with the
    creation's own signal; a non-RigorQuant root and every teammate are
    never armed, and a service that reports the selection still off leaves
    this module disarmed.
9. unloading the plugin (the Plugins-page row toggle) disposes every
   composition it installed on a live agent, and reloading it recomposes
   those agents exactly once (found live, Decision 24).
10. the escalation lane (Decision 25, issue #27): the Lead alone gets the
   `rq_escalate` tool, which mounts the jacobian MCP client into the caller
   or a named live teammate, once per agent; the guard refuses it to every
   teammate; a lane that cannot start is an error the orchestrator sees.
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


def _allow(probe, member):
    return set(probe["classification"][member]["allow"])


def test_a_teammate_is_composed_on_subagent_start_not_on_agent_created(probe):
    """A teammate has no tree identity during its own `agent/created`.

    The subagent manager records the activation (the `<role>-<n>` path) only
    after the child is created, so `agent/created` cannot name it;
    `subagent/start` is published after that residency step and is where the
    composition can be read. Before it, the teammate must be untouched.
    """
    assert probe["beforeSubagentStart"] == {
        "sections": [], "contexts": [], "restricts": [], "guardCount": 0, "tools": []}
    assert probe["present"]["doublechecker1"]["sections"], (
        "the teammate was never composed on subagent/start")


def test_doublechecker_gets_the_blind_tier_classification(probe):
    """A teammate's catalog is an ALLOW set, not a short deny list.

    The blind tier keeps the shared tools but loses web and skills; anything
    the tier does not name stays invisible, so a newly mounted host tool
    cannot widen a teammate's scope by accident.
    """
    entry = probe["classification"]["doublechecker1"]
    assert entry["tier"] == "blind"
    allow = _allow(probe, "doublechecker1")
    assert allow == set(entry["classification"])
    assert "bash" in allow and "team_task_get" in allow and "send_message" in allow
    assert not {"web_search", "web_fetch", "skill"} & allow


def test_explorer_gets_the_open_tier_classification(probe):
    entry = probe["classification"]["explorer1"]
    assert entry["tier"] == "open"
    allow = _allow(probe, "explorer1")
    assert allow == set(entry["classification"])
    assert {"web_search", "web_fetch", "skill"} <= allow


def test_adversary_is_web_denied_but_keeps_skill(probe):
    entry = probe["classification"]["adversary1"]
    assert entry["tier"] == "webDenied"
    allow = _allow(probe, "adversary1")
    assert allow == set(entry["classification"])
    assert "skill" in allow
    assert not {"web_search", "web_fetch"} & allow


def test_a_teammates_visible_tools_are_all_classified(probe):
    """Visibility is exactly the classification, and interruption stays out.

    A tool the core newly mounts is invisible until it is classified, so the
    assertion is one-directional by construction: the visible set must equal
    the tier's allow set for this session, and no every-teammate denial (the
    roster/board, interruption, delegation, the orchestrator's goal tools)
    may appear.
    """
    denied = set(probe["denied"])
    for member in ("doublechecker1", "explorer1", "adversary1"):
        entry = probe["classification"][member]
        visible = set(entry["visible"])
        assert entry["tier"] in {"blind", "webDenied", "open"}, entry
        assert visible == set(entry["classification"]), member
        assert not visible & denied, (member, sorted(visible & denied))
        assert "interrupt_agent" not in visible, member
        for gone in ("list_agents", "team_task_list", "subagent", "subagent_fork",
                     "working_directory", "create_goal", "todo_write",
                     "ask_user_question", "exit_plan_mode"):
            assert gone not in visible, (member, gone)


def test_an_unparseable_teammate_name_is_skipped_silently(probe):
    entry = probe["present"]["unparseableName"]
    assert entry == {"sections": [], "contexts": [], "restricts": [], "guardCount": 0, "tools": []}


def test_a_non_rigorquant_team_is_never_touched(probe):
    entry = probe["present"]["nonRigorQuantTeammate"]
    assert entry == {"sections": [], "contexts": [], "restricts": [], "guardCount": 0, "tools": []}


def test_the_lead_gets_the_armed_guard_line_as_a_context_not_a_section(probe):
    lead = probe["present"]["lead"]
    assert lead["sections"] == []
    assert len(lead["contexts"]) == 1
    context = lead["contexts"][0]
    assert context["name"] == "rq-team:guard-armed"
    assert context["text"] == "RigorQuant team guard: armed"


def test_team_is_armed_only_for_a_rigorquant_root(probe):
    """Arming is per SESSION, through the service's own selection.

    A root composed as rigorquant asks the Team service for `setEnabled`;
    a non-RigorQuant root, a non-RigorQuant teammate and every RigorQuant
    teammate are never armed. Installing the plugin must not turn Team on
    for the operator's other presets.
    """
    arming = probe["arming"]
    armed = {call["agent"] for call in arming["setEnabledCalls"]}
    assert armed == {"lead-1", "lead-2"}, arming["setEnabledCalls"]
    assert all(call["enabled"] is True for call in arming["setEnabledCalls"])
    second = [call for call in arming["setEnabledCalls"] if call["agent"] == "lead-2"]
    assert second[0]["signal"] == "signal:agent-created", (
        "the creation's own cancellation signal must reach setEnabled")
    assert arming["standardRootContexts"] == []
    assert arming["teammateContexts"] == []
    assert arming["nonRigorQuantTeammateSetEnabled"] == []
    assert probe["present"]["standardRoot"] == {
        "sections": [], "contexts": [], "restricts": [], "guardCount": 0, "tools": []}
    assert probe["present"]["secondRoot"]["contexts"] == [{
        "name": "rq-team:guard-armed", "order": 118,
        "text": "RigorQuant team guard: armed"}]


def test_a_service_that_reports_the_selection_off_leaves_the_guard_disarmed(probe):
    """No armed line unless the service confirms the selection.

    A guard the Team tools do not honor is worse than no guard: it would
    tell the orchestrator to delegate into a session whose Team tools are
    absent.
    """
    assert probe["unarmedService"]["lead"] == {
        "sections": [], "contexts": [], "restricts": [], "guardCount": 0, "tools": []}


def test_reapplication_on_a_resume_sourced_creation(probe):
    resume = probe["resume"]
    assert resume["beforeResident"] == {
        "sections": [], "contexts": [], "restricts": [], "guardCount": 0, "tools": []}
    assert len(resume["firstSections"]) == 1
    assert resume["disposedAfterResume"] == ["deployment:persona-prefix"]
    assert len(resume["secondSections"]) == 1


LEAD_LIVE = {"sections": [], "contexts": ["rq-team:guard-armed"], "tools": ["rq_escalate"],
             "restricts": 0, "guards": 1}
TEAMMATE_LIVE = {"sections": ["deployment:persona-prefix"], "contexts": [], "tools": [],
                 "restricts": 1, "guards": 1}
NOTHING_LIVE = {"sections": [], "contexts": [], "tools": [], "restricts": 0, "guards": 0}


def test_unloading_the_plugin_disarms_every_live_agent(probe):
    """Toggling rq-team off in the Plugins page must take the composition with it.

    Everything the plugin registers goes through `agent.ctx`, so it lives in
    the agent's scope, not the plugin's; the plugin's own unload has to
    dispose it, or the Lead stays armed (and guarded) with rq-team off.
    """
    unload = probe["unload"]
    assert unload["firstError"] is None
    assert unload["afterMount"] == {"lead": LEAD_LIVE, "doublechecker": TEAMMATE_LIVE}
    assert unload["afterUnload"] == {"lead": NOTHING_LIVE, "doublechecker": NOTHING_LIVE}


def test_reloading_the_plugin_recomposes_live_agents_exactly_once(probe):
    """Toggling rq-team back on re-applies to the live agents without a collision."""
    unload = probe["unload"]
    assert unload["remountError"] is None
    assert unload["afterRemount"] == {"lead": LEAD_LIVE, "doublechecker": TEAMMATE_LIVE}


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
    assert "only the Lead" in checks["siblingMessageDenied"]
    assert "'lead'" in checks["siblingMessageDenied"], (
        "a refused message must name the legal target")
    assert checks["leadMessageAllowed"] is None
    assert checks["leadSessionIdMessageAllowed"] is None


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


def test_the_orchestrator_subagent_guard_refuses_bad_names_and_fork(probe):
    checks = probe["guardChecks"]
    assert "does not parse to <role>-<n>" in checks["spawnBadNameDenied"]
    assert "fork inherits the Lead conversation" in checks["spawnForkDenied"]
    assert checks["spawnFreshRoleAllowed"] is None


# ── a session composed as rigorquant only after its own agent/created ──────


def test_the_orchestrator_never_rebriefs_a_settled_fresh_per_brief_teammate(probe):
    """Explorer, OffGridThinker and DoubleChecker are fresh per brief.

    Found live in the 0.5.0 release run (Decision 24): the
    orchestrator sent hash-bound "erratum briefs" to a settled
    doublechecker and explorer instead of briefing new teammates. Reuse is
    a new brief after the teammate settled, so the guard reads the live
    roster status: settled (idle/inactive) is refused, running (answering a
    blocking question mid-turn) is allowed, and the reused roles are
    untouched.
    """
    checks = probe["guardChecks"]
    assert "fresh per brief" in checks["briefSettledExplorerDenied"]
    assert "explorer-2" in checks["briefSettledExplorerDenied"]
    assert "fresh per brief" in checks["briefInactiveOffgridDenied"]
    assert checks["answerRunningDoublecheckerAllowed"] is None
    assert checks["briefSettledAdversaryAllowed"] is None
    assert checks["briefInactiveLitLineAllowed"] is None
    assert checks["unknownTargetLeftToTheTool"] is None


def test_a_late_preset_switch_gets_no_composition_until_the_switch_lands(probe):
    """Before `agent-preset/selected` fires, the session was still on its
    original (non-rigorquant) preset when `agent/created` ran — this module
    correctly stayed silent, matching every other non-rigorquant agent."""
    before = probe["latePresetSelection"]["beforeSwitch"]
    assert before == {"sections": [], "contexts": [], "restricts": [], "guardCount": 0, "tools": []}


def test_a_late_preset_switch_to_rigorquant_installs_the_lead_composition(probe):
    """Once `agent-preset/selected` announces the switch (after the harness's
    own recompose already landed on agent.ctx), the Lead gets exactly what it
    would have gotten from a same-preset agent/created: the armed context and
    its spawn_teammate guard — found missing live on the installed harness
    (Decision 24) before this second trigger existed."""
    after = probe["latePresetSelection"]["afterSwitch"]
    assert after["sections"] == []
    assert after["guardCount"] == 1
    assert after["tools"] == ["rq_escalate"]
    assert len(after["contexts"]) == 1
    context = after["contexts"][0]
    assert context["name"] == "rq-team:guard-armed"
    assert context["text"] == "RigorQuant team guard: armed"
    assert probe["latePresetSelection"]["setEnabledCalls"] == [
        {"agent": "lead-late", "enabled": True, "signal": None}]


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


# ── the escalation lane (issue #27) ───────────────────────────────────────


def test_only_the_lead_is_given_rq_escalate(probe):
    escalation = probe["escalation"]
    assert escalation["toolRegisteredOnLead"]
    assert probe["present"]["lead"]["tools"] == ["rq_escalate"]
    for member in ("doublechecker1", "explorer1", "adversary1"):
        assert probe["present"][member]["tools"] == [], member
    assert escalation["teammateTools"] == [[], []]


def test_the_guard_refuses_rq_escalate_to_every_teammate(probe):
    checks = probe["guardChecks"]
    assert "rq_escalate" in checks["teammateEscalateDenied"]
    assert "rq_escalate" in checks["teammateEscalateOtherDenied"]


def test_rq_escalate_takes_only_an_optional_teammate(probe):
    parameters = probe["escalation"]["parameters"]
    assert parameters["type"] == "object"
    assert set(parameters["properties"]) == {"teammate"}
    assert parameters.get("required", []) == []


def test_rq_escalate_mounts_the_pinned_jacobian_client_into_the_caller(probe):
    escalation = probe["escalation"]
    assert escalation["intoCaller"]["value"] == {"target": "lead", "status": "mounted"}
    assert escalation["imports"][0] == "@deepseek-ai/dsh-mcp-client"
    [mount] = escalation["mounts"]["lead"]
    assert mount["plugin"] == "mcp-client"
    config = mount["config"]
    assert config["validated"], "the config must go through the client's own schema"
    assert config["serverName"] == "rigorquant-jacobian"
    assert config["transport"] == "stdio"
    assert config["command"] == "npx"
    assert config["args"] == ["-y", "jacobian@0.12.0", "mcp"]
    assert config["toolCallTimeoutMs"] == 120000
    assert config["failOnStartupError"] is True
    assert config["cwd"] == "/work/lead-esc"
    assert config["env"]["JACOBIAN_LEAN_RUNTIME"]
    assert config["env"]["PATH"].endswith("/.elan/bin")
    rendered = " ".join(block["text"] for block in escalation["intoCaller"]["rendered"])
    assert "mcp__rigorquant-jacobian__" in rendered


def test_rq_escalate_mounts_into_a_named_teammate(probe):
    escalation = probe["escalation"]
    assert escalation["intoTeammate"]["value"] == {"target": "doublechecker-1", "status": "mounted"}
    [mount] = escalation["mounts"]["doublechecker"]
    assert mount["config"]["cwd"] == "/work/dc-esc"


def test_mounting_is_idempotent_per_agent(probe):
    escalation = probe["escalation"]
    assert escalation["intoCallerAgain"]["value"] == {"target": "lead", "status": "already-mounted"}
    assert escalation["intoTeammateAgain"]["value"] == {
        "target": "doublechecker-1", "status": "already-mounted"}
    assert len(escalation["mounts"]["lead"]) == 1
    assert len(escalation["mounts"]["doublechecker"]) == 1


def test_an_unknown_or_unloaded_teammate_is_a_clear_error(probe):
    escalation = probe["escalation"]
    assert "doublechecker-9" in escalation["unknownTeammate"]["error"]
    assert "offgrid-1" in escalation["unloadedTeammate"]["error"]
    assert "inactive" in escalation["unloadedTeammate"]["error"]
    assert "error" in escalation["foreignTeammate"], (
        "the lane resolved a teammate from another tree: %r"
        % (escalation["foreignTeammate"],))
    assert "doublechecker-2" in escalation["foreignTeammate"]["error"]


def test_a_failed_connect_surfaces_as_an_error_and_can_be_retried(probe):
    """failOnStartupError rejects the mount; rq_escalate reports it and points
    at the install step instead of leaving a lane that silently retries."""
    escalation = probe["escalation"]
    error = escalation["failedConnect"]["error"]
    assert "adversary-1" in error and "spawn npx ENOENT" in error
    assert "jacobian@0.12.0 upgrade" in error
    assert "error" in escalation["failedConnectRetried"], "a failure must not be cached as mounted"
    assert len(escalation["mounts"]["adversary"]) == 2, "a failure must not be cached either"
    assert escalation["failedFibersDisposed"] == 2


def test_a_plugin_reload_does_not_mount_the_lane_twice(probe):
    """The lane lives on the agent, not the plugin: after rq-team is toggled
    off and on, rq_escalate still reports the existing mount instead of
    mounting a second client (which the harness would refuse by name)."""
    escalation = probe["escalation"]
    assert escalation["afterReload"] == {"value": {"target": "lead", "status": "already-mounted"}}
    assert len(escalation["mounts"]["lead"]) == 1
