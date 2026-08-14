# The four-part check battery

All four run on simplified/special cases BEFORE numerical implementation.
Order: A and B first (necessary), C alongside, D as staged hardening.

## A — Closed-form equality (necessary)

Derive the EXACT analytic answer to the simplified case. Run the method and
require agreement:

- Exact lane: when both sides are exact (rationals, closed forms), compare
  with `sympy`/`mpmath` exactly or at 50-digit precision; required agreement
  is bit-exact or ≤ 1e-30 relative.
- Numeric lane: relative error ≤ 1e-12; a loosened 1e-9 tolerance must be
  justified in the audit report and recorded.
- Never accept "looks similar" or log-scale plots as evidence.

## B — Exact invariants (necessary)

State every structural identity the method must satisfy and check it with
exact arithmetic: attribution terms sum EXACTLY to the total; weights sum
exactly to 1; symmetry under relabeling; nonnegativity where claimed;
dimensional consistency. A violation at 1e-30 is a FAIL — invariants are
exact or they are wrong.

## C — Analytic bounds (necessary)

Derive a bound the output must respect (Cauchy-Schwarz, convexity,
nonnegativity, Jensen, duality). The method must never violate it, including
at adversarial parameter corners (degenerate covariance, zero weights,
boundary constraints). The adversary searches corners specifically.

## D — Statistical hardening (staged, after A–C pass)

1. **Seeded reproducibility:** identical seed + identical inputs → bit-identical
   (or near-bit-identical, recorded) output.
2. **Property-based falsification:** `hypothesis` strategies over inputs;
   invariants from B must hold across generated cases.
3. **LLN convergence (stochastic methods):** fix the seed; for N in a grid
   (e.g. 1e3, 1e4, 1e5), the sampling error against the analytic mean must
   shrink (≈ C/√N). Report the error table in the audit. Non-shrinking error
   = bias or a broken sampler.
4. **Distributional agreement (when the exact law is derivable):**
   Kolmogorov-Smirnov / chi-square against the analytic law for a low-
   dimensional projection.

## Pass standard

A, B, C all pass (with recorded tolerances), D1 mandatory, D2–D4 run to the
extent the sub-problem admits. The audit file records: statement checked,
tolerance, seed, exact numbers, PASS/FAIL, and the two independent ground-
truth derivations that supplied the targets.
