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

---

# Third-reviewer verdicts and new findings (2026-08-14)

**Reviewer:** third independent AI reviewer, at the maintainer's request.
**Scope:** the two prior reviews above, checked against HEAD (`2239f79`), the
DeepSeek Harness source checkout at `~/gits/deepseek-harness`, the live npm
registry, and the working study `rq-convex-sampling-01`, which has since been
moved out of this repository to
`/Users/linxi/gits/rigorquant_studies/0001_rq-convex-sampling-01/` (HEAD does
not track it). **Study-relative paths** cited below are relative to that
external root.

**Method note:** every claim below that concerns harness behavior was read out
of the harness source, not inferred from documentation. Harness paths are
relative to the `deepseek-harness` checkout root; all other paths are relative
to this repository.

**How to read the verdict blocks:** each `[Verdict]` is a decision the
maintainer has accepted for implementation. `AGREE` means implement the prior
review's recommendation as written. `AGREE, AMENDED` means implement the
amended version stated in the block — the prior recommendation is wrong or
incomplete in the stated respect. `REFRAME` means the finding's facts stand but
its severity or conclusion changes. `STRIKE` means remove the claim; it is not
supported by evidence. `NEW` marks a finding neither prior review raised.

## Verdicts on the prior findings

### Finding 1 — isolation

The prior reviews describe the wall as wholly unenforced. That is too broad in
one direction and not specific enough in another. The context wall *is*
harness-enforced: `packages/subagent/subagent-spawn-in-process/src/index.ts:44`
declares `readonly inheritsParentContext = false`, so a spawned child never
sees the parent conversation. Everything else is prose:
`packages/subagent/subagent-in-process-driver/tests/preset-inheritance.spec.ts`
confirms the child runs on the parent's preset (inheriting `subagent`,
`subagent_fork`, `web_search`, and the full fs toolset), and the in-process
driver stamps the parent's cwd onto the child.

> **[Verdict 1 — AGREE, AMENDED]**
> Implement per-role delegation rows, with these three corrections to the
> prior recommendation:
>
> 1. **Restate the property precisely** in README, persona, and
>    `references/protocol.md`: *context isolation is enforced by the harness;
>    web access, filesystem scope, recursion, and producer≠checker are not.*
>    Do not use the unqualified word "walled" for the latter four.
> 2. **"No web" is enforceable today** and must be enforced, not requested.
>    `toolFilter` is a real capability boundary — filtered tools are removed
>    from the child's prompt *and* reject execution
>    (`packages/subagent/tool-subagent/src/index.ts:63-68`). Add
>    `toolFilter.deny: [web_search]` to the ground-truth row.
> 3. **Filesystem isolation is NOT achievable with the `spawn` provider.**
>    There is no per-child cwd, and `toolFilter` on fs tools is all-or-nothing.
>    A cwd override exists only for out-of-process providers
>    (`packages/subagent/subagent/src/types.ts:107-108`). The prior review
>    offers "separate workspaces or providers" as one option among several; it
>    is the only option. Either route ground-truth work through an
>    out-of-process provider with its own cwd, or drop the filesystem-isolation
>    claim entirely and rely on procedural separation plus the adversary.
>
> Also correct the record: `maxDepth` defaults to `3`
> (`packages/subagent/tool-subagent/src/index.ts:98`), not unbounded. Set it to
> `0` on every role row to forbid re-delegation.
>
> This is a configuration change, not an architectural one. The preset already
> demonstrates the multi-row pattern (four `tool-subagent` rows with distinct
> `toolName`). Budget it accordingly.

### Finding 2 — unpinned, auto-executed verifier

> **[Verdict 2 — AGREE, AMENDED — worse than stated]**
> `packages/mcp/mcp-client/src/index.ts:177` awaits `connection.ready` inside
> `apply()`, so plugin activation *blocks* on the MCP connection.
> `npx -y jacobian mcp` therefore executes on **every preset mount**, not on
> first escalation. Confirmed against the registry: `jacobian` is version
> `0.12.0`, unscoped, pre-1.0, single maintainer.
>
> Implement: pin `jacobian@0.12.0` in every invocation, and set the
> `mcp-jacobian` row `disabled: true` by default given eager activation —
> opt-in at escalation, not opt-out at mount.
>
> Additionally, delete or rewrite the comment in `agent.cordis.yml` that
> justifies `npx -y` with "the package runs no lifecycle scripts." That is a
> safety claim about a version the repo does not control, re-resolved on every
> mount. It is the exact inversion of this framework's own stated discipline
> that a producer cannot certify its own output, and it should not survive in a
> file that also asks agents to hold others to that standard.

