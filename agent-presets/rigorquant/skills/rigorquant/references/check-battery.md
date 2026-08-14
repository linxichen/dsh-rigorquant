# The four-part check battery

All four run on simplified/special cases BEFORE numerical implementation. The
battery is a **reference-case sanity gate**: it catches wrong implementations on
cases whose answer is known exactly, but passing it does **not** establish
general validity (see lifecycle.md "Validity stages"). Order: A and B first
(necessary), C alongside, D as staged hardening.

## Every check must be declared

Each check in an audit must state:

- an **independently computed expected value** (who derived it, by what means);
- the **failure condition** — the exact predicate that would make it fail;
- at least one **deliberately incorrect implementation or mutation** it detects
  (a check that passes an algebraically identical formula is not a check);
- its **producer and oracle provenance** (which agent produced it, which agent
  independently verified the target);
- whether **code paths or formulas are shared** with the method under test.

A check that cannot name its failure condition, or that detects no mutation, is
a tautology and must not be counted as evidence. The adversary audits the design
of the checks, not only their PASS/FAIL outputs.

## A — Closed-form equality (necessary)

Derive the EXACT analytic answer to the simplified case, then require agreement
under **deterministic** and **stochastic** methods separately — never one
blanket tolerance.

**Deterministic methods** — condition-aware tolerances, stated in the audit:

- Exact/symbolic: compare with `sympy` exactly where both sides are exact
  (rationals, closed forms); otherwise `mpmath` at 50 digits.
- Numeric: use an absolute and a relative tolerance chosen for the reference's
  scale — pure relative error is undefined when the reference is zero or very
  small. Never accept "looks similar" or log-scale plots as evidence.

**Stochastic methods** — agreement in standard-error / confidence-interval
units (e.g. within 3 SE of the analytic mean at 95% confidence), because a
finite-sample estimator cannot satisfy a universal `1e-12` relative gate. A
loosened tolerance must be justified in the audit and reconciled with the
`study.json` `tolerances` block (the checker rejects a mismatch).

## B — Exact invariants (necessary)

State every structural identity the method must satisfy and check it with
**exact** arithmetic: attribution terms sum EXACTLY to the total; weights sum
exactly to 1; symmetry under relabeling; nonnegativity where claimed;
dimensional consistency. A violation at any precision is a FAIL — invariants are
exact or they are wrong.

Keep symbolic equality and floating-point residuals distinct: an exact symbolic
identity is not the same claim as a numerical residual bound. Record which you
checked.

## C — Analytic bounds (necessary)

Derive a bound the output must respect (Cauchy-Schwarz, convexity,
nonnegativity, Jensen, duality). The method must never violate it, including
at adversarial parameter corners (degenerate covariance, zero weights, boundary
constraints). The adversary searches corners specifically.

## D — Statistical hardening (staged, after A–C pass)

1. **Seeded reproducibility:** identical seed + identical inputs → identical (or
   near-identical, recorded) output. Record the full environment (Python
   version, OS/arch, BLAS/device backend, JAX precision flags) — bit-identical
   replay is **not** portable across platforms, BLAS, devices, or
   nondeterministic kernels, so the claim is "seeded, environment-pinned",
   never universal bit-identity. Note `jax_enable_x64` is `False` in the
   shipped lane, so JAX calculations cannot meet `1e-12` expectations.
2. **Property-based falsification:** `hypothesis` strategies over inputs;
   invariants from B must hold across generated cases.
3. **LLN convergence (stochastic methods):** fix the seed; for N in a grid
   (e.g. 1e3, 1e4, 1e5), estimate the convergence rate of the sampling error
   against the analytic mean (~ C/√N) and report the table. LLN does **not**
   require a single fixed-seed error sequence to decrease monotonically, so do
   not assert monotonicity; estimate the rate and a confidence band instead.
   Report bias separately — "non-shrinking error = bias or a broken sampler" is
   too strong; run an explicit bias test, do not infer it from the curve.
4. **Distributional agreement (when the exact law is derivable):**
   Kolmogorov-Smirnov / chi-square against the analytic law over several
   low-dimensional projections. A single non-rejection does not establish
   distributional agreement — report the projections and p-values, and treat
   agreement as evidence, not proof.

**Multiplicity control:** when a gate tests many cells (e.g. a per-cell
acceptance band across ~128 cells), apply a multiplicity correction (e.g. Holm)
or a family-wise bound, and state it in the spec. A per-cell band with no
correction is a design bug, not a tolerance to loosen downstream.

## Empirical-finance gates (mandatory for econ/finance/portfolio studies)

A mathematically correct method can still produce an invalid backtest. For any
study claiming empirical or financial validity, also check:

- **Temporal splits** — train/test separated in time, not random shuffling.
- **Look-ahead and target leakage** — no future information in features/labels.
- **Survivorship and selection bias** — the universe reflects what was knowable
  at each point in time.
- **Multiple-hypothesis / data-snooping** — adjust for the number of tried
  variants (e.g. deflated Sharpe, or a held-out confirmation set).
- **Transaction costs and turnover** — net-of-cost performance, not gross.
- **Nonstationarity and regime sensitivity** — stability across sub-periods and
  regimes.
- **Dependence-aware uncertainty** — account for serial/tail dependence.
- **MCMC mixing** — report effective sample size and mixing diagnostics, not
  raw chain length.

## Pass standard

A, B, C all pass (with recorded tolerances), D1 mandatory, D2–D4 run to the
extent the sub-problem admits; the empirical gates pass when they apply. The
audit file records, for each check: its declaration (above), the statement
checked, tolerance, seed, exact numbers, PASS/FAIL, the two independent
ground-truth derivations that supplied the targets, and the hashes of the
generating script, inputs, code, and environment manifest. A summary that does
not match its referenced artifacts is rejected.
