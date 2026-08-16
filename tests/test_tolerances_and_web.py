"""Tolerance reconciliation (check-battery.md gate A) and the web deliverable."""

import json

from conftest import read_study, run_check, write_study


def test_audit_restating_a_different_tolerance_is_refused(study, tex_available):
    """check-battery.md: a loosened tolerance must be reconciled with study.json."""
    battery = study / "audits" / "battery-results.md"
    battery.write_text(battery.read_text().replace(
        "stochastic se_units 3", "stochastic se_units 12"))
    code, out = run_check(study)
    assert code == 1
    assert "se_units" in out and "reconcil" in out


def test_audit_restating_the_declared_tolerance_is_accepted(study, tex_available):
    code, out = run_check(study)
    assert code == 0, out
    assert "se_units 3" in (study / "audits" / "battery-results.md").read_text()


def test_audit_that_does_not_restate_tolerances_is_not_flagged(study, tex_available):
    battery = study / "audits" / "battery-results.md"
    battery.write_text(battery.read_text().split("Tolerances used:")[0])
    code, out = run_check(study)
    assert code == 0, out


WEB_PAGE = """<html><body>
<h1>Minimum-variance weights</h1>
<p>This page is written for a working quantitative researcher.</p>
<h2>References</h2>
<ul><li><a href="https://doi.org/10.2307/2975974">Markowitz, Portfolio Selection, 1952</a></li></ul>
</body></html>
"""


def _require_web(study, page=WEB_PAGE, sentence="This page is written for a working quantitative researcher."):
    s = read_study(study)
    s["deliverables"]["web"] = "required"
    s["deliverables"]["audience"]["web"] = {"role": "researcher", "sentence": sentence}
    write_study(study, s)
    web = study / "artifacts" / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "index.html").write_text(page)
    (study / "audits" / "document-adversary-web.md").write_text("VERDICT: PASS\n")


def test_a_complete_web_deliverable_is_accepted(study, tex_available):
    _require_web(study)
    code, out = run_check(study)
    assert code == 0, out


def test_web_deliverable_with_a_bare_url_reference_is_refused(study, tex_available):
    _require_web(study, WEB_PAGE.replace(
        ">Markowitz, Portfolio Selection, 1952<", ">https://doi.org/10.2307/2975974<"))
    code, out = run_check(study)
    assert code == 1
    assert "anchor text" in out


def test_web_deliverable_missing_its_audience_sentence_is_refused(study, tex_available):
    _require_web(study, WEB_PAGE.replace(
        "This page is written for a working quantitative researcher.", "Hello."))
    code, out = run_check(study)
    assert code == 1
    assert "audience sentence" in out


def test_web_deliverable_with_an_unclosed_tag_is_refused(study, tex_available):
    """The balance check once required <html> to be left OPEN, rejecting valid
    HTML and accepting truncated pages."""
    _require_web(study, WEB_PAGE.replace("</body></html>", ""))
    code, out = run_check(study)
    assert code == 1
    assert "unclosed" in out and "<html>" in out
