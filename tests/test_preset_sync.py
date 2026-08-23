"""The boot-sync engine (dsh/sync.js) — the self-installing distribution.

Decision 23: the bundle row `rq-preset-sync` lands the preset and the compute
lane into $DSH_HOME at profile boot. Its contract has exactly four load-bearing
properties, each pinned here against a real execution of the engine (via
tests/preset_sync_probe.cjs, not by re-implementing it in Python):

1. replace-on-install — a changed source file reaches the target;
2. derived-state safety — a provisioned `.venv` survives every sync, and a
   checkout's own `.venv` never leaks into a managed target;
3. local-edit preservation — a same-version target the user edited in place
   (the escalation lane flips rows in the INSTALLED composition) is kept;
4. ownership marker — `.rq-sync.json` names the manager and version.
"""

import json
import shutil
import subprocess

import pytest

from conftest import REPO

PROBE = REPO / "tests/preset_sync_probe.cjs"


def manifest():
    return json.loads((REPO / "package.json").read_text())


def manifest_export(key):
    return manifest()["exports"][key]


@pytest.fixture(scope="module")
def probe():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the sync engine")
    sync_module = REPO / manifest_export("./sync")
    if not sync_module.exists():
        pytest.fail(f"package.json exports ./sync but {sync_module} is missing")

    def run(steps):
        out = subprocess.run(
            [node, str(PROBE), str(sync_module), json.dumps(steps)],
            capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    return run


def make_source(root):
    """A minimal fake of the bundled trees: two files, one nested."""
    (root / "skills" / "ref").mkdir(parents=True)
    (root / "agent.cordis.yml").write_text("- id: persona\n")
    (root / "skills" / "SKILL.md").write_text("# skill v1\n")
    (root / "skills" / "ref" / "protocol.md").write_text("protocol v1\n")


def test_first_sync_copies_the_tree_and_stamps_ownership(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_source(src)
    [result] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    assert result["status"] == "synced"
    for rel in ("agent.cordis.yml", "skills/SKILL.md", "skills/ref/protocol.md"):
        assert probe([{"op": "exists", "path": str(dst / rel)}])[0]["exists"]
    marker = probe([{"op": "read", "path": str(dst / ".rq-sync.json")}])[0]["data"]
    record = json.loads(marker)
    assert record["managedBy"] == "dsh-rigorquant"
    assert record["version"] == "0.3.1"


def test_rerun_without_changes_is_quiet(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_source(src)
    steps = [{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}]
    probe(steps)
    [again] = probe(steps)
    assert again["status"] == "kept-local"
    # kept-local must not be an accident of the stamp: remove the stamp and an
    # identical tree still writes nothing (byte-compare), taking ownership.
    probe([{"op": "remove", "path": str(dst / ".rq-sync.json")}])
    [third] = probe(steps)
    assert third["status"] == "synced"
    assert third["copied"] == [] and third["pruned"] == 0


def test_changed_source_replaces_target_on_version_bump(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_source(src)
    probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    (src / "skills" / "SKILL.md").write_text("# skill v2\n")
    probe([{"op": "write", "path": str(src / "NEW.md"), "data": "new\n"}])
    [result] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.4.0"}])
    assert result["status"] == "synced" and sorted(result["copied"]) == ["NEW.md", "skills/SKILL.md"]
    body = probe([{"op": "read", "path": str(dst / "skills/SKILL.md")}])[0]["data"]
    assert body == "# skill v2\n"


def test_prune_removes_renamed_files_but_never_a_provisioned_venv(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_source(src)
    probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    # The user's uv lane provisioned a venv at the anchor; the source tree
    # never ships one. A rename in the package retires OLD.md.
    probe([
        {"op": "mkdir", "path": str(dst / ".venv")},
        {"op": "write", "path": str(dst / ".venv" / "pyvenv.cfg"), "data": "home = /usr\n"},
        {"op": "write", "path": str(dst / "OLD.md"), "data": "stale\n"},
        {"op": "remove", "path": str(src / "agent.cordis.yml")},
        {"op": "write", "path": str(src / "renamed.yml"), "data": "- id: persona\n"},
    ])
    [result] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.4.0"}])
    assert result["status"] == "synced" and result["pruned"] >= 1
    assert not probe([{"op": "exists", "path": str(dst / "OLD.md")}])[0]["exists"]
    assert probe([{"op": "exists", "path": str(dst / ".venv" / "pyvenv.cfg")}])[0]["exists"], \
        "prune deleted the provisioned venv — the lane would rebuild mid-study"


def test_a_checkouts_own_venv_never_leaks_into_the_target(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_source(src)
    (src / ".venv").mkdir()
    (src / ".venv" / "lib.py").write_text("derived state\n")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")
    [result] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    assert result["status"] == "synced"
    for leaked in (".venv/lib.py", "__pycache__/x.pyc"):
        assert not probe([{"op": "exists", "path": str(dst / leaked)}])[0]["exists"]


def test_same_version_local_edits_are_kept_until_an_upgrade(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_source(src)
    probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    # The documented per-study flow: enable the jacobian row in the INSTALLED preset.
    probe([{"op": "write", "path": str(dst / "agent.cordis.yml"),
            "data": "- id: persona\n- id: mcp-jacobian\n"}])
    [kept] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    assert kept["status"] == "kept-local"
    body = probe([{"op": "read", "path": str(dst / "agent.cordis.yml")}])[0]["data"]
    assert "mcp-jacobian" in body
    # An upgrade replaces shipped files — the same contract as re-running install.sh.
    [upgraded] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.4.0"}])
    assert upgraded["status"] == "synced"
    body = probe([{"op": "read", "path": str(dst / "agent.cordis.yml")}])[0]["data"]
    assert "mcp-jacobian" not in body


def test_missing_shipped_file_is_damage_and_gets_restored(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_source(src)
    probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    probe([{"op": "remove", "path": str(dst / "skills" / "ref" / "protocol.md")}])
    [result] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": "0.3.1"}])
    assert result["status"] == "synced" and result["copied"] == ["skills/ref/protocol.md"]
