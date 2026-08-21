# RigorQuant architecture — the grilled decision record

## Sources studied

- **Shanmu Jin's Crouzeix run** (2026-07-30): full prompt at
  https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt
  — epistemic isolation, diverse multiagent portfolio with an approach-family
  registry, adversarial counterexample-only audit, concrete-output discipline,
  persistence, terminal honesty. Verification gate: Lean 4 + pinned Mathlib,
  axiom audit (trust boundary `propext`/`Classical.choice`/`Quot.sound`, no
  `sorry`/`admit`), manuscript pinned by SHA-256 and mapped line-by-line to
  Lean declarations.
- **Terence Tao**: Blueprint + Lean formalization (PFR); the Equational
  Theories project (SAT solvers + Vampire/EProver grinding edges, humans/AI on
  the interesting nodes); frontier models as proposal generators on Erdős
  problems, humans verifying.

## Decisions (grilled with the user)

1. **Deliverable** — a framework (preset + skill + compute lanes) enabling any
   model to run long, difficult mathematical tasks **unattended within a single
   live session**; problems are empirical/computational
   (econ/finance/portfolio/simulation), not abstract proof. Crossing a session
   boundary disarms the goal and needs one human turn to re-arm (decision 10).
2. **Rigor gate** — hybrid: falsification by default; escalation to exact/
   formal verification when correctness hinges on an unproven claim.
