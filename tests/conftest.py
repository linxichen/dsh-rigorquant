"""Fixtures for the rq_check meta-validator tests.

The suite is built around one *golden* study: a small but genuinely complete
record that must PASS. Every negative test starts from the golden study and
removes or corrupts exactly one thing, so each test names the single defect the
validator has to catch.

The golden study is deliberately a finance study (minimum-variance portfolio
weights), not the convex-sampling study the framework was first exercised on —
a domain-general framework must be able to certify a domain-general example.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
# RQ_CHECK_BIN lets the suite be pointed at another build of the validator, which
# is how a new gate is shown to fail against the version that lacked it.
SKILL_DIR = REPO / "agent-presets/rigorquant/skills/rigorquant"
RQ_CHECK = Path(os.environ.get("RQ_CHECK_BIN", SKILL_DIR / "scripts/rq_check.py"))

# ── composition parsing (shared by the deny-list and tool-budget tests) ─────
#
# The test venv carries no yaml module and the composition embeds `!!js`
# runtime expressions, so rows are extracted structurally-by-convention rather
# than parsed: a row is one 4-space `    - id: ` block, `toolName:` its
# delegation tool, and `deny:` the row's first deny flow sequence. One copy
# lives here so the deny-list tests and the tool-budget tests cannot drift
# into two different parsers of the same file.

CORDIS = REPO / "agent-presets/rigorquant/agent.cordis.yml"

# Every delegation tool name a MOUNTED delegation row provides, plus web/skill
# for the blind lane. A new delegation row whose toolName is absent here
# silently re-opens Decision 14's C2 for every previously blind child.
# (`subagent_fork`, `workflow`, and `ralph` are NOT here: their rows are
# disabled outright — untagged, unscopeable children — so they are neither
# mounted nor deniable; tools.restrict throws on unmounted names.)
BLIND_TOOLS = {
    "web_search", "web_fetch", "skill",
    "subagent_explorer", "subagent_double_checker", "subagent_adversary",
    "subagent_offgrid", "subagent_lit_line", "subagent_lit_adversary",
    "subagent_document_adversary",
}
DELEGATION = BLIND_TOOLS - {"web_search", "web_fetch", "skill"}

# Tools only the root orchestrator may touch. Children get them mounted by the
# shared composition, so each role's deny list must name them explicitly.
# (Workflow/ralph are absent: their rows are disabled outright — see
# BLIND_TOOLS above.)
ORCHESTRATOR_TOOLS = {
    "send_message", "interrupt_agent", "list_agents",   # child-control
    "create_goal", "update_goal", "get_goal",           # Decision 10: one task-level goal
    "todo_write",                                       # Decision 10
    "ask_user_question",                                # unattended contract
    "exit_plan_mode",                                   # children are never in plan mode
}


def composition_rows(text):
    """Yield (row_id, body) for every 4-space-indented composition row."""
    for part in re.split(r"\n    - id: ", text)[1:]:
        row_id = part.split("\n", 1)[0].strip()
        yield row_id, part


def tool_name_of(body):
    m = re.search(r"toolName:\s*(\S+)", body)
    return m.group(1) if m else None


def deny_of(body):
    m = re.search(r"deny:\s*\[([^\]]*)\]", body)
    if not m:
        return set()
    return {t.strip() for t in m.group(1).split(",") if t.strip()}

PAPER_TEX = r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\title{Minimum-variance weights: 20260815\_minvar-demo}
\maketitle

This paper is written for a working quantitative researcher.

\section{Notation}
$\Sigma$ denotes the asset covariance matrix, assumed symmetric positive
definite. $\mathbf{1}$ is the vector of ones. $w$ denotes a vector of portfolio
weights summing to one.

\section{Statement}
Derive and certify the minimum-variance weights for a covariance matrix
$\Sigma$ under a full-investment constraint.

\section{Method}
$w^\star = \Sigma^{-1}\mathbf{1} / (\mathbf{1}^\top \Sigma^{-1} \mathbf{1})$,
solved by one Cholesky factorization at cost $O(n^3)$.

\section{Validity}
Claim G1 (evidence level: independently re-derived): for symmetric positive
definite $\Sigma$ the stationary point of the Lagrangian is the unique
minimizer. Two independent derivations agree \cite{markowitz1952}.

\section{Certification}
Gate A closed-form equality at 50 digits, gate B the exact budget invariant
$\mathbf{1}^\top w = 1$, gate C the variance lower bound, gate D a seeded
N-grid. See the battery results file.

\section{Limitations}
The claim is conditional on $\Sigma$ being nonsingular; no formal Lean proof
was produced, so nothing here is formally verified.

\section{Reproduction}
Seeds and the pinned-lane command are recorded in the battery results.

\bibliographystyle{plain}
\bibliography{refs}
\end{document}
"""

