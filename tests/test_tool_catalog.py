"""An installed core's new model-facing tool must fail a test, not widen a role.

The 0.8.1 specification (user story 24, #41) asks for structure, not memory: a
Teammate's visible catalog is an explicit per-Role-tier classification, so a
tool the core newly mounts is invisible until someone classifies it. That
fail-safe only proves half the contract. This module proves the other half —
every model-facing tool the INSTALLED core's shipped `docs/tool-catalog.md`
lists has a decision: it is classified for a tier, or it is explicitly
excluded in `tests/tool_catalog_probe.cjs` with the decision that excludes it.

The probe reads the shipped catalog (a generated page whose "Tool Package
Map" lists every model-visible name), imports the real `dsh/team.js`
classification, and fails with the unclassified names. Reading the installed
artifact — not a hand-written fixture — is what makes a future tool fail here
instead of silently widening a teammate's scope. Without an installed
harness there is no catalog to audit, so the live probe skips on the shared
exit codes (tests/harness_locator.cjs).
"""

import json
import shutil
import subprocess

import pytest

from conftest import REPO, require_harness

PROBE = REPO / "tests/tool_catalog_probe.cjs"


def manifest():
    return json.loads((REPO / "package.json").read_text())


@pytest.fixture(scope="module")
def report():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to read the shipped catalog and import the classification")
    module = REPO / manifest()["exports"]["./team"]
    if not module.exists():
        pytest.fail(f"package.json exports ./team but {module} is missing")
    out = subprocess.run([node, str(PROBE), str(module)],
                         capture_output=True, text=True)
    require_harness(out)
    assert out.returncode == 0, (out.stdout, out.stderr)
    return json.loads(out.stdout)


def test_the_installed_catalog_was_actually_read(report):
    """A parse that finds almost nothing must not pass vacuously.

    0.2.2-rc.3's shipped map names 75 model-visible tools across 37 tool
    packages. A future core may add tools (the lower bound is what matters);
    a near-empty parse means the page format moved and the probe must change
    with it, not silently stop auditing.
    """
    assert report["catalogCount"] >= 70, report
    assert report["catalogPath"].endswith("docs/tool-catalog.md"), report["catalogPath"]
    assert report["coreVersion"], report


def test_every_model_facing_tool_has_a_decision(report):
    """The failure this module exists for: a catalog name nobody decided.

    A tool is either classified in a Role tier (a Teammate may be given it) or
    explicitly excluded with a recorded reason (it belongs to the Orchestrator,
    the operator, or a host capability this distribution does not install for
    a study). The classification's own tier data is pinned separately by
    tests/test_role_tool_budgets.py; this is the catalog direction.
    """
    assert report["unclassified"] == [], (
        "the installed core ships model-facing tools no classification decides:\n"
        + "\n".join(report["unclassified"])
    )
    assert report["overlap"] == [], report["overlap"]
    assert report["stale"] == [], report["stale"]
    assert len(report["classified"]) + len(report["excluded"]) == report["catalogCount"], (
        "the catalog is not partitioned into classified and excluded:\n"
        f"{report['catalogCount']} names, {len(report['classified'])} classified, "
        f"{len(report['excluded'])} excluded"
    )


def test_the_classification_still_names_the_teammate_tools(report):
    """A catalog audit that classifies nothing would also be green."""
    classified = set(report["classified"])
    assert {"bash", "read", "write", "edit", "send_message", "wait_agent",
            "team_task_create", "team_task_get", "team_task_update",
            "skill", "web_search", "web_fetch"} <= classified


def test_the_exclusion_table_still_names_the_orchestrator_tools(report):
    """The exclusion half carries the decisions, not a dumping ground."""
    excluded = set(report["excluded"])
    assert {"working_directory", "create_goal", "todo_write", "list_agents",
            "interrupt_agent", "subagent", "apply_patch"} <= excluded
    assert not set(report["classified"]) & excluded
