"""The declared preset must mount on the harness it runs on — validated, not assumed.

The `rigorquant` preset is one `@deepseek-ai/dsh-agent-preset` row in
agent-presets/rigorquant.patch.yml (Decision 25), and its `config.plugins`
is a tree of plugin rows. Each row's `config` is validated against the
plugin's own schemastery schema when the preset activates, and a row that
fails validation takes the whole preset down: the picker then shows
`rigorquant` as broken, and no session can start on it. A renamed config key
is enough, which is what happened when 0.1.3-alpha.2 split the persona into
`prefix`/`suffix` and this preset still passed `text`.

tests/preset_harness_probe.cjs loads every row through the INSTALLED
package's real `Config` — the same schema the loader uses, so there is no
second copy to drift. It resolves the harness from `RQ_HARNESS_MODULES` or
the `dsh` on PATH, and these tests skip when there is no harness to check
against, or when it predates declared presets or cannot be judged (outside the
package's `>=0.2.0-rc.2 <0.2.1` range or without its own gate), because this
repository is also developed and packaged without one.

A core the package REFUSES is not "no harness": that refusal is the subject of
`test_the_probe_refuses_a_harness_outside_the_declared_range`, so the skip
helper must not swallow it.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, require_harness

PROBE = REPO / "tests/preset_harness_probe.cjs"


def test_the_harness_probe_is_shipped():
    assert PROBE.is_file()


def test_every_preset_row_validates_against_the_installed_harness():
    """Every row's config must satisfy the installed plugin's own schema."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to validate the composition")
    out = subprocess.run([node, str(PROBE)], cwd=REPO,
                         capture_output=True, text=True)
    require_harness(out)
    assert out.returncode == 0, (
        "the composition has a row the installed harness rejects (a row whose "
        "config fails validation rejects the whole preset mount):\n%s\n%s"
        % (out.stdout, out.stderr))


def test_the_probe_finds_the_roles_delivery_and_present_rows():
    """A green run must mean the ROWS ARE THERE, not that the probe gave up.

    The probe prints one line per row; this pins that the preset still carries
    the declared row itself, the (disabled) external-agent rows, the `present`
    row the deliverables flow needs, and the `command-goal` row that supplies
    `/goal` — and no longer the classic subagent control row, which the Team
    tools replace.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to validate the composition")
    out = subprocess.run([node, str(PROBE)], cwd=REPO,
                         capture_output=True, text=True)
    require_harness(out)
    for needle in (
        "OK          @deepseek-ai/dsh-agent-preset",
        "@deepseek-ai/dsh-tool-present",
        "@deepseek-ai/dsh-command-goal",
        "@deepseek-ai/dsh-tool-subagent",
        "@deepseek-ai/dsh-persona",
    ):
        assert needle in out.stdout, "%s is no longer mounted" % needle
    assert "dsh-tool-subagent-control" not in out.stdout, (
        "the classic subagent control row is back; the Team tools replace it")
    assert "0 hard failure(s)" in out.stdout, out.stdout


def _installed_harness():
    """The `@deepseek-ai` directory of a real DSH install, or None."""
    from_env = os.environ.get("RQ_HARNESS_MODULES")
    if from_env:
        return Path(from_env)
    dsh = shutil.which("dsh")
    if dsh is None:
        return None
    candidate = Path(os.path.realpath(dsh)).parent.parent / "node_modules" / "@deepseek-ai"
    return candidate if candidate.is_dir() else None


def _shadow_harness(real_scope, root, version):
    """The same packages as `real_scope`, reporting the core version `version`.

    The probe judges the INSTALLED CORE VERSION, so the only deterministic way
    to exercise both answers is to present the real packages under a different
    `@deepseek-ai/dsh` manifest. Every other entry is a symlink into the real
    install — a symlinked package still resolves its own dependencies through
    its real path — so the row schemas under test stay the real ones.
    """
    real_node_modules = real_scope.parent
    (root / "node_modules").mkdir(parents=True)
    for entry in real_node_modules.iterdir():
        if entry.name != "@deepseek-ai":
            (root / "node_modules" / entry.name).symlink_to(entry)
    scope = root / "node_modules" / "@deepseek-ai"
    scope.mkdir()
    for entry in real_scope.iterdir():
        if entry.name != "dsh":
            (scope / entry.name).symlink_to(entry)
    fake = scope / "dsh"
    fake.mkdir()
    (fake / "package.json").write_text(
        json.dumps({"name": "@deepseek-ai/dsh", "version": version}))
    return scope


def _probe_against(scope):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to validate the composition")
    env = {**os.environ, "RQ_HARNESS_MODULES": str(scope)}
    return subprocess.run([node, str(PROBE)], cwd=REPO,
                          capture_output=True, text=True, env=env)


def test_the_probe_refuses_a_harness_outside_the_declared_range(tmp_path):
    """A green run must be about a core this release supports.

    The bundle loader SKIPS a bundle whose `peerDependencies` range the
    running core does not satisfy, so validating every row against, say,
    0.1.7-rc.2 would report the composition healthy for a core where the
    plugin never mounts. The probe therefore judges the installed core with
    the harness's OWN gate (`evaluatePluginCompatibility`) and exits 2 — the
    "no usable harness" path — when the range excludes it.

    Both answers are pinned by presenting the same real packages twice, only
    the core version differing, so the test cannot pass by skipping: a probe
    that stops refusing the old core fails the first half, and one that
    refuses the supported core fails the second. The only skip is a machine
    with no real install to shadow.
    """
    real = _installed_harness()
    if real is None:
        pytest.skip("no real DSH install to shadow the core version of")

    refused = _probe_against(_shadow_harness(real, tmp_path / "old", "0.1.7-rc.2"))
    assert refused.returncode == 2, (refused.stdout, refused.stderr)
    assert "outside the range this package supports" in refused.stderr, refused.stderr
    assert ">=0.2.0-rc.2 <0.2.1" in refused.stderr, (
        "the refusal must name the range it read from the manifest")

    accepted = _probe_against(_shadow_harness(real, tmp_path / "floor", "0.2.0-rc.2"))
    assert "outside the range this package supports" not in accepted.stderr, accepted.stderr
    assert "rows;" in accepted.stdout, (
        "the probe must reach the row summary for a supported core:\n%s\n%s"
        % (accepted.stdout, accepted.stderr))