REFS_BIB = """@article{markowitz1952,
  author  = {Markowitz, Harry},
  title   = {Portfolio Selection},
  journal = {The Journal of Finance},
  volume  = {7},
  number  = {1},
  pages   = {77--91},
  year    = {1952},
  doi     = {10.2307/2975974}
}
"""

BATTERY_RESULTS = """# Battery results -- 20260815_minvar-demo

Run seed: task_seed 20260815; per-run seed = task_seed + run_index.

## Gate A -- closed-form equality
Expected value derived independently by the ground-truth track
(derivations/gt-a-symbolic.md and derivations/gt-b-bruteforce.md).
Failure condition: |w_hat - w_star|_inf > 1e-40 at 50 digits.
Mutation detected: transposing the inverse covariance flips the weights and is
caught by this gate.

## Gate D -- statistical hardening
N in {1e3, 1e4, 1e5}; sampling error against the analytic mean shrinks at the
estimated rate C/sqrt(N).
Failure condition: the fitted rate exponent falls outside [-0.6, -0.4].
Mutation detected: reusing one draw across the grid holds the error flat.

Tolerances used: deterministic abs 1e-40, rel 1e-30; stochastic se_units 3,
confidence 0.95 -- matching study.json.
"""

DOC_ADVERSARY = """# Document adversary -- paper

Read artifacts/paper/main.tex against deliverables.audience.paper.
Notation block defines Sigma, 1 and w. Evidence levels match validity_stages.

VERDICT: PASS
"""


