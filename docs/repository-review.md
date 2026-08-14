# dsh-rigorquant repository review

**Review date:** 2026-08-14  
**Scope:** All 16 tracked repository files, the installed preset, current DeepSeek Harness 0.1.0-rc.6 conventions, and ignored `.rigorquant/` runtime artifacts as behavioral evidence.  
**Mode:** Read-only audit; runtime artifacts are not shipped repository content.

## Overall assessment

RigorQuant is a thoughtful, well-documented research-protocol prototype. Its Cordis composition is technically competent, and its emphasis on falsification, audit trails, and terminal honesty is valuable.

However, the repository currently promises stronger guarantees than it implements. “Walled,” “independent,” “proof-grade,” and “mathematical validity” are largely prompt conventions rather than enforced properties. The current release is best described as promising promptware rather than a dependable unattended research framework.

## Prioritized findings

### 1. Critical — The isolation wall is not enforced

References:

- `agent-presets/rigorquant/agent.cordis.yml:31-52,215-227`
- `agent-presets/rigorquant/skills/rigorquant/SKILL.md:66-81,102-109`
- `agent-presets/rigorquant/skills/rigorquant/references/protocol.md:11-15`

Under current DSH behavior, a spawned subagent inherits the parent preset, working directory, and available tools. The configured generic subagent row supplies no role-specific persona, tool allowlist, or explicit depth restriction.

Consequences include:

- A ground-truth agent can read explorer artifacts in the shared workspace.
- “No web” and “no local files” are prompt requests rather than capability boundaries.
- Children inherit delegation tools and can recursively orchestrate.
- `subagent_fork` remains exposed even though the protocol calls its use an architectural violation.
- A single ground-truth agent performs both supposedly independent derivations, creating correlated errors.

#### Recommendation

Define separate delegation tools for explorers, two independent oracle agents, and the adversary. Give each a system-level role persona, strict tool allowlist, and `maxDepth: 1`. Remove `subagent_fork` if it must never be used. Use separate workspaces or providers where actual filesystem isolation is required, and let only the root merge shared artifacts.

Until this is enforced, describe the property as **procedural separation**, not a wall.

### 2. Critical — The independent verifier is unpinned and automatically executed

References:

- `agent-presets/rigorquant/agent.cordis.yml:279-295`
- `mcp/jacobian.md:3,11-20`

The documentation names Jacobian 0.11.0, but the composition executes:

```text
npx -y jacobian mcp
```

This resolves the latest npm release. Under current DSH behavior, the MCP client connects during preset activation, so the command runs when the preset mounts rather than only when escalation first occurs.

The absence of lifecycle scripts in the current package is not a safety guarantee for future releases. The unpinned command also prevents reproducible verification.

#### Recommendation

- Pin an audited version, such as `jacobian@0.11.0`, in every command.
- Prefer explicit opt-in or a preinstalled binary over automatic execution.
- Record the package version, runtime version, and hashes in every audit.
- Treat Jacobian output as independent evidence, not an unquestioned sole arbiter.
- Explicitly configure startup and reconnect behavior.
- Namespace `serverName` to reduce collisions with other standing presets.

### 3. Critical — Passing simplified cases does not establish general validity

References:

- `agent-presets/rigorquant/skills/rigorquant/references/check-battery.md:3-16`
- `agent-presets/rigorquant/skills/rigorquant/references/lifecycle.md:5-8`

The lifecycle declares PASS after the battery succeeds on simplified cases and then auto-implements the method. This is useful validation but is not sufficient to establish validity across the full problem domain.

A deliberately incorrect method that returns the correct result only in two or three dimensions would pass the suggested simplified cases.

#### Recommendation

Use explicit stages:

1. Specification, assumptions, and applicability domain.
2. Independent reference-case oracle.
3. General proof, certificate, or precisely bounded validity claim.
4. Numerical stability, conditioning, residual, and complexity analysis.
5. Domain-scale stress testing.
6. Empirical or out-of-sample validation where applicable.

Call the existing battery a **reference-case sanity gate** unless it is followed by a general proof or certificate.

### 4. Critical — Validation is prose-driven rather than machine-enforced

