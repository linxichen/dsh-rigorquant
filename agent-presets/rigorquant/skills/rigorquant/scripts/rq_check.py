#!/usr/bin/env python3
"""rq_check.py -- the RigorQuant meta-validator (single canonical copy).

Validates a study's state files against the shipped JSON Schemas (siblings of
this script, in ../schemas/), enforces the COVERAGE gate (the union of
sub-problems must cover the ORIGINAL statement: a general question needs a
`generalization` sub-problem carrying the broad claim and a `domain-scale`
sub-problem certifying a genuinely non-special instance), and refuses a declared
PASS unless the mandatory evidence actually exists on disk.

Standard library only, so it runs inside or outside the pinned compute lane:

    python3 <skill-dir>/scripts/rq_check.py --study <study-root>
    python3 <skill-dir>/scripts/rq_check.py --study <study-root> --out report.json

Exit codes:
    0  state valid (and PASS evidence complete, when a PASS is claimed)
    1  FAIL -- state invalid or PASS evidence incomplete (gaps printed)
    2  ERROR -- cannot read/parse the study state

Design rule, learned the hard way: **a study may not vouch for itself.** Every
evidence check reads the audit/derivation/artifact record, never `study.json`.
A declaration in `study.json` says what was promised; only the record says what
was done.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

EVIDENCE_LEVELS = (
    "falsification-surviving",
    "independently re-derived",
    "certificate-checked",
    "formally verified",
)
SPECIAL_BODIES = ("box", "ball", "simplex", "ellipsoid", "diagonal")
NON_SPECIAL_MARKERS = ("p-norm", "p norm", "quadratic", "intersection",
                       "sublevel", "lens", "polytope", "convex-quadratic")
# The validator's own JSON report is output, never evidence: it must not be able
# to satisfy the audit-derived checks (a study may not vouch for itself, and
# neither may the checker's own report vouch for the study).
SELF_REPORT_NAME = "rq-check.json"
PAPER_SECTIONS = ("statement", "method", "validity", "certification",
                  "limitations", "reproduction")

# A study claims PASS only when `status` *begins* with the PASS token. Anything
# else -- "round 2: SP3 active, no PASS yet" -- is not a claim, and must not trip
# the PASS gates. Documented in references/lifecycle.md.
PASS_CLAIM_RE = re.compile(r"^\s*PASS\b", re.IGNORECASE)

LITERATURE_MAP_DEFAULT = "literature/known-results.json"
NEGATIVE_EXPORTS_DEFAULT = "literature/negative-exports.json"
COMPLETENESS_DEFAULT = "literature/completeness.json"
REFS_SEED_DEFAULT = "literature/refs-seed.bib"


class Problems(list):
    def add(self, check_id, message):
        self.append({"id": check_id, "message": message})


# ---------------------------------------------------------------- utilities


def sha256_hex(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def env_manifest():
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
    }


def claiming_pass(study) -> bool:
    status = str(study.get("status", ""))
    # A status that begins with PASS but is marked reopened is no longer claiming
    # that PASS (it re-entered active work), so the PASS gates must not fire.
    # Documented in references/lifecycle.md and the schema "status" description.
    if "reopen" in status.lower():
        return False
    return bool(PASS_CLAIM_RE.match(status))


def strip_tex_comments(text: str) -> str:
    """Drop LaTeX comments so a required sentence cannot be satisfied by one."""
    return re.sub(r"(?<!\\)%.*", " ", text)


def norm(s: str) -> str:
    return " ".join(str(s).split()).lower()


def _names_special_body(text: str) -> bool:
    """True if the text names a special/reference body as a bare, non-negated term.

    'diagonal covariance' is special; 'non-diagonal covariance' is not.
    """
    tokens = re.split(r"[^a-z0-9]+", text)
    for b in SPECIAL_BODIES:
        for i, tok in enumerate(tokens):
            if tok == b and (i == 0 or tokens[i - 1] != "non"):
                return True
    return False


def _validate_output_paths(outputs, root):
    """Split declared output paths into (missing, invalid).

    A path is invalid if it is absolute, escapes the study root (".."), or names
    the validator's own report. Outputs are study-root-relative by contract
    (lifecycle.md); the validator's report is output, not evidence.
    """
    missing, invalid = [], []
    for o in outputs:
        if not isinstance(o, str) or not o.strip():
            invalid.append(repr(o))
            continue
        p = Path(o)
        if p.is_absolute() or ".." in p.parts:
            invalid.append(o)
            continue
        if p.name == SELF_REPORT_NAME:
            invalid.append(o)
            continue
        if not (root / o).exists():
            missing.append(o)
    return missing, invalid


def evidence_corpus(root: Path):
    """The record the study produced: audits, derivations, artifact results.

    Deliberately EXCLUDES study.json -- a declaration is not evidence.
    Returns (joined_lowercase_text, list_of_paths).
    """
    paths = []
    for sub in ("audits", "derivations", "artifacts"):
        d = root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.name == SELF_REPORT_NAME:
                continue  # the validator's own report is output, not evidence
            if p.is_file() and p.suffix.lower() in (".md", ".txt", ".json", ".csv"):
                paths.append(p)
    parts = []
    for p in paths:
        try:
            parts.append(p.read_text(errors="replace"))
        except OSError:
            continue
    return "\n".join(parts).lower(), paths


# ------------------------------------------------- minimal JSON Schema check
#
# Supports exactly the draft-07 subset the shipped schemas use: type, required,
# properties, additionalProperties (bool), items, enum, pattern, minItems,
# minimum, exclusiveMinimum/Maximum, $ref to #/definitions/*. Anything outside
# that subset is a schema authoring error and raises, so the schemas can never
# quietly drift past what this validator understands.

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "number": (int, float), "integer": int, "null": type(None),
}
_SUPPORTED = {
    "$schema", "$id", "title", "description", "type", "required", "properties",
    "additionalProperties", "items", "enum", "pattern", "minItems", "minLength",
    "minimum", "exclusiveMinimum", "exclusiveMaximum", "definitions", "$ref",
}


def _resolve(schema, root):
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/definitions/"):
            raise ValueError("unsupported $ref: " + ref)
        return root["definitions"][ref.split("/")[-1]]
    return schema


def validate_json_schema(instance, schema, root=None, path="", errs=None):
    errs = [] if errs is None else errs
    root = schema if root is None else root
    schema = _resolve(schema, root)
    unsupported = set(schema) - _SUPPORTED
    if unsupported:
        raise ValueError("unsupported schema keywords at %s: %s" % (path or "/", sorted(unsupported)))
    where = path or "(root)"

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        py = tuple(x for name in types for x in
                   (_TYPES[name] if isinstance(_TYPES[name], tuple) else (_TYPES[name],)))
        ok = isinstance(instance, py)
        if ok and bool not in py and isinstance(instance, bool):
            ok = False  # JSON booleans are not numbers
        if not ok:
            errs.append("%s: expected type %s" % (where, t))
            return errs
    if "enum" in schema and instance not in schema["enum"]:
        errs.append("%s: %r is not one of %s" % (where, instance, schema["enum"]))
    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            errs.append("%s: %r does not match %s" % (where, instance, schema["pattern"]))
    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            errs.append("%s: needs at least %d character(s)" % (where, schema["minLength"]))
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append("%s: %r < minimum %r" % (where, instance, schema["minimum"]))
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errs.append("%s: %r <= exclusiveMinimum %r" % (where, instance, schema["exclusiveMinimum"]))
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            errs.append("%s: %r >= exclusiveMaximum %r" % (where, instance, schema["exclusiveMaximum"]))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append("%s: needs at least %d item(s)" % (where, schema["minItems"]))
        if "items" in schema:
            for i, item in enumerate(instance):
                validate_json_schema(item, schema["items"], root, "%s[%d]" % (where, i), errs)
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errs.append("%s: missing required field %r" % (where, key))
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                validate_json_schema(value, props[key], root, "%s.%s" % (where, key), errs)
            else:
                extra = schema.get("additionalProperties", True)
                if extra is False:
                    errs.append("%s: unexpected field %r" % (where, key))
                elif isinstance(extra, dict):
                    validate_json_schema(value, extra, root, "%s.%s" % (where, key), errs)
    return errs


def load_schema(name):
    p = SCHEMA_DIR / name
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def check_against_schemas(study, registry, problems):
    for name, instance, label in (("study.schema.json", study, "study.json"),
                                  ("registry.schema.json", registry, "registry.json")):
        schema = load_schema(name)
        if schema is None:
            problems.add("schema.missing", "shipped schema %s not found next to the validator" % name)
            continue
        if instance is None:
            continue
        for e in validate_json_schema(instance, schema):
            problems.add("schema", "%s does not match %s: %s" % (label, name, e))


# ------------------------------------------------------------ state validity


def check_coverage(study, problems):
    subs = study.get("subproblems") or []
    if not study.get("broad_criterion"):
        problems.add(
            "coverage.broad",
            "coverage gate: study.json has no `broad_criterion` -- the ORIGINAL "
            "broad claim a PASS must deliver (verbatim restatement of the user's "
            "general question). Record it at intake, never re-scope it to the "
            "simplified cases.")
    stages = [sp.get("stage", "") for sp in subs if isinstance(sp, dict)]
    if "generalization" not in stages:
        problems.add(
            "coverage.generalization",
            "coverage gate FAILED: no subproblem has stage=generalization. "
            "The broad claim is not carried by any sub-problem -- a study that "
            "only exercises its simplified cases can never answer a general question.")
    if "domain-scale" not in stages:
        problems.add(
            "coverage.domain-scale",
            "coverage gate FAILED: no subproblem has stage=domain-scale. "
            "There is no certification on a genuinely non-special instance.")


def check_registry_consistency(study, registry, root: Path, problems):
    """The registry is parsed, never grepped: a PASS needs a route whose status
    is `passed` and whose outputs exist on disk (lifecycle.md: `passed` requires
    an audit reference)."""
    if not isinstance(registry, dict):
        return
    reg_subs = registry.get("subproblems")
    if not isinstance(reg_subs, dict):
        return
    study_ids = {sp["id"] for sp in study.get("subproblems", [])
                 if isinstance(sp, dict) and "id" in sp}
    if study_ids and set(reg_subs) != study_ids:
        only_reg = sorted(set(reg_subs) - study_ids)
        only_study = sorted(study_ids - set(reg_subs))
        problems.add(
            "registry.keys",
            "registry.json subproblem keys do not match study.json subproblem ids "
            "(only in registry: %s; only in study: %s)" % (only_reg, only_study))

    def routes_of(sp):
        for fam in sp.get("families") or []:
            for route in (fam.get("routes") or []) if isinstance(fam, dict) else []:
                if isinstance(route, dict):
                    yield route

    for key, sp in reg_subs.items():
        if not isinstance(sp, dict):
            continue
        passed_routes = [r for r in routes_of(sp) if r.get("status") == "passed"]
        if sp.get("status") == "passed" and not passed_routes:
            problems.add(
                "registry.passed-route",
                "registry.json %s is marked passed but carries no passed route "
                "(a sub-problem passes through a route, never by assertion)" % key)
        for route in passed_routes:
            outputs = route.get("outputs") or []
            if not outputs:
                problems.add(
                    "registry.passed-outputs",
                    "registry.json %s route %r is passed with empty outputs; "
                    "`passed` requires an audit reference (lifecycle.md)"
                    % (key, route.get("routeId", "?")))
                continue
            missing, invalid = _validate_output_paths(outputs, root)
            if invalid:
                problems.add(
                    "registry.passed-outputs",
                    "registry.json %s route %r references invalid output paths "
                    "(must be study-root-relative, not the validator's own report): %s"
                    % (key, route.get("routeId", "?"), invalid))
            if missing:
                problems.add(
                    "registry.passed-outputs",
                    "registry.json %s route %r references outputs that do not exist: %s"
                    % (key, route.get("routeId", "?"), missing))

    if claiming_pass(study):
        any_passed = any(
            r.get("status") == "passed"
            for sp in reg_subs.values() if isinstance(sp, dict)
            for r in routes_of(sp))
        if not any_passed:
            problems.add(
                "registry.no-pass",
                "PASS refused: registry.json has no audit-referenced passed route")


def check_record_present(study, root: Path, problems):
    """The tracks must have left a record behind.

    Only a study that CLAIMS a PASS owes one: the validator also runs at intake,
    where `derivations/` and `audits/` are legitimately still empty.
    """
    if not claiming_pass(study):
        return
    for name, why in (
            ("derivations", "the ground-truth track re-derives the check targets "
                            "twice and stores both derivations here"),
            ("audits", "the adversary writes its report and the battery results here")):
        d = root / name
        if not d.is_dir():
            problems.add("record." + name, "missing directory: %s/ -- %s" % (name, why))
            continue
        entries = [e for e in d.iterdir() if not e.name.startswith(".")]
        if not entries:
            problems.add("record." + name, "empty directory: %s/ -- %s" % (name, why))


def check_pass_evidence(study, root: Path, problems):
    if not claiming_pass(study):
        return
    vs = study.get("validity_stages") or {}
    s3 = vs.get("stage3_general_claim")
    s5 = vs.get("stage5_domain_scale")

    def check_outputs(stage, label):
        outputs = stage.get("outputs")
        if not outputs:
            problems.add(
                "stage.outputs",
                "PASS refused: %s records no `outputs` -- the stage is a claim with "
                "nothing behind it. List the derivations/audits that establish it."
                % label)
            return
        missing, invalid = _validate_output_paths(outputs, root)
        if invalid:
            problems.add("stage.outputs",
                         "PASS refused: %s outputs are not study-root-relative "
                         "evidence (or name the validator's own report): %s"
                         % (label, invalid))
        if missing:
            problems.add("stage.outputs",
                         "PASS refused: %s outputs missing: %s" % (label, missing))

    if not s3:
        problems.add(
            "stage3.absent",
            "PASS refused: validity_stages.stage3_general_claim absent. "
            "A PASS needs the general validity claim with ALL hypotheses and an "
            "evidence level (%s)." % " / ".join(EVIDENCE_LEVELS))
    else:
        if s3.get("evidence_level") not in EVIDENCE_LEVELS:
            problems.add("stage3.evidence-level",
                         "PASS refused: stage3 evidence_level %r is not one of %s"
                         % (s3.get("evidence_level"), list(EVIDENCE_LEVELS)))
        if not s3.get("claim"):
            problems.add("stage3.claim", "PASS refused: stage3_general_claim has no `claim` text")
        check_outputs(s3, "stage3_general_claim")

    if not s5:
        problems.add(
            "stage5.absent",
            "PASS refused: validity_stages.stage5_domain_scale absent. "
            "A PASS needs the full battery on a genuinely non-special instance.")
    else:
        inst = str(s5.get("instance", "")).lower()
        if not inst:
            problems.add("stage5.instance",
                         "PASS refused: stage5_domain_scale does not name its instance")
        else:
            inst_norm = norm(inst)
            simplified = [norm(c) for c in (study.get("simplified_cases") or [])
                          if isinstance(c, str) and c.strip()]
            restates = any(fam and (fam in inst_norm or inst_norm in fam)
                           for fam in simplified)
            if (not any(m in inst for m in NON_SPECIAL_MARKERS)
                    and (_names_special_body(inst) or restates)):
                problems.add(
                    "stage5.instance",
                    "PASS refused: stage5 instance %r names only a reference/special "
                    "body or restates a simplified case; the domain-scale instance "
                    "must be genuinely non-special (a diagonal or box/ball/simplex/"
                    "ellipsoid body does not qualify; negated forms like non-diagonal "
                    "are allowed)." % s5.get("instance"))
        check_outputs(s5, "stage5_domain_scale")

    # Seeded/falsifiable evidence, read from the RECORD only (never study.json).
    text, _ = evidence_corpus(root)
    if "seed" not in text:
        problems.add(
            "evidence.seed",
            "PASS refused: no seed recorded anywhere in audits/ derivations/ "
            "artifacts/ (a declaration in study.json is not evidence)")
    if not re.search(r"n\s*(?:in|=)\s*\{[^}\n]*?1e\d", text):
        problems.add(
            "evidence.n-grid",
            "PASS refused: no seeded N-grid (e.g. N in {1e3,1e4,1e5}) reported in "
            "audits/ derivations/ artifacts/")
    for marker, why in (
            ("failure condition",
             "a check that cannot name the predicate that would make it fail is a tautology"),
            ("mutation",
             "a check that detects no deliberately incorrect implementation is a tautology")):
        if marker not in text:
            problems.add(
                "evidence.falsifiability",
                "PASS refused: no audit declares a %r for its checks -- %s "
                "(check-battery.md 'Every check must be declared')" % (marker, why))


TOLERANCE_KEYS = {
    "se_units": ("stochastic", "se_units"),
    "confidence": ("stochastic", "confidence"),
    "abs": ("deterministic", "abs"),
    "rel": ("deterministic", "rel"),
}
TOLERANCE_RE = re.compile(
    r"\b(se_units|confidence|abs|rel)\b\s*[:=]?\s*"
    r"([0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)")


def check_tolerance_reconciliation(study, root: Path, problems):
    """check-battery.md: a tolerance restated in an audit must match study.json."""
    declared = study.get("tolerances") or {}
    text, paths = evidence_corpus(root)
    for p in paths:
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            body = p.read_text(errors="replace")
        except OSError:
            continue
        for key, value in TOLERANCE_RE.findall(body):
            block, field = TOLERANCE_KEYS[key]
            expected = (declared.get(block) or {}).get(field)
            if expected is None:
                continue
            try:
                if abs(float(value) - float(expected)) <= 1e-12 * max(1.0, abs(float(expected))):
                    continue
            except (TypeError, ValueError):
                continue
            problems.add(
                "tolerance.mismatch",
                "%s states %s = %s but study.json tolerances.%s.%s = %r; a loosened "
                "tolerance must be reconciled with the study record "
                "(check-battery.md gate A)"
                % (p.name, key, value, block, field, expected))


# ---------------------------------------------------------- document gates


def notation_block(text: str, is_beamer: bool = False) -> str:
    if is_beamer:
        m = re.search(
            r"\\begin\{frame\}[^\n{]*\{[^}]*?(?:notation|definitions)[^}]*\}"
            r"(.*?)\\end\{frame\}",
            text, re.IGNORECASE | re.DOTALL)
        return m.group(1) if m else ""
    m = re.search(r"\\(?:section|subsection)\*?\{[^}]*?(?:notation|definitions)",
                  text, re.IGNORECASE)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"\\section\*?\{", rest)
    return rest[:nxt.start()] if nxt else rest


# Cross-domain notation that is routinely used without definition. Deliberately
# small and domain-neutral: study-specific notation belongs in the audience
# spec's `symbols` map (see references/deliverables.md), not in this file.
DEFAULT_SYMBOLS = {
    "O^*": (r"O\^\*|\\tilde\{O\}", ["polylog", "hides", "soft-o", "up to"]),
    "poly(": (r"\bpoly\s*\(", ["polynomial"]),
    "TV": (r"\\mathrm\{TV\}|\btotal[- ]variation\b", ["total-variation", "total variation"]),
    "w.h.p.": (r"\bw\.h\.p\.", ["high probability"]),
    "lesssim": (r"\\lesssim", ["up to a constant", "absolute constant"]),
}


def symbol_registry(spec):
    """Default cross-domain registry, extended by the audience spec's `symbols`."""
    registry = dict(DEFAULT_SYMBOLS)
    for key, entry in ((spec or {}).get("symbols") or {}).items():
        if isinstance(entry, dict):
            pattern = entry.get("pattern") or re.escape(key)
            witnesses = entry.get("witnesses") or [key.lower()]
        else:  # a bare list of witnesses
            pattern, witnesses = re.escape(key), list(entry)
        registry[key] = (pattern, [str(w).lower() for w in witnesses])
    return registry