def golden_study(root: Path) -> Path:
    """Write a complete, honest study that must PASS. Returns the study root."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "derivations").mkdir(exist_ok=True)
    (root / "audits").mkdir(exist_ok=True)
    (root / "artifacts" / "paper").mkdir(parents=True, exist_ok=True)

    study = {
        "slug": "20260815_minvar-demo",
        "title": "Minimum-variance portfolio weights",
        "mode": "repo-root",
        "repo_root": str(root),
        "env_lane": "/opt/dsh/share/rigorquant/env",
        "task_id": "20260815_minvar-demo",
        "created": "2026-08-15",
        "statement": "Derive and certify minimum-variance weights under a full-investment constraint.",
        "broad_criterion": "The method returns the true minimum-variance weights for any symmetric positive definite covariance matrix.",
        "success_criterion": "Broad criterion plus stage-3 general claim and stage-5 domain-scale evidence.",
        "subproblems": [
            {
                "id": "SP1",
                "name": "two-asset reference case",
                "status": "known",
                "stage": "reference-case",
                "success_criterion": "closed-form agreement at 50 digits",
            },
            {
                "id": "SP2",
                "name": "general n-asset claim",
                "status": "known",
                "stage": "generalization",
                "success_criterion": "the broad criterion, with all hypotheses stated",
                "evidence_level": "independently re-derived",
            },
            {
                "id": "SP3",
                "name": "non-diagonal high-condition instance",
                "status": "novel",
                "stage": "domain-scale",
                "success_criterion": "full battery on a dense ill-conditioned covariance",
            },
        ],
        "validity_stages": {
            "stage3_general_claim": {
                "claim": "For symmetric positive definite Sigma the closed form is the unique minimizer.",
                "evidence_level": "independently re-derived",
                "outputs": ["derivations/gt-a-symbolic.md", "derivations/gt-b-bruteforce.md"],
            },
            "stage5_domain_scale": {
                "instance": "dense convex-quadratic covariance with condition number 1e6",
                "outputs": ["audits/battery-results.md"],
            },
        },
        "deliverables": {
            "paper": "required",
            "slides": "not-required:library deliverable, no talk planned",
            "web": "optional",
            "consultation_pending": False,
            "audience": {
                "paper": {
                    "role": "quantitative researcher",
                    "level": "graduate",
                    "sentence": "This paper is written for a working quantitative researcher.",
                    "assume_known": ["linear algebra"],
                    "must_define": [],
                    "avoid": [],
                    "depth": "proof sketches",
                    "format": "article",
                }
            },
        },
        "simplified_cases": ["two assets with diagonal covariance"],
        "seeds": {"task_seed": 20260815, "convention": "per-run seed = task_seed + run_index"},
        "tolerances": {
            "deterministic": {"abs": 1e-40, "rel": 1e-30},
            "stochastic": {"se_units": 3, "confidence": 0.95, "lln_grid": [1000, 10000, 100000]},
        },
        "budget": {"max_orchestrator_rounds": 5, "max_cost_usd": None, "max_wall_minutes": None},
        "status": "PASS",
    }
    (root / "study.json").write_text(json.dumps(study, indent=2) + "\n")

    registry = {
        "task": "20260815_minvar-demo",
        "rounds": 2,
        "subproblems": {
            "SP1": {
                "status": "passed",
                "evidence_level": "independently re-derived",
                "families": [
                    {
                        "familyId": "lagrangian-stationarity",
                        "idea": "Solve the equality-constrained quadratic program in closed form.",
                        "routes": [
                            {
                                "routeId": "cholesky-closed-form",
                                "status": "passed",
                                "outputs": ["audits/battery-results.md"],
                            }
                        ],
                    }
                ],
            },
            "SP2": {
                "status": "passed",
                "evidence_level": "independently re-derived",
                "families": [
                    {
                        "familyId": "lagrangian-stationarity",
                        "idea": "Lift the closed form to n assets.",
                        "routes": [
                            {
                                "routeId": "general-spd",
                                "status": "passed",
                                "outputs": ["derivations/gt-a-symbolic.md"],
                            }
                        ],
                    }
                ],
            },
            "SP3": {
                "status": "passed",
                "families": [
                    {
                        "familyId": "lagrangian-stationarity",
                        "idea": "Stress the closed form on an ill-conditioned dense instance.",
                        "routes": [
                            {
                                "routeId": "dense-illconditioned",
                                "status": "passed",
                                "outputs": ["audits/battery-results.md"],
                            }
                        ],
                    }
                ],
            },
        },
    }
    (root / "registry.json").write_text(json.dumps(registry, indent=2) + "\n")

    (root / "derivations" / "gt-a-symbolic.md").write_text(
        "# Ground truth A (symbolic)\n\nLagrangian stationarity gives "
        "w = Sigma^{-1} 1 / (1' Sigma^{-1} 1).\n"
    )
    (root / "derivations" / "gt-b-bruteforce.md").write_text(
        "# Ground truth B (brute force)\n\nGrid search over the simplex reproduces "
        "the same weights to 50 digits.\n"
    )
    (root / "audits" / "battery-results.md").write_text(BATTERY_RESULTS)
    (root / "audits" / "document-adversary-paper.md").write_text(DOC_ADVERSARY)
    (root / "artifacts" / "paper" / "main.tex").write_text(PAPER_TEX)
    (root / "artifacts" / "paper" / "refs.bib").write_text(REFS_BIB)
    return root


def run_check(study_root: Path, *extra):
    """Run the validator; return (exit_code, combined output).

    Under RQ_COVERAGE=1 the child runs through `coverage run --parallel`
    instead of the bare interpreter: the validator is only ever a subprocess
    here, so this is the one place its execution can be measured. Each run
    drops a .coverage.* file for `coverage combine` (see .coveragerc and the
    pre-commit hook).
    """
    command = [sys.executable]
    if os.environ.get("RQ_COVERAGE") == "1":
        command += ["-m", "coverage", "run", "--rcfile",
                    str(REPO / ".coveragerc"), "--parallel-mode"]
    command += [str(RQ_CHECK), "--study", str(study_root), *extra]
    cp = subprocess.run(command, capture_output=True, text=True)
    return cp.returncode, cp.stdout + cp.stderr


def read_study(root: Path) -> dict:
    return json.loads((root / "study.json").read_text())


def write_study(root: Path, study: dict) -> None:
    (root / "study.json").write_text(json.dumps(study, indent=2) + "\n")


@pytest.fixture
def study(tmp_path):
    """A complete, honest study that must PASS."""
    return golden_study(tmp_path / "study")


@pytest.fixture
def tex_available():
    if shutil.which("pdflatex") or shutil.which("tectonic") or Path("/Library/TeX/texbin/pdflatex").exists():
        return True
    pytest.skip("no TeX engine available")