The repository ships configuration, prose, a lockfile, and an installer, but no executable check runner, actual JSON Schema, validation script, or Lean project. The model decides whether sufficient evidence exists and whether PASS occurred.

Ignored runtime artifacts demonstrate the consequence:

- Required LLN grids were omitted while work proceeded.
- Tolerances were silently weakened.
- Tautological checks passed.
- Generated reports, scripts, and journal summaries drifted apart.

#### Recommendation

Provide a checker CLI that:

- validates `task.json` and `registry.json`;
- checks evidence completeness;
- runs reference, invariant, residual, and statistical tests;
- rejects missing required N-grids;
- audits whether checks are falsifiable;
- emits immutable machine-readable reports;
- records source, input, environment, and generator hashes;
- refuses PASS when mandatory evidence is absent.

### 5. High — Statistical acceptance criteria are internally unsound

References:

- `agent-presets/rigorquant/skills/rigorquant/references/check-battery.md:8-15,20-24,35-45`

Problems include:

- `mpmath` is arbitrary-precision floating point, not exact arithmetic.
- Pure relative error is undefined or misleading when the reference is zero or very small.
- Exact symbolic invariants and floating-point residuals are conflated.
- A finite-sample stochastic estimator generally cannot satisfy a universal `1e-12` relative-error gate.
- LLN does not require one fixed-seed error sequence to decrease monotonically.
- “Non-shrinking error = bias or broken sampler” is too strong.
- A single KS or chi-square non-rejection does not establish distributional agreement.
- Bit-identical replay is not portable across platforms, BLAS implementations, devices, or nondeterministic kernels.
- The installed lane reports `jax_enable_x64=False`, which conflicts with blanket `1e-12` expectations for JAX calculations.

Runtime artifacts reportedly loosened the stochastic tolerance to `5e-3` without reconciling it with the normative specification.

#### Recommendation

Separate deterministic and stochastic Gate A:

- Deterministic methods: condition-aware absolute and relative tolerances.
- Stochastic methods: agreement in standard-error or confidence-interval units.

Use repeated independent streams, confidence intervals, explicit bias tests, and convergence-rate estimates rather than monotonicity. Record the complete execution environment and distinguish symbolic equality from numerical residual bounds.

### 6. High — Checks themselves are not audited

Ignored runtime artifacts contained tautological checks such as comparing a formula to algebraically identical code. Such checks always pass and provide no independent evidence.

#### Recommendation

Every check should declare:

- an independently computed expected value;
- the condition that would make it fail;
- at least one deliberately incorrect implementation or mutation it detects;
- the producer and oracle provenance;
- whether code paths or formulas are shared.

The adversary must audit the design of the checks, not only their PASS/FAIL outputs.

### 7. High — The compute lane is not installed with the preset

References:

- `install.sh:17-22`
- `agent-presets/rigorquant/skills/rigorquant/SKILL.md:54-60`

The installer copies only `agent-presets/rigorquant`. It does not install `env/`, `mcp/`, or `docs/`. The skill nevertheless expects to find `env/pyproject.toml` in the original checkout without recording a stable checkout location.

Ignored runtime state reportedly contains an absolute checkout path, confirming the coupling in practice. That state is not shipped, but it demonstrates the operational failure mode.

#### Recommendation

Either bundle the compute environment and referenced documentation under the preset, or install shared assets under a stable location such as `$DSH_HOME/share/rigorquant` and expose that exact path to the agent. Add a root-level preflight for `uv`, the lockfile, permissions, disk space, and runtime versions before launching subagents.

### 8. High — “Lean as the last resort” is advertised but not implemented

References:

- `README.md:18-19`
- `docs/architecture.md:33-34`
- `agent-presets/rigorquant/skills/rigorquant/references/escalation.md:52-59`

There is no `lean-toolchain`, `lakefile`, Lean source, installation path, container, or axiom-audit script.

#### Recommendation

Either label Lean as a manual external lane or ship a minimal pinned Lean/Mathlib project with a reproducible command and axiom-audit procedure.

### 9. High — Goal scope, round accounting, and cost limits are inconsistent

References:

