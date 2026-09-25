"""The boot-sync engine (dsh/sync.js) -- the compute lane under $DSH_HOME.

Decision 22, shrunk by Decision 25: the bundle row `rq-lane-sync` lands the
compute lane (`env/`, plus the `mcp/` and `docs/` the skill cites) into
$DSH_HOME/share/rigorquant at profile boot, so a `dsh plugin add` install has
a lane without ever running install.sh. The preset is declared now, so the
row copies no preset; it only removes the copy an older release landed.

Pinned here against a real execution of the engine (via
tests/lane_sync_probe.cjs, not by re-implementing it in Python):

1. replace-on-sync -- a changed or missing source file reaches the target;
2. derived-state safety -- a provisioned `.venv` survives every sync, and a
   checkout's own `.venv` never leaks into a managed target;
3. ownership marker -- `.rq-sync.json` names the manager and version;
4. orphan removal -- the old `.agent-presets/rigorquant` goes only when its
   marker says this package landed it.
"""

import json
import shutil
import subprocess

import pytest

from conftest import REPO

PROBE = REPO / "tests/lane_sync_probe.cjs"
LANE_ANCHOR = "pyproject.toml"


def manifest():
    return json.loads((REPO / "package.json").read_text())


@pytest.fixture(scope="module")
def probe():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the sync engine")
    sync_module = REPO / manifest()["exports"]["./sync"]
    if not sync_module.exists():
        pytest.fail(f"package.json exports ./sync but {sync_module} is missing")

    def run(steps):
        out = subprocess.run(
            [node, str(PROBE), str(sync_module), json.dumps(steps)],
            capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    return run


def sync(probe, src, dst, version):
    [result] = probe([{"op": "sync", "src": str(src), "dst": str(dst), "version": version}])
    return result


def exists(probe, path):
    return probe([{"op": "exists", "path": str(path)}])[0]["exists"]


def read(probe, path):
    return probe([{"op": "read", "path": str(path)}])[0]["data"]


def make_lane(root):
    """A minimal fake of the bundled lane: its anchor file plus a nested file."""
    (root / "scripts").mkdir(parents=True)
    (root / LANE_ANCHOR).write_text('[project]\nversion = "0.6.0"\n')
    (root / "uv.lock").write_text("lock v1\n")
    (root / "scripts" / "check.py").write_text("print('v1')\n")


def test_first_sync_copies_the_lane_and_stamps_ownership(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_lane(src)
    assert sync(probe, src, dst, "0.6.0")["status"] == "synced"
    for rel in (LANE_ANCHOR, "uv.lock", "scripts/check.py"):
        assert exists(probe, dst / rel)
    record = json.loads(read(probe, dst / ".rq-sync.json"))
    assert record["managedBy"] == "dsh-rigorquant"
    assert record["version"] == "0.6.0"


def test_rerun_without_changes_writes_nothing(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_lane(src)
    sync(probe, src, dst, "0.6.0")
    again = sync(probe, src, dst, "0.6.0")
    assert again == {"status": "current", "copied": [], "pruned": 0}


def test_an_unstamped_identical_lane_is_adopted_without_a_rewrite(probe, tmp_path):
    """install.sh lands the lane without a stamp; the first boot adopts it."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_lane(src)
    sync(probe, src, dst, "0.6.0")
    probe([{"op": "remove", "path": str(dst / ".rq-sync.json")}])
    adopted = sync(probe, src, dst, "0.6.0")
    assert adopted["status"] == "synced"
    assert adopted["copied"] == [] and adopted["pruned"] == 0
    assert exists(probe, dst / ".rq-sync.json")


def test_changed_source_replaces_the_target(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_lane(src)
    sync(probe, src, dst, "0.6.0")
    (src / "uv.lock").write_text("lock v2\n")
    probe([{"op": "write", "path": str(src / "NEW.md"), "data": "new\n"}])
    result = sync(probe, src, dst, "0.6.1")
    assert result["status"] == "synced"
    assert sorted(result["copied"]) == ["NEW.md", "uv.lock"]
    assert read(probe, dst / "uv.lock") == "lock v2\n"


def test_a_same_version_edit_to_the_lane_is_restored(probe, tmp_path):
    """The lane is never edited in place: a changed lock is damage."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_lane(src)
    sync(probe, src, dst, "0.6.0")
    probe([{"op": "write", "path": str(dst / "uv.lock"), "data": "hand edit\n"},
           {"op": "remove", "path": str(dst / "scripts" / "check.py")}])
    result = sync(probe, src, dst, "0.6.0")
    assert result["status"] == "synced"
    assert sorted(result["copied"]) == ["scripts/check.py", "uv.lock"]
    assert read(probe, dst / "uv.lock") == "lock v1\n"


def test_prune_removes_retired_files_but_never_a_provisioned_venv(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_lane(src)
    sync(probe, src, dst, "0.6.0")
    # The uv lane provisioned a venv at the anchor; the source tree never
    # ships one. A later release retires OLD.md.
    probe([
        {"op": "mkdir", "path": str(dst / ".venv")},
        {"op": "write", "path": str(dst / ".venv" / "pyvenv.cfg"), "data": "home = /usr\n"},
        {"op": "write", "path": str(dst / "OLD.md"), "data": "stale\n"},
    ])
    result = sync(probe, src, dst, "0.6.1")
    assert result["status"] == "synced" and result["pruned"] == 1
    assert not exists(probe, dst / "OLD.md")
    assert exists(probe, dst / ".venv" / "pyvenv.cfg"), \
        "prune deleted the provisioned venv -- the lane would rebuild mid-study"


def test_a_checkouts_own_venv_never_leaks_into_the_target(probe, tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_lane(src)
    (src / ".venv").mkdir()
    (src / ".venv" / "lib.py").write_text("derived state\n")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")
    assert sync(probe, src, dst, "0.6.0")["status"] == "synced"
    for leaked in (".venv/lib.py", "__pycache__/x.pyc"):
        assert not exists(probe, dst / leaked)


def orphan(probe, home, marker):
    """An `.agent-presets/rigorquant` tree as an older release left it."""
    root = home / ".agent-presets" / "rigorquant"
    steps = [{"op": "write", "path": str(root / "agent.cordis.yml"), "data": "- id: persona\n"}]
    if marker is not None:
        steps.append({"op": "write", "path": str(root / ".rq-sync.json"), "data": json.dumps(marker)})
    probe(steps)
    return root


def remove_orphan(probe, home):
    [result] = probe([{"op": "removeOrphanedPreset", "home": str(home)}])
    return result


def test_the_preset_an_older_release_landed_is_removed(probe, tmp_path):
    root = orphan(probe, tmp_path, {"managedBy": "dsh-rigorquant", "version": "0.5.0"})
    assert remove_orphan(probe, tmp_path) == {"status": "removed"}
    assert not exists(probe, root)
    assert exists(probe, tmp_path / ".agent-presets"), "only our own preset directory goes"


def test_a_preset_directory_this_package_does_not_own_is_left_alone(probe, tmp_path):
    for marker in (None, {"managedBy": "someone-else", "version": "0.5.0"}):
        root = orphan(probe, tmp_path, marker)
        assert remove_orphan(probe, tmp_path) == {"status": "not-ours"}
        assert exists(probe, root / "agent.cordis.yml")
        probe([{"op": "remove", "path": str(root)}])


def test_no_orphan_is_a_quiet_no_op(probe, tmp_path):
    assert remove_orphan(probe, tmp_path) == {"status": "absent"}
