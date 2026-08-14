#!/usr/bin/env python3
"""rq_check — the RigorQuant meta-validator.

Validates a study's state files, checks evidence completeness, audits check
falsifiability, rejects missing N-grids, hashes the inputs, and refuses PASS
when mandatory evidence is absent.

Standard library only, so it runs inside or outside the pinned compute lane:

    python3 scripts/rq_check.py --study <study-root>
    python3 scripts/rq_check.py --study <study-root> --out report.json

Exit code: 0 = all required checks pass; 1 = a required check failed;
2 = usage/load error.
"""

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import uuid

EVIDENCE_LEVELS = {
    "falsification-surviving",
    "independently re-derived",
    "certificate-checked",
    "formally verified",
}
SUB_STATUSES = {"active", "blocked", "passed", "dead", "unknown"}
ROUTE_STATUSES = {"active", "blocked", "dead", "passed"}
MODES = {"repo-root", "multi-study"}
SUB_KIND = {"known", "novel"}
FAILURE_MARKERS = ("failure condition", "fails if", "would fail", "fail when", "make it fail")


def _pass(check_id, name, detail=""):
    return {"id": check_id, "name": name, "status": "pass", "detail": detail}


def _fail(check_id, name, detail=""):
    return {"id": check_id, "name": name, "status": "fail", "detail": detail}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def env_manifest():
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "uname": platform.uname()._asdict(),
    }


def validate_study(d):
    """Structural validation mirroring schemas/study.schema.json."""
    errs = []
    if not isinstance(d, dict):
        return ["study.json must be a JSON object"]
    required = [
        "slug", "title", "mode", "repo_root", "statement", "success_criterion",
        "subproblems", "simplified_cases", "seeds", "tolerances", "budget", "status",
    ]
    for k in required:
        if k not in d:
            errs.append("missing required field: " + k)
    for k in ("slug", "title", "repo_root", "statement", "success_criterion", "status"):
        if k in d and not isinstance(d[k], str):
            errs.append("%s must be a string" % k)
    if "slug" in d and isinstance(d["slug"], str):
        slug_ok = bool(d["slug"]) and d["slug"][0].isalnum() and all(c.isalnum() or c == "-" for c in d["slug"])
        if not slug_ok:
            errs.append("slug must match [a-z0-9][a-z0-9-]*")
    if "mode" in d and d["mode"] not in MODES:
        errs.append("mode must be one of " + repr(sorted(MODES)))
    if "env_lane" in d and d["env_lane"] is not None:
        lane = d["env_lane"]
        if not isinstance(lane, str):
            errs.append("env_lane must be a string")
        elif not (os.path.isabs(lane) or lane.startswith("$DSH_HOME")):
            errs.append("env_lane must be an absolute path or the $DSH_HOME anchor")
    if "subproblems" in d:
        if not isinstance(d["subproblems"], list) or not d["subproblems"]:
            errs.append("subproblems must be a non-empty array")
        else:
            seen = set()
            for i, sp in enumerate(d["subproblems"]):
                if not isinstance(sp, dict):
                    errs.append("subproblems[%d] must be an object" % i)
                    continue
                for k in ("id", "name", "status", "success_criterion"):
                    if k not in sp:
                        errs.append("subproblems[%d] missing %s" % (i, k))
                if "id" in sp:
                    if not isinstance(sp["id"], str):
                        errs.append("subproblems[%d].id must be a string" % i)
                    elif sp["id"] in seen:
                        errs.append("duplicate subproblem id: " + sp["id"])
                    else:
                        seen.add(sp["id"])
                if "status" in sp and sp["status"] not in SUB_KIND:
                    errs.append("subproblems[%d].status must be known|novel" % i)
                if "evidence_level" in sp and sp["evidence_level"] not in EVIDENCE_LEVELS:
                    errs.append("subproblems[%d].evidence_level invalid" % i)
    if "seeds" in d:
        if not isinstance(d["seeds"], dict) or "task_seed" not in d["seeds"] or not isinstance(d["seeds"].get("task_seed"), int):
            errs.append("seeds.task_seed must be an integer")
    if "tolerances" in d:
        t = d["tolerances"]
        if not isinstance(t, dict) or "deterministic" not in t or "stochastic" not in t:
            errs.append("tolerances must contain deterministic and stochastic blocks")
        else:
            sto = t.get("stochastic", {})
            if isinstance(sto, dict) and "lln_grid" in sto:
                grid = sto["lln_grid"]
                if not isinstance(grid, list) or not grid:
                    errs.append("tolerances.stochastic.lln_grid must be a non-empty array")
            if isinstance(sto, dict) and "confidence" in sto:
                c = sto["confidence"]
                if not isinstance(c, (int, float)) or not (0 < c < 1):
                    errs.append("tolerances.stochastic.confidence must be in (0, 1)")
    return errs


