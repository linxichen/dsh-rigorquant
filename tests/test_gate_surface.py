"""The gate surface: refusal paths of rq_check no other module exercises.

The pre-commit hook (hooks/pre-commit) gates commits on 95% coverage of the
shipped validator, measured across the suite (see .coveragerc). This module
closes the surface: each test below pins one refusal branch -- deliverable
variants (slides/web), the document-adversary gate, declared hashes, the
procedural L4/L6/L7 gates, registry/coverage/schema negatives, the notation
and symbol audit, junk on the committed surface, and the compile pipeline's
engine-discovery branches. Every test asserts the specific refusal message,
not just a nonzero exit: a gate that fires for the wrong reason is a bug.
"""

import json
import os
import stat

import pytest

from conftest import read_study, run_check, write_study

SLIDES_TEX = r"""\documentclass{beamer}
\begin{document}
\begin{frame}{Notation}
$\Sigma$ denotes the covariance matrix, $\mathbf{1}$ the vector of ones and
$w$ the weight vector.
\end{frame}
\begin{frame}{Summary}
This deck is for a working quantitative researcher. \cite{markowitz1952}
\end{frame}
\bibliographystyle{plain}
\bibliography{../paper/refs}
\end{document}
"""


def _require_slides(study, tex=SLIDES_TEX, spec=None):
    s = read_study(study)
    s["deliverables"]["slides"] = "required"
    s["deliverables"]["audience"]["slides"] = spec or {
        "role": "researcher",
        "sentence": "This deck is for a working quantitative researcher.",
    }
    write_study(study, s)
    slides = study / "artifacts" / "slides"
    slides.mkdir(parents=True, exist_ok=True)
    if tex is not None:
        (slides / "main.tex").write_text(tex)
    (study / "audits" / "document-adversary-slides.md").write_text(
        "# Document adversary -- slides\n\nNotation frame present.\n\nVERDICT: PASS\n")


# ── run() top-level error paths ────────────────────────────────────────────


def test_a_directory_without_study_json_is_an_error(tmp_path):
    code, out = run_check(tmp_path)
    assert code == 2
    assert "no study.json" in out


def test_invalid_study_json_is_an_error(study):
    (study / "study.json").write_text("{not json")
    code, out = run_check(study)
    assert code == 2
    assert "invalid JSON" in out


def test_a_missing_registry_json_is_reported(study):
    (study / "registry.json").unlink()
    code, out = run_check(study)
    assert code == 1
    assert "registry.json missing" in out


def test_an_invalid_registry_json_is_reported(study):
    (study / "registry.json").write_text("[oops")
    code, out = run_check(study)
    assert code == 1
    assert "registry.json invalid JSON" in out


# ── deliverables declaration and consultation ──────────────────────────────


