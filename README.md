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

- **Parallel explorers** propose candidate methods (`explorer-<n>`, blank
  context).
- An **OffGridThinker** (`offgrid-<n>`) works off the grid when a route
  must be isolated: raw model intelligence plus compute tools (sympy, numpy,
  mpmath, Lean checkers) — no web, no literature, no other agents' results.
- A **ground-truth track** re-derives the analytic closed forms, invariants, and
  bounds for simplified cases — twice, by different means (two independent
  fresh `doublechecker-<n>` teammates).
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

Eight roles around one hub, each a teammate the orchestrator creates with its
own persona and tool budget. The orchestrator is the only role that sees every
report — a teammate cannot message another teammate, list the roster, or read
the whole board — so the separation is enforced rather than agreed, and **the
producer never checks its own work**: an idea dies only on a concrete
counterexample, never on style or vibes.

<img src="docs/figs/avatar-orchestrator.png" align="left" width="200" alt="Orchestrator">

**Orchestrator** · `root persona` — fans out the work, synthesizes, and writes the state. Bound by four rules: producer ≠ checker, counterexample-only elimination, seeds always recorded, no handwaved load-bearing claims.

<br clear="left">


<img src="docs/figs/avatar-explorer.png" align="left" width="200" alt="Explorer">

**Explorer** · `explorer-<n>` — blank-context and divergent. Proposes lemmas, equations, constructions, and candidate methods with exact statements. Status reports are rejected.

<br clear="left">


<img src="docs/figs/avatar-offgrid.png" align="left" width="200" alt="OffGridThinker">

**OffGridThinker** · `offgrid-<n>` — the off-grid lane. Raw model intelligence plus the pinned compute lane (sympy, numpy, mpmath, cvxpy, hypothesis, jax; Lean checkers when provisioned) — and nothing else: no web, no skills, no delegation, no other agents' results. Its own agent, not an Explorer variant: isolation is the identity.

<br clear="left">


<img src="docs/figs/avatar-doublechecker.png" align="left" width="200" alt="DoubleChecker">

**DoubleChecker** · `doublechecker-<n>` — blind (no web, no skills, no delegation, no drafts). Re-derives the load-bearing claims from first principles, twice by different means.

<br clear="left">


<img src="docs/figs/avatar-adversary.png" align="left" width="200" alt="Adversary">

**Adversary** · `adversary-<n>` — runs the check group and hunts counterexamples. Ends in a verdict: `PASS` or `NEEDS-EDITS`.

<br clear="left">


<img src="docs/figs/avatar-literature.png" align="left" width="200" alt="Literature">

**Literature** · `lit-line-<n>` · `lit-adversary-<n>` — a walled citation-graph sweep, then an independent adversary re-retrieves each claim and certifies it's real **and** current.

<br clear="left">


<img src="docs/figs/avatar-validator.png" align="left" width="200" alt="Validator">

**Validator** · `rq_check.py` + schemas — refuses a `PASS` with missing evidence. Reads the audit record, never the study's own claims — a study cannot vouch for itself.

<br clear="left">


<img src="docs/figs/avatar-document-adversary.png" align="left" width="200" alt="Document adversary">

**Document adversary** · `doc-adversary-<n>` — an independent agent that audits each finished deliverable for **self-completeness** (the thing 90% of AI-generated writing drops): every jargon term, symbol, and abbreviation the document uses must be defined in the artifact itself or the audience spec's symbol registry. Returns `VERDICT: PASS` / `VERDICT: NEEDS-EDITS`; a `NEEDS-EDITS` is a blocking gap the validator refuses a `PASS` without.

<br clear="left">

### The team, live — the native team view