def check_document_spec(text: str, spec, label: str, problems, is_beamer: bool = False):
    """Enforce the audience spec, plus the conditional symbol audit: every
    registered symbol that APPEARS in the document must have a defining witness
    in the Notation/Definitions block (references/deliverables.md)."""
    source = strip_tex_comments(text)
    block = notation_block(source, is_beamer)
    if not block:
        problems.add(
            "document.notation",
            "PASS refused: %s has no Notation/Definitions block; every symbol the "
            "document uses must be defined there and conventions never assumed" % label)
        return
    low_block = block.lower()
    body = source.replace(block, " ")
    doc_norm = norm(source)

    sentence = (spec or {}).get("sentence", "")
    if not sentence:
        problems.add(
            "document.audience-sentence",
            "PASS refused: the audience spec for %s has no `sentence` -- a document "
            "that cannot say who it is for fails the gate "
            "(references/deliverables.md)" % label)
    elif norm(sentence) not in doc_norm:
        problems.add(
            "document.audience-sentence",
            "PASS refused: %s does not state its confirmed audience sentence (%r); "
            "the audience spec is authoritative (LaTeX comments do not count)"
            % (label, sentence))

    registry = symbol_registry(spec)
    for key, (pattern, witnesses) in sorted(registry.items()):
        used = re.search(pattern, body, re.IGNORECASE)
        required = key in ((spec or {}).get("must_define") or [])
        if not (used or required):
            continue
        if not any(w in low_block for w in witnesses):
            problems.add(
                "document.symbol",
                "PASS refused: %s uses %r but its Notation/Definitions block does "
                "not define it (expected a witness among %s)" % (label, key, witnesses))
    for key in (spec or {}).get("avoid", []):
        entry = registry.get(key)
        pattern = entry[0] if entry else re.escape(key)
        if re.search(pattern, body, re.IGNORECASE):
            problems.add(
                "document.avoid",
                "PASS refused: %s uses the avoided convention %r outside its "
                "definition; the audience spec forbids it" % (label, key))