def test_a_study_without_a_deliverables_declaration_is_refused(study):
    s = read_study(study)
    del s["deliverables"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "no `deliverables` declaration" in out


def test_an_invalid_slides_declaration_is_refused(study):
    s = read_study(study)
    s["deliverables"]["slides"] = "sometimes"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "`slides` must be 'required' or 'not-required" in out


def test_an_invalid_web_declaration_is_refused(study):
    s = read_study(study)
    s["deliverables"]["web"] = "maybe"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "`web` must be 'optional' or 'required'" in out


def test_a_pending_consultation_refuses_pass(study):
    s = read_study(study)
    s["deliverables"]["consultation_pending"] = True
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "consultation_pending" in out and "not been completed" in out


def test_a_missing_paper_audience_spec_refuses_pass(study):
    s = read_study(study)
    del s["deliverables"]["audience"]["paper"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "deliverables.audience.paper is missing" in out


def test_required_slides_without_an_audience_spec_refuse_pass(study):
    _require_slides(study, spec=None)
    s = read_study(study)
    del s["deliverables"]["audience"]["slides"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "deliverables.audience.slides is missing" in out


# ── the slides-required block ──────────────────────────────────────────────


def test_a_complete_beamer_deck_is_accepted(study, tex_available):
    _require_slides(study)
    code, out = run_check(study)
    assert code == 0, out


def test_a_missing_slides_file_is_refused(study):
    _require_slides(study, tex=None)
    code, out = run_check(study)
    assert code == 1
    assert "artifacts/slides/main.tex missing" in out


def test_a_non_beamer_deck_is_refused(study, tex_available):
    _require_slides(study, tex=SLIDES_TEX.replace("beamer", "article")
                    .replace("\\begin{frame}{Notation}", "\\section{Notation}")
                    .replace("\\end{frame}", "")
                    .replace("\\begin{frame}{Summary}", "\\section{Summary}"))
    code, out = run_check(study)
    assert code == 1
    assert "not a Beamer document" in out


def test_a_deck_without_a_bibliography_is_refused(study, tex_available):
    _require_slides(study, tex=SLIDES_TEX.replace(
        "\\bibliography{../paper/refs}", ""))
    code, out = run_check(study)
    assert code == 1
    assert "slides have no" in out and "bibliography" in out


def test_a_deck_whose_bibliography_file_is_missing_is_refused(study, tex_available):
    _require_slides(study, tex=SLIDES_TEX.replace("../paper/refs", "../paper/absent"))
    code, out = run_check(study)
    assert code == 1
    assert "slides bibliography file(s) missing" in out


# ── the web-required block ─────────────────────────────────────────────────


def _require_web_files(study, page):
    s = read_study(study)
    s["deliverables"]["web"] = "required"
    s["deliverables"]["audience"]["web"] = {
        "role": "researcher",
        "sentence": "This page is written for a working quantitative researcher.",
    }
    write_study(study, s)
    web = study / "artifacts" / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "index.html").write_text(page)
    (study / "audits" / "document-adversary-web.md").write_text("VERDICT: PASS\n")


GOOD_PAGE = """<html><body>
<h1>Weights</h1>
<p>This page is written for a working quantitative researcher.</p>
<h2>References</h2>
<ul><li><a href="https://doi.org/10.2307/2975974">Markowitz, 1952</a></li></ul>
</body></html>
"""


def test_a_missing_web_page_is_refused(study):
    s = read_study(study)
    s["deliverables"]["web"] = "required"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "artifacts/web/index.html missing" in out


def test_a_non_html_web_page_is_refused(study):
    _require_web_files(study, "just plain text, deliberately longer than fifty bytes")
    code, out = run_check(study)
    assert code == 1
    assert "is not an HTML document" in out


def test_mis_nested_markup_is_refused(study):
    _require_web_files(study, GOOD_PAGE.replace(
        "<ul><li><a href", "<ul><b><li><a href"))
    code, out = run_check(study)
    assert code == 1
    assert "malformed markup" in out


def test_a_web_page_without_a_references_section_is_refused(study):
    _require_web_files(study, GOOD_PAGE.replace("<h2>References</h2>", "<h2>Notes</h2>")
                       .replace('id="references"', ""))
    code, out = run_check(study)
    assert code == 1
    assert "no references" in out


def test_a_web_page_without_its_audience_spec_sentence_is_refused(study):
    _require_web_files(study, GOOD_PAGE)
    s = read_study(study)
    del s["deliverables"]["audience"]["web"]["sentence"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "no `sentence`" in out and "artifacts/web/index.html" in out


# ── document-adversary verdicts ────────────────────────────────────────────


def test_a_missing_document_adversary_report_is_refused(study):
    (study / "audits" / "document-adversary-paper.md").unlink()
    code, out = run_check(study)
    assert code == 1
    assert "document-adversary-paper.md missing" in out


def test_a_verdictless_document_adversary_report_is_refused(study):
    (study / "audits" / "document-adversary-paper.md").write_text("Looks fine.\n")
    code, out = run_check(study)
    assert code == 1
    assert "no 'VERDICT:" in out


def test_a_needs_edits_verdict_refuses_pass(study):
    (study / "audits" / "document-adversary-paper.md").write_text(
        "Symbols undefined.\n\nVERDICT: NEEDS-EDITS\n")
    code, out = run_check(study)
    assert code == 1
    assert "verdict is NEEDS-EDITS" in out


# ── declared hashes (reproducibility R6) ───────────────────────────────────


def test_a_wrong_declared_sha256_is_refused(study, tex_available):
    code_dir = study / "code"
    code_dir.mkdir(exist_ok=True)
    (code_dir / "gen.py").write_text("print('weights')\n")
    (study / "audits" / "battery-results.md").write_text(
        (study / "audits" / "battery-results.md").read_text()
        + "\nGenerator code/gen.py sha256: " + "0" * 64 + "\n")
    code, out = run_check(study)
    assert code == 1
    assert "matches none of the referenced" in out


def test_a_correct_declared_sha256_is_accepted(study, tex_available):
    import hashlib
    code_dir = study / "code"
    code_dir.mkdir(exist_ok=True)
    (code_dir / "gen.py").write_text("print('weights')\n")
    digest = hashlib.sha256((code_dir / "gen.py").read_bytes()).hexdigest()
    (study / "audits" / "battery-results.md").write_text(
        (study / "audits" / "battery-results.md").read_text()
        + "\nGenerator code/gen.py sha256: " + digest + "\n")
    code, out = run_check(study)
    assert code == 0, out


# ── procedural gates (hard-lessons L4, L6, L7) ─────────────────────────────


def test_a_verdict_claiming_status_without_a_reference_is_refused(study):
    s = read_study(study)
    s["status"] = "PASS -- method certified"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "status asserts a certification outcome" in out


def test_a_status_anchored_by_a_frozen_hash_is_accepted(study, tex_available):
    s = read_study(study)
    s["status"] = "PASS -- certified against frozen snapshot 0123456789abcdef"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_an_edited_stage3_claim_reopens_certification(study):
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["claim_sha256"] = "0" * 64
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "text changed since the recorded digest" in out
    assert "reopens certification" in out


def test_a_schema_pin_mismatch_is_a_reintake_event(study):
    s = read_study(study)
    s["intake_pins"] = {"schema_sha256": "0" * 64, "validator_sha256": "0" * 64}
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "different study.schema.json" in out
    assert "different rq_check.py" in out


def test_matching_intake_pins_are_accepted(study, tex_available):
    import hashlib
    from conftest import REPO
    schema = (REPO / "agent-presets" / "rigorquant" / "skills" /
              "rigorquant" / "schemas" / "study.schema.json")
    s = read_study(study)
    s["intake_pins"] = {
        "schema_sha256": hashlib.sha256(schema.read_bytes()).hexdigest(),
    }
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


# ── coverage and registry negatives ────────────────────────────────────────


def test_a_missing_broad_criterion_is_refused(study):
    s = read_study(study)
    del s["broad_criterion"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "no `broad_criterion`" in out


def test_a_study_without_a_generalization_stage_is_refused(study):
    s = read_study(study)
    s["subproblems"][1]["stage"] = "reference-case"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "no subproblem has stage=generalization" in out


def test_registry_keys_must_match_study_ids(study):
    reg = json.loads((study / "registry.json").read_text())
    reg["subproblems"]["SP9"] = reg["subproblems"].pop("SP1")
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "keys do not match" in out and "SP9" in out and "SP1" in out


def test_a_passed_subproblem_without_a_passed_route_is_refused(study):
    reg = json.loads((study / "registry.json").read_text())
    reg["subproblems"]["SP1"]["families"][0]["routes"][0]["status"] = "blocked"
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "marked passed but carries no passed route" in out


def test_a_passed_route_with_invalid_output_paths_is_refused(study):
    reg = json.loads((study / "registry.json").read_text())
    route = reg["subproblems"]["SP1"]["families"][0]["routes"][0]
    route["outputs"] = ["", "/abs/x.md", "../escape.md", "audits/rq-check.json"]
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "invalid output paths" in out


def test_a_passed_route_with_missing_outputs_is_refused(study):
    reg = json.loads((study / "registry.json").read_text())
    reg["subproblems"]["SP1"]["families"][0]["routes"][0]["outputs"] = [
        "audits/absent.md"]
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "outputs that do not exist" in out


def test_a_passed_route_with_empty_outputs_is_refused(study):
    reg = json.loads((study / "registry.json").read_text())
    reg["subproblems"]["SP1"]["families"][0]["routes"][0]["outputs"] = []
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "passed with empty outputs" in out


def test_a_pass_without_any_passed_route_is_refused(study):
    for key in ("SP1", "SP2", "SP3"):
        reg = json.loads((study / "registry.json").read_text())
        for fam in reg["subproblems"][key].get("families", []):
            for route in fam.get("routes", []):
                route["status"] = "blocked"
        (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    assert code == 1
    assert "no audit-referenced passed route" in out


def test_a_missing_derivations_directory_is_refused(study):
    import shutil
    shutil.rmtree(study / "derivations")
    code, out = run_check(study)
    assert code == 1
    assert "missing directory: derivations/" in out


# ── schema negatives (the hand-rolled validator's keyword branches) ────────


def test_an_enum_violation_is_reported(study):
    s = read_study(study)
    s["subproblems"][0]["status"] = "maybe"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "is not one of" in out


def test_a_minimum_violation_is_reported(study):
    s = read_study(study)
    s["budget"]["max_orchestrator_rounds"] = 0
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "< minimum" in out


def test_a_pattern_violation_is_reported(study):
    s = read_study(study)
    s["slug"] = "not the slug pattern at all"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "does not match" in out


def test_a_type_violation_is_reported(study):
    s = read_study(study)
    s["seeds"] = "nope"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "expected type" in out


# ── evidence and stage branches ────────────────────────────────────────────


def test_stage_outputs_with_absolute_paths_are_refused(study):
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["outputs"] = ["/abs/claim.md"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "not study-root-relative" in out


def test_a_special_body_domain_scale_instance_is_refused(study):
    s = read_study(study)
    s["validity_stages"]["stage5_domain_scale"]["instance"] = "diagonal covariance"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "names only a reference/special body" in out


def test_missing_seed_in_the_record_is_refused(study):
    (study / "audits" / "battery-results.md").write_text(
        "# Battery\n\nN in {1e3,1e4}; failure condition: none; mutation: none\n")
    (study / "derivations" / "gt-a-symbolic.md").write_text("nothing here\n")
    (study / "derivations" / "gt-b-bruteforce.md").write_text("nothing here\n")
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace(
        "Seeds and the pinned-lane command are recorded in the battery results.",
        "The battery results carry the run details."))
    code, out = run_check(study)
    assert code == 1
    assert "no seed recorded" in out


def test_a_missing_n_grid_is_refused(study):
    battery = (study / "audits" / "battery-results.md")
    battery.write_text(battery.read_text().split("## Gate D")[0]
                       + "\nRun seed: task_seed 1; failure condition: none; mutation: none\n")
    code, out = run_check(study)
    assert code == 1
    assert "no seeded N-grid" in out


def test_a_missing_failure_condition_is_refused(study):
    battery = (study / "audits" / "battery-results.md")
    battery.write_text(battery.read_text().replace("Failure condition:", "Predicate:"))
    code, out = run_check(study)
    assert code == 1
    assert "no audit declares a 'failure condition'" in out


def test_a_missing_mutation_note_is_refused(study):
    battery = (study / "audits" / "battery-results.md")
    battery.write_text(battery.read_text().replace("Mutation detected:", "Caught:"))
    code, out = run_check(study)
    assert code == 1
    assert "no audit declares a 'mutation'" in out


# ── notation, symbols, overclaim ───────────────────────────────────────────


def test_a_paper_without_a_notation_block_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace("\\section{Notation}", "\\section{Setup}"))
    code, out = run_check(study)
    assert code == 1
    assert "no Notation/Definitions block" in out


def test_an_undefined_symbol_witness_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace(
        "\\section{Validity}",
        "\\section{Validity}\nThe sampler runs in $O^*(n)$ rounds."))
    code, out = run_check(study)
    assert code == 1
    assert "does not\nnot define it" in out or "does not define it" in out


def test_an_avoided_convention_is_refused(study, tex_available):
    s = read_study(study)
    s["deliverables"]["audience"]["paper"]["avoid"] = ["lesssim"]
    write_study(study, s)
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace(
        "\\section{Validity}",
        "\\section{Validity}\nThe error is $\\lesssim \\varepsilon$."))
    code, out = run_check(study)
    assert code == 1
    assert "avoided convention" in out


def test_an_overclaimed_evidence_level_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace(
        "Two independent derivations agree",
        "The claim is certificate-checked throughout"))
    code, out = run_check(study)
    assert code == 1
    assert "overclaim" in out


def test_a_mismatched_audience_sentence_is_refused(study, tex_available):
    s = read_study(study)
    s["deliverables"]["audience"]["paper"]["sentence"] = "Written for poets."
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "does not state its confirmed audience sentence" in out


# ── close-out junk and reproducibility paths ───────────────────────────────


def test_derived_junk_on_the_committed_surface_is_refused(study):
    (study / ".DS_Store").write_text("junk")
    (study / "__pycache__").mkdir()
    (study / "__pycache__" / "x.pyc").write_text("")
    code, out = run_check(study)
    assert code == 1
    assert "derived junk on the committed surface" in out


def test_a_scratch_file_citation_in_a_deliverable_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace(
        "\\section{Reproduction}",
        "\\section{Reproduction}\nSee interim/tmp/gen.py for the generator."))
    code, out = run_check(study)
    assert code == 1
    assert "cites a file under the gitignored scratch" in out