3. **Check battery** — (A) closed-form equality, (B) exact invariants,
   (C) analytic bounds, (D) staged statistical hardening; on simplified/special
   cases BEFORE numerical implementation. The battery is a **reference-case
   sanity gate**, not a general-validity proof; general validity is established
   in explicit stages (see the skill's references/lifecycle.md).
4. **Trust** — two tracks (method open / ground-truth re-derived twice by
   different means) + adversarial audit; counterexample-only elimination; "a
   producer cannot certify its own output". Context isolation between the root
   and its subagents is harness-enforced; web access, filesystem scope, and
   recursion are **procedural** (per-role delegation tools), not a "wall".
5. **Compute substrate** — pinned uv Python lane (sympy/mpmath/cvxpy/hypothesis/
   jax) as default; **jacobian MCP as the independent escalation verifier** —
   dual verification, jacobian kept as escalation only. The `mcp-jacobian` row
   ships **disabled** and the command **pinned** (`jacobian@0.12.0`) so nothing
   runs at mount time; provisioning is approval-gated.
6. **Stochastic convention** — fixed seed + LLN: sampling error against the
   analytic mean must shrink (≈ C/√N) as N grows. Seeded, environment-pinned
   replay — not portable bit-identity.
7. **Isolation** — track-split: method track open (existing results allowed),
   ground-truth track re-derives; orchestrator-detected novelty toggle flips
   the method track to full Jin isolation (no web, no prior context, no local
   files). These are procedural separations; only context isolation is
   harness-enforced.
8. **Multi-agent mechanism** — DSH-native: per-role delegation tools
   (`subagent` explorer, `subagent_ground_truth` oracle with `web_search`
   denied, `subagent_adversary`; each `maxDepth: 1`, which permits exactly one
   level of delegation — a child is always at depth ≥ 1, so `maxDepth: 0` would
   block delegation entirely) + `workflow` fan-out with
   JSON schemas + goal-round driver; registry/journal files are the cross-round
   memory. `subagent_fork` is not used for track work.
9. **Model routing** — one model everywhere (user's choice); reasoning-effort
   knob available per role; independence comes from context separation.
10. **Lifecycle** — PASS → auto-implement under branch/worktree + frozen write
    scope + rollback, then proceed; BLOCKED → same exact gap 3 consecutive
    rounds → deliver strongest derivation + exact gap; UNKNOWN → recorded when
    neither proof nor counterexample lands; BUDGET → 5 orchestrator rounds →
    checkpoint + report. One task-level goal (no per-sub-problem goals); budget
    fields (`max_cost_usd`, `max_wall_minutes`) may be set. Resuming across a
    session needs one human turn.
11. **Publishing** — repo distributes a bundle (package.json
    `dsh.bundle.patch` + cordis.patch.yml registering the skill), an agent
    preset + bundled skill (install.sh), MIT, `dsh-plugin` GitHub topic —
    compliant with the awesome-list `dsh plugin add` convention. The npm bundle
    ships `env/` and `mcp/`; `install.sh` anchors the compute lane at
    `$DSH_HOME/share/rigorquant`.
12. **Workspace** — a **study** is the self-contained work unit: one
    rigorquant task in one directory with an identical internal structure
    everywhere. Two modes, implied by location, no config flag: **Mode A —
    one study per repo** (`study.json` at repo root) and **Mode B — multiple
    studies per repo** (`studies/<slug>/study.json`, roster derived from
    `studies/*/study.json`). Durable deliverables (study.json, STUDY.md,
    registry.json, journal, derivations/, audits/, artifacts/) are committed;
    ALL scratch lives in `interim/` (explorer-reports, gt-scripts, tmp),
    gitignored via a study-local `.gitignore`. Intake resolves the study root
    by detection first (bounded at the git root, rejecting symlinks) and asks
    the user at most ONE question (mode + slug) when creating a study — resumed
    studies ask nothing, keeping runs unattended within the session. Supersedes
    the legacy hidden `.rigorquant/` layout, which conflated deliverables with
    scratch and could not hold multiple studies.

## Review amendments

The four-pass repository review ([docs/repository-review.md](repository-review.md))
recorded accepted verdicts that amend decisions 1 (unattended scope), 3/6
(sanity gate + statistical criteria), 4/7/8 (isolation language + per-role
tools), 5 (opt-in, pinned jacobian), 10 (one goal, auto-implement safety), and
11/12 (bundle contents + workspace). Those verdicts are the source of truth for
the wording above; the checker CLI and JSON Schemas they require ship inside the
skill, at `skills/rigorquant/scripts/` and `skills/rigorquant/schemas/`.

## Decision 13 — the checker is the honesty boundary

A later review demonstrated that a study with an empty `derivations/`, empty
stage `outputs`, a one-line adversary report and a paper reading "This paper
says nothing" was certified `PASS -- complete evidence`. Three rules follow, and
they bind every future change to the checker:

1. **A study may not vouch for itself.** Every evidence check reads
   `audits/`, `derivations/`, `artifacts/` — never `study.json`. A declaration
   states what was promised; only the record states what was done.
2. **Parse, never grep.** Registry state is read as JSON and traversed;
   `"passed"` appearing somewhere in the file is not a passed route.
3. **One validator, one schema, both tested.** A second copy of either is how
   the two silently diverged into different programs. `tests/` enforces this,
   and the schemas are what the validator actually loads.

## Decision 14 — literature lane

A new literature-research lane answers "what is settled / impossible / open /
current" before compute is spent, and a membrane exports ONLY verified negatives
(proven impossibilities) to the novel lane so it stays un-anchored. The lane is
a grad-student-style citation-graph traversal (backward references + forward
citations + related work + surveys), walled per line, with an independent
literature adversary that re-retrieves each load-bearing claim and certifies
validity + freshness (version/venue/retraction/supersession). Tooling is two
vendored skills (arxiv and academic-paper-search — both MIT; each skill's own
vendoring record carries its provenance) plus a tiered retriever (author page →
open repos/Unpaywall → preprint → OpenAlex/CORE → user-supplied mirrors,
disabled by default). Thoroughness outranks speed (10+ hr runs welcome); the
completeness gate — not the budget ceiling — is the finish line. The field
procedure lives in the `literature` skill; this record owns the decisions.

**Locked constraints.** These are the user decisions the implementation is
bound by, and they outlive any particular gate:

| # | Constraint |
|---|---|
| C1 | The blind lane keeps `bash`. Blindness is **tool-enforced** for web_search/web_fetch and delegation, **procedural + audited** for no-curl and no-cross-lane-read. Never described as a "wall"; the residual holes are named below. |
| C2 | The blind lane gets **delegation denied outright**, not merely capped by depth. Blind = the ground-truth oracle (always) + the explorer after the novelty toggle. A per-role network sandbox in DSH core is the future upgrade path. |
| C3 | A **verified negative** is a *mathematically proven* impossibility, falsehood, or known-intractability. Expert opinion, "big names think it unlikely", and the absence of a known result are NOT negatives. |
| C4 | The literature lane briefs the orchestrator; the orchestrator passes the novel lane **negatives only — never hints, never semi-positives**. |
| C5 | A fully-settled sub-problem gets no novel lane (the answer is a citation). A fully-impossible one gets no novel lane either (the answer is the impossibility, recorded as `status: "impossible"` with its math-lane escalation). |
| C6 | Paywall bypass is permitted and author-hosted copies are first-class. Retrieval is tiered; mirrors are **user-supplied and disabled by default**, with the legal basis recorded by the user. |
| C7 | Thoroughness beats speed; 10+ hours per run is acceptable. The budget is a resume-able safety ceiling, never a finish target. |

**The membrane, as edges.** This is the complete set of crossings; anything not
listed does not cross:

```
orchestrator ──line hypotheses──▶ lit line-agent (walled)
lit line-agent ──dossier──▶ orchestrator (interim/, never read by the novel lane)
orchestrator ──claims list──▶ lit adversary (NOT the dossier prose)
lit adversary ──verdict──▶ orchestrator
orchestrator ──verified negatives (provenance-stripped)──▶ novel lane
```

Open status never crosses (transmitting "this is open" is a hint), settled
results for other sub-problems never cross, and no source, survey, or
related-work framing crosses. The lane certifies "the literature says X, and X
is current" — never "X is true"; that stays with the math lane, and a negative
the study's *conclusion* rests on escalates there before the study may rely on
it.

What is **enforced**, and where: the blind deny lists live in the composition
(`tests/test_blind_deny_list.py`); the known-mark, routed-away-impossible +
math-lane escalation, negative-export subset, completeness-checklist,
refs-seed and fabricated-citation gates live in `rq_check.py`
(`tests/test_literature_gate.py`, `tests/test_integration.py`). The lane's
boundary to the outside world (arXiv, Semantic Scholar, Crossref) is a live
network dependency; `tests/test_retrieval_boundary.py` marks it unverified
rather than reporting "not run" as "passed".

**Residual holes, named.** What stays procedural and audited, because no
per-role network or filesystem scope exists in the spawn provider:

- **Bash-curl.** The blind lane keeps `bash`; nothing prevents it from curling
  `export.arxiv.org`. The math adversary audits for it — a blind output that
  cites or recalls an external result it could not have derived is flagged.
- **Cross-lane filesystem read.** A blind child could read `literature/` or a
  sibling's `interim/lit/`. Same class as the ground-truth hole the repository
  review named; per-line directories and a root-only merge are conventions,
  not enforcement.
- **Paywalled full text.** Where no tier yields full text, the lit adversary
  records `unverifiable` (abstract-only): a lower confidence tier, never
  `verified-current`, never load-bearing.
- **Mirror rot.** Mirrors rotate domains and break unattended runs; the
  user-supplied, empty-by-default tier keeps those URLs out of this repository
  and makes the legal basis a user-owned fact.
- **Hallucinated dossiers.** The lit adversary's independent re-retrieval plus
  the provenance gate is the defense; a dossier may never vouch for itself.
- **Rate limits and resume drift.** Semantic Scholar and Crossref throttle;
  retrieval must back off and record partial sweeps honestly rather than
  fabricate coverage, and a resumed walk re-anchors on the checkpointed
  frontier, with the completeness checklist carrying what was already swept.
- **Cost.** Thoroughness-first runs burn tokens; `max_cost_usd` /
  `max_wall_minutes` remain available as ceilings.

Deferred on purpose: OCR of PDFs (revisit only if abstract-only verification
proves insufficient in practice), and any mirror URL hardcoded in-repo.

## Decision 15 — the retrieval skills install globally

`arxiv` (MIT, vendored verbatim from NousResearch/hermes-agent) and
`academic-paper-search` (user-authored SKILL.md, MIT, author-confirmed
2026-08-16) are useful to any preset, not just this one, and
the literature roles load them by name. `install.sh` therefore copies both to
`$DSH_HOME/skills/` in both install modes and removes them on `--uninstall`,
while the preset keeps its own copies under
`agent-presets/rigorquant/skills/` so a checkout is self-contained. The blind
roles deny `skill` outright, so a global install never widens what the novel
lane can reach.

## Decision 16 — role-routed models (the rq-model-router plugin)

The preset used to run every agent on one model: children inherit the parent's
route, so the session default (flash@high) powered the oracle and the
adversary too. The economics point both ways — most of the agent volume is
divergent exploration and retrieval where flash@high is the right price, while
the two proof-critical roles are exactly where a weak model burns the most
rounds (a wrong derivation or a missed counterexample triggers the whole
BLOCKED loop). Decision: route **per role**, in a plugin, not in the
composition.

- **Mechanism.** The `dsh-rigorquant` package ships a host half that listens
  on the `agent/request` waterfall. It mounts at profile boot, so its listener
  registers before any agent-scoped model-selection listener; the outermost
  listener's rewrite composes last, and the per-role choice — provider, model,
  AND reasoning effort — wins over both the chatbox picker (root) and parent
  inheritance (children). Effort per role is expressible here even though
  `AgentOptions` (the per-tool `agentOptions:` channel) cannot carry it.
- **Role identity.** Every role persona carries a machine-readable tag
  `[[rq:role=<role>]]`. Continuable children persist the persona in their
  first `subagent/descriptor` event; one-shot (foreground) children carry it
  only in the live prompt, so the router probes the child's assembled persona
  section once. Children without a tag — fork, workflow workers, ralph
  rounds — and sessions on other presets are never touched. The `root` role
  applies only to sessions without a `parentSession` (a workflow worker also
  runs under this preset, but it is not the root).
- **Root follows the chatbox.** The root role has no primary by default: the
  picker stays the master switch for the root and for every role left on
  "inherit". Pinning root is a one-select action in the card.
- **One fallback per role.** On a terminal primary failure (no adapter, or an
  HTTP 4xx the route cannot recover from) the router degrades that
  session+role to the role's own fallback and forces exactly one retry. A
  successful assistant step on the fallback — or the TTL (10 min) — restores
  the primary; a failing fallback is never retried again by the router.
- **Persistence and UI.** Choices live in the `rigorquant-models` settings
  namespace (user layer of `settings.yaml`); the browser half renders the
  card in the Plugins settings tab, keyed by that namespace, with model and
  effort dropdowns from the live provider catalog.
- **Shipped defaults.** Oracle and adversary: `deepseek-v4-pro`@high with a
  `deepseek-v4-flash`@low fallback (a fallback is a degrade lane, not a second
  full-price route). Every other role: inherit. Defaults
  assume the `deepseek-official` catalog; a deployment without it overrides
  the row config or the card, and a default that cannot route degrades
  through the same fallback lane (or fails loudly if the fallback cannot
  either).

Guarded by tests: every role persona must keep its tag, and the router's
ROLES list must equal the tagged roles plus `root` — a persona that loses its
tag silently falls back to the session model, which is exactly the failure
class this closes.

## Decision 17 — budgets are finish targets, with explicit escalation

Measured on real runs, the previous framing — "the budget is a resume-able
safety ceiling, never a finish target; 10+ hour runs are expected"
(literature lane), `max_orchestrator_rounds: 5`, fan-out 2–4, and an
unconditional dual ground-truth track — let a single study bill into the
hundreds of millions of metered tokens, dominated by per-step re-sends of a
~9k-token header plus open-ended traversal. Decision: **bounded by default,
escalation is an explicit recorded act.**

- `max_orchestrator_rounds` default 5 → **3**; BUDGET fires at 3 rounds.
- Fan-out default 2–4 explorers → **1–2**; the second ground-truth track is
  mandatory only for **load-bearing** claims (the whole study rests on them),
  never one agent doing both "independent" derivations.
- Literature budget default 8/4/80/8 → **4/3/20/4**. A line concludes at the
  budget with the strongest completed dossier and remaining checklist items
  recorded open. Exceeding the budget requires an explicit user escalation
  recorded in `study.json` `literature.budget` (raising numbers or setting
  `max_cost_usd`); a silent overrun is a defect. `max_wall_minutes` stays
  unset by default (the field remains nullable).
- Compaction fires at **60%** of the routed context window (was 80%) and the
  tool-result pruner retains **4 KiB** per result (was 8 KiB): an earlier,
  smaller compaction shrinks the cached prefix re-sent on every step. The
  model-facing tool catalog itself is host-plane — the heavy tools
  (`workflow`, `ralph`, `ask_user_question`, …) are registered by the profile
  composition, not this preset, so they cannot be trimmed from this
  repository; a session's catalog is the union of host tools + preset rows.
- Journal stays append-only (a rolling journal was considered and rejected:
  the append-only record is the study's audit trail).

## Decision 18 — j-space is unbundled

The j-space cognition suite shipped inside this preset (skill directory,
install.sh wiring, and an inline j-space protocol paragraph in every persona).
It is the user's separate distribution and adds a hard external dependency to
every rigorquant session — including the blind roles (`novel`, `oracle`),
which deny the `skill` tool and can never load it, so the inline block was
pure prompt tax on every one of their requests. Decision: **j-space lives in
its own branch, not here.** The skill directory, its install/uninstall lines,
and all inline persona references are removed; rigorquant no longer mandates
it. Guarded by a consistency test asserting the absence.

## Repo map

```
agent-presets/rigorquant/   the preset: composition + persona + rigorquant skill
  skills/rigorquant/        SKILL.md, references/, scripts/rq_check.py, schemas/
dsh/                        the rq-model-router plugin (host + client halves)
cordis.patch.yml            bundle patch: skill layer + model-router row
env/                        pinned uv compute lane (pyproject + lockfile)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        this record
tests/                      the validator's suite; a forged study must FAIL
install.sh                  installs the preset (or --skill-only) into $DSH_HOME
```

A study folder (`studies/<slug>/` in Mode B, the repo root in Mode A) lives in
the *research* repo, not here: `interim/` inside each is gitignored, everything
else commits.