### Finding 3 — simplified cases and general validity

> **[Verdict 3 — AGREE, AMENDED]**
> The recommendation stands, but the finding as written slightly strawmans the
> skill: `SKILL.md`'s anti-patterns already forbid "accepting 'matches at fixed
> parameters' as validity," and `references/protocol.md:23` states "fixed-
> parameter computational success does not count." The framework is not unaware
> of the failure mode.
>
> State the defect correctly in the rewrite: PASS is defined against the
> battery, while the anti-pattern that would block PASS exists only as prose
> with nothing evaluating it. That is finding 4, not a separate blind spot.
> Implement the staged rewrite of `references/lifecycle.md:32-35` as
> recommended, and rename the battery a **reference-case sanity gate**.

### Finding 4 — prose-driven validation

> **[Verdict 4 — AGREE, PROMOTED TO ROOT CAUSE]**
> Implement the checker CLI as specified. Additionally, restructure the
> priority list: findings 3, 5, 6, 10, and 12 are symptoms of this one and
> should be scheduled behind it, not in parallel with it. Fixing them
> individually in prose reproduces the same class of defect.

### Finding 5 — statistical acceptance criteria

The technical objections are correct (`jax_enable_x64` is `False`; a universal
`1e-12` gate cannot bind a finite-sample estimator; monotonic per-N decrease is
not what LLN asserts; bit-identical replay is not portable). The behavioral
claim attached to them is not.

> **[Verdict 5 — AGREE on the criteria; STRIKE "silently weakened"; ADD the
> real defect]**
> Implement the deterministic/stochastic split as recommended.
>
> Strike "tolerances were silently weakened." Every loosening is documented in
> `<study>/journal.md` with its reasoning. The second
> reviewer's "normative/operative drift" is the correct characterization, and
> the concrete remediation is: reconcile `study.json` `tolerances` (still
> `numeric_lane: 1e-12`) with the operative values the run actually adopted
> (spectral `~1e-4`; finite-chain adjudication `~4e-3`; D1 band
> `[0.85, 1.15]`), or make the checker reject the mismatch.
>
> Add the defect the finding missed. The D1 band was widened because the
> original band produced a **~26% per-cell false-reject rate across ~128
> cells**. That is not a weakened tolerance — it is the run discovering a
> design bug in `references/check-battery.md`: a per-cell acceptance band with
> no multiplicity correction. Multiplicity control (the run reached for Holm)
> belongs in the normative battery spec, not in a downstream fix.

### Finding 6 — checks not audited

> **[Verdict 6 — AGREE, with three cited instances]**
> Implement the per-check declaration requirements as recommended. The prior
> review cites one tautology; there are at least three consecutive ones in
> `<study>/audits/round-1-audit.md:48-50` — "marginals
> integrate to exactly 1" verified by `C_d·(1/C_d)=1`; "`C_d` exactly
> reciprocal to …" verified by simplifying the definition against itself; and
> the simplex row-sum identity verified by substituting the closed forms into
> the identity they were derived from. Use all three as the regression corpus
> for the mutation-detection requirement: a correct implementation of the
> requirement must reject all three.

### Finding 7 / N3 — compute lane not installed

> **[Verdict 7 — AGREE, AMENDED — see also Verdict T3]**
> Implement the stable-shared-location fix
> (`$DSH_HOME/share/rigorquant`) rather than the "bundle under the preset"
> alternative, because the bundle path (N3) needs the same anchor. Note that
> the bundle does not lose *everything* outside `agent-presets/` — see
> Verdict T3 for what it does ship, which changes the priority.

### Finding 8 — Lean lane

> **[Verdict 8 — AGREE with the second reviewer: PARTIALLY ADDRESSED]**
> Remaining work is unchanged: no in-repo Lean source or lakefile, and the
> axiom-audit trust boundary is still prose in `references/escalation.md:64-65`
> with nothing executing it. Ship the axiom audit as a script or drop the
> "proof-grade" language. Do not treat the provisioning script as closing this
> finding — see N1 and Verdict T3.