def test_an_unresolvable_reproduction_path_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace(
        "Seeds and the pinned-lane command are recorded in the battery results.",
        "Run: python code/missing.py"))
    code, out = run_check(study)
    assert code == 1
    assert "references 'code/missing.py' which does not exist" in out


# ── compile pipeline: engine discovery branches ────────────────────────────


def _fake_engine(tmp_path, name, body):
    fake = tmp_path / "fakebin"
    fake.mkdir(exist_ok=True)
    exe = fake / name
    exe.write_text("#!/bin/sh\n" + body)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(fake)


def test_a_tectonic_style_engine_is_discovered_and_used(study, tmp_path,
                                                        monkeypatch, tex_available):
    fakebin = _fake_engine(tmp_path, "tectonic", "exit 0\n")
    monkeypatch.setenv("PATH", fakebin + os.pathsep + os.environ["PATH"])
    code, out = run_check(study)
    assert code == 0, out


def test_a_failing_engine_refuses_pass(study, tmp_path, monkeypatch, tex_available):
    fakebin = _fake_engine(tmp_path, "tectonic", "echo 'boom' >&2\nexit 3\n")
    monkeypatch.setenv("PATH", fakebin + os.pathsep + os.environ["PATH"])
    code, out = run_check(study)
    assert code == 1
    assert "fails compilation" in out and "tectonic" in out