- `agent-presets/rigorquant/skills/rigorquant/SKILL.md:51-52`
- `agent-presets/rigorquant/skills/rigorquant/references/lifecycle.md:13-15,53-57`
- `docs/architecture.md:45-47`

The skill creates one goal for the whole task, while the lifecycle describes a goal per subproblem. DSH supports one current same-session goal, so these instructions cannot both be followed literally.

Each round launches roughly four to six agents. Five rounds therefore imply approximately 20–30 model runs before retries, yet the repository explicitly has no API-cost ceiling.

#### Recommendation

Use one task-level goal, represent subproblems in validated state, and define exactly one orchestration cycle per continuation. Add limits for total tokens, financial cost, wall time, concurrency, subagent count, retries, and nested delegation. Document that only the root manages the goal and that each resumed round reconstructs state from persisted artifacts.

### 10. Medium — Runtime artifacts lack provenance and consistency enforcement

Ignored runtime evidence reportedly showed disagreement among a generating script, an audit Markdown file, and the journal summary. It also included a journal claim that materially understated an observed error.

These files are not shipped defects, but they show that the current protocol does not preserve an auditable chain from code to result to summary.

#### Recommendation

- Store the generating script path and SHA-256 in every report.
- Hash inputs, code, outputs, and environment manifests.
- Make reports immutable.
- Generate journal summaries mechanically from audit records.
- Reject summaries that do not match their referenced artifacts.

### 11. Medium — Reproducibility requires more than seed plus lockfile

Reference: `env/README.md:25-30`

Record at least:

- repository commit and code hash;
- input-data hashes and transformations;
- exact Python version;
- operating system and architecture;
- BLAS and device backend;
- solver, status, tolerances, residuals, and thread settings;
- JAX precision and determinism configuration;
- every random stream, including Hypothesis.

Use `uv sync --frozen` and `uv run --frozen`. Either pin a supported Python range and backend or replace “bit-identical” with a documented numerical-tolerance guarantee.

### 12. Medium — State artifacts are underspecified

References:

- `agent-presets/rigorquant/skills/rigorquant/SKILL.md:39-49`
- `agent-presets/rigorquant/skills/rigorquant/references/lifecycle.md:17-51`

Issues include:

- no schema for `task.json`;
- `registry.json` models only one subproblem although intake creates several;
- blocked-state equality depends on an exact prose string;
- no immutable round or agent identifiers;
- no prescribed filenames, hashes, or merge policy;
- no synchronization rule before launching the adversary;
- no explicit treatment of failed, timed-out, or truncated agents.

#### Recommendation

Provide actual JSON Schemas, immutable `round-<n>/<role>-<id>` outputs, stable gap IDs, hashes, and parent-only atomic state updates.

### 13. Medium — The affirmative-result assumption creates confirmation bias

References:

- `agent-presets/rigorquant/skills/rigorquant/references/protocol.md:11-15`
- `agent-presets/rigorquant/skills/rigorquant/references/escalation.md:44-50`

The correct outcome may be impossibility, non-identifiability, divergence, or a counterexample. A prose derivation surviving another instance of the same model is peer review, not proof-grade settlement.

#### Recommendation

Run proof and refutation tracks in parallel and support an `unknown` outcome. Use explicit evidence levels:

- falsification-surviving;
- independently re-derived;
- certificate-checked;
- formally verified.

Only checked certificates or formal verification should conclusively settle load-bearing claims.

### 14. Medium — The empirical-finance scope lacks domain-specific gates

The project advertises economics, finance, portfolios, and simulation, but the battery mostly checks mathematical consistency.

Add mandatory checks for:

- temporal rather than random train/test splits;
- look-ahead and target leakage;
- survivorship and selection bias;
- multiple-hypothesis and data-snooping adjustment;
- transaction costs and turnover;
- nonstationarity and regime sensitivity;
- dependence-aware uncertainty;
- MCMC effective sample size and mixing.

A mathematically correct toy optimizer can still produce an invalid backtest.

### 15. Medium — The installer is destructive and non-atomic

Reference: `install.sh:11-21`

