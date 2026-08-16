"""Decision 14 literature gate: known marks, negative exports, citations.

The gate fires only when study.json carries a 'literature' object, so the
pre-lane golden study is unaffected. Verified state lives only in
literature/known-results.json; interim dossiers are advisory.
"""

import json
import sys

from conftest import SKILL_DIR, read_study, run_check, write_study

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import rq_check  # noqa: E402  (stdlib-only; the suite already imports it this way)


def _verified_source(status="verified-current", paper_id="DOI:10.2307/2975974"):
    return {
        "paper_id": paper_id,
        "version": "published",
        "access_date": "2026-08-16",
        "retrieval_method": "openalex",
        "adversarial_check": {
            "status": status,
            "checked_by": "lit-adversary",
            "date": "2026-08-16",
            "evidence": "interim/lit/l1/verdict.json",
        },
    }


def _verified_map():
    entry = {"category": "settled", "claim": "c", "negative_export": False,
             "sources": [_verified_source()]}
    return {"SP1": [dict(entry)], "SP2": [dict(entry)]}


def _enable_literature(study):
    s = read_study(study)
    s["status"] = "active"  # no PASS claim, so the TeX compile gate stays off
    s["literature"] = {"phase": "concluded",
                       "map_file": "literature/known-results.json",
                       "negative_exports_file": "literature/negative-exports.json",
                       "completeness_file": "literature/completeness.json"}
    write_study(study, s)


def _sweeps():
    return {
        "forward_citations": "Semantic Scholar forward sweep, 41 citing papers",
        "related_work": "related-work sections of both hubs read",
        "surveys": "Brandt (2010) survey read; no newer survey in scope",
        "adjacent_fields": "robust optimization probed, nothing load-bearing",
        "retractions_and_versions": "Crossref clean; no newer arXiv version",
        "author_pages": "author pages checked for both load-bearing papers",
    }


def _completeness(subproblem_ids=("SP1", "SP2")):
    return {"lines": [
        {"line": "line-%s" % spid.lower(),
         "subproblem_id": spid,
         "sweeps": _sweeps(),
         "frontier": [],
         "stop_reason": "citation closure: one round added no unvisited paper",
         "termination": "citation-closure"}
        for spid in subproblem_ids]}


def _write_lit(study, name, data):
    (study / "literature").mkdir(exist_ok=True)
    (study / "literature" / name).write_text(json.dumps(data))


def _write_map(study, map_data):
    _write_lit(study, "known-results.json", map_data)


def _write_completeness(study, data=None):
    _write_lit(study, "completeness.json", _completeness() if data is None else data)


def test_golden_with_verified_literature_is_accepted(study):
    _enable_literature(study)
    _write_map(study, _verified_map())
    _write_completeness(study)
    _write_refs_seed(study, GOOD_BIB)
    code, out = run_check(study)
    assert code == 0, out


# ------------------------------------------------- completeness (anti-early-stop)


def test_concluded_lane_without_a_completeness_checklist_is_refused(study):
    """§6/§11: 'the model finished early' must be a failing condition."""
    _enable_literature(study)
    _write_map(study, _verified_map())
    code, out = run_check(study)
    assert code == 1
    assert "literature/completeness.json" in out


def test_an_empty_mandatory_sweep_is_refused(study):
    _enable_literature(study)
    _write_map(study, _verified_map())
    c = _completeness()
    c["lines"][0]["sweeps"]["surveys"] = "   "
    _write_completeness(study, c)
    code, out = run_check(study)
    assert code == 1
    assert "empty mandatory sweep" in out


def test_a_missing_mandatory_sweep_is_refused(study):
    _enable_literature(study)
    _write_map(study, _verified_map())
    c = _completeness()
    del c["lines"][0]["sweeps"]["forward_citations"]
    _write_completeness(study, c)
    code, out = run_check(study)
    assert code == 1
    assert "forward_citations" in out


def test_a_mapped_subproblem_with_no_swept_line_is_refused(study):
    """A verified record cannot exist for a line the checklist never swept."""
    _enable_literature(study)
    _write_map(study, _verified_map())
    _write_completeness(study, _completeness(("SP1",)))
    code, out = run_check(study)
    assert code == 1
    assert "no completeness line" in out