### Finding 9 — goal scope and round accounting

> **[Verdict 9 — AGREE, ESCALATED from inconsistency to runtime failure]**
> This is not two instructions that "cannot both be followed literally." It is
> one instruction that throws. `packages/goal/goal/src/fold.ts:289-293` rejects
> `create` unless the current goal's phase is `complete`, so
> `references/lifecycle.md:82` ("`create_goal` with the sub-problem objective")
> raises on the second subproblem of any multi-subproblem study — which is
> every study the intake step produces.
>
> Implement the one-task-level-goal resolution and delete the per-subproblem
> `create_goal` instruction from `lifecycle.md`. Represent subproblems in
> `registry.json`/`study.json` state only.

### Finding 10 — runtime provenance

> **[Verdict 10 — AGREE on provenance; STRIKE the understatement claim]**
> Implement the hashing and mechanical-summary-generation recommendations.
>
> Strike "a journal claim that materially understated an observed error." Two
> independent reviewers have now failed to locate it, and the evidence runs the
> other way: the journal corrects the audit's overclaimed `1e-6` down to an
> honest `~1e-4`, and later overrules the Round-1 adversary's under-resolved
> Galerkin values. An unlocatable claim of dishonesty should not stay in a
> review that will be used to prioritize work.
>
> Also strike "required LLN grids were omitted": `artifacts/battery.py:608`
> carries the full `{1e3, 1e4, 1e5}` grid.

### Findings 11, 12, 13, 14, 16 — no change

> **[Verdict 11-14, 16 — AGREE as written]**
> Implement as recommended. On finding 12, note that the artifacts have since
> been renamed (`task.json` → `study.json`, `.rigorquant/` → `studies/<slug>/`)
> per `docs/architecture.md` decision 12; the schema work targets the new names.
> On finding 14, the domain gates remain the largest unaddressed gap between
> what the README advertises and what the battery checks.

### Finding 15 and 17 — re-ranked

> **[Verdict 15 — REFRAME: lower to Low]**
> `rm -rf` on a directory the installer owns, whose contents are re-copyable
> from the checkout, is not a High. Fix the argument fall-through (any
> unrecognized argument silently performs a full install) — that is the real
> bug. Staging-directory atomicity is optional polish.

> **[Verdict 17 — REFRAME: promote the auto-implementation bullet to High]**
> `references/lifecycle.md:32-35` specifies that PASS auto-implements the
> method "into the target artifact/codebase" with "No user confirmation
> required by default." Combined with the framework's unattended premise, that
> is an autonomous writer into an arbitrary repository with no branch, no
> frozen write scope, and no rollback. It is currently filed as a
> documentation-polish bullet. Implement the branch/worktree + write-scope +
> rollback requirement at High priority, ahead of findings 11-14.

## New findings

### T1 — "Unattended" is contradicted by the goal service, and the runtime proves it

Neither prior review checked the harness's goal-continuation semantics against
the framework's headline claim.

Goal activation is an in-memory, per-session cache seeded `disarmed`
(`packages/goal/goal/src/index.ts:428`). After a session resume or fork an
active goal is disarmed, and only a **direct human turn** rearms it
(`packages/goal/tool-goal/src/index.ts:117`). `complete` and `blocked`
likewise require a direct human turn or the current goal round
(`packages/goal/tool-goal/src/authority.ts:107`), and goal creation "rejects
non-human and subagent authority" (`.../tool-goal/src/index.ts:49`), so no
subagent can own or advance a goal.

The live study confirms the consequence in the field.
`<study>/journal.md` records, verbatim:
*"Round 2 — implementation (2026-08-14, resumed on user 'continue')."* The
flagship run required a human to type "continue."

> **[Verdict T1 — NEW, HIGH]**
> Correct the advertised property everywhere it appears (README, README.zh-CN,
> persona text in `agent.cordis.yml`, `SKILL.md`, `docs/architecture.md`): the
> framework is **unattended within one live session**; crossing a session
> boundary requires one human turn to rearm the goal. Do not describe rounds as
> continuing autonomously across restarts.
>
> Then decide and document a continuation strategy: either (a) accept the
> single-session bound and make the checkpoint/resume path explicit and cheap,
> or (b) drive continuation off a mechanism that survives restart — persisted
> study state re-read at each launch — and stop relying on the goal service for
> durability. Do not ship both stories at once.
>
> **Note for the implementer:** this is the finding most likely to change what
> the project *is*, so resolve it before investing in findings 11-14. A
> framework that is honestly "unattended within a session, checkpointed across
> sessions" is a coherent and useful product. A framework that claims
> restart-surviving autonomy it does not have will keep generating findings
> like this one.