It removes the destination before copying, so an interrupted update can leave no working installation and silently destroys local modifications. Unknown arguments also fall through to a full installation.

#### Recommendation

Validate arguments, copy into a staging directory, validate it, then atomically replace the destination. Require `--force` or create a backup when replacing an installation. Add `--help`, `--uninstall`, version reporting, and a declared supported DSH version.

The `--skill-only` destination itself is valid under current DSH: `$DSH_HOME/skills` is automatically scanned and watched.

### 16. Low — Persona and skill duplicate the operating procedure

References:

- `agent-presets/rigorquant/agent.cordis.yml:63-103`
- `agent-presets/rigorquant/skills/rigorquant/SKILL.md:86-138`

Duplicating the battery, lifecycle, isolation, and escalation rules creates two sources of truth.

#### Recommendation

Keep only identity, mission, and non-negotiable constraints in the persona. Put the detailed procedure exclusively in the skill that the persona already instructs the agent to load.

### 17. Low — Publishing and documentation polish

- `README.md:32` uses the placeholder `github.com/<you>/dsh-rigorquant`.
- `README.md:45-47` says `uv sync` creates a lockfile that is already committed.
- There are no release tags, changelog, compatibility matrix, or upgrade instructions.
- Auto-implementation should use a branch or worktree, frozen write scope, tests, and rollback rather than directly changing an arbitrary target repository.

## Notable strengths

- No obvious Cordis host/agent-plane or isolate-realm mistake.
- The composition closely follows the current standard preset.
- The preset-local skill path is relocatable and correctly uses `baseUrl`.
- The Python lockfile contains exact versions and SHA-256 hashes.
- Terminal honesty and explicit PASS/BLOCKED/BUDGET states are valuable.
- The audit trail and combination of symbolic, numerical, adversarial, and formal techniques are a strong direction.
- Runtime evidence indicates the protocol caught a real mathematical error in the first round, demonstrating genuine value despite the current trust-model weaknesses.
- The registry’s idea-family grouping and evidence references provide a clean basis for a stronger machine-enforced state model.

## Verification performed

The audit reviewed all 16 tracked files and checked:

- DSH YAML parsing: passed; 17 top-level rows.
- Resolution of all 24 referenced plugin packages against DSH 0.1.0-rc.6: passed.
- `sh -n install.sh`: passed.
- Installed preset versus repository preset: identical.
- Compute-lane imports and installed solvers: passed.
- Working tree: clean.

A full preset mount was not performed because it would execute the unpinned `npx` MCP command. `uv lock --check` could not complete because the read-only sandbox prevented uv cache initialization.

## Recommended implementation order

1. Enforce role isolation and remove prohibited delegation capabilities.
2. Build a machine-enforced meta-validator that audits methods and checks.
3. Separate deterministic and stochastic acceptance criteria.
4. Pin or opt in Jacobian and attach provenance to every verification artifact.
5. Make the compute lane self-contained.
6. Add artifact consistency controls, budgets, CI, and DSH compatibility tests.
7. Ship the Lean lane or remove it from the advertised capability set.

---

# Second-reviewer responses (added at the maintainer's request, 2026-08-14)

These responses were produced by an independent second AI reviewer. They annotate
the findings above rather than replace them, and were verified against HEAD
(`ed88d77`), the reviewed commit (`944f3fd`), the installed preset under
`$DSH_HOME/.agent-presets/rigorquant`, the runtime artifacts in `.rigorquant/`,
and the installed harness packages.

**Context the reviewer of these responses needs:** the original review audited
the initial import `944f3fd` ("16 tracked files"). HEAD now has 20 tracked
files from six additional same-day commits: `51bc836` (jacobian upgrade flow),
`87bef2d` (auto self-provisioning lane, enabled by default), `882a9db` (Lean
runtime pinning), `610424a` (agentic Lean auto-provisioning), `0f455cb`
(README fixes + zh-CN README), `ed88d77` (dsh.bundle manifest). Verdicts below
are against HEAD unless stated otherwise.

**Verdict key:** CONFIRMED = agree, still true at HEAD. CONFIRMED WITH CAVEAT =
agree in substance, with a factual correction. PARTIALLY ADDRESSED = agree, but
later commits changed the state. NEW = not in the original review.

