# RigorQuant compute lane

The pinned uv environment every rigorquant study executes against. One
environment, two duties:

- **Exact lane:** `sympy` (symbolic closed forms, exact invariants), `mpmath`
  (50-digit ground-truth checks for Gate A).
- **Numeric/statistical lane:** `numpy`/`scipy` (methods), `cvxpy` + Clarabel/SCS
  (convex optimization, constrained multi-objective), `jax` (sampling/simulation),
  `pytest` + `hypothesis` (Gate D property-based falsification).

## A template, copied into each study

This directory is a **template**. `install.sh` and the plugin's boot sync
place it at `$DSH_HOME/share/rigorquant/env`; nothing runs against that copy.
At intake (SKILL.md Step 2) a study copies `pyproject.toml` and `uv.lock`
into its own `env/` and commits them, so a clone of the study can rebuild the
exact environment even after a later release replaces this template. The venv
and the uv cache are scratch under the study's `interim/`. From the study
root:

```sh
UV_PROJECT_ENVIRONMENT="$PWD/interim/venv" UV_CACHE_DIR="$PWD/interim/uv-cache" uv sync --frozen --project env
UV_PROJECT_ENVIRONMENT="$PWD/interim/venv" UV_CACHE_DIR="$PWD/interim/uv-cache" uv run --frozen --offline --project env python script.py
```

A study that needs another package adds it to its own lane
(`uv add --project env <package>`); the template stays as shipped. The
validator refuses a PASS without the study's `env/uv.lock` (`evidence.lane`).

This repository's own test suite runs against this directory directly
(`uv sync --frozen --project env`); the lockfile `env/uv.lock` is committed
(reproducibility is Gate D).

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
