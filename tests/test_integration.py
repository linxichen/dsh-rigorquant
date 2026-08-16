"""End-to-end behaviour: the forged study, the JSON report, schema authority."""

import json

import pytest
from conftest import RQ_CHECK, SKILL_DIR, read_study, run_check, write_study


FORGED_PAPER = r"""\documentclass{article}
\begin{document}
This paper says nothing. totally-bogus \cite{x}
\section{Notation}
ball, uniform.
\section{Statement} method validity certification limitations reproduction.
\bibliography{refs}
\bibliographystyle{plain}
\end{document}
"""


def test_the_reviews_forged_study_is_refused(tmp_path, tex_available):
    """The exact content-free study that the old validator certified as PASS.

    Empty derivations, empty stage outputs, a one-line adversary report, and a
    paper whose body is "This paper says nothing."
    """
    root = tmp_path / "forged"
    (root / "artifacts" / "paper").mkdir(parents=True)
    (root / "audits").mkdir()
    (root / "derivations").mkdir()
    (root / "study.json").write_text(json.dumps({
        "slug": "totally-bogus",
        "title": "Nothing At All",
        "mode": "repo-root",
        "repo_root": "/tmp",
        "env_lane": "/tmp/env",
        "task_id": "T1",
        "created": "2026-08-15",
        "statement": "lorem ipsum",
        "broad_criterion": "lorem ipsum broad",
        "success_criterion": "lorem",
        "subproblems": [
            {"id": "SP1", "name": "a", "status": "novel", "stage": "generalization",
             "success_criterion": "x"},
            {"id": "SP2", "name": "b", "status": "novel", "stage": "domain-scale",
             "success_criterion": "y"},
        ],
        "simplified_cases": ["none"],
        "seeds": {"task_seed": 1},
        "tolerances": {"deterministic": {}, "stochastic": {}},
        "budget": {},
        "status": "PASS",
        "validity_stages": {
            "stage3_general_claim": {"claim": "it works",
                                     "evidence_level": "falsification-surviving",
                                     "outputs": []},
            "stage5_domain_scale": {"instance": "a polytope", "outputs": []},
        },
        "deliverables": {
            "paper": "required", "slides": "not-required:lazy", "web": "optional",
            "consultation_pending": False,
            "audience": {"paper": {"role": "x", "sentence": "This paper says nothing."}},
        },
        "notes": "seed=1; N in {1e3,1e4}; failure condition: none; mutation: none",
    }))
    (root / "registry.json").write_text(
        '{"task":"T1","rounds":1,"subproblems":{"SP1":{"status":"passed","families":[]}}}')
    (root / "audits" / "document-adversary-paper.md").write_text("VERDICT: PASS\n")
    (root / "artifacts" / "paper" / "main.tex").write_text(FORGED_PAPER)
    (root / "artifacts" / "paper" / "refs.bib").write_text("@misc{x, title={y}}\n")

    code, out = run_check(root)
    assert code == 1, out
    # It must be refused for the substantive reasons, not one incidental typo.
    for expected in ("outputs", "derivations", "passed route", "N-grid"):
        assert expected in out, "forgery not caught on %r:\n%s" % (expected, out)


def test_report_is_written_with_the_out_flag(study, tmp_path, tex_available):
    out_path = tmp_path / "report.json"
    code, _ = run_check(study, "--out", str(out_path))
    assert code == 0
    report = json.loads(out_path.read_text())
    assert report["schema"] == "rq-check-report"
    assert report["result"] == "pass"
    assert report["claiming_pass"] is True
    assert report["problems"] == []
    assert set(report["hashes"]) == {"study.json", "registry.json"}
    assert report["environment"]["python"]


def test_report_records_the_problems_on_failure(study, tmp_path, tex_available):
    s = read_study(study)
    del s["validity_stages"]
    write_study(study, s)
    out_path = tmp_path / "report.json"
    code, _ = run_check(study, "--out", str(out_path))
    assert code == 1
    report = json.loads(out_path.read_text())
    assert report["result"] == "fail"
    assert any(p["id"].startswith("stage3") for p in report["problems"])


def _schema():
    return json.loads((SKILL_DIR / "schemas" / "study.schema.json").read_text())


