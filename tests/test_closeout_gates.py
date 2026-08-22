"""The close-out gates: reproducibility is the record; junk is derived state.

Core philosophy (references/reproducibility.md): a fresh clone regenerates
every piece of study evidence, and nothing disposable sits on the committed
surface. Each test starts from the golden study and introduces exactly one
violation of the close-out rules, asserting the validator refuses the PASS.
"""

import json

from conftest import run_check


def _append_paper(study, text: str) -> None:
    p = study / "artifacts" / "paper" / "main.tex"
    body = p.read_text()
    p.write_text(body.replace("\\end{document}", text + "\n\\end{document}"))


def test_derived_state_on_committed_surface_refused(study, tex_available):
    """A venv on the committed surface is derived state, not record."""
    (study / "venv").mkdir()
    code, out = run_check(study)
    assert code == 1
    assert "junk" in out and "venv" in out


def test_os_metadata_on_committed_surface_refused(study, tex_available):
    (study / ".DS_Store").write_text("")
    code, out = run_check(study)
    assert code == 1
    assert "junk" in out and ".DS_Store" in out


def test_junk_under_interim_is_tolerated(study, tex_available):
    """interim/ is the designated scratch home: derived state belongs there."""
    (study / "interim").mkdir()
    (study / "interim" / "venv").mkdir()
    (study / "interim" / "uv-cache").mkdir()
    (study / "interim" / "tmp" / "__pycache__").mkdir(parents=True)
    (study / "interim" / "tmp" / "module.pyc").write_text("")
    code, out = run_check(study)
    assert code == 0, out


def test_midrun_status_with_junk_is_not_blocked(study, tex_available):
    """The close-out gates fire at PASS time, not during the search."""
    (study / "venv").mkdir()
    s = json.loads((study / "study.json").read_text())
    s["status"] = "round 2: SP1 active, no PASS yet"
    (study / "study.json").write_text(json.dumps(s, indent=2) + "\n")
    code, out = run_check(study)
    assert code == 0, out


def test_deliverable_citing_scratch_is_refused(study, tex_available):
    """Audience-facing documents never treat scratch as record."""
    _append_paper(study, r"Run: python interim/gt-scripts/gt-a-symbolic.py")
    code, out = run_check(study)
    assert code == 1
    assert "scratch" in out and "interim/" in out


def test_scratch_home_env_assignment_is_tolerated(study, tex_available):
    """Pointing uv's cache/env at the designated scratch home is exactly what
    interim/ is for; only FILE citations into scratch are defects."""
    _append_paper(
        study,
        r"\verb|UV_CACHE_DIR=\"$PWD/interim/tmp/uv-cache\"| and "
        r"\verb|UV_PROJECT_ENVIRONMENT=\"$PWD/interim/venv\"|.",
    )
    code, out = run_check(study)
    assert code == 0, out


def test_deliverable_citing_missing_tracked_path_is_refused(study, tex_available):
    """A reproduction command must resolve from the study root."""
    _append_paper(study, r"Reproduce with \texttt{code/gt-a-symbolic.py}.")
    code, out = run_check(study)
    assert code == 1
    assert "does not exist" in out and "code/gt-a-symbolic.py" in out


def test_deliverable_citing_existing_tracked_path_passes(study, tex_available):
    """A tracked, existing path in the deliverable is the happy path."""
    (study / "code").mkdir()
    (study / "code" / "gt-a-symbolic.py").write_text(
        "# ground-truth symbolic track\n")
    _append_paper(study, r"Reproduce with \texttt{code/gt-a-symbolic.py}.")
    code, out = run_check(study)
    assert code == 0, out


def test_deliverable_citing_existing_derivation_path_passes(study, tex_available):
    """Record paths (derivations/) already resolve; they must stay green."""
    _append_paper(
        study,
        r"Ground truth: \texttt{derivations/gt-a-symbolic.md} and "
        r"\texttt{derivations/gt-b-bruteforce.md}.",
    )
    code, out = run_check(study)
    assert code == 0, out
