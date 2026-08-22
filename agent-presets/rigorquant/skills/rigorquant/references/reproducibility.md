# Reproducibility is the record; junk is derived state

*Core philosophy of the rigorquant plugin. Hard-won from the
20260820 var-expected-return-term run (docs/hard-lessons-from-the-var-expected-return-run.md,
L13–L14): the study tree ended at ~729 MB of venvs and caches, its deliverables
promised "reproduction" through gitignored scratch paths, and a fresh clone had
zero working reproduction commands. The two obligations below are enforced by
`rq_check.py` at PASS time.*

## The philosophy, in two obligations

1. **Perfect reproducibility.** The committed study record is self-contained: a
   fresh clone of the repo, plus the pinned uv lane, regenerates every piece of
   study evidence. Every command a deliverable prints, and every path the
   record cites (`study.json`, `registry.json`, audits), resolves to a file
   that is part of the committed record — never to scratch.
2. **Minimal junk.** Nothing disposable sits on the committed surface. Derived
   state — virtualenvs, package caches, bytecode, OS metadata — is never
   committed and never left behind at close-out; scratch lives only under
   `interim/`, which is gitignored by construction.

The two obligations are one discipline: **cleanup and reproducibility are the
same pass.** You cannot delete what the record cites, and you cannot cite what
is not tracked. Doing both together is the close-out sweep (below); the
validator turns it from an intention into a gate.

## Why

- **The record is the source of truth.** Evidence that cannot be reproduced
  from the committed tree is not evidence; it is a local memory. A command
  that works in the author's checkout but not from a clone *documents a file*,
  it does not *reproduce a study*.
- **Derived state is not the record.** A venv is recreated deterministically
  from the pinned lane's `pyproject.toml` + `uv.lock` via
  `uv sync --frozen` (or `uv run --frozen`). Keeping it costs ~0.5 GB of noise
  that hides the study and imports megabytes of unverifiable state into a
  record whose whole point is verifiability. The lockfile is the guarantee;
  the venv is the residue.
- **A clone is the only honest auditor.** Hash statements in audits, verdict
  records, and reproduction commands are only checkable if the files they name
  travel with the record.

## Operational rules

- **R1 — `interim/` is the only scratch home.** Scratch, working files, and
  lane caches (`UV_CACHE_DIR`, `UV_PROJECT_ENVIRONMENT` pointed inside
  `interim/`) belong under `interim/` and are never committed. Everything else
  in the study is committed.
- **R2 — Derived state is disposable.** Virtualenvs and uv caches are
  gitignored, never committed, and deleted at study close. They are rebuilt
  from the pinned lane with `uv sync --frozen` / `uv run --frozen`.
- **R3 — Study-generating code is tracked in `code/`.** Every script that
  generates evidence (ground-truth tracks, battery generators, reproduction
  scripts the deliverables print) lives in a tracked `code/` directory, with a
  `code/README.md` mapping each script to what it produces. Copies are
  byte-identical (`cmp`) to any file whose hash an audit records, so hash
  statements stay valid of the tracked copy.
- **R4 — Deliverables never cite scratch files.** Audience-facing documents
  (paper, slides) never reference a file under `interim/` as if it were
  record; reproduction commands print tracked paths only. Pointing uv's
  cache/environment at the designated scratch home
  (`export UV_CACHE_DIR="$PWD/interim/tmp/uv-cache"`) is expected and
  tolerated — the validator distinguishes *file citations* into scratch
  (flagged) from *scratch-home assignments* (tolerated).
- **R5 — Record-cited files live in tracked directories.** Anything the record
  cites (`registry.json` outputs, `study.json` notes, audit reports) resolves
  from the study root. A record-cited file found living under gitignored
  `interim/` is relocated to `audits/` (or `literature/`, `code/`) and every
  citation updated.
- **R6 — Cleanup and reproducibility are the same pass (close-out sweep).**
  In order: (1) grep deliverables and the record for every referenced path;
  (2) move study-generating scripts into tracked `code/`; (3) relocate
  record-cited files out of `interim/` and update every citation; (4) delete
  only what the record never cites; (5) re-run `rq_check` — the validator's
  registry-outputs-exist, scratch-refs, repro-paths, and junk checks are the
  reproduction gate.
- **R7 — Prove it after every cleanup.** After any cleanup (venv removal,
  cache purge, tmp sweep), re-run one pinned script and the validator before
  claiming the pre-cleanup state.

## Junk taxonomy (what the validator refuses at PASS)

On the committed surface (study root excluding `interim/` and `.git`), the
validator refuses PASS while any of these is present:

| junk | why |
|---|---|
| `venv` / `.venv` / `.rigorquant-venv` | derived environment, rebuilt by `uv sync --frozen` |
| `uv-cache` / `.uv-cache` | package cache, rebuilt by uv |
| `__pycache__/`, `*.pyc` | bytecode, regenerated on import |
| `.DS_Store` | OS metadata, regenerated by Finder |

Tolerated: LaTeX build intermediates (`*.aux`, `*.log`, `*.out`, `*.toc`,
`*.nav`, `*.snm`, `*.vrb`, `*.fls`, `*.fdb_latexmk`, `*.synctex.gz`, `*.bbl`,
`*.blg`, `*.bcf`, `*.run.xml`) — light, gitignored, and necessarily present
after a compile the validator itself performs. And `interim/` itself is exempt
by definition: it is the one designated scratch home, gitignored at intake.

## The validator as gate

| check | enforces | fires when |
|---|---|---|
| `evidence.junk` | R2, minimal junk | derived state sits on the committed surface at PASS |
| `deliverables.scratch-refs` | R4 | a deliverable's `.tex` cites a file under `interim/` (scratch-home env assignments tolerated) |
| `deliverables.repro-paths` | R3, R5 | a deliverable cites a `code/|derivations/|audits/|literature/` path that does not exist on disk |
| registry outputs must exist | R5 | a registry route cites an output that does not exist on disk |

A green validator for these checks means "nothing is missing and nothing is
scratch"; it never means "the mathematics is right" — that remains the job of
the check battery and the audit track.