@pytest.mark.parametrize("field", _schema()["required"])
def test_every_schema_required_field_is_enforced(study, field, tex_available):
    """The shipped schema is the single source of truth for required fields.

    If the validator ever grows its own private list again, a field present in
    one and absent from the other shows up here.
    """
    s = read_study(study)
    del s[field]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1, "deleting %r left the study valid" % field
    assert field in out


def test_missing_schema_file_fails_loudly(study, tmp_path, monkeypatch, tex_available):
    """A validator that cannot find its schemas must not silently accept."""
    import shutil

    fake_skill = tmp_path / "skill"
    (fake_skill / "scripts").mkdir(parents=True)
    shutil.copy(RQ_CHECK, fake_skill / "scripts" / "rq_check.py")
    monkeypatch.setenv("RQ_CHECK_BIN", str(fake_skill / "scripts" / "rq_check.py"))
    import subprocess
    import sys
    cp = subprocess.run(
        [sys.executable, str(fake_skill / "scripts" / "rq_check.py"), "--study", str(study)],
        capture_output=True, text=True)
    assert cp.returncode == 1
    assert "schema" in (cp.stdout + cp.stderr)


# ---------------------------------------------------- the assembled literature path


def test_a_full_literature_run_passes_end_to_end(study, tex_available):
    """docs/literature-lane.md A7: one real assembled path, not leaf unit tests.

    An intake that ran the lane leaves a known-results map, a completeness
    checklist, provenance-stripped negative exports, a verified refs-seed.bib and
    an advisory dossier -- and the study still PASSes with its paper's citations
    tracing to fetched, adversarially verified sources.
    """
    from test_literature_gate import (_completeness, _verified_source, GOOD_BIB)

    lit = study / "literature"
    lit.mkdir()
    s = read_study(study)
    s["literature"] = {
        "phase": "concluded",
        "consulted_at": "2026-08-16",
        "map_file": "literature/known-results.json",
        "negative_exports_file": "literature/negative-exports.json",
        "completeness_file": "literature/completeness.json",
        "refs_seed_file": "literature/refs-seed.bib",
        "budget": {"max_lines": 8, "max_depth": 4, "max_papers_per_line": 80,
                   "max_rounds": 8, "max_cost_usd": None, "max_wall_minutes": None},
    }
    write_study(study, s)

    settled = {"category": "settled",
               "claim": "the closed form for minimum-variance weights is standard",
               "negative_export": False, "sources": [_verified_source()]}
    impossible = {
        "category": "impossible",
        "claim": "no estimator attains the oracle variance without the true covariance",
        "negative_export": True,
        "escalation": "audits/math-lane-impossibility.md",
        "sources": [_verified_source(paper_id="arXiv:1706.03762")],
    }
    (lit / "known-results.json").write_text(json.dumps(
        {"SP1": [dict(settled)], "SP2": [dict(settled)], "SP3": [impossible]}, indent=2))
    (lit / "completeness.json").write_text(json.dumps(
        _completeness(("SP1", "SP2", "SP3")), indent=2))
    (lit / "negative-exports.json").write_text(json.dumps({"exports": [{
        "subproblem_id": "SP3",
        "constraint": "It is settled that no estimator attains the oracle variance "
                      "without the true covariance. Treat this as a closed path, not "
                      "a premise and not a clue.",
        "source_paper_id": "arXiv:1706.03762",
    }]}, indent=2))
    (lit / "refs-seed.bib").write_text(GOOD_BIB)
    (study / "audits" / "math-lane-impossibility.md").write_text(
        "# Math-lane escalation -- the exported negative\n\n"
        "The impossibility was re-derived independently by the ground-truth track "
        "before the study relied on it. VERDICT: accepted.\n")

    line_dir = study / "interim" / "lit" / "oracle-bounds"
    line_dir.mkdir(parents=True)
    (line_dir / "dossier.json").write_text(json.dumps({
        "line": "oracle-bounds",
        "frontier": ["arXiv:2401.09999 (out of scope: discrete-time only)"],
        "sweeps": ["forward citations", "surveys", "author pages"],
        "papers": [{"paper_id": "arXiv:1706.03762", "version": "v5",
                    "title": "A load-bearing bound", "claim": "no such estimator exists",
                    "evidence_quote": "Theorem 3 rules out any such estimator.",
                    "references": ["DOI:10.2307/2975974"], "cited_by": []}],
    }, indent=2))

    code, out = run_check(study)
    assert code == 0, out
