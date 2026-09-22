"""Team composition (dsh/team.js) — the first Agent Teams tracer bullet.

DSH 0.1.6 ships native Agent Teams. This host half applies each teammate's
role composition — persona, tool-tier budget, and (on the Lead) a runtime
fact that the guard is armed — purely from the teammate's NAME
(`<role>-<n>`, e.g. `doublechecker-1`), resolved through the harness's
`agentTeams` service. It is purely additive: the classic `[[rq:role=...]]`
tag mechanism (dsh/index.js) and the seven classic delegation rows
(agent-presets/rigorquant/agent.cordis.yml) are untouched and coexist with
this module until a later issue removes them. Per-call guards (hub-and-spoke
messaging, roster-blindness, own-task-only board access, the bash
network-verb denial, `spawn_teammate` refusal) are a later issue too — this
module only registers `tools.restrict`, never `tools.guard`.

These checks pin the load-bearing properties against a real execution of the
module (via tests/team_probe.cjs, not by re-implementing it in Python):

1. persona composition — a teammate's role persona lands at the harness's
   own `deployment:persona-prefix` slot, first, and its tool catalog is
   restricted by tier;
2. the Lead gets a distinct "RigorQuant team guard: armed" runtime CONTEXT
   (not a persona section — see dsh/team.js's module header for why);
3. an unparseable teammate name, and a non-RigorQuant team, are both
   silently untouched;
4. every `agent/created` source re-applies composition from scratch (proven
   via a resume-sourced re-creation: the first registration is disposed and
   a fresh one takes its place, not skipped as a no-op);
5. `agentTeams` absent -> one warning, no armed context anywhere;
6. the module never imports the experimental Agent Teams packages and never
   declares `agentTeams` a hard dependency.
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
    assert entry == {"sections": [], "contexts": [], "restricts": []}


def test_a_non_rigorquant_team_is_never_touched(probe):
    entry = probe["present"]["nonRigorQuantTeammate"]
    assert entry == {"sections": [], "contexts": [], "restricts": []}


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
