"""Stage-4 document gates: overclaim, structure, notation, audience spec."""

from conftest import read_study, run_check, write_study


def edit_paper(study, old, new):
    p = study / "artifacts" / "paper" / "main.tex"
    text = p.read_text()
    assert old in text, "fixture drift: %r not in the golden paper" % old
    p.write_text(text.replace(old, new))


def test_overclaiming_certificate_checked_is_refused(study, tex_available):
    """The no-overclaim rule covers all four evidence levels, not just formal."""
    edit_paper(study, "Two independent derivations agree",
               "Every claim here is certificate-checked; two independent derivations agree")
    code, out = run_check(study)
    assert code == 1
    assert "overclaim" in out and "certificate-checked" in out


def test_overclaiming_formal_verification_is_refused(study, tex_available):
    edit_paper(study, "so nothing here is formally verified",
               "and the result is formally verified end to end")
    code, out = run_check(study)
    assert code == 1
    assert "formally verified" in out


def test_asserted_level_backed_by_the_record_is_allowed(study, tex_available):
    """'independently re-derived' IS carried by the golden study's record."""
    code, out = run_check(study)
    assert code == 0, out
    assert "independently re-derived" in (study / "artifacts" / "paper" / "main.tex").read_text()


def test_required_sections_must_be_real_headings(study, tex_available):
    """Six words sprinkled in prose are not six sections.

    The word "certification" stays in the body, so only a validator that looks
    for an actual \\section heading catches this.
    """
    edit_paper(study, r"\section{Certification}",
               r"\subsection*{Numbers}" "\nThis certification summary reports the gates.")
    code, out = run_check(study)
    assert code == 1
    assert "certification" in out.lower() and "section" in out.lower()


def test_symbol_used_but_not_defined_is_refused(study, tex_available):
    """Conditional symbol audit: a registered symbol that APPEARS must be defined."""
    edit_paper(study, "at cost $O(n^3)$", "at cost $poly(n)$")
    code, out = run_check(study)
    assert code == 1
    assert "poly(" in out


def test_symbol_used_and_defined_is_accepted(study, tex_available):
    edit_paper(study, "at cost $O(n^3)$", "at cost $poly(n)$")
    edit_paper(study, "weights summing to one.",
               "weights summing to one. Here $poly(n)$ denotes polynomial dependence on $n$.")
    code, out = run_check(study)
    assert code == 0, out


def test_study_specific_symbols_come_from_the_audience_spec(study, tex_available):
    """Domain notation lives in the spec, not hard-coded in the validator."""
    s = read_study(study)
    s["deliverables"]["audience"]["paper"]["symbols"] = {
        "Sigma": {"pattern": r"\\Sigma", "witnesses": ["covariance matrix"]}
    }
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out

    edit_paper(study, "$\\Sigma$ denotes the asset covariance matrix, assumed symmetric positive\ndefinite.",
               "$\\mathbf{1}$ is used throughout.")
    code, out = run_check(study)
    assert code == 1
    assert "Sigma" in out


def test_audience_spec_without_a_sentence_is_refused(study, tex_available):
    s = read_study(study)
    del s["deliverables"]["audience"]["paper"]["sentence"]
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "sentence" in out


def test_audience_sentence_in_a_latex_comment_does_not_count(study, tex_available):
    edit_paper(study,
               "This paper is written for a working quantitative researcher.",
               "% This paper is written for a working quantitative researcher.")
    code, out = run_check(study)
    assert code == 1
    assert "audience sentence" in out


def test_validator_leaves_no_build_products_in_the_study(study, tex_available):
    before = {p.name for p in (study / "artifacts" / "paper").iterdir()}
    run_check(study)
    after = {p.name for p in (study / "artifacts" / "paper").iterdir()}
    assert after == before, "validator dirtied the committed artifacts tree: %s" % (after - before)