## Verdict per finding

**1. Isolation wall not enforced — CONFIRMED (fully valid).** The
`tool-subagent` row still configures only `provider: spawn`; `subagent_fork`
remains registered and enabled; SKILL.md Step 3.2 still assigns both "independent"
ground-truth derivations to one agent. The recommended fix is available on this
harness: the installed `@deepseek-ai/dsh-tool-subagent` schema supports
`persona`, `toolFilter.allow/deny`, and `maxDepth` (default 3) per row, and none
of it is used, so children inherit the full toolset and can recurse to depth 3.

**2. Unpinned jacobian — CONFIRMED for HEAD, with a citation caveat.** HEAD
still runs `npx -y jacobian mcp`, unpinned. However, at the reviewed commit
`944f3fd` the row was `disabled: true` with `command: jacobian`; the enabled
`npx -y` form arrived with `87bef2d`. The original citation
(`agent.cordis.yml:279-295`) matches neither state exactly — it appears to
describe the installed preset, which postdated the reviewed commit. The
recommendation remains unimplemented (see NEW N2).

**3. Simplified cases do not establish general validity — CONFIRMED.**
`lifecycle.md:5-8` still declares PASS on simplified cases and then
auto-implements. The recommended explicit stage split has not been adopted.

**4. Prose-driven validation — CONFIRMED.** Still no checker CLI, no JSON
Schema files, no validation script in the repo. The runtime `battery.py` is the
closest thing and is not a shipped repository artifact.

**5. Statistical criteria — CONFIRMED, one wording softened.** I ran the
installed lane: `jax_enable_x64` is indeed `False`, confirming the x64/1e-12
tension. But "tolerances were silently weakened" is too strong: the journal and
registry document each loosening (D1 band widened to `[0.85,1.15]`; honest
spectral agreement ~1e-4 vs. the audit's claimed 1e-6; round-2 spectral
adjudication at ~4e-3). The real defect is that the normative files
(`task.json` tolerances, `check-battery.md`) were never reconciled with those
operative changes — normative/operative drift, not silence.

**6. Checks not audited — CONFIRMED.** Example in the runtime: the Gate-B entry
"C_d exactly reciprocal to √π Γ((d+1)/2)/Γ(d/2+1)" is verified by algebraically
simplifying the definition against itself — precisely the tautological pattern
described.

**7. Compute lane not installed — CONFIRMED, and now worse.** `install.sh`
still copies only `agent-presets/rigorquant`. Additionally, the new npm bundle
(`package.json` `files`) ships no `env/` or `mcp/`, while SKILL.md Step 2 tells
the agent to find the lane in "the checkout" — bundle-installed users get a
skill pointing at a lane they do not have (see NEW N3).

**8. Lean lane — PARTIALLY ADDRESSED by later commits.** New
`skills/rigorquant/scripts/provision-lean.sh` pins `leanprover/lean4:v4.31.0`
and a jacobian tag and builds jacobian's Mathlib runtime;
`agent.cordis.yml` pins `JACOBIAN_LEAN_RUNTIME` and extends the lane PATH.
Still missing: any in-repo Lean source/lakefile and a machine-enforced axiom
audit (the trust boundary remains prose in `escalation.md`). The fix also
introduces new risks — see NEW N1.

