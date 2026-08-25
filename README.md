# dsh-rigorquant

**English** | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="docs/figs/edgesworth-box.png" alt="Edgeworth box with contract curve and Pareto optimum" width="70%">

</p>
<p align="center"><sub>
  <a href="docs/figs/edgesworth-box.png">Edgeworth box</a> — hand-drawn in
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

## The research team — and how it works

Six roles, each a separate tool with its own powers and limits. The separation is
enforced by the composition, so **the producer never checks its own work** — an idea
dies only on a concrete counterexample, never on style or vibes.

<img src="docs/figs/avatar-orchestrator.png" align="left" width="200" alt="Orchestrator">

**Orchestrator** · `root persona` — fans out the work, synthesizes, and writes the state. Bound by four rules: producer ≠ checker, counterexample-only elimination, seeds always recorded, no handwaved load-bearing claims.

<br clear="left">


<img src="docs/figs/avatar-explorer.png" align="left" width="200" alt="Explorer">

**Explorer** · `subagent` — blank-context and divergent. Proposes lemmas, equations, constructions, and candidate methods with exact statements. Status reports are rejected.

<br clear="left">


<img src="docs/figs/avatar-oracle.png" align="left" width="200" alt="Oracle">

**Oracle** · `subagent_ground_truth` — blind (no web, no skills, no delegation, no drafts). Re-derives the load-bearing claims from first principles, twice by different means.

<br clear="left">


<img src="docs/figs/avatar-adversary.png" align="left" width="200" alt="Adversary">

**Adversary** · `subagent_adversary` — runs the check group and hunts counterexamples. Ends in a verdict: `PASS` or `NEEDS-EDITS`.

<br clear="left">


<img src="docs/figs/avatar-literature.png" align="left" width="200" alt="Literature">

**Literature** · `subagent_lit_line` · `_adversary` — a walled citation-graph sweep, then an independent adversary re-retrieves each claim and certifies it's real **and** current.

<br clear="left">


<img src="docs/figs/avatar-validator.png" align="left" width="200" alt="Validator">

**Validator** · `rq_check.py` + schemas — refuses a `PASS` with missing evidence. Reads the audit record, never the study's own claims — a study cannot vouch for itself.

<br clear="left">

### The team, live — the activity view

<img src="docs/figs/agent-team-hero.svg" width="70%" alt="RigorQuant live team graph — captain, oracle, adversary, validator, and the five-move task chain">

<p align="center">
  <img src="docs/figs/agent-team-activity.svg" width="52%" alt="RigorQuant agent team activity view — team summary, segmented progress, member roster, and task dependency graph">
</p>

