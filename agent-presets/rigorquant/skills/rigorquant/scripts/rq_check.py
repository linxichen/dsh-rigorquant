#!/usr/bin/env python3
"""rq_check.py -- RigorQuant meta-validator.

Validates study.json / registry.json, enforces the COVERAGE gate (the union of
sub-problems must cover the ORIGINAL statement: every general question needs a
`generalization` sub-problem carrying the broad claim and a `domain-scale`
sub-problem certifying a genuinely non-special instance), and refuses a
declared PASS without the mandatory stage evidence (stage-3 general validity
claim with hypotheses + evidence level, stage-5 domain-scale stress test,
seeded N-grid hardening, audit-referenced passed routes, and falsifiable check
declarations).

Usage:
    python3 scripts/rq_check.py --study <study-root>

Exit codes:
    0  state valid (and PASS evidence complete, when a PASS is claimed)
    1  FAIL -- state invalid or PASS evidence incomplete (gaps printed)
    2  ERROR -- cannot read/parse the study state
"""

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

REQUIRED_STUDY_FIELDS = [
    "slug", "title", "mode", "repo_root", "env_lane", "task_id", "created",
    "statement", "broad_criterion", "success_criterion", "subproblems",
    "simplified_cases", "seeds", "tolerances", "budget", "status",
]

SUB_STAGES = {"reference-case", "generalization", "domain-scale"}
EVIDENCE_LEVELS = {
    "falsification-surviving", "independently re-derived",
    "certificate-checked", "formally verified",
}
REFERENCE_BODIES = ("box", "ball", "simplex", "ellipsoid")