def validate_registry(d, study):
    """Structural validation mirroring schemas/registry.schema.json."""
    errs = []
    if not isinstance(d, dict):
        return ["registry.json must be a JSON object"]
    for k in ("task", "rounds", "subproblems"):
        if k not in d:
            errs.append("missing required field: " + k)
    if "rounds" in d and (not isinstance(d["rounds"], int) or d["rounds"] < 0):
        errs.append("rounds must be a non-negative integer")
    if "subproblems" in d:
        if not isinstance(d["subproblems"], dict):
            errs.append("subproblems must be an object keyed by SPn")
        else:
            for key, sp in d["subproblems"].items():
                if not isinstance(sp, dict):
                    errs.append("subproblems.%s must be an object" % key)
                    continue
                if "status" in sp and sp["status"] not in SUB_STATUSES:
                    errs.append("subproblems.%s.status invalid" % key)
                if "evidence_level" in sp and sp["evidence_level"] not in EVIDENCE_LEVELS:
                    errs.append("subproblems.%s.evidence_level invalid" % key)
                if "blockedRounds" in sp and (not isinstance(sp["blockedRounds"], int) or sp["blockedRounds"] < 0):
                    errs.append("subproblems.%s.blockedRounds must be a non-negative integer" % key)
                if "families" in sp:
                    if not isinstance(sp["families"], list):
                        errs.append("subproblems.%s.families must be an array" % key)
                    else:
                        for i, fam in enumerate(sp["families"]):
                            if not isinstance(fam, dict):
                                errs.append("subproblems.%s.families[%d] must be an object" % (key, i))
                                continue
                            for k in ("familyId", "idea", "routes"):
                                if k not in fam:
                                    errs.append("subproblems.%s.families[%d] missing %s" % (key, i, k))
                            if "routes" in fam and isinstance(fam["routes"], list):
                                for j, rt in enumerate(fam["routes"]):
                                    if isinstance(rt, dict) and "status" in rt and rt["status"] not in ROUTE_STATUSES:
                                        errs.append("subproblems.%s.families[%d].routes[%d].status invalid" % (key, i, j))
            sp_ids = {sp["id"] for sp in study.get("subproblems", []) if isinstance(sp, dict) and "id" in sp}
            if sp_ids and set(d["subproblems"].keys()) != sp_ids:
                errs.append("registry.json subproblems keys do not match study.json subproblems ids")
    return errs


def dir_has_files(root, name):
    p = os.path.join(root, name)
    if not os.path.isdir(p):
        return False, "missing directory: " + name
    entries = [e for e in os.listdir(p) if not e.startswith(".")]
    if not entries:
        return False, "empty directory: " + name
    return True, ""


def audit_falsifiability(root):
    """Scan audit files for a declared failure condition."""
    audits = os.path.join(root, "audits")
    if not os.path.isdir(audits):
        return False, "missing audits/ directory"
    files = [f for f in os.listdir(audits) if f.endswith((".md", ".txt", ".json"))]
    if not files:
        return False, "no audit files found"
    declared = []
    for f in files:
        try:
            text = open(os.path.join(audits, f), encoding="utf-8").read().lower()
        except OSError:
            continue
        if any(m in text for m in FAILURE_MARKERS):
            declared.append(f)
    if not declared:
        return False, "no audit file declares a failure condition (checks are not falsifiable)"
    return True, "failure condition declared in: " + ", ".join(declared)