# ── round 2: schema keyword branches, corpus edges, paper negatives ─────────


def test_schema_keyword_violations_are_reported_together(study):
    s = read_study(study)
    s["budget"]["max_orchestrator_rounds"] = True      # boolean is not a number
    s["tolerances"]["stochastic"]["confidence"] = 0    # exclusiveMinimum
    s["literature"] = {"phase": "skipped", "skip_reason": ""}  # minLength
    s["subproblems"][0]["mystery"] = "unexpected"      # additionalProperties
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "expected type" in out
    assert "<= exclusiveMinimum" in out
    assert "needs at least 1 character" in out
    assert "unexpected field 'mystery'" in out


def test_an_exclusive_maximum_violation_is_reported(study):
    s = read_study(study)
    s["tolerances"]["stochastic"]["confidence"] = 1
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert ">= exclusiveMaximum" in out


def test_the_validators_own_report_is_not_evidence(study, tex_available):
    (study / "audits" / "rq-check.json").write_text("{}")
    code, out = run_check(study)
    assert code == 0, out  # present but excluded from the corpus


def test_unreadable_record_files_are_skipped_not_fatal(study, tex_available):
    locked = study / "audits" / "locked.md"
    locked.write_text("seed 1")
    locked.chmod(0)
    (study / "audits" / "data.csv").write_text("n,err\n1e3,0\n")
    code, out = run_check(study)
    locked.chmod(0o644)
    assert code == 0, out