def test_schema_min_length_rejects_an_empty_string():
    """The completeness schema needs minLength; an unsupported keyword raises."""
    schema = {"type": "object", "properties": {"a": {"type": "string", "minLength": 1}}}
    assert rq_check.validate_json_schema({"a": ""}, schema)
    assert not rq_check.validate_json_schema({"a": "x"}, schema)


def test_known_mark_without_any_record_is_refused(study):
    _enable_literature(study)
    code, out = run_check(study)
    assert code == 1
    assert "literature/known-results.json missing" in out
    assert "marked 'known'" in out


def test_known_mark_needs_verified_current_not_just_a_record(study):
    _enable_literature(study)
    m = _verified_map()
    m["SP1"][0]["sources"][0]["adversarial_check"]["status"] = "unverifiable"
    _write_map(study, m)
    _write_completeness(study)
    code, out = run_check(study)
    assert code == 1
    assert "marked 'known'" in out


def test_negative_export_must_trace_to_impossible_verified_entry(study):
    _enable_literature(study)
    _write_map(study, _verified_map())
    _write_completeness(study)
    exports = {"exports": [{"subproblem_id": "SP1", "constraint": "no P",
                            "source_paper_id": "DOI:10.9999/ghost"}]}
    (study / "literature" / "negative-exports.json").write_text(json.dumps(exports))
    code, out = run_check(study)
    assert code == 1
    assert "cannot appear from nowhere" in out


def test_negative_export_to_impossible_verified_entry_is_accepted(study):
    _enable_literature(study)
    m = _verified_map()
    m["SP2"][0]["category"] = "impossible"
    m["SP2"][0]["negative_export"] = True
    _write_map(study, m)
    _write_completeness(study)
    _write_refs_seed(study, GOOD_BIB)
    exports = {"exports": [{"subproblem_id": "SP2", "constraint": "no P",
                            "source_paper_id": "DOI:10.2307/2975974"}]}
    (study / "literature" / "negative-exports.json").write_text(json.dumps(exports))
    code, out = run_check(study)
    assert code == 0, out


# --------------------------------------------- routed-away impossible (C5, §4)


def _route_away(study, spid="SP3"):
    s = read_study(study)
    for sp in s["subproblems"]:
        if sp["id"] == spid:
            sp["status"] = "impossible"
    write_study(study, s)


def _impossible_entry(escalation=None):
    entry = {"category": "impossible", "claim": "no such method exists",
             "negative_export": False, "sources": [_verified_source()]}
    if escalation is not None:
        entry["escalation"] = escalation
    return entry


def test_routed_away_impossible_needs_a_verified_impossible_record(study):
    """C5: a sub-problem answered by an impossibility owes that impossibility."""
    _enable_literature(study)
    _route_away(study)
    _write_map(study, _verified_map())
    _write_completeness(study, _completeness(("SP1", "SP2", "SP3")))
    code, out = run_check(study)
    assert code == 1
    assert "routed away as impossible" in out


def test_routed_away_impossible_needs_the_math_lane_escalation(study):
    """§4: when the conclusion RESTS on the impossibility, the math lane must
    have accepted it -- the literature lane never certifies that X is true."""
    _enable_literature(study)
    _route_away(study)
    m = _verified_map()
    m["SP3"] = [_impossible_entry()]
    _write_map(study, m)
    _write_completeness(study, _completeness(("SP1", "SP2", "SP3")))
    code, out = run_check(study)
    assert code == 1
    assert "escalation" in out


def test_routed_away_impossible_escalation_path_must_exist(study):
    _enable_literature(study)
    _route_away(study)
    m = _verified_map()
    m["SP3"] = [_impossible_entry("audits/never-written.md")]
    _write_map(study, m)
    _write_completeness(study, _completeness(("SP1", "SP2", "SP3")))
    code, out = run_check(study)
    assert code == 1
    assert "audits/never-written.md" in out