### T2 — Study state is addressed by mutable relative paths, with no lock and no run identity

`<study>/journal.md` records a workspace incident that no review saw, because
it is not visible at HEAD: an uncoordinated repository reorganization moved
the entire runtime workspace (`.rigorquant/` → `studies/rq-convex-sampling-01/`)
**while the Round-2 battery was executing with cwd-relative paths**. The
recovery was to recreate `.rigorquant` as a symlink to
`studies/rq-convex-sampling-01` so the in-flight `battery-results.md` write
would land in the canonical location. The study has since moved to the
external root given in the scope note, and both `studies/` and the symlink
have been removed from this repository.

That symlink was live in the working tree at the time, and `.gitignore`
ignores the legacy workspace path, so the recovery mechanism was itself
invisible to any reviewer working from a clean checkout. No data was lost,
but nothing prevented loss: there is no lock, no run identifier, and no
absolute-path anchor binding a running battery to the study it belongs to.

> **[Verdict T2 — NEW, HIGH]**
> Implement three things:
>
> 1. **Run identity.** Every launched check run resolves the study root once,
>    at launch, to an absolute path, and records it plus a run id in its output
>    header. A run whose recorded root no longer matches the resolved root
>    fails loudly instead of writing.
> 2. **A study lock.** A lockfile in the study root naming the live run, so a
>    second orchestrator or an external reorganization is detectable rather
>    than silently racing.
> 3. **Remove the symlink recovery.** Delete the `.rigorquant` symlink and the
>    `.rigorquant/` `.gitignore` entry once no run depends on them, and make
>    `SKILL.md` Step 1's study-root resolution reject a symlinked study root.
>    The legacy-compatibility comment in `.gitignore` currently makes a live
>    workaround look like dead history.

### T3 — The npm bundle ships the risky half of the escalation lane and drops the half that gates every check

N3 states that the bundle "loses the compute lane." The sharper and more
actionable form: `package.json` `files` **includes `agent-presets/`**, and
`scripts/provision-lean.sh` lives under it. So every `dsh plugin add` install
receives the script that pipes `curl | sh` for elan-init, downloads five Lean
files by mutable tag, and appends `export PATH=...` to `~/.zprofile`,
`~/.bash_profile`, and `~/.profile` (N1) — while `env/` and `mcp/` are not in
`files` and do not ship at all.

A bundle user therefore gets an agent instructed to auto-provision a Lean
toolchain unattended, but with no pinned Python lane to run gate A, B, C, or D
against. The dangerous capability ships; the one that does the actual
verification does not.

> **[Verdict T3 — NEW, CRITICAL — supersedes N3 and raises N1]**
> Do these in order:
>
> 1. **Stop shipping unattended remote-installer execution.** Either remove
>    `scripts/provision-lean.sh` from the bundle, or change the escalation
>    instructions so provisioning requires explicit user approval rather than
>    "no user prompt." Do not ship an auto-install path to users who cannot run
>    the checks it is meant to serve.
> 2. **Ship the lane** — add `env/` and `mcp/` to `package.json` `files`, and
>    resolve `env_lane` against the installed package root rather than "the
>    checkout" (`SKILL.md` Step 2).
> 3. **Then** apply N1's hardening to whatever provisioning path survives: pin
>    the installer by hash, never pipe curl to sh, make rc-file mutation
>    opt-in, and reconcile `mcp/jacobian.md`'s "0.11.0" with
>    `provision-lean.sh`'s `jacobian-v0.12.0` and the (now pinned, per
>    Verdict 2) MCP row.

## Reframing the overall assessment