def test_a_registry_without_a_subproblems_map_fails_the_schema(study):
    (study / "registry.json").write_text('{"task": "T1", "rounds": 1}')
    code, out = run_check(study)
    assert code == 1
    assert "missing required field 'subproblems'" in out


def test_non_dict_families_and_routes_are_ignored_by_the_gate(study):
    reg = json.loads((study / "registry.json").read_text())
    reg["subproblems"]["SP1"]["families"].append("not-a-family")
    reg["subproblems"]["SP1"]["families"][0]["routes"].append("not-a-route")
    (study / "registry.json").write_text(json.dumps(reg))
    code, out = run_check(study)
    # The schema rejects the strings; the gate itself must not crash on them.
    assert code == 1
    assert "expected type" in out
    assert "marked passed but carries no passed route" not in out


def test_a_bad_evidence_level_and_empty_claim_are_refused(study):
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["evidence_level"] = "vibes"
    s["validity_stages"]["stage3_general_claim"]["claim"] = ""
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "evidence_level 'vibes' is not one of" in out
    assert "has no `claim` text" in out


def test_an_unnamed_domain_scale_instance_is_refused(study):
    s = read_study(study)
    s["validity_stages"]["stage5_domain_scale"]["instance"] = ""
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "does not name its instance" in out


def test_a_nonnumeric_declared_tolerance_is_skipped_not_fatal(study, tex_available):
    s = read_study(study)
    s["tolerances"]["deterministic"]["abs"] = "tight"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_a_bare_witness_list_in_the_symbol_registry_is_used(study, tex_available):
    s = read_study(study)
    s["deliverables"]["audience"]["paper"]["symbols"] = {
        "eta": ["eta-is-the-learning-rate"]}
    write_study(study, s)
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace(
        "\\section{Validity}",
        "\\section{Validity}\nThe step size $\\eta$ is fixed."))
    code, out = run_check(study)
    assert code == 1
    assert "does not" in out and "define it" in out


