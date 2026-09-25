"""The PASS gate must refuse a study whose environment is not in its record.

Issue #36, amending Decision 21. A study carries its own lane declaration:
`env/pyproject.toml` and `env/uv.lock`, copied from the shipped lane at
intake and committed with the record. The venv and uv cache are scratch
under `interim/`. The lane RigorQuant installs under `$DSH_HOME` is only the
template, and every release replaces it, so a study that cites it cannot be
rebuilt from a clone.

Each test breaks exactly one part of that contract in the golden study and
reads the `evidence.lane` problem off the JSON report, so the assertions hold
with or without a TeX engine.
"""

import json
import shutil

from conftest import read_study, run_check, write_study


def lane_problems(study, tmp_path):
    report = tmp_path / "report.json"
    run_check(study, "--out", str(report))
    return [p for p in json.loads(report.read_text())["problems"] if p["id"] == "evidence.lane"]


def test_the_golden_study_carries_its_own_lane(study, tmp_path):
    assert (study / "env" / "pyproject.toml").is_file()
    assert (study / "env" / "uv.lock").is_file()
    assert read_study(study)["env_lane"] == "env"
    assert lane_problems(study, tmp_path) == []


def test_a_missing_lockfile_is_refused(study, tmp_path):
    (study / "env" / "uv.lock").unlink()
    [problem] = lane_problems(study, tmp_path)
    assert "env/uv.lock" in problem["message"]


def test_a_missing_pyproject_is_refused(study, tmp_path):
    (study / "env" / "pyproject.toml").unlink()
    [problem] = lane_problems(study, tmp_path)
    assert "env/pyproject.toml" in problem["message"]


def test_an_empty_lockfile_is_refused(study, tmp_path):
    (study / "env" / "uv.lock").write_text("")
    [problem] = lane_problems(study, tmp_path)
    assert "env/uv.lock" in problem["message"]


def test_a_lane_kept_only_in_scratch_is_refused(study, tmp_path):
    """interim/ is gitignored: a lane there does not travel with a clone."""
    (study / "interim").mkdir(exist_ok=True)
    shutil.move(str(study / "env"), str(study / "interim" / "env"))
    s = read_study(study)
    s["env_lane"] = "interim/env"
    write_study(study, s)
    problems = lane_problems(study, tmp_path)
    assert problems, "a lane under interim/ was accepted as record"


def test_the_shared_template_is_refused_as_the_studys_lane(study, tmp_path):
    """0.5.0 recorded the $DSH_HOME template; a release replaces it."""
    s = read_study(study)
    s["env_lane"] = "/opt/dsh/share/rigorquant/env"
    write_study(study, s)
    [problem] = lane_problems(study, tmp_path)
    assert "env_lane" in problem["message"]
    # The refusal says how an in-flight study adopts its own lane.
    assert "share/rigorquant/env" in problem["message"] and "env/" in problem["message"]


def test_an_absolute_path_to_the_studys_own_lane_is_accepted(study, tmp_path):
    s = read_study(study)
    s["env_lane"] = str(study / "env")
    write_study(study, s)
    assert lane_problems(study, tmp_path) == []


def test_a_pass_without_any_env_lane_is_refused(study, tmp_path):
    s = read_study(study)
    del s["env_lane"]
    write_study(study, s)
    [problem] = lane_problems(study, tmp_path)
    assert "env_lane" in problem["message"]


def test_the_lane_is_not_owed_before_a_pass_is_claimed(study, tmp_path):
    """At intake, before Step 2, the study has no lane yet."""
    shutil.rmtree(study / "env")
    s = read_study(study)
    del s["env_lane"]
    s["status"] = "round 1: SP1 active"
    write_study(study, s)
    assert lane_problems(study, tmp_path) == []


def test_skill_step_2_gives_each_study_its_own_lane():
    """The procedure the validator enforces is the one the skill teaches."""
    from conftest import SKILL_DIR
    skill = (SKILL_DIR / "SKILL.md").read_text()
    step = skill[skill.index("## Step 2 — "):skill.index("## Step 2b")]
    flat = " ".join(step.split())
    for required in ("$DSH_HOME/share/rigorquant/env", "env/pyproject.toml", "env/uv.lock",
                     '"env_lane": "env"', "uv sync --frozen --project env",
                     "uv add --project env", "interim/venv", "interim/uv-cache"):
        assert required in flat, "SKILL.md Step 2 never says %r" % required
    reproducibility = (SKILL_DIR / "references" / "reproducibility.md").read_text()
    assert "evidence.lane" in reproducibility