> **[Verdict 0 — REFRAME the bottom line]**
> "Promising promptware rather than a dependable unattended research
> framework" is accurate about the *guarantees* and misleading about the
> *value*, and the difference changes what should be built.
>
> The runtime evidence shows the multi-voice protocol catching real errors
> three times in two rounds: the naive `sinc` eigenpair was refuted because of
> the boundary "stay" atom (wrong by ~9% at δ=1); the Round-2 implementer
> overruled **Round 1's own adversary** for under-resolved Galerkin truncation;
> and the journal corrected the audit's overclaimed `1e-6` to an honest
> `~1e-4`. A protocol that catches its own auditor is producing epistemic value
> that no checker CLI would have produced on its own.
>
> Implement the machine enforcement *under* the existing protocol, not as a
> replacement for it. Specifically: the checker (finding 4) should mechanize
> the gates and the provenance chain, while the adversary, the counterexample-
> only elimination rule, and the multi-voice registry stay exactly as they are.
> A plan that treats the prompt layer as the thing to be removed will discard
> the only part of this repository with demonstrated results.

## Recommended implementation order (replaces the prior list)

1. **T1** — resolve and document what "unattended" means. It gates the design
   of everything below.
2. **T3**, then **Verdict 2** — stop shipping unattended remote installers and
   unpinned mount-time execution. Both are outward-facing safety issues.
3. **Verdict 17** — branch/worktree, frozen write scope, and rollback before
   any further autonomous auto-implementation runs.
4. **Verdict 1** — per-role delegation rows with `persona`, `toolFilter`, and
   `maxDepth: 0`; correct the isolation language. Cheap; do it early.
5. **Verdict 9** — delete the per-subproblem `create_goal` instruction.
6. **Verdict 4** — the checker CLI, carrying findings 3, 5, 6, 10, and 12 with
   it, including the multiplicity fix from Verdict 5 and the tautology corpus
   from Verdict 6.
7. **T2** — run identity, study lock, symlink removal.
8. **Findings 11, 13, 14, 16, and Verdict 15** — remaining hardening; finding
   14 (domain gates) is the largest advertised-versus-delivered gap left.

## Notes for the implementer

- **Prose edits and enforcement edits are not interchangeable.** Several
  verdicts above ask for a documentation change (Verdict 1's language, T1's
  claims). Those are not lesser work: the recurring failure mode in this
  repository is a document asserting a property nothing evaluates. Changing the
  document *is* the fix when the property is not going to be enforced.
- **Where a verdict strikes a claim, strike it — do not soften it.** Verdicts 5
  and 10 remove assertions about silent weakening and understated errors. Those
  assertions are unsupported, and leaving them in weakened form will keep
  distorting priorities.
- **Do not treat this document as the specification.** It is a decision record.
  Findings 4, 12, and T2 all imply real schemas and a real CLI; write those as
  their own artifacts.
- **Verification claims in this section are reproducible.** Every harness line
  reference was read from the `deepseek-harness` checkout at the state
  described above; if a reference does not resolve, the harness moved — re-read
  it rather than assuming the verdict is stale.

---

# Fourth pass — cloud review triage (2026-08-14)

**Source:** an automated multi-agent cloud review run on the branch diff
(8 files, ~1044 insertions), triaged and verified by the third reviewer.
It returned 9 findings, all graded `nit`.

**Scope caveat — read this before using the results.** The cloud pass reviewed
the **branch diff**, so it saw only the study-layout rewrite and the review
documents. It found nothing bearing on T1 (unattended), T3 (bundle safety),
Verdict 2 (unpinned mount-time `npx`), or Verdict 17 (autonomous writer with no
branch), because all four live in files this diff does not touch. A clean
result on a diff-scoped pass is not a clean result on the repository. Do not
let the `nit`-only grading reorder the implementation plan above.

**Triage outcome:** 3 accepted as new findings (T4–T6), 3 folded into existing
verdicts as amendments, 2 accepted as instances of finding 12, 1 partly
rejected on a false premise.

## New findings accepted from the cloud pass

### T4 — Mode A writes an unanchored `interim/` into a `.gitignore` it does not own

SKILL.md:63-65 instructs Mode A intake to *"append `interim/` to the repo-root
`.gitignore`."* Per gitignore(5), a pattern with no leading separator matches
at any depth below the `.gitignore`. Verified empirically in a scratch repo:

```
pattern `interim/`   → matches data/interim/staged.parquet  AND interim/scratch.txt
pattern `/interim/`  → matches interim/scratch.txt only
```