def test_junk_under_scratch_and_git_is_exempt(study, tex_available):
    interim = study / "interim"
    interim.mkdir()
    (interim / "scratch.md").write_text("junk")
    git = study / ".git"
    git.mkdir()
    (git / "config").write_text("junk")
    (study / ".DS_Store").write_text("junk")
    code, out = run_check(study)
    assert code == 1
    assert "derived junk" in out and "interim" not in out.split("junk")[0]
    import shutil
    shutil.rmtree(git)


def test_a_missing_artifacts_tree_reports_the_missing_paper(study):
    import shutil
    shutil.rmtree(study / "artifacts")
    code, out = run_check(study)
    assert code == 1
    assert "artifacts/paper/main.tex missing or empty" in out


def test_a_paper_without_documentclass_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace("\\documentclass{article}", ""))
    code, out = run_check(study)
    assert code == 1
    assert "no \\documentclass" in out


def test_a_paper_missing_a_mandatory_section_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace("\\section{Statement}", "\\section{Task}"))
    code, out = run_check(study)
    assert code == 1
    assert "mandatory section" in out or "missing" in out.lower() and "section" in out.lower()


def test_a_paper_without_a_bibliography_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace("\\bibliography{refs}", ""))
    code, out = run_check(study)
    assert code == 1
    assert "no \\bibliography" in out


def test_a_paper_whose_bibliography_file_is_missing_is_refused(study, tex_available):
    paper = study / "artifacts" / "paper" / "main.tex"
    paper.write_text(paper.read_text().replace("\\bibliography{refs}", "\\bibliography{absent}"))
    code, out = run_check(study)
    assert code == 1
    assert "bibliography file(s) missing" in out


# ── round 2: the HTML balance parser's remaining branches ──────────────────


def test_a_self_closing_tag_does_not_open_the_stack(study):
    _require_web_files(study, GOOD_PAGE.replace("<h1>Weights</h1>", "<h1>Weights<br/></h1>"))
    code, out = run_check(study)
    assert code == 0, out


def test_a_stray_close_after_the_stack_empties_is_refused(study):
    _require_web_files(study, GOOD_PAGE + "\n</div>")
    code, out = run_check(study)
    assert code == 1
    assert "unexpected closing" in out


def test_a_closing_void_tag_is_ignored(study):
    _require_web_files(study, GOOD_PAGE.replace("<h1>Weights</h1>", "<h1>Weights</h1></br>"))
    code, out = run_check(study)
    assert code == 0, out


def test_an_omissible_close_chain_closes_its_ancestors(study):
    _require_web_files(study, GOOD_PAGE.replace(
        "<ul><li><a href", "<ul><li><p>see <a href"))
    code, out = run_check(study)
    assert code == 0, out


# ── round 2: compile pipeline failure modes ────────────────────────────────


def test_an_unexecutable_engine_fails_loudly(study, tmp_path, monkeypatch, tex_available):
    fake = tmp_path / "fakebin"
    fake.mkdir()
    exe = fake / "tectonic"
    exe.write_bytes(b"\x00\x01not-a-script")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake) + os.pathsep + os.environ["PATH"])
    code, out = run_check(study)
    assert code == 1
    assert "compile check failed" in out


# ── round 2: literature gate failure modes ─────────────────────────────────


def _lit_declare(study, **overrides):
    s = read_study(study)
    s["literature"] = {
        "phase": "concluded",
        "consulted_at": "2026-08-16",
        "map_file": "literature/known-results.json",
        "negative_exports_file": "literature/negative-exports.json",
        "completeness_file": "literature/completeness.json",
        "refs_seed_file": "literature/refs-seed.bib",
        "budget": {"max_lines": 4, "max_depth": 3, "max_papers_per_line": 20,
                   "max_rounds": 4},
    }
    s["literature"].update(overrides)
    write_study(study, s)
    lit = study / "literature"
    lit.mkdir(exist_ok=True)
    return lit


