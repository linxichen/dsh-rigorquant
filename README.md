# dsh-rigorquant

**English** | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="docs/figs/edgesworth-box.png" alt="Edgeworth box with contract curve and Pareto optimum" width="52%">
  <img src="docs/figs/utility-maximization.png" alt="Utility maximization: convex indifference curves against a convex budget set" width="44%">
</p>
<p align="center">
  <img src="docs/figs/binomial-tree.png" alt="Three-step binomial option pricing tree with backward-induction values" width="80%">
</p>
<p align="center"><sub>
  <a href="docs/figs/edgesworth-box.png">Edgeworth box</a> &middot;
  <a href="docs/figs/utility-maximization.png">utility maximization</a> &middot;
  <a href="docs/figs/binomial-tree.png">binomial option pricing</a> — hand-drawn in
  <a href="https://en.wikibooks.org/wiki/LaTeX/PGF/TikZ">TikZ</a>, no AI-generated imagery
</sub></p>

Unattended-within-a-session, long-running **empirical/computational mathematics
research** for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
— economics, finance, portfolio construction/optimization, simulation,
computational econ/finance.

RigorQuant is an agent preset + bundled skills that turns one DSH session into a
context-isolated multi-agent research lab:

- **J-Space** is used integrally across the root persona, every subagent role,
  and plan mode as the inference-time cognitive-control layer (workspace gate,
  ledger, seam refresh, dense inner / clean outer registers).
- **Parallel explorers** propose candidate methods (`subagent`, blank context).
- A **ground-truth track** re-derives the analytic closed forms, invariants, and
  bounds for simplified cases — twice, by different means (two independent
  `subagent_ground_truth` calls).
- An **adversary** eliminates routes by counterexample only.
- A **four-part check battery** (closed-form equality, exact invariants,
  analytic bounds, statistical hardening) runs BEFORE numerical implementation.
- **A meta-validator** (`rq_check.py`) refuses a PASS whose evidence is missing:
  empty stage outputs, an empty `derivations/`, a registry with no
  audit-referenced passed route, or deliverables that do not compile. Its
  evidence checks read the audit record, not `study.json` — a study may not
  vouch for itself.
- **Fixed-seed + LLN** conventions for stochastic work.
- A **jacobian MCP escalation lane** (opt-in; Lean as a manual external lane)
  settles proof-critical claims before implementation.
- **PASS → auto-implement and proceed; BLOCKED → 3 rounds of the same gap →
  strongest derivation + exact gap; BUDGET → 5 rounds → checkpoint + report.**

