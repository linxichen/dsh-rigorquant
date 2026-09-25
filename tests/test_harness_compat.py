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
against, or when it predates declared presets (outside the package's
`>=0.1.7-rc.2 <0.1.8` range), because this repository is also developed and
packaged without one.
"""

import shutil
import subprocess

import pytest

from conftest import REPO

PROBE = REPO / "tests/preset_harness_probe.cjs"


def skip_without_harness(out):
    """Skip when the probe found no harness in the supported range."""
    if out.returncode != 2:
        return
    if "cannot locate an installed harness" in out.stderr:
        pytest.skip("no DSH install to validate the composition against")
    if "predates @deepseek-ai/dsh-agent-preset" in out.stderr:
        pytest.skip("the installed DSH predates declared presets")


def test_the_harness_probe_is_shipped():
    assert PROBE.is_file()


def test_every_preset_row_validates_against_the_installed_harness():
    """Every row's config must satisfy the installed plugin's own schema."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to validate the composition")
    out = subprocess.run([node, str(PROBE)], cwd=REPO,
                         capture_output=True, text=True)
    skip_without_harness(out)
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
    skip_without_harness(out)
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
