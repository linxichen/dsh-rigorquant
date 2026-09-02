"""The live team-activity monitor (dsh/activity.js) — the functional panel.

The README activity view is rendered by a browser floater (`shell.overlay`),
and the data it shows comes from this host half: role agents observed from the
events the core already publishes, served as a JSON snapshot plus the
docs/figs role portraits over /plugins/dsh-rigorquant/... — the same HTTP surface
dsh-agent-teams uses for its activity panel.

These checks pin the load-bearing properties against a real execution of the
module (via tests/activity_probe.cjs, not by re-implementing it in Python):

1. it observes without interfering — drive the lifecycle events and read the
   snapshot: the lab, its working statuses, role members, and feed appear;
2. the five-move stage heuristic — the latest distinctive tool call names the
   stage;
3. the portraits — served from docs/figs with an exact allowlist, so a path
   traversal attempt 404s;
4. webless safety — a profile without webServer mounts and just never serves
   routes.

Design credit: activity-panel concept adapted from dsh-agent-teams
(NanmiCoder, MIT) — see README "The team, live".
"""

import json
import shutil
import subprocess

import pytest

from conftest import REPO

PROBE = REPO / "tests/activity_probe.cjs"


def manifest():
    return json.loads((REPO / "package.json").read_text())


@pytest.fixture(scope="module")
def probe():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the activity monitor")
    module = REPO / manifest()["exports"]["./activity"]
    if not module.exists():
        pytest.fail(f"package.json exports ./activity but {module} is missing")
    out = subprocess.run([node, str(PROBE), str(module)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_activity_export_points_at_a_shipped_file():
    assert (REPO / manifest()["exports"]["./activity"]).is_file()


def test_the_monitor_mounts_without_error(probe):
    assert probe["mountError"] is None, probe.get("mountError")


def test_it_registers_both_host_routes(probe):
    assert "exact:/plugins/dsh-rigorquant/activity" in probe["routes"]
    assert "prefix:/plugins/dsh-rigorquant/avatar" in probe["routes"]


def test_snapshot_reports_the_lab_and_live_roles(probe):
    """The lab, its working set, and the role members appear in the payload.

    lab-1 was found despite its STALE durable header (agentPreset 'standard'
    with the real switch in the log) — the exact shape of a RigorQuant session
    resumed after a restart.
    """
    labs = probe["snapshot"]["labs"]
    assert probe["snapshotCode"] == 200
    assert len(labs) == 2
    lab = labs[0]
    assert lab["id"] == "lab-1"
    assert lab["title"] == "Boundary cases of the VaR estimator"
    assert lab["stage"] == "ground truth"  # latest distinctive tool call
    assert lab["summary"] == {"total": 2, "working": 2, "idle": 0}
    assert lab["captain"]["label"] == "Orchestrator"
    assert lab["members"][0]["label"] == "Explorer"
    assert lab["members"][0]["tool"] == "subagent_explorer"
    assert lab["members"][0]["status"] == "running"


def test_a_session_switching_to_rigorquant_is_promoted_to_captain(probe):
    """The picker flow creates `standard`, then switches — a live switch must
    promote the parentless session into a lab of its own."""
    labs = probe["snapshot"]["labs"]
    promoted = next(lab for lab in labs if lab["id"] == "lab-2")
    assert promoted["captain"]["label"] == "Orchestrator"
    assert promoted["summary"] == {"total": 3, "working": 2, "idle": 1}


def test_a_oneshot_subagent_gets_its_role_and_status_from_the_parents_tool_call(probe):
    """One-shot subagents carry only a label (no persona tag). The parent's
    subagent_lit_line tool call must attach the lit-line role to the child,
    and its agent/status must light it up as running."""
    labs = probe["snapshot"]["labs"]
    promoted = next(lab for lab in labs if lab["id"] == "lab-2")
    member = next(m for m in promoted["members"] if m["sessionId"] == "child-shot-1")
    assert member["role"] == "lit-line"
    assert member["label"] == "Literature"
    assert member["tool"] == "subagent_lit_line"
    assert member["status"] == "running"


def test_a_subagent_with_recent_activity_lights_up_without_a_running_status(probe):
    """A subagent that never surfaces a running agent status still lights its
    role when it emitted session activity within the recent-active window."""
    labs = probe["snapshot"]["labs"]
    promoted = next(lab for lab in labs if lab["id"] == "lab-2")
    member = next(m for m in promoted["members"] if m["sessionId"] == "child-shot-2")
    assert member["role"] == "doublechecker"
    assert member["status"] == "running"


def test_a_disposed_subagent_stays_in_the_roster_but_drops_from_the_live_summary(probe):
    """A finished (disposed) one-shot subagent must remain in the roster as
    idle so the hub map keeps its role, while the live-team summary
    counts only still-present agents."""
    disposed = probe["snapshotDisposed"]
    promoted = next(lab for lab in disposed["labs"] if lab["id"] == "lab-2")
    member = next(m for m in promoted["members"] if m["sessionId"] == "child-shot-1")
    assert member["disposed"] is True
    assert member["status"] == "idle"
    assert promoted["summary"] == {"total": 2, "working": 1, "idle": 1}


def test_snapshot_feed_is_newest_first(probe):
    feed = probe["snapshot"]["labs"][0]["feed"]
    times = [item["t"] for item in feed]
    assert times == sorted(times, reverse=True)
    assert feed[0]["text"].startswith("captain")
    assert feed[1]["kind"] == "tool"
    assert "bash" in feed[1]["text"]


def test_portraits_come_from_an_allowlist(probe):
    ok = probe["portraitOk"]
    assert ok["code"] == 200
    assert ok["type"] == "image/png"
    assert ok["isPng"] is True
    assert probe["portraitBad"]["code"] == 404


def test_the_patch_registers_the_monitor_row():
    """The bundle patch must actually mount dsh/activity.js — a row that
    exists only in package.json exports never runs."""
    patch = (REPO / "cordis.patch.yml").read_text()
    assert "rq-activity" in patch
    assert "dsh-rigorquant/activity" in patch