**Rationale corrected from the cloud report.** The cloud finding motivates this
with the Cookiecutter Data Science `data/interim/` convention. That
justification does not apply and should not be carried into the fix: this
framework does not target data-science pipeline users, and its `interim/` holds
explorer reports, ground-truth scripts, theorem drafts, and logs
(`docs/architecture.md` decision 12) — not staged data. There is no reason for
a rigorquant study to nest `interim/` under `data/`.

The fix stands on a different and simpler basis: in Mode A, rigorquant writes
into the **user's** repo-root `.gitignore`, in a repository whose contents it
cannot know. The intent is exactly one directory — the study root's scratch
folder. An unanchored pattern asserts something broader than the intent, for
no benefit.

> **[Verdict T4 — NEW, LOW / hygiene]**
> Change the Mode A instruction at SKILL.md:64 to append `/interim/`, and
> update the layout diagram caption at SKILL.md:85 to match. Mode B needs no
> change: its `.gitignore` is written inside the study folder, where the
> pattern is already naturally scoped.
>
> Do not reproduce the data-science rationale in the commit message or the
> docs. The reason is namespace ownership, not convention compliance.

### T5 — In Mode A, the study README overwrites the repository README

Mode A sets study root = repo root (SKILL.md:58). The study layout, labelled
"identical in both modes," places `README.md` at the study root with the
caption *"human-facing summary, refreshed at checkpoints"* (SKILL.md:75). The
lifecycle auto-implements on PASS with *"No user confirmation required by
default"* (`references/lifecycle.md:32-35`). Nothing in Step 1.4's creation
list mentions `README.md`, so an existing one is never detected at intake.

Running Mode A in this very repository would overwrite the 108-line framework
README at the first checkpoint.

> **[Verdict T5 — NEW, MEDIUM — merge into Verdict 17]**
> This is the same defect as Verdict 17 with a concrete target: an
> unconfirmed autonomous write into a user-authored file. Implement it as part
> of the Verdict 17 work, not separately.
>
> Preferred fix: rename the study summary so it cannot collide — `STUDY.md`
> rather than `README.md` — in **both** modes, keeping the layout genuinely
> identical. Renaming only in Mode A reintroduces the mode-dependent layout
> that decision 12 exists to eliminate. Secondary fix if the name is kept:
> intake must detect a pre-existing README with non-study content and the
> checkpoint must merge rather than replace.

### T6 — Incomplete rename: `env/README.md` still points at the legacy `.rigorquant/task.json`

`env/README.md:28` reads *"Record the seed of every stochastic run in
`.rigorquant/task.json`."* Verified: after the study-layout rewrite this is the
only remaining live normative pointer to the legacy filename anywhere in the
repository outside this review document and the dogfood study (now external,
see the scope note).

It matters because `SKILL.md` Step 2 explicitly directs the agent to consult
`env/README.md`, while Step 0.3 gives the new instruction (`study.json`). The
same PR hands a subagent two contradictory pointers, and the losing branch
writes the seed where no Gate-D reproducibility audit will look for it.

> **[Verdict T6 — NEW, LOW]**
> One-line edit: `- Record the seed of every stochastic run in `study.json`
> (at the study root).` Then grep the repository for `task\.json` and
> `\.rigorquant` and confirm the only remaining hits are historical citations
> in this document, the explicit "legacy" callout in `docs/architecture.md`
> decision 12, and the `.gitignore` legacy line — the last of which Verdict T2
> removes anyway.

## Amendments to existing verdicts

> **[Amendment to T2 — the study-root walk-up has no boundary]**
> SKILL.md:50-51 walks up from the working directory looking for `study.json`
> with no stop condition — not the git repo root, not `$HOME`, not `/` — and
> Step 1.4 forbids re-asking on resume. Any ancestor `study.json` is therefore
> adopted silently and permanently, misrouting `derivations/`, `audits/`, and
> `journal.md` into the wrong tree.
>
> This is a second instance of T2 (study state has no boundary or identity),
> not a separate finding. Implement it inside T2's step 1: bound the walk-up at
> the git repo root (`git rev-parse --show-toplevel`), and fall through to
> Step 1.2/1.3 when the walk would leave the repository.