def test_invalid_json_across_the_literature_record_is_reported(study):
    lit = _lit_declare(study)
    for name in ("known-results.json", "negative-exports.json", "completeness.json"):
        (lit / name).write_text("{oops")
    dossier = study / "interim" / "lit" / "alpha"
    dossier.mkdir(parents=True)
    (dossier / "dossier.json").write_text("{oops")
    (lit / "refs-seed.bib").write_text("@misc{x, title={y}}\n")
    code, out = run_check(study)
    assert code == 1
    for frag in ("known-results.json is not valid JSON",
                 "negative-exports.json is not valid JSON",
                 "completeness.json is not valid JSON",
                 "dossier.json is not valid JSON"):
        assert frag in out, frag


def test_a_map_entry_violating_the_schema_is_reported(study):
    lit = _lit_declare(study)
    (lit / "known-results.json").write_text(json.dumps({"SP1": [{}]}))
    (lit / "negative-exports.json").write_text('{"exports": []}')
    (lit / "completeness.json").write_text('{"lines": []}')
    (lit / "refs-seed.bib").write_text("@misc{x, title={y}}\n")
    code, out = run_check(study)
    assert code == 1
    assert "known-results.json does not match" in out


def test_junk_entries_in_the_map_and_completeness_are_tolerated(study):
    lit = _lit_declare(study)
    (lit / "known-results.json").write_text(json.dumps({
        "SP1": ["junk-entry", {"sources": ["junk-source"], "category": "settled",
                               "claim": "c", "negative_export": False}]}))
    (lit / "negative-exports.json").write_text('{"exports": ["junk-export"]}')
    (lit / "completeness.json").write_text(json.dumps({"lines": ["junk-line", {}]}))
    (lit / "refs-seed.bib").write_text("@misc{x, title={y}}\n")
    code, out = run_check(study)
    assert code == 1  # SP1 is known with nothing verified behind it
    assert "marked 'known' but" in out


def test_a_missing_refs_seed_leaves_citations_unbacked(study):
    from test_literature_gate import GOOD_BIB
    lit = _lit_declare(study)
    (lit / "known-results.json").write_text(json.dumps({}))
    (lit / "negative-exports.json").write_text('{"exports": []}')
    (lit / "completeness.json").write_text('{"lines": []}')
    (lit / "refs-seed.bib").write_text(GOOD_BIB)
    code, out = run_check(study)
    assert code == 1
    assert "marked 'known' but" in out
    assert "no verified source" in out or "verified" in out


def _run_copied_validator(study, tmp_path):
    import shutil
    import subprocess
    import sys
    from conftest import RQ_CHECK, REPO
    fake = tmp_path / "skill" / "scripts"
    fake.mkdir(parents=True)
    shutil.copy(RQ_CHECK, fake / "rq_check.py")
    command = [sys.executable]
    if os.environ.get("RQ_COVERAGE") == "1":
        command += ["-m", "coverage", "run", "--rcfile",
                    str(REPO / ".coveragerc"), "--parallel-mode"]
    command += [str(fake / "rq_check.py"), "--study", str(study)]
    cp = subprocess.run(command, capture_output=True, text=True)
    return cp.returncode, cp.stdout + cp.stderr


def test_a_validator_without_its_schemas_reports_every_missing_schema(study, tmp_path):
    lit = _lit_declare(study)
    (lit / "known-results.json").write_text(json.dumps({}))
    (lit / "negative-exports.json").write_text('{"exports": []}')
    (lit / "completeness.json").write_text('{"lines": []}')
    (lit / "refs-seed.bib").write_text("@misc{x, title={y}}\n")
    dossier = study / "interim" / "lit" / "alpha"
    dossier.mkdir(parents=True)
    (dossier / "dossier.json").write_text("{}")
    code, out = _run_copied_validator(study, tmp_path)
    assert code == 1
    for frag in ("study.schema.json not found",
                 "registry.schema.json not found",
                 "completeness.schema.json not found",
                 "known-results.schema.json not found",
                 "negative-exports.schema.json not found",
                 "dossier.schema.json not found"):
        assert frag in out, frag