def sha256_hex(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_schema(study, problems):
    missing = [f for f in REQUIRED_STUDY_FIELDS if f not in study]
    if missing:
        problems.append(f"study.json missing required fields: {missing}")
        return None
    subs = study.get("subproblems")
    if not isinstance(subs, list) or not subs:
        problems.append("study.json has no subproblems (expected a non-empty list)")
        return None
    return subs


def check_coverage(study, subs, problems):
    if not study.get("broad_criterion"):
        problems.append(
            "coverage gate: study.json has no `broad_criterion` -- the ORIGINAL "
            "broad claim a PASS must deliver (verbatim restatement of the user's "
            "general question). Record it at intake, never re-scope it to the "
            "simplified cases.")
    stages = [sp.get("stage", "") for sp in subs]
    if "generalization" not in stages:
        problems.append(
            "coverage gate FAILED: no subproblem has stage=generalization. "
            "The broad claim is not carried by any sub-problem -- a study that "
            "only exercises its simplified cases can never answer a general "
            "question.")
    if "domain-scale" not in stages:
        problems.append(
            "coverage gate FAILED: no subproblem has stage=domain-scale. "
            "There is no certification on a genuinely non-special instance.")
    for sp in subs:
        st = sp.get("stage", "")
        if st and st not in SUB_STAGES:
            problems.append(f"subproblem {sp.get('id', '?')} has unknown stage {st!r}")


def check_pass_evidence(study, root: Path, problems):
    status = str(study.get("status", ""))
    if "PASS" not in status.upper() or "reopen" in status.lower():
        return  # only a declared PASS is gated here
    vs = study.get("validity_stages") or {}
    s3 = vs.get("stage3_general_claim")
    s5 = vs.get("stage5_domain_scale")
    if not s3:
        problems.append(
            "PASS refused: validity_stages.stage3_general_claim absent. "
            "A PASS needs the general validity claim with ALL hypotheses and an "
            "evidence level (falsification-surviving / independently re-derived / "
            "certificate-checked / formally verified).")
    else:
        if s3.get("evidence_level") not in EVIDENCE_LEVELS:
            problems.append(
                f"PASS refused: stage3 evidence_level {s3.get('evidence_level')!r} "
                f"is not one of {sorted(EVIDENCE_LEVELS)}")
        if not s3.get("claim"):
            problems.append("PASS refused: stage3_general_claim has no `claim` text")
        missing = [p for p in (s3.get("outputs") or []) if not (root / p).exists()]
        if missing:
            problems.append(f"PASS refused: stage3 outputs missing: {missing}")
    if not s5:
        problems.append(
            "PASS refused: validity_stages.stage5_domain_scale absent. "
            "A PASS needs the full battery on a genuinely non-special instance.")
    else:
        inst = str(s5.get("instance", "")).lower()
        if not inst:
            problems.append("PASS refused: stage5_domain_scale does not name its instance")
        else:
            non_special_markers = ("p-norm", "p norm", "quadratic", "intersection",
                                   "sublevel", "lens", "polytope", "convex-quadratic")
            if not any(m in inst for m in non_special_markers) and \
               any(re.search(rf"\b{b}\b", inst) for b in REFERENCE_BODIES):
                problems.append(
                    f"PASS refused: stage5 instance {s5.get('instance')!r} names only a "
                    f"reference-case body {REFERENCE_BODIES}; the domain-scale instance "
                    f"must be non-special (e.g. a p-norm ball with p not in {{1,2,inf}}, "
                    f"a convex-quadratic set, an intersection of bodies).")
        missing = [p for p in (s5.get("outputs") or []) if not (root / p).exists()]
        if missing:
            problems.append(f"PASS refused: stage5 outputs missing: {missing}")
    # seeded N-grid evidence must be discoverable in study/artifacts/audits text
    parts = []
    sp = root / "study.json"
    try:
        parts.append(sp.read_text(errors="replace"))
    except OSError:
        pass
    for p in sorted((root / "artifacts").glob("*.md")) + sorted((root / "audits").glob("*.md")):
        try:
            parts.append(p.read_text(errors="replace"))
        except OSError:
            pass
    text = "\n".join(parts)
    low = text.lower()
    if "seed" not in low:
        problems.append("PASS refused: no seed recorded in study.json / artifacts / audits")
    if not re.search(r"n\s*(?:in|=)\s*\{[^}\n]*?1e3", low):
        problems.append("PASS refused: no seeded N-grid (e.g. N in {1e3,1e4,1e5}) "
                        "found in study.json / artifacts / audits")
    for marker in ("failure condition", "mutation"):
        if marker not in low:
            problems.append(
                f"PASS refused: no audit text declares a {marker!r} for its checks "
                f"(a check without a failure condition or a detected mutation is a "
                f"tautology, not evidence)")


PAPER_SECTIONS = ("statement", "method", "validity", "certification",
                  "limitations", "reproduction")


def claiming_pass(study) -> bool:
    status = str(study.get("status", ""))
    return "PASS" in status.upper() and "reopen" not in status.lower()


TEX_ENGINE_CANDIDATES = ("tectonic", "pdflatex", "latexmk", "xelatex", "lualatex")


def find_tex_engine():
    """Return the first usable TeX engine, searching PATH and standard installs."""
    bases = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    bases += ["/Library/TeX/texbin", "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    bases += sorted(glob.glob("/usr/local/texlive/*/bin/*"))
    for name in TEX_ENGINE_CANDIDATES:
        for base in bases:
            exe = Path(base) / name
            if exe.is_file() and os.access(exe, os.X_OK):
                return str(exe)
    return None


def tex_compile_command(engine: str, target: Path):
    """Engine-correct compile command. Runs in the target's directory."""
    name = Path(engine).name
    if name == "tectonic":
        return [engine, str(target)]
    if name == "latexmk":
        return [engine, "-pdf", "-interaction=nonstopmode", "-halt-on-error", str(target)]
    return [engine, "-interaction=nonstopmode", "-halt-on-error", str(target)]


UNDEFINED_CITE_RE = re.compile(
    r"Citation [^\n]* undefined|There were undefined references", re.IGNORECASE)


def find_bibtex(engine: str):
    exe = Path(engine).parent / "bibtex"
    if exe.is_file() and os.access(exe, os.X_OK):
        return str(exe)
    for base in ("/Library/TeX/texbin", "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        exe = Path(base) / "bibtex"
        if exe.is_file() and os.access(exe, os.X_OK):
            return str(exe)
    return None


def bib_files_of(tex: Path):
    """Resolved .bib files referenced by \\bibliography{...} in the TeX source."""
    out = []
    text = tex.read_text(errors="replace")
    for m in re.finditer(r"\\bibliography\s*\{([^}]*)\}", text):
        for name in m.group(1).split(","):
            name = name.strip()
            if name:
                out.append((tex.parent / (name + ".bib")).resolve())
    return out


def compile_tex_artifact(engine: str, tex: Path, label: str, problems):
    """Full pipeline (engine + BibTeX + reruns) for a TeX artifact; a failed
    render or unresolved citations refuse the PASS."""
    name = Path(engine).name
    base = [engine, "-interaction=nonstopmode", "-halt-on-error", str(tex)]
    if name == "tectonic":
        steps = [[engine, str(tex)]]
    elif name == "latexmk":
        steps = [[engine, "-pdf", "-interaction=nonstopmode", "-halt-on-error", str(tex)]]
    else:
        steps = [base]
        bibtex = find_bibtex(engine)
        if bibtex is not None:
            steps.append([bibtex, tex.stem])
        steps += [base, base]
    logs = []
    for step in steps:
        try:
            cp = subprocess.run(step, cwd=str(tex.parent), capture_output=True, timeout=300)
        except (subprocess.TimeoutExpired, OSError) as e:
            problems.append(f"PASS refused: {label} compile check failed: {e}")
            return
        logs.append((cp.stdout + cp.stderr).decode(errors="replace"))
        if cp.returncode != 0:
            problems.append(
                f"PASS refused: {label} fails compilation ({step[0]} exit "
                f"{cp.returncode}); log tail: {logs[-1][-600:]}")
            return
    # Only the FINAL engine pass is authoritative: the first pass legitimately
    # warns "Citation ... undefined" before bibtex has produced the .bbl.
    if UNDEFINED_CITE_RE.search(logs[-1]):
        problems.append(
            f"PASS refused: {label} has unresolved citations (undefined-citation "
            f"warnings in the FINAL build pass); fix the \\cite keys or the .bib entries")


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
        # HTML5 auto-closes omissible start tags (e.g. </div> closes a pending <p>)
        while (self.stack and self.stack[-1] != tag
               and self.stack[-1] in self.OMISSIBLE_CLOSE):
            self.stack.pop()
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
            return
        self.errors.append(f"mis-nested </{tag}> (open: <{self.stack[-1]}>)")


def check_deliverables(study, root: Path, problems):
    """Stage-4 deliverable gates: declaration at intake; existence + structure +
    no-overclaim at PASS (references/deliverables.md)."""
    d = study.get("deliverables") or {}
    if not isinstance(d, dict) or "paper" not in d:
        problems.append(
            "deliverables gate: study.json has no `deliverables` declaration "
            "(paper/slides/web). Record it at intake (see references/deliverables.md).")
        return
    slides_req = str(d.get("slides", "")).lower()
    web_req = str(d.get("web", "")).lower()
    if not slides_req.startswith("required") and not slides_req.startswith("not-required"):
        problems.append(
            f"deliverables gate: `slides` must be 'required' or 'not-required:<reason>', "
            f"got {d.get('slides')!r}")
    if web_req not in ("optional", "required"):
        problems.append(
            f"deliverables gate: `web` must be 'optional' or 'required', got {d.get('web')!r}")
    if not claiming_pass(study):
        return
    engine = find_tex_engine()
    if engine is None:
        problems.append(
            "PASS refused: no TeX engine found (searched PATH plus "
            "/Library/TeX/texbin, /opt/homebrew/bin, /usr/local/texlive/*/bin/*). "
            "Stage-4 artifacts must COMPILE before success is claimed; install "
            "tectonic or a TeX distribution, then re-run this validator.")
    paper = root / "artifacts" / "paper" / "main.tex"
    if not paper.exists() or paper.stat().st_size < 50:
        problems.append("PASS refused: artifacts/paper/main.tex missing or empty "
                        "(the stage-4 white paper is mandatory)")
    else:
        text = paper.read_text(errors="replace")
        if "\\documentclass" not in text:
            problems.append("PASS refused: artifacts/paper/main.tex has no \\documentclass")
        low = text.lower()
        missing = [s for s in PAPER_SECTIONS if s not in low]
        if missing:
            problems.append(f"PASS refused: paper missing required sections: {missing}")
        for ref in (study.get("slug", ""), study.get("task_id", "")):
            if ref and ref in text:
                break
        else:
            problems.append("PASS refused: paper does not reference the study slug/task_id")
        # no-overclaim: ASSERTIONS of formal verification (not disclaimers) must be
        # backed by a claim carrying that evidence level in the study record.
        assertion = re.sub(r"\bnot formally verified\b|nothing[^.]{0,80}formally verified|"
                           r"no lean formalization|not\s+[a-z ]{0,15}formally verified",
                           " ", low)
        if "formally verified" in assertion:
            try:
                blob = json.dumps(study) + (root / "registry.json").read_text(errors="replace")
            except OSError:
                blob = json.dumps(study)
            if "formally verified" not in blob.lower():
                problems.append(
                    "PASS refused: paper asserts 'formally verified' but no claim in "
                    "study.json / registry.json carries that evidence level "
                    "(no-overclaim rule)")
        bibs = bib_files_of(paper)
        if not bibs:
            problems.append(
                "PASS refused: paper has no \\bibliography{...} command "
                "(proper BibTeX references are mandatory)")
        else:
            missing_bib = [str(b) for b in bibs if not b.exists()]
            if missing_bib:
                problems.append(
                    "PASS refused: paper bibliography file(s) missing: "
                    f"{missing_bib}")
        if engine is not None:
            compile_tex_artifact(engine, paper, "artifacts/paper/main.tex", problems)
    if slides_req.startswith("required"):
        slides = root / "artifacts" / "slides" / "main.tex"
        if not slides.exists() or slides.stat().st_size < 50:
            problems.append("PASS refused: artifacts/slides/main.tex missing "
                            "(slides declared required)")
        else:
            t = slides.read_text(errors="replace")
            if "\\documentclass" not in t or "beamer" not in t.lower():
                problems.append("PASS refused: slides/main.tex is not a Beamer document")
            bibs = bib_files_of(slides)
            if not bibs:
                problems.append(
                    "PASS refused: slides have no \\bibliography{...} command "
                    "(proper BibTeX references are mandatory; may share the paper's refs.bib)")
            else:
                missing_bib = [str(b) for b in bibs if not b.exists()]
                if missing_bib:
                    problems.append(
                        "PASS refused: slides bibliography file(s) missing: "
                        f"{missing_bib}")
            if engine is not None:
                compile_tex_artifact(engine, slides, "artifacts/slides/main.tex", problems)
    if web_req == "required":
        web = root / "artifacts" / "web" / "index.html"
        if not web.exists() or web.stat().st_size < 50:
            problems.append("PASS refused: artifacts/web/index.html missing "
                            "(web declared required)")
        elif "<html" not in web.read_text(errors="replace").lower():
            problems.append("PASS refused: artifacts/web/index.html is not an HTML document")
        else:
            parser = _HTMLBalanceParser()
            try:
                parser.feed(web.read_text(errors="replace"))
                parser.close()
            except Exception as e:
                problems.append(f"PASS refused: artifacts/web/index.html does not parse: {e}")
            if parser.errors:
                problems.append(
                    "PASS refused: artifacts/web/index.html has malformed markup: "
                    + "; ".join(parser.errors[:5]))
            if not parser.stack or parser.stack[-1] != "html":
                problems.append(
                    "PASS refused: artifacts/web/index.html does not close its <html> tag")
            raw = web.read_text(errors="replace")
            if not (re.search(r'id\s*=\s*["\']references["\']', raw, re.IGNORECASE)
                    or re.search(r"<h[1-6][^>]*>\s*references", raw, re.IGNORECASE)):
                problems.append(
                    "PASS refused: artifacts/web/index.html has no references "
                    "section (id=\"references\" or a References heading)")
            for m in re.finditer(
                    r'<a\b[^>]*href\s*=\s*"https?://[^"]*"[^>]*>(.*?)</a>',
                    raw, re.IGNORECASE | re.DOTALL):
                txt = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                if not txt or re.match(r"https?://", txt):
                    problems.append(
                        "PASS refused: artifacts/web/index.html has an external "
                        "link without proper anchor text (bare URLs are not "
                        "references); label each link with author, title, year")
                    break


def check_registry(study, root: Path, problems):
    reg = root / "registry.json"
    if not reg.exists():
        problems.append("registry.json missing")
        return
    try:
        json.loads(reg.read_text())
    except json.JSONDecodeError as e:
        problems.append(f"registry.json invalid JSON: {e}")
        return
    status = str(study.get("status", ""))
    if "PASS" in status.upper() and "reopen" not in status.lower():
        raw = reg.read_text(errors="replace")
        if '"passed"' not in raw:
            problems.append(
                "PASS refused: registry.json has no route with status passed "
                "(a PASS requires an audit-referenced passed route)")


def check_declared_hashes(root: Path, problems):
    for p in sorted((root / "artifacts").glob("*.md")) + sorted((root / "audits").glob("*.md")):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"(?:sha-?256)\s*[:=]\s*([0-9a-fA-F]{64})", text):
            declared = m.group(1).lower()
            line = text[:m.start()].rsplit("\n", 1)[-1]
            candidates = re.findall(r"[\w./-]+\.(?:py|json|md|csv)", line)
            for c in candidates:
                fp = root / c
                if fp.exists() and sha256_hex(fp) == declared:
                    break
            else:
                if candidates:
                    problems.append(
                        f"{p.name}: declared sha256 {declared[:12]}... matches none "
                        f"of the referenced artifacts on its line")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", required=True, help="path to the study root")
    args = ap.parse_args()
    root = Path(args.study).resolve()
    sp = root / "study.json"
    if not sp.exists():
        print(f"ERROR: no study.json under {root}")
        return 2
    try:
        study = json.loads(sp.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: study.json invalid JSON: {e}")
        return 2
    problems = []
    subs = check_schema(study, problems)
    if subs is not None:
        check_coverage(study, subs, problems)
        check_deliverables(study, root, problems)
        check_pass_evidence(study, root, problems)
        check_registry(study, root, problems)
        check_declared_hashes(root, problems)
    if problems:
        print(f"FAIL -- {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    status = study.get("status", "")
    if "PASS" in str(status).upper():
        print(f"PASS -- state valid; declared status {status!r} has complete evidence.")
    else:
        print(f"OK -- state valid; status {status!r} (no PASS claimed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