> **[Amendment to T3 — `env_lane`'s schema contradicts where the lane lives]**
> `references/lifecycle.md:14` constrains `env_lane` to a *"repo-root-relative
> path to the pinned uv lane,"* where `repo_root` is the **study's** repo. But
> SKILL.md Step 2 places the lane in the dsh-rigorquant checkout — a different
> repository in every install path except developing rigorquant itself, and one
> that does not exist at all for bundle users (T3).
>
> The two constraints are jointly satisfiable only when the study repo *is* the
> framework checkout. An agent following the schema literally records either a
> fragile `../dsh-rigorquant/env` escape or a bare `env` that resolves nowhere,
> and Step 2's fallback then `uv sync`s a stray lane inside the user's project.
>
> This is the schema half of T3 and was recommended there but never applied.
> Implement both halves together: ship the lane under a stable anchor
> (`$DSH_HOME/share/rigorquant`), and change the schema to permit an absolute
> path or a documented anchor scheme. Mirror the wording in SKILL.md Step 2 so
> the two files stop disagreeing.

> **[Amendment to Verdict 12 — two concrete schema instances, one new mechanism]**
> Two cloud findings are instances of finding 12 rather than new defects, but
> both carry detail worth keeping in the schema work:
>
> 1. **`mode` mixes an enum literal with a placeholder pattern**
>    (`lifecycle.md:12`: `"repo-root | studies/<slug>"`). Every other
>    pipe-separated field in the same schema uses clean literals, and every
>    `<...>` elsewhere is an interpolation placeholder. Two agents will
>    reasonably store different values. Use `"repo-root" | "multi-study"` and
>    put the location semantics in prose.
> 2. **`registry.json` is still singular** (`lifecycle.md:47-50`) while
>    `study.json` now formalizes plural `subproblems`, and SKILL.md:76 places
>    exactly one registry at the study root. The **new mechanism**: the
>    3-consecutive-round BLOCKED counter (`lifecycle.md:77-78`) becomes
>    *unreconstructable* when the orchestrator alternates subproblems, because
>    each synthesis overwrites the previous subproblem's `blockedReason` state.
>    The termination rule silently stops working on exactly the multi-subproblem
>    studies intake is designed to produce. Reshape to a subproblems map keyed
>    by `SPn`.

> **[Amendment to Verdict 12 — `env_lane` is persisted before it is known]**
> SKILL.md:66 tells Step 1.4 to persist `env_lane` at study creation, but Step 2
> is the only place it is resolved, and SKILL.md:25 requires Steps 0–2 to run in
> order. Drop `env_lane` from Step 1.4's persist list, or mark it deferred:
> *"Persist mode, slug, and `repo_root` (`env_lane` is added by Step 2)."*

## Partly rejected

> **[Verdict on the layout-drift finding — ACCEPT the drift, REJECT the premise]**
> **Accept:** the durable-deliverable enumerations genuinely disagree across
> three documents — `README.md`/`README.zh-CN.md` list 6, `docs/architecture.md`
> decision 12 lists 7 (adds README), and SKILL.md's tree shows 9 (adds README.md
> and `.gitignore`). Align them, with SKILL.md canonical since it is what the
> agent builds from. Note that Verdict T5 may rename the README entry, so
> sequence this after T5 to avoid aligning twice.
>
> **Reject:** the claim that `studies/` does not exist in the framework repo.
> It existed as the dogfood study `studies/rq-convex-sampling-01/`, which has
> since moved to `/Users/linxi/gits/rigorquant_studies/0001_rq-convex-sampling-01/`
> (this checkout is kept plugin-only); the cloud checkout simply had no
> untracked files. The reviewer's underlying discomfort is still worth one
> clarifying word, though: `studies/` is neither tracked nor listed in
> `package.json` `files`, so a "Repository layout" block that lists it
> alongside shipped assets does conflate what the framework distributes with
> what a checkout happens to be running. Annotate it inline rather than
> removing it.

## What this pass tells us about the process

> **[Verdict — evidence for finding 4, not a separate finding]**
> Three human-directed reviewers and one automated multi-agent pass have now
> produced roughly thirty findings against this repository. **Not one was
> produced by anything executable.** Every finding required a reader. The single
> highest-value item in this pass (T4) turns on a gitignore anchoring rule that
> a two-line test settles definitively and that four readers had missed.
>
> Treat this as the strongest available argument for prioritizing finding 4 and
> the checker CLI. Record it in the checker's design rationale: the class of
> defect this repository actually produces is not subtle mathematics, it is
> unenforced consistency between documents and between a document and a
> filesystem. Those are cheap to test and, as demonstrated, expensive to review.

