"""The package-shape smoke CI runs is a suite test too, in both harness shapes.

Decision 29: distribution is the plugin manager, so CI no longer runs an
installer to prove the package is installable. `tests/package_shape_smoke.py`
checks what the plugin manager and the boot sync consume -- both
`dsh.bundle.patch` files, every export, the lane templates the boot sync
copies, and the absence of any reference to the removed installer. It needs no
DSH and no network, so it runs here under the pre-commit gate even on a
machine with no harness, where the live probes skip.
"""

import os
import subprocess
import sys

from conftest import REPO

SMOKE = REPO / "tests" / "package_shape_smoke.py"


def test_package_shape_smoke_passes_with_no_dsh_on_path(tmp_path):
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)  # deliberately no `dsh` to find
    result = subprocess.run(
        [sys.executable, str(SMOKE)],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no DSH required" in result.stdout