def test_a_declared_escalation_path_must_exist_even_when_unused(study):
    """An escalation nobody can read is a claim, not a record -- whatever the
    sub-problem's own status says."""
    _enable_literature(study)
    m = _verified_map()
    m["SP2"] = [_impossible_entry("audits/never-written.md")]
    _write_map(study, m)
    _write_completeness(study)
    code, out = run_check(study)
    assert code == 1
    assert "audits/never-written.md" in out


def test_routed_away_impossible_with_escalation_is_accepted(study):
    _enable_literature(study)
    _route_away(study)
    (study / "audits" / "math-lane-impossibility.md").write_text(
        "# Math-lane escalation -- SP3\n\nThe impossibility was re-derived "
        "independently by the ground-truth track. VERDICT: accepted.\n")
    m = _verified_map()
    m["SP3"] = [_impossible_entry("audits/math-lane-impossibility.md")]
    _write_map(study, m)
    _write_completeness(study, _completeness(("SP1", "SP2", "SP3")))
    _write_refs_seed(study, GOOD_BIB)
    code, out = run_check(study)
    assert code == 0, out


# ------------------------------------------------------- refs-seed.bib (§8/§11)


GOOD_BIB = ("@article{markowitz1952,\n  author = {Markowitz, Harry},\n"
            "  title = {Portfolio Selection},\n  year = {1952},\n"
            "  doi = {10.2307/2975974}\n}\n")


def _write_refs_seed(study, text):
    (study / "literature").mkdir(exist_ok=True)
    (study / "literature" / "refs-seed.bib").write_text(text)


def test_refs_seed_entry_without_a_verified_record_is_refused(study):
    _enable_literature(study)
    _write_map(study, _verified_map())
    _write_completeness(study)
    _write_refs_seed(study, "@article{ghost,\n  author = {Nemo},\n"
                            "  year = {2000},\n  doi = {10.9999/ghost}\n}\n")
    code, out = run_check(study)
    assert code == 1
    assert "refs-seed.bib" in out


def test_refs_seed_may_not_carry_a_still_open_entry(study):
    """§8: the seed holds category != open entries only."""
    _enable_literature(study)
    m = _verified_map()
    m["SP1"] = [{"category": "open", "claim": "still open", "negative_export": False,
                 "sources": [_verified_source(paper_id="arXiv:2401.00001")]}]
    _write_map(study, m)
    _write_completeness(study)
    _write_refs_seed(study, "@article{openq,\n  author = {Nemo},\n"
                            "  year = {2024},\n  eprint = {2401.00001}\n}\n")
    code, out = run_check(study)
    assert code == 1
    assert "refs-seed.bib" in out


def test_refs_seed_of_verified_entries_is_accepted(study):
    _enable_literature(study)
    _write_map(study, _verified_map())
    _write_completeness(study)
    _write_refs_seed(study, GOOD_BIB)
    code, out = run_check(study)
    assert code == 0, out


def test_concluded_lane_without_refs_seed_is_refused(study):
    """A concluded lane that verified results must leave a refs-seed.bib."""
    _enable_literature(study)
    _write_map(study, _verified_map())
    _write_completeness(study)
    code, out = run_check(study)
    assert code == 1
    assert "refs-seed.bib missing" in out


def test_bib_title_matches_normalized_title_record(study):
    """paper_id may be a normalized title; a BibTeX title must trace to it."""
    _enable_literature(study)
    m = _verified_map()
    m["SP1"] = [{"category": "settled", "claim": "c", "negative_export": False,
                 "sources": [_verified_source(paper_id="Portfolio Selection")]}]
    _write_map(study, m)
    _write_completeness(study)
    _write_refs_seed(study, "@article{markowitz,\n  author = {Markowitz, Harry},\n"
                            "  title = {Portfolio Selection},\n  year = {1952}\n}\n")
    code, out = run_check(study)
    assert code == 0, out