Reworked from the live activity panel of
[dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) — the picture
in [its README](https://github.com/NanmiCoder/dsh-agent-teams/blob/main/assets/ui.png)
— here showing RigorQuant's own six roles at a fan-out moment: the captain
splits and dispatches, the explorers and the literature lane are working, and
the oracle / adversary / validator are queued on their gates. The panel SVG is
generated from [`docs/figs/agent-team-activity.js`](docs/figs/agent-team-activity.js).

> **Attribution.** The activity-panel design is adapted from
> [dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) by
> [NanmiCoder](https://github.com/NanmiCoder) (程序员阿江 / Relakkes) —
> Copyright (c) 2026, MIT License. The role portraits are this repo's own
> `docs/figs/` assets. The header banner is likewise reworked from the
> upstream hero graphic.

**The loop, in five moves.** Each round is fan-out → ground truth → adversary → synthesize.

1. **Promise** — record the original question verbatim, split it into sub-problems with crisp criteria, pick hand-checkable simplified cases, and pin seeds, tolerances and the schema/validator digests.
2. **Fan out** — blank-context explorers and literature lines run in parallel; most are never told the favored approach.
3. **Ground-truth it** — blind oracles re-derive the load-bearing claims without seeing anyone's draft; two independent derivations for anything the study rests on.
4. **Attack it** — the adversary runs the four-gate battery, then hunts counterexamples; divergent tracks are lined up as an adjudication docket.
5. **Certify & ship** — the validator checks nothing is missing; the paper and slides are assembled from validated records, never written fresh.

**The check battery**, run before any numerical implementation: **A** closed-form equality · **B** exact invariants · **C** analytic bounds · **D** statistical hardening (fixed seed + LLN shrinking ≈ C/√N).

**With receipts:** in one hard run, 21 errors were caught by a specific mechanism and none by luck (11 of them the orchestrator's own); only 35% of 81 literature claims survived independent verification; and the honesty gate is itself tested — a forged study *must* fail.

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

**Plugin only** — the same everything, via the ecosystem's bundle path. The
package declares a `dsh.bundle` manifest whose rows include a boot-sync half
(`rq-preset-sync`): on the profile's next start it lands the agent preset into
`$DSH_HOME/.agent-presets/rigorquant` and the compute lane into
`$DSH_HOME/share/rigorquant/`, so `dsh plugin add` alone yields a working
distribution (docs/architecture.md Decision 23):

```sh
dsh plugin --profile web add dsh-rigorquant
```

The sync is idempotent (a byte-identical tree is left untouched; derived state
like `.venv` is never copied or pruned) and keeps same-version local edits to
the installed preset — an upgrade replaces shipped files, exactly like
re-running `./install.sh`. There is no uninstall hook in DSH's plugin CLI, so
removal stays explicit (`./install.sh --uninstall`); if you remove only the
plugin, the synced preset keeps working standalone and simply routes nothing.

Start a new DSH session and pick the **RigorQuant** preset. Then:

> rigorquant: derive and validate a method for [problem], simplified cases
> first, before any numerical implementation.

## Compute lane (one-time)

The pinned uv lane lives at `$DSH_HOME/share/rigorquant/env`, placed there by
`install.sh` or by the plugin's boot-sync row — whichever ran last owns the
anchor, and both land identical bytes (see [env/README.md](env/README.md)).
The venv itself is **never installed**: it is derived state, provisioned
lazily inside the anchor by the first `uv run --frozen --project <env_lane>`
(subsequent runs are instant; `--frozen` honors the committed lockfile). The
jacobian escalation lane ships **disabled** and **pinned** (`jacobian@0.12.0`):
enable the `mcp-jacobian` row, and the framework asks for approval before any
one-time provisioning (`npx -y jacobian@0.12.0 upgrade`, or the Lean toolchain
via the skill's `scripts/provision-lean.sh`). See [mcp/jacobian.md](mcp/jacobian.md).

## Role-routed models (rq-model-router)

The bundled plugin routes each RigorQuant role to its own model + reasoning
effort, with one fallback per role. Configure it in **Settings → Plugins →
RigorQuant model routing**: the last saved selection persists (settings user
layer). Shipped defaults:

| Role | Primary | Fallback |
| --- | --- | --- |
| Ground-truth oracle | `deepseek-v4-pro` @ high | `deepseek-v4-flash` @ low |
| Adversary | `deepseek-v4-pro` @ high | `deepseek-v4-flash` @ low |
| Root, explorers, literature roles | inherit (root follows the chatbox picker) | — |

On a terminal primary failure (no adapter / HTTP 4xx) the role degrades to its
fallback for one forced retry, and recovers on the next success or after 10
minutes. Untagged agents (other presets, workflow workers, forks) are never
touched. Requires DSH ≥ 0.1.0-rc.7 (self-registered plugin settings). Design
record: [docs/architecture.md](docs/architecture.md) Decision 16.

## Repository layout

```
package.json                dsh.bundle manifest (dsh plugin add support)
cordis.patch.yml            bundle patch: skills layer + rq-model-router +
                            rq-preset-sync rows
dsh/                        host halves (rq-model-router router + rq-preset-sync
                            boot-sync) and the Plugins-tab card
agent-presets/rigorquant/   preset composition + persona + bundled skills
  skills/rigorquant/        SKILL.md + references/ + scripts/ + schemas/
  .../scripts/rq_check.py   the meta-validator (single canonical copy)
  .../schemas/              study.json + registry.json JSON Schemas, which the
                            validator loads — so schema and checker cannot drift
env/                        pinned uv compute lane (sympy/cvxpy/hypothesis/…)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        grilled decision record + sources
docs/figs/agent-team-activity.svg  generated live activity-view panel
docs/figs/agent-team-hero.svg       team-graph banner, reworked from the
                             dsh-agent-teams hero graphic (see credit below)
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