---

## Pass 5 — the honesty gate did not hold (2026-08-15)

The prior passes closed on a prediction: *"the class of defect this repository
actually produces is not subtle mathematics, it is unenforced consistency
between documents and between a document and a filesystem."* This pass ran the
gates instead of reading them, and the prediction held — including for the
checker that was built to prevent it.

### The finding that mattered

A study with an empty `derivations/`, `outputs: []` on both validity stages, a
one-line adversary report, and a paper whose body read *"This paper says
nothing."* was accepted:

```
PASS -- state valid; declared status 'PASS' has complete evidence.   (exit 0)
```

Every gate that let it through was a keyword search over a corpus that
**included `study.json` itself**, so the study vouched for its own evidence; or
a substring test (`'"passed"'` in the registry text) where a parse was needed;
or a check whose "outputs missing" loop was vacuous on an empty list. The
no-overclaim rule only ever looked for `formally verified`, so a paper asserting
*"certificate-checked and independently re-derived"* with nothing behind it
passed as well.

### Structural findings

1. **Two validators.** `scripts/rq_check.py` (320 lines) and the skill's copy
   (646 lines) had become different programs returning opposite verdicts on the
   same study; neither was a superset. Six documents invoked
   `scripts/rq_check.py`, a path that does not exist after `install.sh`.
2. **The schemas contradicted the skill.** `schemas/study.schema.json` had
   `additionalProperties: false` and defined neither `broad_criterion`,
   `deliverables`, `validity_stages`, nor the sub-problem `stage` on which the
   whole coverage gate rests. Every `study.json` the skill mandated was invalid
   against the repository's own schema, and `install.sh` never shipped it.
3. **One study hard-coded into a general framework.** `deliverables.md` required
   *every* study's slides to carry convex-body, TV-distance and oracle-model
   background frames and named counterexamples from `rq-convex-sampling-01`;
   `rq_check.py`'s symbol registry was that study's notation. For the
   portfolio-optimization use case on the README's first line, the document gate
   was inert.
4. **Documented enforcement that did not exist**: tolerance reconciliation
   ("the checker rejects a mismatch"), summary-vs-artifact matching, the
   conditional symbol audit (the code only checked keys a spec listed), the
   audience statement (skipped entirely when the spec had no `sentence`), the
   report `lifecycle.md` said to ship, and a "three tiers" block that had listed
   two since it was written.
5. **`docs/architecture.md` decision 8** recorded `maxDepth: 0` for the
   delegation tools; the preset uses `1`, and `0` blocks all delegation.
6. Compilation ran in-place, leaving `.aux/.log/.pdf` in the committed
   `artifacts/` tree; `claiming_pass` matched `"PASS" in status`, so
   `"no PASS yet"` tripped every PASS gate. A pre-existing inverted check in the
   HTML balance parser required `<html>` to be left *unclosed*.

### Verdicts — all applied

One validator, in the skill, loading the schemas that sit beside it. Evidence
read from `audits/`/`derivations/`/`artifacts/` and never from `study.json`.
The registry parsed, not grepped. Stage outputs required non-empty and resolved
on disk. All four evidence levels covered by the no-overclaim rule. Sections
required as real headings. The symbol registry split into a small cross-domain
default plus a per-study `symbols` map in the audience spec. Compilation on a
throwaway copy. `--out` restoring the report. The three architectural rules are
recorded as decision 13 in `docs/architecture.md`.

### The change that makes this pass different

`tests/` — 57 tests, of which 23 fail against the pre-fix validator. The
centrepiece is the forged study above, which must FAIL, and
`tests/test_repo_consistency.py` asserts the things four human passes had to
catch by reading: one validator, one schema, invocations that resolve, layout
blocks that match the filesystem, `lifecycle.md`'s hand-written schema mirror
agreeing with the schema that actually runs, and no study-specific notation in
the validator. CI runs them, installs the preset, and checks the installed
layout is the tested layout.

This closes the recommendation the previous pass opened with. The next finding
against this repository should come from a red test, not a reader.