A study runs on the harness's own Agent Teams surface, so there is no custom
panel to learn: while a RigorQuant session runs, the session header's team
action opens the **roster** (name, role, status) and the round's **task board**
with its blocking edges — the two things to watch. The roster's model column
shows the member's model selection, not the model `rq-model-router` routes
its requests to (Decision 16), so read a role's route off the **Plugins →
dsh-rigorquant** card, never off the roster. Each teammate is a row there:
**open one** and its own conversation opens, so you can read a derivation or
an audit while it runs (steering it is the ordinary conversation, and it
breaks that teammate's blank context — documented, not prevented).

The topology is **hub-and-spoke**, and the guards enforce it rather than
asking: a teammate's message reaches the orchestrator or nowhere, a teammate
cannot list the roster or the whole board, and it may read or update only a
task no other teammate owns (the one its brief names, which it claims). The
figure below is that topology — the orchestrator at the hub, the roles it
creates as spokes, the round's tasks beneath them:

<p align="center">
  <img src="docs/figs/agent-team-activity.svg" width="52%" alt="RigorQuant agent team topology — hub-and-spoke roles over the round's task dependency graph">
</p>

The figure is the reader-safe rendering of that view, generated from
[`docs/figs/agent-team-activity.js`](docs/figs/agent-team-activity.js) — the
live roster and board are visible only in a running web session. It is adapted
from the activity panel of
[dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) — the picture
in
[its README](https://github.com/NanmiCoder/dsh-agent-teams/blob/main/assets/ui.png)
— showing RigorQuant's own eight roles at a fan-out moment.

> **Attribution.** The figure adapts the activity-panel design of
> [dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) by
> [NanmiCoder](https://github.com/NanmiCoder) (程序员阿江 / Relakkes) —
> Copyright (c) 2026, MIT License. The role portraits are this repo's own
> `docs/figs/` assets. The hero banner (`docs/figs/agent-team-hero.svg`) is
> likewise reworked from the upstream hero graphic.

**The loop, in five moves.** Each round is fan-out → ground truth → adversary → synthesize.

1. **Promise** — record the original question verbatim, split it into sub-problems with crisp criteria, pick hand-checkable simplified cases, and pin seeds, tolerances and the schema/validator digests.
2. **Fan out** — blank-context explorers and literature lines run in parallel; most are never told the favored approach.
3. **Ground-truth it** — the blind DoubleChecker re-derives the load-bearing claims without seeing anyone's draft; two independent derivations for anything the study rests on.
4. **Attack it** — the adversary runs the four-gate battery, then hunts counterexamples; divergent tracks are lined up as an adjudication docket.
5. **Certify & ship** — the validator checks nothing is missing; the paper and slides are assembled from validated records, never written fresh.

**The check battery**, run before any numerical implementation: **A** closed-form equality · **B** exact invariants · **C** analytic bounds · **D** statistical hardening (fixed seed + LLN shrinking ≈ C/√N).

**With receipts:** in one hard run, 21 errors were caught by a specific mechanism and none by luck (11 of them the orchestrator's own); only 35% of 81 literature claims survived independent verification; and the honesty gate is itself tested — a forged study *must* fail.

## Install

Requires DSH `>=0.1.7-rc.2 <0.1.8` (Decision 25,
`docs/adr/0002-declared-preset-on-dsh-0.1.7.md`). The preset is a declared
`@deepseek-ai/dsh-agent-preset` row, the routes are the router row's own
profile config, and the card edits them through the Plugins page's config
forms; none of that exists on an older harness, and the installer refuses one.
**0.5.0 is the last release for the 0.1.6 alpha harness**: nothing is
backported, so stay on 0.5.0 if you cannot move the harness yet.

That range is a prerelease and the team layer is experimental: this release
runs team-only on the **Agent Teams** bundle the harness ships as a **Beta**
card, *Agent Teams* under **Plugins → Official**. Turn it on there yourself,
or let a full install do it for you (below).

**Upgrading from 0.5.0** is one cutover, done before the first 0.1.7 boot.
First finish or archive the RigorQuant studies in progress: resuming a session
started on the 0.1.6 harness is not promised. Then:

1. Stop dsh (every running process, the web app included).
2. Install the harness pinned to the release this range was tested on:

   ```sh
   npm i -g @deepseek-ai/dsh@0.1.7-rc.2   # or @deepseek-ai/dsh@next
   ```

   Never an unqualified `npm i -g`: npm `latest` is still `0.1.5-rc.3`.
3. Run `./install.sh` (or `npx dsh-rigorquant`) before starting dsh. It
   carries your saved routes and a saved RigorQuant default over from the old
   `settings.yaml`. If dsh already booted once, re-running it recovers them
   from `settings.yaml.imported`.
4. Start the web app and pick **RigorQuant** in the new-session picker. If
   the picker is missing, switch **Coding Tools** back on in General
   Settings: it is the picker's only gate, on by default, and off only if you
   or Desktop onboarding switched it off.

Fan-out is bounded by the host: eight live children per root
(`maxActiveSubagents`, **Plugins → Subagent**). A literature-heavy study that
wants four lines running beside its explorers can raise it there.

A full install turns on that **Beta** bundle, the Plugins page's *Agent
Teams* card under **Official**, when the target profile does not have it,
pinned to the core's own version (a profile that lists it at some other
version is re-pinned; a bundle you enabled without a recorded version is left
alone). It always removes the separate *Agent Teams Web UI* bundle a 0.5.0
profile has, saying so in one line: DSH 0.1.7 folded that panel into the one
bundle and publishes no web bundle for this core, and if the removal fails
the install stops. It raises the team service's lifetime member cap to 64
through a marked `dsh-rigorquant` block it appends to the profile's user
patch (`$DSH_HOME/profiles/<profile>/cordis.patch.yml`), printing every line
it writes. Re-running changes nothing once installed; `--uninstall` removes
the marked block and disables the bundle only if that block records the
installer having turned it on, leaving a bundle you enabled yourself
untouched. With no `dsh` on the path this step is skipped with a warning,
same as the rest of the install, and the Beta card on the Plugins page is
then yours to toggle (docs/adr/0001-rigorquant-on-agent-teams.md).

**One line, everything**: the compute lane and the plugin (the declared
preset, the role model router and its card on the Plugins page):

```sh
npx dsh-rigorquant
# npx dsh-rigorquant --profile tui     # a profile other than web
```

**From a clone**: the same install, from your own working tree. A checkout
installs itself into the profile, so re-run this after editing `dsh/` to
refresh the plugin:

```sh
git clone https://github.com/linxichen/dsh-rigorquant
cd dsh-rigorquant
./install.sh
# ./install.sh --skill-only     # only the skills, for any preset, no plugin
# ./install.sh --uninstall      # removes everything, plugin included
```

**Plugin only**: the same everything, via the ecosystem's bundle path. The
package declares a `dsh.bundle` manifest that declares the `rigorquant` preset
itself, and one of its rows is a boot-sync half (`rq-lane-sync`): on the
profile's next start it lands the compute lane into
`$DSH_HOME/share/rigorquant/`, so `dsh plugin add` alone yields a working
distribution (docs/architecture.md Decisions 22 and 25). This path neither
enables Agent Teams nor carries saved routes over; the installer does both:

```sh
dsh --version                 # must be >= 0.1.7-rc.2 and < 0.1.8
dsh plugin --profile web add dsh-rigorquant
```

The sync is idempotent (a byte-identical tree is left untouched; derived state
like `.venv` is never copied or pruned). It also removes the directory preset
that releases before 0.6.0 copied under `$DSH_HOME`, but only when that
copy's `.rq-sync.json` says this package put it there. There is no uninstall
hook in DSH's plugin CLI, so removal of the lane stays explicit
(`./install.sh --uninstall`).

Start a new DSH session and pick the **RigorQuant** preset. Then:

> rigorquant: derive and validate a method for [problem], simplified cases
> first, before any numerical implementation.

## Deployment notes

Four harness facts a research deployment should decide on. None of them is
RigorQuant's own machinery, and installing RigorQuant changes none of them:

- **The DeepSeek session log is on by default.** The base bundle mounts
  `session-log-deepseek` with `enabled: true`: each session's canonical event
  log goes up as request metadata to the official DeepSeek API — no model-input
  tokens, but the whole run leaves the machine. To turn it off, overlay the row
  in the profile's user patch
  (`$DSH_HOME/profiles/<profile>/cordis.patch.yml`) and restart the profile —
  changes land at the next start:

  ```yaml
  - id: session-log-deepseek
    config:
      enabled: false
  ```

- **The goal-round driver is the harness's, and it is already mounted.** The
  goal service and `goal-round-driver` are host-plane rows of the shipped base
  bundle (`@deepseek-ai/dsh-base`); the preset re-mounts only the human
  `/goal` command and the model-facing goal tool, which the web bundle
  disables at the host plane. Nothing in this repo ships, mounts or arms the
  round driver: "unattended" is a native contract, and crossing a session
  boundary still disarms the goal until one human turn re-arms it (Decision
  10).

- **The workspace-changes card is the human-visible witness of an edit.** The
  web bundle's `workspace-changes` row records each top-level turn's changed
  files from git working-tree snapshots and renders the changed-files card
  under that turn, so an edit that lands after a verdict is visible exactly
  where and when it happened — what the frozen-write rule of Decision 19 needs
  a human to be able to see. Certification itself reads the study record,
  never the session (`docs/architecture.md` Decision 19).

- **Scheduled tasks are neither used nor guarded.** DSH 0.1.7 ships
  scheduled tasks (and their time context) disabled. RigorQuant does not use
  them, and its per-call guards do not cover them: a scheduled task you
  enable yourself runs outside the team's hub-and-spoke rules.

## Compute lane (one-time)

The pinned uv lane lives at `$DSH_HOME/share/rigorquant/env`, placed there by
`install.sh` or by the plugin's boot-sync row — whichever ran last owns the
anchor, and both land identical bytes (see [env/README.md](env/README.md)).
The venv itself is **never installed**: it is derived state, provisioned
lazily inside the anchor by the first `uv run --frozen --project <env_lane>`
(subsequent runs are instant; `--frozen` honors the committed lockfile). The
jacobian escalation lane is **pinned** (`jacobian@0.12.0`) and is no preset
row: it mounts at runtime. When a claim needs it, the orchestrator calls
`rq_escalate` without asking, into itself or into a teammate it names, and
the jacobian tools appear from the next request until the session ends. The
framework still asks for approval before any one-time provisioning
(`npx -y jacobian@0.12.0 upgrade`, or the Lean toolchain via the skill's
`scripts/provision-lean.sh`). See [mcp/jacobian.md](mcp/jacobian.md).

## Role-routed models (rq-model-router)

The bundled plugin gives each RigorQuant role a model + reasoning-effort
policy, with one fallback per role. Role identity comes from the teammate's
Team membership name (`<role>-<n>`; the Lead is the orchestrator) — the
router carries the shipped tier matrix itself (DoubleChecker and adversary
default to `deepseek-v4-pro` @ `high`) and overlays a saved route on top.
Configure routes in **Plugins → dsh-rigorquant** (the bundle's own page,
under its description): only Save writes, a saved route is the router row's
own config in the profile's `cordis.patch.yml` and applies from the next
request, and leaving the page drops staged edits. Shipped defaults:

| Role | Primary | Fallback |
| --- | --- | --- |
| DoubleChecker | `deepseek-v4-pro` @ high | `deepseek-flash` @ low |
| Adversary | `deepseek-v4-pro` @ high | `deepseek-flash` @ low |
| Root, explorers, OffGridThinker, literature/document roles | inherit (root follows the chatbox picker) | — |

On a terminal primary failure (no adapter / HTTP 4xx, including the official
quota response `1308` / “Usage limit reached”) the role degrades to its
fallback for one forced retry, and recovers on the next success or after 10
minutes. An agent outside a RigorQuant team (another preset, or with no Team
membership at all) is never touched.

**Signed in with a DeepSeek account only?** DSH 0.1.7 splits DeepSeek into
`deepseek-official` (API key) and `deepseek-account` (account sign-in). When
the official route is not routable (no API key) and the account route is, the
shipped defaults above move to the same model ids on `deepseek-account`, and
those requests are billed to your account quota, not to an API key. A route
you saved yourself is never moved. Design record:
[docs/architecture.md](docs/architecture.md) Decisions 16 and 25.

## Repository layout

```
package.json                dsh.bundle manifest (dsh plugin add support)
cordis.patch.yml            bundle patch: skill layer + rq-model-router +
                            rq-team + rq-lane-sync rows
dsh/                        host halves (role router, team composition and
                            per-call guard, boot-sync) + one persona file per
                            role, and the web client bundle (routing card)
agent-presets/
  rigorquant.patch.yml      the declared `rigorquant` preset (persona + child rows)
  rigorquant/skills/        bundled skills
    rigorquant/             SKILL.md + references/ + scripts/ + schemas/
  .../scripts/rq_check.py   the meta-validator (single canonical copy)
  .../schemas/              study.json + registry.json JSON Schemas, which the
                            validator loads — so schema and checker cannot drift
env/                        pinned uv compute lane (sympy/cvxpy/hypothesis/…)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        grilled decision record + sources
docs/figs/agent-team-activity.svg  reader-safe hub-and-spoke topology figure
docs/figs/agent-team-activity.js   its generator (freshness-pinned in tests)
docs/figs/agent-team-hero.svg       hero banner, reworked from the
                             dsh-agent-teams hero graphic (see the credit above)
tests/                      the validator's test suite (see Testing below)
studies/                    one folder per study (Mode B; a checkout's own
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

### Pre-commit coverage gate (validator ≥95%)

The checked-in hook at [`.githooks/pre-commit`](.githooks/pre-commit) runs the
same full suite under coverage and refuses a commit when the shipped validator
(`rq_check.py`) drops below **95% line coverage**. `./install.sh` enables it in
a git checkout; in an existing checkout, enable it explicitly:

```sh
git config core.hooksPath .githooks
```

The validator is a subprocess, so coverage is deliberately explicit rather
than plugin magic: `RQ_COVERAGE=1` makes `tests/conftest.py::run_check` invoke
`coverage run --parallel`; the hook combines those child data files and applies
`coverage report --fail-under=95`. CI runs the identical gate. Bypass one
commit only with Git's standard `git commit --no-verify`.


`tests/test_repo_consistency.py` covers the other half: one validator, one
schema, documented commands that resolve, layout blocks that match the
filesystem, and one word per concept across the tracked docs. That is the
defect class this repository actually produces.

**What a green validator means:** nothing declared is missing, and the
deliverables build. It does not mean the mathematics is right — that stays with
the check battery, the independent ground-truth track, and the adversary.

## Studies

A **study** is the assignment: one self-contained piece of work with an
identical folder structure everywhere. Its durable deliverables
(`study.json`, `STUDY.md`, `registry.json`, `journal.md`, `derivations/`,
`audits/`, `artifacts/`) sit at the study root and are meant to be committed;
all scratch lives in a gitignored `interim/`. Two modes, implied by location:

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