def run(study_root):
    checks = []
    study_root = os.path.abspath(study_root)
    study_path = os.path.join(study_root, "study.json")
    registry_path = os.path.join(study_root, "registry.json")

    # Load inputs.
    load_errors = []
    if not os.path.isfile(study_path):
        load_errors.append("study.json not found at " + study_path)
        study = {}
    else:
        try:
            study = json.load(open(study_path, encoding="utf-8"))
        except (ValueError, OSError) as e:
            load_errors.append("study.json is not valid JSON: " + str(e))
            study = {}
    if not os.path.isfile(registry_path):
        load_errors.append("registry.json not found at " + registry_path)
        registry = {}
    else:
        try:
            registry = json.load(open(registry_path, encoding="utf-8"))
        except (ValueError, OSError) as e:
            load_errors.append("registry.json is not valid JSON: " + str(e))
            registry = {}
    if load_errors:
        for e in load_errors:
            checks.append(_fail("load", "input files", e))

    # Schema checks.
    study_errs = validate_study(study)
    checks.append(_pass("study.schema", "study.json structure") if not study_errs
                  else _fail("study.schema", "study.json structure", "; ".join(study_errs)))
    reg_errs = validate_registry(registry, study)
    checks.append(_pass("registry.schema", "registry.json structure") if not reg_errs
                  else _fail("registry.schema", "registry.json structure", "; ".join(reg_errs)))

    # Evidence completeness.
    for d in ("derivations", "audits"):
        ok_dir, detail = dir_has_files(study_root, d)
        checks.append(_pass("evidence." + d, "evidence completeness: " + d) if ok_dir
                      else _fail("evidence." + d, "evidence completeness: " + d, detail))

    # Falsifiability.
    fals_ok, fals_detail = audit_falsifiability(study_root)
    checks.append(_pass("falsifiability", "checks declare a failure condition") if fals_ok
                  else _fail("falsifiability", "checks declare a failure condition", fals_detail))

    # N-grid presence.
    grid = ((study.get("tolerances") or {}).get("stochastic") or {}).get("lln_grid")
    if isinstance(grid, list) and grid:
        checks.append(_pass("lln-grid", "stochastic N-grid present", "grid=" + repr(grid)))
    else:
        checks.append(_fail("lln-grid", "stochastic N-grid present", "tolerances.stochastic.lln_grid missing or empty"))

    # Refuse PASS when mandatory evidence is absent.
    reg_sub = registry.get("subproblems", {})
    passed = [k for k, sp in reg_sub.items() if isinstance(sp, dict) and sp.get("status") == "passed"]
    if passed:
        art_ok, art_detail = dir_has_files(study_root, "artifacts")
        if art_ok:
            checks.append(_pass("pass-evidence", "PASS sub-problems have artifacts", "passed=" + ", ".join(passed)))
        else:
            checks.append(_fail("pass-evidence", "PASS sub-problems have artifacts",
                                "sub-problems marked passed (%s) but %s" % (", ".join(passed), art_detail)))
    else:
        checks.append(_pass("pass-evidence", "PASS sub-problems have artifacts", "no sub-problem marked passed"))

    # Hashes.
    hashes = {}
    if os.path.isfile(study_path):
        hashes["study.json"] = sha256_file(study_path)
    if os.path.isfile(registry_path):
        hashes["registry.json"] = sha256_file(registry_path)

    result = "pass" if all(c["status"] == "pass" for c in checks) else "fail"
    report = {
        "schema": "rq-check-report",
        "version": 1,
        "study_root": study_root,
        "run": {
            "id": time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8],
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "result": result,
        "checks": checks,
        "hashes": hashes,
        "environment": env_manifest(),
    }
    return report, result


def main(argv):
    ap = argparse.ArgumentParser(description="RigorQuant meta-validator")
    ap.add_argument("--study", required=True, help="path to the study root (contains study.json)")
    ap.add_argument("--out", help="write the report to this file instead of stdout")
    args = ap.parse_args(argv)
    report, result = run(args.study)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("wrote report to", args.out)
    else:
        print(text)
    return 0 if result == "pass" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