def test_bib_title_without_a_verified_record_is_refused(study):
    _enable_literature(study)
    m = _verified_map()
    m["SP1"] = [{"category": "settled", "claim": "c", "negative_export": False,
                 "sources": [_verified_source(paper_id="Portfolio Selection")]}]
    _write_map(study, m)
    _write_completeness(study)
    _write_refs_seed(study, "@article{other,\n  author = {Nemo},\n"
                            "  title = {Something Else},\n  year = {2000}\n}\n")
    code, out = run_check(study)
    assert code == 1
    assert "refs-seed.bib" in out


# ------------------------------------------------ state consistency (§8/§10)


def test_a_skipped_lane_must_record_the_user_assertion(study):
    """§10: the sweep is skippable only on an explicit user assertion."""
    _enable_literature(study)
    s = read_study(study)
    s["literature"] = {"phase": "skipped"}
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "skip_reason" in out


def test_a_skipped_lane_with_a_recorded_assertion_needs_no_map(study):
    _enable_literature(study)
    s = read_study(study)
    s["literature"] = {"phase": "skipped",
                       "skip_reason": "user asserted at intake that SP1-SP3 are "
                                      "textbook results and named the sources"}
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_phase_not_run_may_not_carry_verified_records(study):
    """A lane that never ran cannot have verified anything."""
    _enable_literature(study)
    s = read_study(study)
    s["literature"]["phase"] = "not-run"
    write_study(study, s)
    _write_map(study, _verified_map())
    _write_completeness(study)
    code, out = run_check(study)
    assert code == 1
    assert "phase" in out


def test_negative_export_flag_must_match_the_exports_file(study):
    """The map says it exported a negative; the exports file says otherwise."""
    _enable_literature(study)
    m = _verified_map()
    m["SP2"][0]["category"] = "impossible"
    m["SP2"][0]["negative_export"] = True
    _write_map(study, m)
    _write_completeness(study)
    code, out = run_check(study)
    assert code == 1
    assert "negative_export" in out


def test_an_export_whose_entry_is_not_flagged_is_refused(study):
    _enable_literature(study)
    m = _verified_map()
    m["SP2"][0]["category"] = "impossible"  # flag left False
    _write_map(study, m)
    _write_completeness(study)
    _write_lit(study, "negative-exports.json", {"exports": [
        {"subproblem_id": "SP2", "constraint": "no P",
         "source_paper_id": "DOI:10.2307/2975974"}]})
    code, out = run_check(study)
    assert code == 1
    assert "negative_export" in out


def test_a_malformed_dossier_is_refused(study):
    """Dossiers stay advisory, but an unparsable one is still a defect."""
    _enable_literature(study)
    _write_map(study, _verified_map())
    _write_completeness(study)
    line_dir = study / "interim" / "lit" / "l1"
    line_dir.mkdir(parents=True)
    (line_dir / "dossier.json").write_text(json.dumps(
        {"line": "l1", "papers": [{"paper_id": "arXiv:1", "version": "v1"}]}))
    code, out = run_check(study)
    assert code == 1
    assert "dossier.schema.json" in out


def test_citation_matcher_is_id_based():
    """Unit check: a bib entry is verified by DOI/arXiv id, not by its key."""
    verified = {rq_check._norm_id("DOI:10.2307/2975974")}
    real = "author = {Markowitz, H.}, doi = {10.2307/2975974}, year = {1952}"
    assert rq_check._bib_entry_ids(real) & verified
    forged = "author = {Nemo}, doi = {10.9999/ghost}, year = {2000}"
    assert not (rq_check._bib_entry_ids(forged) & verified)


def test_citation_unverified_is_refused_at_pass(study, tex_available):
    """End-to-end: a PASS whose refs.bib has no verified record is refused."""
    s = read_study(study)
    s["literature"] = {"phase": "concluded", "map_file": "literature/known-results.json"}
    write_study(study, s)
    _write_map(study, _verified_map())
    _write_completeness(study)
    (study / "artifacts" / "paper" / "refs.bib").write_text(
        "@article{ghost,\n  author = {Nemo},\n  title = {Ghost},\n"
        "  year = {2000},\n  doi = {10.9999/ghost}\n}\n")
    code, out = run_check(study)
    assert code == 1
    assert "no verified-current literature record" in out
