"""Procedural gates from the hard-lessons doc
(docs/hard-lessons-from-the-var-expected-return-run.md, Decisions 19-20).

L4: status is written from verdicts — a status asserting a certification
    outcome must reference an existing verdict file or frozen hash.
L6: the record is the source of truth — an edited stage-3 claim (recorded
    digest mismatch) reopens certification.
L7: schema/validator digests are pinned at intake — a reissued schema or
    validator is a re-intake event, flagged, not repaired on the fly.
"""

import hashlib
from pathlib import Path

from conftest import RQ_CHECK, SKILL_DIR, read_study, run_check, write_study


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------- L4: status


def test_verdictless_status_claim_is_refused(study, tex_available):
    """A status that asserts a certification outcome without naming a verdict
    file or frozen hash is exactly the L4 defect (self-certification by
    prose)."""
    s = read_study(study)
    s["status"] = "stage-3 restored on the round-4 certification"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "written from verdicts" in out


def test_status_claim_with_existing_verdict_file_passes(study, tex_available):
    s = read_study(study)
    (study / "audits" / "round-4-certification.md").write_text(
        "VERDICT: PASS\n")
    s["status"] = ("stage-3 certified on the round-4 certification "
                   "(audits/round-4-certification.md)")
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_status_claim_with_frozen_hash_passes(study, tex_available):
    s = read_study(study)
    s["status"] = ("stage-3 certified on the round-4 certification "
                   "of frozen hash 723662c7")
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_routine_status_without_certification_language_is_unaffected(study, tex_available):
    s = read_study(study)
    s["status"] = "round 2: SP3 active, no PASS yet"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


# ------------------------------------------------------------- L6: claim digest


def test_stage3_claim_digest_mismatch_is_flagged(study, tex_available):
    """The claim text changed since its recorded digest: certification is
    reopened (the record is the source of truth)."""
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["claim_sha256"] = (
        hashlib.sha256(b"an entirely different claim").hexdigest())
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "re-certify" in out


def test_stage3_claim_digest_match_passes(study, tex_available):
    s = read_study(study)
    claim = s["validity_stages"]["stage3_general_claim"]["claim"]
    s["validity_stages"]["stage3_general_claim"]["claim_sha256"] = (
        hashlib.sha256(claim.encode("utf-8")).hexdigest())
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out


def test_claim_digest_is_schema_validated(study, tex_available):
    """claim_sha256 must be a real 64-hex sha256, not free text."""
    s = read_study(study)
    s["validity_stages"]["stage3_general_claim"]["claim_sha256"] = "not-a-hash"
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "claim_sha256" in out


# ------------------------------------------------------------- L7: intake pins


def test_intake_schema_pin_mismatch_is_flagged(study, tex_available):
    """A study created under a different schema is a re-intake event."""
    s = read_study(study)
    s["intake_pins"] = {"schema_sha256": "0" * 64,
                        "validator_sha256": "1" * 64}
    write_study(study, s)
    code, out = run_check(study)
    assert code == 1
    assert "schema reissue is a re-intake event" in out


def test_intake_pins_match_passes(study, tex_available):
    s = read_study(study)
    s["intake_pins"] = {
        "schema_sha256": sha256_file(SKILL_DIR / "schemas" / "study.schema.json"),
        "validator_sha256": sha256_file(RQ_CHECK),
    }
    write_study(study, s)
    code, out = run_check(study)
    assert code == 0, out
