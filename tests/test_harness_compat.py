"""The preset must mount on the harness it runs on — validated, not assumed.

An agent preset is a tree of plugin rows, and the DSH loader validates each
row's `config` against the plugin's own schemastery schema. A row that fails
validation does not degrade: it rejects the WHOLE mount

    agent-presets: preset "rigorquant" failed to mount: …

and discovery's health check cannot see it, because that check only resolves
module NAMES (packages/preset/agent-presets/src/discovery.ts). So a renamed
config key ships a preset that looks healthy in the picker and cannot start a
session at all. That is exactly what happened when 0.1.3-alpha.2 split the
persona into `prefix`/`suffix` and this preset still passed `text`.

tests/preset_harness_probe.cjs closes the gap by loading every row through the
INSTALLED package's real `Config` — the same schema the loader uses, so there
is no second copy to drift. It resolves the harness from the `dsh` on PATH
(`tests/preset_harness_probe.cjs`), and skips when there is no DSH to check
against, because this repository is also developed and packaged without one.
"""

import shutil
import subprocess

import pytest

from conftest import REPO

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
    if out.returncode == 2 and "cannot locate an installed harness" in out.stderr:
        pytest.skip("no DSH install to validate the composition against")
    assert out.returncode == 0, (
        "the composition has a row the installed harness rejects (a row whose "
        "config fails validation rejects the whole preset mount):\n%s\n%s"
        % (out.stdout, out.stderr))


def test_the_probe_finds_the_roles_delivery_and_present_rows():
    """A green run must mean the ROWS ARE THERE, not that the probe gave up.

    The probe prints one line per row; this pins that the preset still mounts
    the delegation tools, the `present` row the deliverables flow needs, and
    the `command-goal` row that supplies `/goal`.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to validate the composition")
    out = subprocess.run([node, str(PROBE)], cwd=REPO,
                         capture_output=True, text=True)
    if out.returncode == 2 and "cannot locate an installed harness" in out.stderr:
        pytest.skip("no DSH install to validate the composition against")
    for needle in (
        "@deepseek-ai/dsh-tool-present",
        "@deepseek-ai/dsh-command-goal",
        "@deepseek-ai/dsh-tool-subagent",
        "@deepseek-ai/dsh-persona",
    ):
        assert needle in out.stdout, "%s is no longer mounted" % needle
    assert "0 hard failure(s)" in out.stdout, out.stdout
