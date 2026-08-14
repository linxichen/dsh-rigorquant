# RigorQuant compute lane

The pinned uv environment every rigorquant subagent executes against. One
environment, two duties:

- **Exact lane:** `sympy` (symbolic closed forms, exact invariants), `mpmath`
  (50-digit ground-truth checks for Gate A).
- **Numeric/statistical lane:** `numpy`/`scipy` (methods), `cvxpy` + Clarabel/SCS
  (convex optimization, constrained multi-objective), `jax` (sampling/simulation),
  `pytest` + `hypothesis` (Gate D property-based falsification).

## Setup

```sh
uv sync --frozen --project env
```

The lockfile `env/uv.lock` is committed (reproducibility is Gate D). Subagents
run code through this lane:

```sh
uv run --frozen --project <path-to-this-env> python script.py
```

## Rules

- Never `pip install` into the ambient interpreter; the lane is the contract.
- Record the seed of every stochastic run in `study.json` (at the study root).
- Python ≥ 3.12 (aligns with the jacobian escalation lane's runtime).

## Reproducing a result

"Same lane, same lockfile, same seed" is not enough. A reproduction manifest
must record:

- repository commit and code hash;
- input-data hashes and any transformations;
- the exact Python version;
- operating system and architecture;
- BLAS and device backend;
- solver, status, tolerances, residuals, and thread settings;
- JAX precision (`jax_enable_x64`) and determinism configuration;
- every random stream, including Hypothesis.

Use `uv sync --frozen` / `uv run --frozen` so the pinned lockfile is honored.
Either pin a supported Python range and backend, or replace any "bit-identical"
claim with a documented numerical-tolerance guarantee.