The operating pattern adapts Shanmu Jin's Crouzeix-conjecture run
([prompt](https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt),
[Lean audit](https://github.com/jinshanmu/CrouzeixConjecture/tree/main/Lean))
and Terence Tao's blueprint/equational-theories projects to numerical work.
Full design record: [docs/architecture.md](docs/architecture.md).

**"Unattended", precisely:** the framework runs unattended within one live
session. Crossing a session boundary disarms the goal; one human turn
("continue") re-arms it. It does not continue autonomously across restarts.

## Install

Requires DSH ≥ 0.1.0-rc.7.

**One line, everything** — the preset, the compute lane, and the plugin (role
model router + its Settings card):

```sh
npx dsh-rigorquant
# npx dsh-rigorquant --profile tui     # a profile other than web
```

**From a clone** — the same install, from your own working tree. A checkout
installs itself into the profile, so re-run this after editing `dsh/` to
refresh the plugin:

```sh
git clone https://github.com/linxichen/dsh-rigorquant
cd dsh-rigorquant
./install.sh
# ./install.sh --skill-only     # only the skills, for any preset, no plugin
# ./install.sh --uninstall      # removes everything, plugin included
```

**Plugin only** — the router, its card, and the skills, with no preset and no
compute lane. Useful to add role routing to a profile you drive with your own
preset; note that the `root` role routes only sessions running the
`rigorquant` preset, so this form alone leaves the router with nothing to
route:

```sh
dsh plugin --profile web add dsh-rigorquant
```

Start a new DSH session and pick the **RigorQuant** preset. Then:

> rigorquant: derive and validate a method for [problem], simplified cases
> first, before any numerical implementation.

## Compute lane (one-time)

The pinned uv compute lane is installed at `$DSH_HOME/share/rigorquant/env` by
`install.sh` (see [env/README.md](env/README.md)). The jacobian escalation lane
ships **disabled** and **pinned** (`jacobian@0.12.0`): enable the `mcp-jacobian`
row, and the framework asks for approval before any one-time provisioning
(`npx -y jacobian@0.12.0 upgrade`, or the Lean toolchain via the skill's
`scripts/provision-lean.sh`). See [mcp/jacobian.md](mcp/jacobian.md).

## Role-routed models (rq-model-router)

The bundled plugin routes each RigorQuant role to its own model + reasoning
effort, with one fallback per role. Configure it in **Settings → Plugins →
RigorQuant model routing**: the last saved selection persists (settings user
layer). Shipped defaults:

| Role | Primary | Fallback |
| --- | --- | --- |
| Ground-truth oracle | `deepseek-v4-pro` @ high | `deepseek-v4-flash` @ high |
| Adversary | `deepseek-v4-pro` @ high | `deepseek-v4-flash` @ high |
| Root, explorers, literature roles | inherit (root follows the chatbox picker) | — |

On a terminal primary failure (no adapter / HTTP 4xx) the role degrades to its
fallback for one forced retry, and recovers on the next success or after 10
minutes. Untagged agents (other presets, workflow workers, forks) are never
touched. Requires DSH ≥ 0.1.0-rc.7 (self-registered plugin settings). Design
record: [docs/architecture.md](docs/architecture.md) Decision 16.

## Repository layout

```
package.json                dsh.bundle manifest (dsh plugin add support)
cordis.patch.yml            bundle patch: skills layer + rq-model-router row
dsh/                        rq-model-router plugin (host half + Plugins-tab card)
agent-presets/rigorquant/   preset composition + persona + bundled skills
  skills/rigorquant/        SKILL.md + references/ + scripts/ + schemas/
  .../scripts/rq_check.py   the meta-validator (single canonical copy)
  .../schemas/              study.json + registry.json JSON Schemas, which the
                            validator loads — so schema and checker cannot drift
  skills/j-space/           J-Space cognition suite (SKILL.md + modules/ + references/ + scripts/)
env/                        pinned uv compute lane (sympy/cvxpy/hypothesis/…)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        grilled decision record + sources
tests/                      the validator's test suite (see Testing below)
studies/                    one study folder per task (Mode B; a checkout's own
                            live studies — not shipped in the npm bundle)
```

## Testing

The validator has a test suite, and its centrepiece is a *forged* study — empty
derivations, empty stage outputs, a one-line adversary report, and a paper whose
body reads "This paper says nothing." It must FAIL. A framework whose honesty
gate is not itself tested is a framework that certifies whatever it is handed.

```sh
uv sync --frozen --project env
uv run --frozen --project env python -m pytest tests/ -q
```

`tests/test_repo_consistency.py` covers the other half: one validator, one
schema, documented commands that resolve, and layout blocks that match the
filesystem. That is the defect class this repository actually produces.

**What a green validator means:** nothing declared is missing, and the
deliverables build. It does not mean the mathematics is right — that stays with
the check battery, the independent ground-truth track, and the adversary.

## Studies

A **study** is one self-contained rigorquant task with an identical folder
structure everywhere: durable deliverables at the study root (`study.json`,
`STUDY.md`, `registry.json`, `journal.md`, `derivations/`, `audits/`,
`artifacts/`) are meant to be committed; all scratch lives in a gitignored
`interim/`. Two modes, implied by location:

- **One study per repo** — `study.json` at the repo root.
- **Multiple studies per repo** — `studies/<slug>/study.json`; the roster is
  `studies/*/study.json`.

Intake detects an existing study and continues it silently; a new study asks
one question (mode + slug) and never asks again. See
[docs/architecture.md](docs/architecture.md) §12.

## Publishing

This repo is a community DSH plugin distribution (bundle + preset + skill
form): it declares a `dsh.bundle` manifest in `package.json`, is tagged
[`dsh-plugin`](https://github.com/topics/dsh-plugin), and is discoverable by
the ecosystem's topic-based indexes — see
[dsh-find-plugins](https://github.com/Nagi-ovo/dsh-find-plugins) and the
[awesome-deepseek-harness](https://github.com/0xsline/awesome-deepseek-harness)
list for the conventions.

MIT License.
