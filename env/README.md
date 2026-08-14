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
uv sync --project env
```

This creates `env/uv.lock` (commit it — reproducibility is Gate D). Subagents
run code through this lane:

```sh
uv run --project <path-to-this-env> python script.py
```

## Rules

- Never `pip install` into the ambient interpreter; the lane is the contract.
- Record the seed of every stochastic run in `.rigorquant/task.json`.
- Reproduce = same lane, same lockfile, same seed.
- Python ≥ 3.12 (aligns with the jacobian escalation lane's runtime).
