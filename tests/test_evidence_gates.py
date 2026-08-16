"""The PASS gate must refuse a study that records no research.

Each test removes exactly one piece of evidence from the golden study and
asserts the validator refuses the PASS.
"""

import json
import shutil

from conftest import golden_study, read_study, run_check, write_study


def test_golden_study_passes(study, tex_available):
    code, out = run_check(study)
    assert code == 0, out


def test_stage3_outputs_must_not_be_empty(study, tex_available):
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["outputs"] = []
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "stage3" in out and "outputs" in out


def test_stage5_outputs_must_not_be_empty(study, tex_available):
    s = read_study(study)
    s["validity_stages"]["stage5_domain_scale"]["outputs"] = []
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "stage5" in out and "outputs" in out


def test_evidence_keywords_in_study_json_do_not_satisfy_the_gate(study, tex_available):
    """study.json must not be able to vouch for itself.

    Seeds, the N-grid, failure conditions and mutations are evidence recorded by
    the audit track; a study that merely mentions the words in its own identity
    file has produced nothing.
    """
    (study / "audits" / "battery-results.md").unlink()
    s = read_study(study)
    s["notes"] = (
        "seed=1; N in {1e3,1e4,1e5}; failure condition: none; mutation: none"
    )
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "failure condition" in out or "N-grid" in out


def test_empty_derivations_directory_refused(study, tex_available):
    """The ground-truth track must have left something behind.

    stage-3 is re-pointed at a file that still exists, so the empty
    `derivations/` directory is the only remaining defect.
    """
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["outputs"] = ["audits/battery-results.md"]
    write_study(study, s)
    for p in (study / "derivations").iterdir():
        p.unlink()
    code, out = run_check(study)
    assert code == 1
    assert "derivations" in out and "empty" in out


def test_registry_needs_a_real_passed_route_not_the_substring(study, tex_available):
    """A registry whose only 'passed' is decorative must not satisfy the gate."""
    (study / "registry.json").write_text(
        json.dumps(
            {
                "task": "rq-minvar-demo",
                "rounds": 1,
                "subproblems": {
                    "SP1": {"status": "active", "families": []},
                    "SP2": {"status": "active", "families": []},
                    "SP3": {
                        "status": "passed",
                        "families": [
                            {
                                "familyId": "lagrangian-stationarity",
                                "idea": "closed form",
                                "routes": [
                                    {
                                        "routeId": "dense-illconditioned",
                                        "status": "blocked",
                                        "blockedReason": "the ill-conditioned instance was never run",
                                        "outputs": [],
                                    }
                                ],
                            }
                        ],
                    },
                },
            }
        )
    )
    code, out = run_check(study)
    assert code == 1
    assert "passed route" in out


def test_passed_route_must_reference_an_existing_output(study, tex_available):
    """`passed` requires an audit reference (lifecycle.md), not a bare status."""
    reg = json.loads((study / "registry.json").read_text())
    for sp in reg["subproblems"].values():
        for fam in sp["families"]:
            for route in fam["routes"]:
                route["outputs"] = []
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "outputs" in out


def test_registry_keys_must_match_study_subproblem_ids(study, tex_available):
    reg = json.loads((study / "registry.json").read_text())
    reg["subproblems"]["SP9"] = reg["subproblems"].pop("SP3")
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "SP9" in out or "do not match" in out


def test_missing_lln_grid_refused(study, tex_available):
    s = read_study(study)
    del s["tolerances"]["stochastic"]["lln_grid"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "lln_grid" in out


def test_status_mentioning_pass_in_prose_is_not_a_pass_claim(study):
    """'no PASS yet' is a blocked study, and must not trip the PASS gates."""
    s = read_study(study)
    s["status"] = "round 2: SP3 active, no PASS yet"
    del s["validity_stages"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_a_fresh_intake_study_is_accepted(tmp_path):
    """rq_check runs at intake too, where the record is legitimately empty.

    A brand-new study has no derivations, no audits, and no artifacts yet; only
    a study that CLAIMS a PASS owes evidence.
    """
    root = tmp_path / "intake"
    root.mkdir()
    (root / "derivations").mkdir()
    (root / "audits").mkdir()
    s = read_study(golden_study(tmp_path / "src"))
    s["status"] = "intake: round 0"
    del s["validity_stages"]
    (root / "study.json").write_text(json.dumps(s))
    (root / "registry.json").write_text(
        json.dumps({"task": s["task_id"], "rounds": 0, "subproblems": {
            sp["id"]: {"status": "active", "families": []} for sp in s["subproblems"]}}))
    code, out = run_check(root)
    assert code == 0, out


def test_reopened_study_is_not_a_pass_claim(study):
    """A status that begins with PASS but is marked reopened is no longer a claim.

    Reopening re-enters active work, so the PASS gates are skipped and the
    validator reports "no PASS claimed" rather than certifying an empty record.
    """
    s = read_study(study)
    s["status"] = "PASS reopened"
    del s["validity_stages"]
    write_study(study, s)
    reg = json.loads((study / "registry.json").read_text())
    for sp in reg["subproblems"].values():
        sp["status"] = "active"
        for fam in sp["families"]:
            for route in fam["routes"]:
                route["status"] = "active"
                route["outputs"] = []
    (study / "registry.json").write_text(json.dumps(reg))
    for d in ("derivations", "audits", "artifacts"):
        shutil.rmtree(study / d, ignore_errors=True)
    code, out = run_check(study)
    assert code == 0, out
    assert "no PASS claimed" in out


def test_stage5_diagonal_instance_is_refused(study, tex_available):
    """A still-diagonal domain-scale instance is the same special family."""
    s = read_study(study)
    s["validity_stages"]["stage5_domain_scale"]["instance"] = "another diagonal covariance matrix"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "stage5" in out


def test_stage5_negated_diagonal_instance_is_allowed(study, tex_available):
    """'non-diagonal' is genuinely non-special and must not trip the gate."""
    s = read_study(study)
    s["validity_stages"]["stage5_domain_scale"]["instance"] = "non-diagonal covariance matrix"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_stage5_restating_a_simplified_case_is_refused(study, tex_available):
    """The domain-scale instance must not just be another simplified case."""
    s = read_study(study)
    s["simplified_cases"] = ["icosahedron"]
    s["validity_stages"]["stage5_domain_scale"]["instance"] = "an icosahedron"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "stage5" in out


def test_absolute_output_path_is_refused(study, tex_available):
    """Evidence outputs are study-root-relative; absolute paths escape the study."""
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["outputs"] = ["/etc/hosts"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "study-root-relative" in out


def test_output_escaping_the_study_root_is_refused(study, tex_available):
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["outputs"] = ["../outside.md"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "study-root-relative" in out


def test_output_naming_the_validators_report_is_refused(study, tex_available):
    """The validator's own report is output, not evidence; it cannot vouch."""
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["outputs"] = ["audits/rq-check.json"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "report" in out
