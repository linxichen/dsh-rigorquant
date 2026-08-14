# dsh-rigorquant

**English** | [简体中文](README.zh-CN.md)

Unattended-within-a-session, long-running **empirical/computational mathematics
research** for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
— economics, finance, portfolio construction/optimization, simulation,
computational econ/finance.

RigorQuant is an agent preset + bundled skill that turns one DSH session into a
context-isolated multi-agent research lab:

- **Parallel explorers** propose candidate methods (`subagent`, blank context).
- A **ground-truth track** re-derives the analytic closed forms, invariants, and
  bounds for simplified cases — twice, by different means (two independent
  `subagent_ground_truth` calls).
- An **adversary** eliminates routes by counterexample only.
- A **four-part check battery** (closed-form equality, exact invariants,
  analytic bounds, statistical hardening) runs BEFORE numerical implementation.
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

Two install forms:

**Bundle (skill layer)** — one command, makes the `rigorquant` skill available
to every session of a profile; the repo declares a `dsh.bundle` manifest so the
ecosystem's `dsh plugin add` path works:

```sh
dsh plugin --profile web add github:linxichen/dsh-rigorquant
```

**Preset (full framework)** — the RigorQuant agent preset (persona +
orchestration + tools) with the bundled skill:

```sh
git clone https://github.com/linxichen/dsh-rigorquant
cd dsh-rigorquant
./install.sh                    # installs the preset + skill + compute lane
# ./install.sh --skill-only     # or just the rigorquant skill, for any preset
```

Start a new DSH session and pick the **RigorQuant** preset. Then:

> rigorquant: derive and validate a method for [problem], simplified cases
> first, before any numerical implementation.

## Compute lane (one-time)

The pinned uv compute lane is installed at `$DSH_HOME/share/rigorquant/env` by
`install.sh` (see [env/README.md](env/README.md)). The jacobian escalation lane
ships **disabled** and **pinned** (`jacobian@0.12.0`): enable the `mcp-jacobian`
row, and the framework asks for approval before any one-time provisioning
(`npx -y jacobian@0.12.0 upgrade`, or the Lean toolchain via
`scripts/provision-lean.sh`). See [mcp/jacobian.md](mcp/jacobian.md).

## Repository layout

```
package.json                dsh.bundle manifest (dsh plugin add support)
cordis.patch.yml            bundle patch: registers the rigorquant skill
agent-presets/rigorquant/   preset composition + persona + bundled skill
env/                        pinned uv compute lane (sympy/cvxpy/hypothesis/…)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        grilled decision record + sources
studies/                    one study folder per task (Mode B; this checkout's
                            live studies — not shipped in the npm bundle)
```

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