**9. Goal scope, round accounting, cost limits — CONFIRMED.** `SKILL.md:51`
("goal for the whole task") still contradicts `lifecycle.md:55` ("create_goal
with the sub-problem objective"), and `lifecycle.md:15` still records no
API-cost ceiling.

**10. Runtime provenance — CONFIRMED WITH CAVEAT.** The drift among generating
script, audit file, and journal is real and is documented in the journal (the
audit claimed 1e-6 spectral agreement; the journal records honest agreement
~1e-4). But I could not find the claimed "journal claim that materially
understated an observed error" — the journal does the opposite, correcting the
audit's overclaim. "Required LLN grids were omitted" is unverifiable in the
current artifacts: `battery.py` now contains the full {1e3, 1e4, 1e5} grid.

**11. Reproducibility — CONFIRMED.** `env/README.md:29` still reduces
reproduction to "same lane, same lockfile, same seed."

**12. State artifacts — CONFIRMED.** No JSON Schemas in the repo;
`registry.json` still models a single subproblem while `task.json` carries six;
blocked-state equality still depends on the exact `blockedReason` prose string.

**13. Affirmative-result assumption — CONFIRMED.** `protocol.md:12` and
escalation Lane 2 still instruct the agent to "assume a complete affirmative
result exists."

**14. Empirical-finance gates — CONFIRMED absent.** The battery remains purely
mathematical; none of the listed domain checks exist.

**15. Installer — CONFIRMED.** Still `rm -rf` then `cp` (non-atomic,
destructive), and any argument other than `--skill-only` silently falls through
to a full install.

**16. Persona/skill duplication — CONFIRMED.** The persona (lines 31–106 of the
composition) still restates the battery, lifecycle, isolation, and escalation
rules that SKILL.md owns.

**17. Publishing polish — PARTIALLY ADDRESSED.** The `github.com/<you>/`
placeholder was fixed (`0f455cb`). The "`uv sync` creates env/uv.lock" wording
remains despite the committed lockfile; there are still no tags, changelog, or
compatibility matrix.

## New findings (material added after the reviewed commit)

**N1. Unattended auto-provisioning is a supply-chain and consent risk.** The
persona and skill now instruct the agent to run `npx -y jacobian upgrade` and
`scripts/provision-lean.sh` with "no user prompt" (persona ESCALATION section;
SKILL.md escalation section). The script pipes `curl | sh` for elan-init,
downloads five Lean files by tag from GitHub, and appends
`export PATH=...` to the user's `~/.zprofile` / `~/.bash_profile` / `~/.profile`.
For a framework whose stated discipline is "a producer cannot certify its own
output," auto-executing unpinned remote installers and mutating shell rc files is
in tension with its own trust model. Recommend: pin installers by hash, never
pipe curl to sh, make rc-file mutation opt-in, and route auto-installs through
user-visible approval.

**N2. Version drift between docs and script; the package itself stays
unpinned.** `mcp/jacobian.md` still describes "pre-stable 0.11.0", while
`provision-lean.sh` defaults `JACOBIAN_TAG=jacobian-v0.12.0` — two versions of
truth for one dependency, while the MCP row itself (`npx -y jacobian mcp`)
remains unpinned. Finding 2's recommendation was not implemented even though
the surrounding Lean toolchain was pinned.

**N3. The bundle distribution path loses the compute lane entirely.**
`package.json` `files` includes only `cordis.patch.yml`, `agent-presets/`,
`install.sh`, READMEs, and LICENSE. `env/` and `mcp/` are not shipped, yet
SKILL.md Step 2 and `task.json` `env_lane` assume a checkout layout. This
aggravates finding 7 for every `dsh plugin add` install.

## Verification performed by this reviewer

- Diffed the installed preset at `$DSH_HOME/.agent-presets/rigorquant` against
  the repo copy: identical.
- Confirmed the review audited `944f3fd` (16 tracked files); HEAD has 20
  tracked files from the six later commits listed above.
- Re-read `install.sh` argument handling and destination logic: unchanged.
- Ran the lane's interpreter: `jax_enable_x64` → `False` (finding 5).
- Inspected the installed `@deepseek-ai/dsh-tool-subagent` schema: `persona`,
  `toolFilter.allow/deny`, `maxDepth` (default 3) supported and unused by the
  preset (finding 1).
- Checked `uv.lock`: 548 SHA-256 hashes over 35 pinned packages.
- Grepped runtime artifacts for the original review's behavioral claims
  (findings 5, 6, 10).

## Bottom line

Agree with the overall assessment and approximately 15 of 17 findings as
written. Findings 8 and 17 are partially addressed by later commits; finding
2's citation is stale (the row was disabled at the reviewed commit); findings
5 and 10 should read "unreconciled drift" rather than "silent," and parts of
10 are unverifiable. N1–N3 are new and are the highest-priority review targets —
N1 in particular contradicts the framework's own stated trust discipline.