class _HTMLBalanceParser(HTMLParser):
    """Catches unexpected or mis-nested end tags; HTML5-omissible start tags
    (e.g. <p>, <li>) are allowed to close implicitly, as browsers do."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}
    OMISSIBLE_CLOSE = {"p", "li", "dt", "dd", "tr", "td", "th", "option",
                       "thead", "tbody", "tfoot"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"unexpected closing </{tag}>")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        while (self.stack and self.stack[-1] != tag
               and self.stack[-1] in self.OMISSIBLE_CLOSE):
            self.stack.pop()
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
            return
        self.errors.append(f"mis-nested </{tag}> (open: <{self.stack[-1]}>)")


# ------------------------------------------------------------- TeX compiling

TEX_ENGINE_CANDIDATES = ("tectonic", "latexmk", "pdflatex", "xelatex", "lualatex")


def find_tex_engine():
    bases = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    bases += ["/Library/TeX/texbin", "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    import glob as _glob
    bases += sorted(_glob.glob("/usr/local/texlive/*/bin/*"))
    for name in TEX_ENGINE_CANDIDATES:
        for base in bases:
            exe = Path(base) / name
            if exe.is_file() and os.access(exe, os.X_OK):
                return str(exe)
    return None


def find_bibtex(engine: str):
    for base in [str(Path(engine).parent), "/Library/TeX/texbin", "/opt/homebrew/bin",
                 "/usr/local/bin", "/usr/bin"]:
        exe = Path(base) / "bibtex"
        if exe.is_file() and os.access(exe, os.X_OK):
            return str(exe)
    return None


UNDEFINED_CITE_RE = re.compile(
    r"Citation [^\n]* undefined|There were undefined references", re.IGNORECASE)


def bib_files_of(tex: Path):
    out = []
    text = strip_tex_comments(tex.read_text(errors="replace"))
    for m in re.finditer(r"\\bibliography\s*\{([^}]*)\}", text):
        for name in m.group(1).split(","):
            name = name.strip()
            if name:
                out.append((tex.parent / (name + ".bib")).resolve())
    return out


def compile_tex_artifact(engine: str, tex: Path, label: str, problems):
    """Full pipeline (engine + BibTeX + reruns). Runs on a COPY so the study's
    committed artifacts/ tree never collects .aux/.log/.pdf build products."""
    name = Path(engine).name
    if name == "tectonic":
        steps = [[engine, tex.name]]
    elif name == "latexmk":
        steps = [[engine, "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name]]
    else:
        base = [engine, "-interaction=nonstopmode", "-halt-on-error", tex.name]
        steps = [base]
        bibtex = find_bibtex(engine)
        if bibtex is not None:
            steps.append([bibtex, tex.stem])
        steps += [base, base]
    # A discovered engine may live outside PATH (e.g. /Library/TeX/texbin); its
    # own toolchain (pdflatex for latexmk, bibtex) is resolved by name, so put the
    # engine's directory on PATH for the subprocesses it launches.
    env = os.environ.copy()
    engine_dir = str(Path(engine).parent)
    env["PATH"] = engine_dir + os.pathsep + env.get("PATH", "")
    logs = []
    for step in steps:
        try:
            cp = subprocess.run(step, cwd=str(tex.parent), capture_output=True,
                                timeout=300, env=env)
        except (subprocess.TimeoutExpired, OSError) as e:
            problems.add("document.compile",
                         "PASS refused: %s compile check failed: %s" % (label, e))
            return
        logs.append((cp.stdout + cp.stderr).decode(errors="replace"))
        if cp.returncode != 0:
            problems.add(
                "document.compile",
                "PASS refused: %s fails compilation (%s exit %d); log tail: %s"
                % (label, Path(step[0]).name, cp.returncode, logs[-1][-600:]))
            return
    # Only the FINAL pass is authoritative: earlier passes legitimately warn
    # "Citation ... undefined" before bibtex has produced the .bbl. The .log
    # holds exactly the last pass; accumulated stdout (latexmk, tectonic) does
    # not, so prefer the file whenever the engine wrote one.
    log_file = tex.with_suffix(".log")
    final_log = log_file.read_text(errors="replace") if log_file.is_file() else logs[-1]
    if UNDEFINED_CITE_RE.search(final_log):
        problems.add(
            "document.citations",
            "PASS refused: %s has unresolved citations (undefined-citation warnings "
            "in the FINAL build pass); fix the \\cite keys or the .bib entries" % label)


# ------------------------------------------------------------- deliverables


def check_overclaim(text: str, study, root: Path, problems):
    """No evidence level may be asserted in prose unless some claim in the study
    record carries it. Applies to ALL four levels, not just formal verification."""
    low = strip_tex_comments(text).lower()
    try:
        record = json.dumps(study) + (root / "registry.json").read_text(errors="replace")
    except OSError:
        record = json.dumps(study)
    record = record.lower()
    for level in EVIDENCE_LEVELS:
        # Strip disclaimers ("nothing here is formally verified") before looking
        # for an assertion of the level. The negation must be adjacent to the
        # phrase: an unrelated "no" earlier in the same sentence must not launder
        # an assertion that follows it.
        esc = re.escape(level)
        disclaimers = (
            r"\b(?:not|no|never)\s+(?:\w+\s+){0,3}" + esc,
            r"\b(?:nothing|none)\b[^.]{0,60}?\bis\s+" + esc,
        )
        assertion = low
        for pattern in disclaimers:
            assertion = re.sub(pattern, " ", assertion)
        if level in assertion and level not in record:
            problems.add(
                "document.overclaim",
                "PASS refused: the paper asserts %r but no claim in study.json / "
                "registry.json carries that evidence level (no-overclaim rule)" % level)


def check_deliverables(study, root: Path, problems):
    d = study.get("deliverables") or {}
    if not isinstance(d, dict) or "paper" not in d:
        problems.add(
            "deliverables.declaration",
            "deliverables gate: study.json has no `deliverables` declaration "
            "(paper/slides/web). Record it at intake (see references/deliverables.md).")
        return
    slides_req = str(d.get("slides", "")).lower()
    web_req = str(d.get("web", "")).lower()
    if not slides_req.startswith("required") and not slides_req.startswith("not-required"):
        problems.add("deliverables.declaration",
                     "deliverables gate: `slides` must be 'required' or "
                     "'not-required:<reason>', got %r" % d.get("slides"))
    if web_req not in ("optional", "required"):
        problems.add("deliverables.declaration",
                     "deliverables gate: `web` must be 'optional' or 'required', got %r"
                     % d.get("web"))
    if not claiming_pass(study):
        return

    if d.get("consultation_pending"):
        problems.add(
            "deliverables.consultation",
            "PASS refused: deliverables.consultation_pending is true -- the one-time "
            "audience consultation has not been completed; answer the checkpointed "
            "questionnaire before claiming PASS")
    aud = d.get("audience") or {}
    paper_spec, slides_spec, web_spec = aud.get("paper"), aud.get("slides"), aud.get("web")
    if not isinstance(paper_spec, dict):
        problems.add("deliverables.audience",
                     "PASS refused: deliverables.audience.paper is missing -- the "
                     "paper's audience spec must be set by the post-research consultation")
    if slides_req.startswith("required") and not isinstance(slides_spec, dict):
        problems.add("deliverables.audience",
                     "PASS refused: deliverables.audience.slides is missing -- the "
                     "slides' audience spec must be set by the post-research consultation")

    engine = find_tex_engine()
    if engine is None:
        problems.add(
            "deliverables.engine",
            "PASS refused: no TeX engine found (searched PATH plus /Library/TeX/texbin, "
            "/opt/homebrew/bin, /usr/local/texlive/*/bin/*). Stage-4 artifacts must "
            "COMPILE before success is claimed; install tectonic or a TeX "
            "distribution, then re-run this validator.")

    # Compile on a throwaway copy of artifacts/ so build products never land in
    # the study's committed tree.
    with tempfile.TemporaryDirectory(prefix="rq-compile-") as tmp:
        sandbox = Path(tmp) / "artifacts"
        if (root / "artifacts").is_dir():
            shutil.copytree(root / "artifacts", sandbox)
        else:
            sandbox.mkdir(parents=True)

        paper = root / "artifacts" / "paper" / "main.tex"
        if not paper.exists() or paper.stat().st_size < 50:
            problems.add("deliverables.paper",
                         "PASS refused: artifacts/paper/main.tex missing or empty "
                         "(the stage-4 white paper is mandatory)")
        else:
            text = paper.read_text(errors="replace")
            source = strip_tex_comments(text)
            if "\\documentclass" not in source:
                problems.add("deliverables.paper",
                             "PASS refused: artifacts/paper/main.tex has no \\documentclass")
            missing = [s for s in PAPER_SECTIONS
                       if not re.search(r"\\(?:sub)?section\*?\{[^}]*\b%s" % s, source,
                                        re.IGNORECASE)]
            if missing:
                problems.add(
                    "deliverables.sections",
                    "PASS refused: paper is missing required sections as \\section "
                    "headings: %s" % missing)
            for ref in (study.get("slug", ""), study.get("task_id", "")):
                if ref and ref in source:
                    break
            else:
                problems.add("deliverables.paper",
                             "PASS refused: paper does not reference the study slug/task_id")
            check_overclaim(text, study, root, problems)
            bibs = bib_files_of(paper)
            if not bibs:
                problems.add("deliverables.bibliography",
                             "PASS refused: paper has no \\bibliography{...} command "
                             "(proper BibTeX references are mandatory)")
            else:
                missing_bib = [str(b) for b in bibs if not b.exists()]
                if missing_bib:
                    problems.add("deliverables.bibliography",
                                 "PASS refused: paper bibliography file(s) missing: %s"
                                 % missing_bib)
            check_document_spec(text, paper_spec, "artifacts/paper/main.tex", problems)
            if engine is not None:
                compile_tex_artifact(engine, sandbox / "paper" / "main.tex",
                                     "artifacts/paper/main.tex", problems)

        if slides_req.startswith("required"):
            slides = root / "artifacts" / "slides" / "main.tex"
            if not slides.exists() or slides.stat().st_size < 50:
                problems.add("deliverables.slides",
                             "PASS refused: artifacts/slides/main.tex missing "
                             "(slides declared required)")
            else:
                t = slides.read_text(errors="replace")
                st = strip_tex_comments(t)
                if "\\documentclass" not in st or "beamer" not in st.lower():
                    problems.add("deliverables.slides",
                                 "PASS refused: slides/main.tex is not a Beamer document")
                bibs = bib_files_of(slides)
                if not bibs:
                    problems.add("deliverables.bibliography",
                                 "PASS refused: slides have no \\bibliography{...} command "
                                 "(mandatory; may share the paper's refs.bib)")
                else:
                    missing_bib = [str(b) for b in bibs if not b.exists()]
                    if missing_bib:
                        problems.add("deliverables.bibliography",
                                     "PASS refused: slides bibliography file(s) missing: %s"
                                     % missing_bib)
                check_document_spec(t, slides_spec, "artifacts/slides/main.tex",
                                    problems, is_beamer=True)
                if engine is not None:
                    compile_tex_artifact(engine, sandbox / "slides" / "main.tex",
                                         "artifacts/slides/main.tex", problems)

    if web_req == "required":
        if not isinstance(web_spec, dict):
            problems.add("deliverables.audience",
                         "PASS refused: deliverables.audience.web is missing -- the web "
                         "artifact's audience spec must be set by the consultation")
        web = root / "artifacts" / "web" / "index.html"
        if not web.exists() or web.stat().st_size < 50:
            problems.add("deliverables.web",
                         "PASS refused: artifacts/web/index.html missing (web declared required)")
        else:
            raw = web.read_text(errors="replace")
            if "<html" not in raw.lower():
                problems.add("deliverables.web",
                             "PASS refused: artifacts/web/index.html is not an HTML document")
            else:
                parser = _HTMLBalanceParser()
                try:
                    parser.feed(raw)
                    parser.close()
                except Exception as e:
                    problems.add("deliverables.web",
                                 "PASS refused: artifacts/web/index.html does not parse: %s" % e)
                if parser.errors:
                    problems.add("deliverables.web",
                                 "PASS refused: artifacts/web/index.html has malformed markup: "
                                 + "; ".join(parser.errors[:5]))
                # A well-formed page closes everything it opened, leaving the
                # stack empty. Anything still open never got its end tag.
                if parser.stack:
                    problems.add("deliverables.web",
                                 "PASS refused: artifacts/web/index.html leaves tag(s) "
                                 "unclosed: %s" % ["<%s>" % t for t in parser.stack])
                sentence = (web_spec or {}).get("sentence") if isinstance(web_spec, dict) else None
                if not sentence:
                    problems.add(
                        "document.audience-sentence",
                        "PASS refused: the audience spec for artifacts/web/index.html has "
                        "no `sentence` -- a document that cannot say who it is for fails "
                        "the gate")
                elif norm(sentence) not in norm(raw):
                    problems.add("document.audience-sentence",
                                 "PASS refused: artifacts/web/index.html does not state its "
                                 "confirmed audience sentence")
                if not (re.search(r'id\s*=\s*["\']references["\']', raw, re.IGNORECASE)
                        or re.search(r"<h[1-6][^>]*>\s*references", raw, re.IGNORECASE)):
                    problems.add("deliverables.web",
                                 "PASS refused: artifacts/web/index.html has no references "
                                 'section (id="references" or a References heading)')
                for m in re.finditer(
                        r'<a\b[^>]*href\s*=\s*"https?://[^"]*"[^>]*>(.*?)</a>',
                        raw, re.IGNORECASE | re.DOTALL):
                    txt = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                    if not txt or re.match(r"https?://", txt):
                        problems.add("deliverables.web",
                                     "PASS refused: artifacts/web/index.html has an external "
                                     "link without proper anchor text (bare URLs are not "
                                     "references); label each link with author, title, year")
                        break


def check_document_adversary_reports(study, root: Path, problems):
    if not claiming_pass(study):
        return
    d = study.get("deliverables") or {}
    names = ["paper"]
    if str(d.get("slides", "")).lower().startswith("required"):
        names.append("slides")
    if str(d.get("web", "")).lower() == "required":
        names.append("web")
    for name in names:
        report = root / "audits" / f"document-adversary-{name}.md"
        if not report.exists():
            problems.add(
                "document-adversary.missing",
                "PASS refused: audits/document-adversary-%s.md missing -- the "
                "document-adversary (soft tier) has not audited the %s deliverable "
                "against its audience spec" % (name, name))
            continue
        text = report.read_text(errors="replace")
        verdicts = re.findall(r"VERDICT:\s*(PASS|NEEDS-EDITS)", text, re.IGNORECASE)
        if not verdicts:
            problems.add("document-adversary.verdict",
                         "PASS refused: audits/document-adversary-%s.md has no "
                         "'VERDICT: PASS'/'VERDICT: NEEDS-EDITS' line" % name)
        elif verdicts[-1].upper() == "NEEDS-EDITS":
            problems.add("document-adversary.verdict",
                         "PASS refused: audits/document-adversary-%s.md verdict is "
                         "NEEDS-EDITS -- the %s deliverable must be revised and "
                         "re-audited" % (name, name))


def check_declared_hashes(root: Path, problems):
    _, paths = evidence_corpus(root)
    for p in paths:
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"(?:sha-?256)\s*[:=]\s*([0-9a-fA-F]{64})", text):
            declared = m.group(1).lower()
            line = text[:m.start()].rsplit("\n", 1)[-1]
            candidates = re.findall(r"[\w./-]+\.(?:py|json|md|csv|tex)", line)
            for c in candidates:
                fp = root / c
                if fp.exists() and sha256_hex(fp) == declared:
                    break
            else:
                if candidates:
                    problems.add(
                        "hash.mismatch",
                        "%s: declared sha256 %s... matches none of the referenced "
                        "artifacts on its line" % (p.name, declared[:12]))


# ------------------------------------------------------------ literature gate
#
# Decision 14: the literature lane. Verified literature state lives ONLY in
# literature/known-results.json (+ negative-exports.json); interim dossiers are
# advisory and are never counted as verified records. The gate fires only when
# study.json carries a 'literature' object, so studies that never ran the lane
# are unaffected (backward compatible with pre-lane studies).


def _norm_id(s):
    s = str(s).strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^(arxiv|doi)\s*:?\s*", "", s)
    s = s.strip("{}'\"")
    return " ".join(s.split())


def _verified_source_ids(map_data):
    """paper_id values whose adversarial check is verified-current.

    Sources of `open` entries are excluded: the lane may have fetched the paper,
    but the question it was fetched for is still open, so nothing may be cited
    as a result on its authority.
    """
    ids = set()
    for entries in (map_data or {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("category") == "open":
                continue
            for src in entry.get("sources") or []:
                if not isinstance(src, dict):
                    continue
                if (src.get("adversarial_check") or {}).get("status") == "verified-current":
                    ids.add(_norm_id(src.get("paper_id", "")))
    return ids


def bib_entries_of(bib_path):
    """Parse @type{key,...} entries with stdlib regex (no external parser)."""
    if not bib_path.exists():
        return {}
    text = bib_path.read_text(errors="replace")
    entries = {}
    for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", text):
        body = text[m.end():]
        nxt = re.search(r"@\w+\s*\{", body)
        body = body[:nxt.start()] if nxt else body
        entries[m.group(1)] = body
    return entries


def _bib_entry_ids(body):
    ids = set()
    for field in ("doi", "eprint"):
        m = re.search(r"\b" + field + r"\s*=\s*([^\s,}]+)", body, re.IGNORECASE)
        if m:
            ids.add(_norm_id(m.group(1)))
    return ids


def _bib_titles(body):
    """Normalized titles from a BibTeX entry, for paper_id = normalized-title."""
    titles = set()
    for m in re.finditer(r"\btitle\s*=\s*\{([^}]*)\}", body, re.IGNORECASE):
        titles.add(_norm_id(m.group(1)))
    for m in re.finditer(r'\btitle\s*=\s*"([^"]*)"', body, re.IGNORECASE):
        titles.add(_norm_id(m.group(1)))
    return titles


def _check_completeness(lit, root: Path, problems):
    """The anti-premature-termination gate (§6). Returns the swept sub-problem ids.

    The mandatory sweeps are read from the schema's own `required` list, so the
    validator never carries a second copy of them (Decision 13, rule 3).
    """
    comp_file = lit.get("completeness_file") or COMPLETENESS_DEFAULT
    comp_path = root / comp_file
    if not comp_path.exists():
        problems.add(
            "literature.completeness-missing",
            "literature gate: %s missing -- the lane may not conclude without a "
            "per-line completeness checklist; 'the model finished early' is a "
            "failing condition, not the default" % comp_file)
        return set()
    try:
        data = json.loads(comp_path.read_text())
    except json.JSONDecodeError as e:
        problems.add("literature.completeness-invalid",
                     "literature gate: %s is not valid JSON: %s" % (comp_file, e))
        return set()

    schema = load_schema("completeness.schema.json")
    if schema is None:
        problems.add("schema.missing",
                     "shipped schema completeness.schema.json not found next to "
                     "the validator")
        return set()
    for e in validate_json_schema(data, schema):
        problems.add("literature.completeness-schema",
                     "%s does not match completeness.schema.json: %s" % (comp_file, e))

    mandatory = schema["definitions"]["sweeps"]["required"]
    swept = set()
    for line in (data.get("lines") or []) if isinstance(data, dict) else []:
        if not isinstance(line, dict):
            continue
        swept.add(line.get("subproblem_id"))
        sweeps = line.get("sweeps")
        if not isinstance(sweeps, dict):
            continue
        for name in mandatory:
            value = sweeps.get(name)
            if isinstance(value, str) and not value.strip():
                problems.add(
                    "literature.completeness-empty-sweep",
                    "literature gate: line %r records an empty mandatory sweep (%s) "
                    "in %s -- state what was actually swept, or the line is not done"
                    % (line.get("line"), name, comp_file))
    return swept


def check_literature_gate(study, root: Path, problems):
    lit = study.get("literature")
    if not isinstance(lit, dict):
        return

    # §10: the intake sweep is mandatory, skippable ONLY on an explicit user
    # assertion -- which must then be on the record, not in someone's memory.
    if lit.get("phase") == "skipped":
        if not (lit.get("skip_reason") or "").strip():
            problems.add(
                "literature.skip-unrecorded",
                "literature gate: literature.phase is 'skipped' with no `skip_reason` -- "
                "the sweep is skippable only on an explicit user assertion at intake, "
                "and that assertion has to be recorded to count")
        return

    map_file = lit.get("map_file") or LITERATURE_MAP_DEFAULT
    map_path = root / map_file
    map_data = None
    if not map_path.exists():
        problems.add("literature.map-missing",
                     "literature gate: %s missing -- the lane must leave a verified "
                     "known-results map before marking a sub-problem known or "
                     "exporting a negative" % map_file)
    else:
        try:
            map_data = json.loads(map_path.read_text())
        except json.JSONDecodeError as e:
            problems.add("literature.map-invalid",
                         "literature gate: %s is not valid JSON: %s" % (map_file, e))
            map_data = None
        if map_data is not None:
            schema = load_schema("known-results.schema.json")
            if schema is None:
                problems.add("schema.missing",
                             "shipped schema known-results.schema.json not found "
                             "next to the validator")
            else:
                for e in validate_json_schema(map_data, schema):
                    problems.add("literature.map-schema",
                                 "%s does not match known-results.schema.json: %s"
                                 % (map_file, e))

    verified = _verified_source_ids(map_data)

    # The declared phase and the record on disk must agree: a lane that never ran
    # cannot have verified anything, and one still running has not concluded.
    phase = lit.get("phase") or "not-run"
    if verified and phase != "concluded":
        problems.add(
            "literature.phase",
            "literature gate: study.json literature.phase is %r but %s already "
            "carries verified-current records -- only a concluded lane may hold "
            "verified state" % (phase, map_file))

    def verified_entries(spid):
        entries = (map_data or {}).get(spid) if isinstance(map_data, dict) else None
        out = []
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for src in entry.get("sources") or []:
                    if (isinstance(src, dict)
                            and (src.get("adversarial_check") or {}).get("status") == "verified-current"):
                        out.append(entry)
                        break
        return out

    # (1) a 'known' mark must be backed by an independently verified record.
    for sp in study.get("subproblems") or []:
        if not isinstance(sp, dict):
            continue
        if sp.get("status") == "known" and not verified_entries(sp.get("id")):
            problems.add(
                "literature.known-unverified",
                "literature gate: sub-problem %s is marked 'known' but %s has no "
                "verified-current record for it -- a 'known' mark must be backed by "
                "an independently verified literature source" % (sp.get("id"), map_file))

        # (1a) C5: routed away as impossible. The answer IS the impossibility, so
        #      the study's conclusion rests on it -- §4 makes that load-bearing and
        #      sends it to the math lane before the study may rely on it.
        if sp.get("status") == "impossible":
            spid = sp.get("id")
            impossible = [e for e in verified_entries(spid)
                          if e.get("category") == "impossible"]
            if not impossible:
                problems.add(
                    "literature.impossible-unverified",
                    "literature gate: sub-problem %s is routed away as impossible but "
                    "%s has no verified-current 'impossible' record for it -- an "
                    "impossibility is an answer, and it owes the same provenance as one"
                    % (spid, map_file))
                continue
            for entry in impossible:
                target = entry.get("escalation")
                if not target:
                    problems.add(
                        "literature.impossible-unescalated",
                        "literature gate: the 'impossible' record for %s carries no "
                        "`escalation` -- a conclusion that RESTS on an impossibility is "
                        "load-bearing and must be accepted by the math lane first "
                        "(the literature lane never certifies that a claim is true)" % spid)

    # (1c) a declared escalation must be readable, wherever it is declared: an
    #      escalation nobody can open is a claim, not a record.
    if isinstance(map_data, dict):
        for spid, entries in map_data.items():
            for entry in entries if isinstance(entries, list) else []:
                target = entry.get("escalation") if isinstance(entry, dict) else None
                if target and not (root / target).exists():
                    problems.add(
                        "literature.escalation-missing",
                        "literature gate: the %s record for %s declares escalation %r, "
                        "which does not exist" % (entry.get("category"), spid, target))

    # (1b) the completeness checklist: a verified record may not exist for a
    #      line the lane never swept, and no mandatory sweep may be empty.
    swept = _check_completeness(lit, root, problems)
    if isinstance(map_data, dict):
        for spid, entries in map_data.items():
            if not isinstance(entries, list):
                continue
            if not any(isinstance(e, dict) and e.get("category") != "open" for e in entries):
                continue
            if spid not in swept:
                problems.add(
                    "literature.completeness-line-missing",
                    "literature gate: %s carries a non-open record for %s but the "
                    "completeness checklist has no completeness line for it -- a line "
                    "that was never swept cannot produce a verified record" % (map_file, spid))

    # (2) every exported negative must trace to an 'impossible' verified entry.
    exports_file = lit.get("negative_exports_file") or NEGATIVE_EXPORTS_DEFAULT
    exports_path = root / exports_file
    exports_data = None
    if exports_path.exists():
        try:
            exports_data = exports = json.loads(exports_path.read_text())
        except json.JSONDecodeError as e:
            problems.add("literature.exports-invalid",
                         "literature gate: %s is not valid JSON: %s" % (exports_file, e))
            exports = None
        if isinstance(exports, dict):
            schema = load_schema("negative-exports.schema.json")
            if schema is None:
                problems.add("schema.missing",
                             "shipped schema negative-exports.schema.json not found "
                             "next to the validator")
            else:
                for e in validate_json_schema(exports, schema):
                    problems.add("literature.exports-schema",
                                 "%s does not match negative-exports.schema.json: %s"
                                 % (exports_file, e))
            for ex in exports.get("exports") or []:
                if not isinstance(ex, dict):
                    continue
                spid = ex.get("subproblem_id")
                pid = _norm_id(ex.get("source_paper_id", ""))
                ok = False
                entries = (map_data or {}).get(spid) if isinstance(map_data, dict) else None
                for entry in (entries or []):
                    if not isinstance(entry, dict) or entry.get("category") != "impossible":
                        continue
                    for src in entry.get("sources") or []:
                        if (isinstance(src, dict)
                                and _norm_id(src.get("paper_id", "")) == pid
                                and (src.get("adversarial_check") or {}).get("status") == "verified-current"):
                            ok = True
                if not ok:
                    problems.add(
                        "literature.negative-unverified",
                        "literature gate: exported negative for %s from %r does not trace "
                        "to an 'impossible' entry with a verified-current source in %s -- "
                        "a negative cannot appear from nowhere"
                        % (spid, ex.get("source_paper_id"), map_file))

    # (2b) the map's negative_export flag and the exports file are one fact
    #      recorded twice; they may not disagree.
    exported_pairs = set()
    if isinstance(exports_data, dict):
        for ex in exports_data.get("exports") or []:
            if isinstance(ex, dict):
                exported_pairs.add((ex.get("subproblem_id"), _norm_id(ex.get("source_paper_id", ""))))
    if isinstance(map_data, dict):
        for spid, entries in map_data.items():
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict):
                    continue
                pids = {_norm_id(s.get("paper_id", "")) for s in entry.get("sources") or []
                        if isinstance(s, dict)}
                sent = any((spid, pid) in exported_pairs for pid in pids)
                if entry.get("negative_export") and not sent:
                    problems.add(
                        "literature.export-flag",
                        "literature gate: %s marks a %s entry `negative_export: true` but "
                        "%s carries no matching export -- the map and the exports file "
                        "record one fact and may not disagree" % (map_file, spid, exports_file))
                elif sent and not entry.get("negative_export"):
                    problems.add(
                        "literature.export-flag",
                        "literature gate: %s exports a negative for %s but its entry in %s "
                        "is not flagged `negative_export: true` -- what crossed the membrane "
                        "must be recorded on both sides" % (exports_file, spid, map_file))

    # (2c) dossiers stay advisory evidence, never verified records -- but an
    #      unparsable dossier is a defect in the record the adversary sampled.
    dossier_schema = load_schema("dossier.schema.json")
    for dossier in sorted((root / "interim" / "lit").glob("*/dossier.json")):
        rel = dossier.relative_to(root)
        try:
            data = json.loads(dossier.read_text())
        except json.JSONDecodeError as e:
            problems.add("literature.dossier-invalid",
                         "literature gate: %s is not valid JSON: %s" % (rel, e))
            continue
        if dossier_schema is None:
            problems.add("schema.missing",
                         "shipped schema dossier.schema.json not found next to the validator")
            break
        for e in validate_json_schema(data, dossier_schema):
            problems.add("literature.dossier-schema",
                         "%s does not match dossier.schema.json: %s" % (rel, e))

    def refuse_unverified_bib(bib_path, label):
        for key, body in bib_entries_of(bib_path).items():
            ids = _bib_entry_ids(body)
            titles = _bib_titles(body)
            if not (ids & verified) and _norm_id(key) not in verified \
                    and not (titles & verified):
                problems.add(
                    "literature.citation-unverified",
                    "literature gate: bibliography entry %r (in %s) has no "
                    "verified-current literature record with a settled/impossible/"
                    "superseded category -- every citation must trace to a fetched, "
                    "adversarially verified source (DOI, arXiv id, or normalized "
                    "title), and a still-open question is not a result to cite"
                    % (key, label))

    # (3) the verified refs.bib seed (§8): a concluded lane that verified any
    #     non-open result must leave a seed; if present, every entry must trace.
    seed_file = lit.get("refs_seed_file") or REFS_SEED_DEFAULT
    seed_path = root / seed_file
    if phase == "concluded" and verified:
        if not seed_path.exists():
            problems.add(
                "literature.refs-seed-missing",
                "literature gate: %s missing -- a concluded literature lane with "
                "verified records must leave a refs-seed.bib whose entries trace "
                "to those records" % seed_file)
    if seed_path.exists():
        refuse_unverified_bib(seed_path, seed_file)

    # (4) fabricated-citation gate (PASS only): every \cite traces to a verified
    #     source. The paper may not cite what the lane never verified.
    if claiming_pass(study):
        tex_files = [root / rel for rel in
                     ("artifacts/paper/main.tex", "artifacts/slides/main.tex")]
        for tex in tex_files:
            if not tex.exists():
                continue
            for bp in bib_files_of(tex):
                refuse_unverified_bib(bp, bp.name)


# --------------------------------------------------------------------- main


def run(study_root: str):
    root = Path(study_root).resolve()
    sp = root / "study.json"
    if not sp.exists():
        return None, "ERROR: no study.json under %s" % root, 2
    try:
        study = json.loads(sp.read_text())
    except json.JSONDecodeError as e:
        return None, "ERROR: study.json invalid JSON: %s" % e, 2
    registry = None
    rp = root / "registry.json"
    problems = Problems()
    if not rp.exists():
        problems.add("registry.missing", "registry.json missing")
    else:
        try:
            registry = json.loads(rp.read_text())
        except json.JSONDecodeError as e:
            problems.add("registry.invalid", "registry.json invalid JSON: %s" % e)

    check_against_schemas(study, registry, problems)
    check_literature_gate(study, root, problems)
    check_coverage(study, problems)
    check_registry_consistency(study, registry or {}, root, problems)
    check_record_present(study, root, problems)
    check_deliverables(study, root, problems)
    check_document_adversary_reports(study, root, problems)
    check_pass_evidence(study, root, problems)
    check_tolerance_reconciliation(study, root, problems)
    check_declared_hashes(root, problems)

    hashes = {}
    for name in ("study.json", "registry.json"):
        p = root / name
        if p.is_file():
            hashes[name] = sha256_hex(p)

    status = study.get("status", "")
    result = "fail" if problems else "pass"
    if problems:
        summary = "FAIL -- %d problem(s):\n" % len(problems) + "\n".join(
            "  - " + p["message"] for p in problems)
    elif claiming_pass(study):
        summary = "PASS -- state valid; declared status %r has complete evidence." % status
    else:
        summary = "OK -- state valid; status %r (no PASS claimed)." % status

    report = {
        "schema": "rq-check-report",
        "version": 2,
        "study_root": str(root),
        "run": {
            "id": time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8],
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "result": result,
        "claiming_pass": claiming_pass(study),
        "problems": list(problems),
        "hashes": hashes,
        "environment": env_manifest(),
    }
    return report, summary, (1 if problems else 0)


def main(argv=None):
    ap = argparse.ArgumentParser(description="RigorQuant meta-validator")
    ap.add_argument("--study", required=True, help="path to the study root (contains study.json)")
    ap.add_argument("--out", help="also write the JSON report to this file")
    args = ap.parse_args(argv)
    report, summary, code = run(args.study)
    print(summary)
    if args.out and report is not None:
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print("wrote report to", args.out)
    return code


if __name__ == "__main__":
    sys.exit(main())
