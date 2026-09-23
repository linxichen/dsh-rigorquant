# The search protocol (adapted from Jin's Crouzeix run and Tao's projects)

Primary sources:
- Jin's full prompt: https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt
- Jin's Lean formalization + axiom audit: https://github.com/jinshanmu/CrouzeixConjecture/tree/main/Lean
- Tao's PFR Blueprint tour (blueprint + Lean): https://terrytao.wordpress.com
- Tao's Equational Theories project (SAT/prover-assisted): https://github.com/teorth/equational_theories

## Jin's rules, translated to empirical/computational work

1. **Epistemic isolation where it matters.** For novel sub-problems: no web,
   no prior conversations, no project files. Do **not** assume a complete
   affirmative result exists — prove it or find a counterexample, and record an
   explicit `unknown` if neither lands. (For `known` sub-problems the method
   track stays open — building on existing analytical results is an explicit
   goal.) Isolation is **routed, not requested**: the blind roles are
   `offgrid-<n>` (the OffGridThinker — raw model intelligence plus compute
   tools, no one else's results) and `doublechecker-<n>` (the DoubleChecker).
   The team plugin reads the role from the teammate's name and denies both
   `web_search`, `web_fetch` and `skill`; no teammate can create teammates.
   Never ask an open role to *pretend* it has no web — create the blind role
   instead. What that buys is partial and must be stated so: context
   isolation is the only wall; the web/skill budget is enforced by scope, and
   the guard refuses a web-denied role's network verbs in `bash` (`curl`,
   `wget`, `pip install`, `uv sync|add|pip`) at the call, while filesystem
   scope stays procedural and audited (the residual holes named under
   Decisions 14 and 24 in docs/architecture.md) — never describe the rest as a
   network "wall". Because `skill` is denied, a blind role cannot load this
   file: its persona carries the derivation protocol itself.
2. **Diverse portfolio, no premature convergence.** Begin with genuinely
   different formulations. Do not tell most agents the favored approach.
   Group by mathematical idea in `registry.json`, not by wording. Redirect
   over-crowded families toward underexplored formulations.
3. **Strength-aware progress.** A route that ends at a lemma equivalent in
   strength to the original sub-problem is BLOCKED, not "close". Reductions
   to other unproved conjectures do not count. Fixed-parameter computational
   success does not count.
4. **Counterexample-only elimination.** Adversarial agents check for gaps,
   conditionals, handwaving, and circularity. A route dies only when a
   checker produces a failing case.
5. **Concrete outputs.** Lemmas, equations, constructions, counterexamples.
   Reject status reports, vague optimism, and "routine" claims.
6. **Persistence.** The root repeatedly synthesizes, challenges, redirects,
   and relaunches. Blocked routes reopen only on a materially new mechanism,
   invariant, or construction.
7. **Terminal honesty.** On BLOCKED: report the strongest rigorously proved
   derivation and its exact remaining gap — nothing else.

## Tao's additions

- **Blueprint decomposition:** split a hard claim into a dependency graph of
  lemmas; attack leaves bottom-up; track exactly which nodes are proved. In
  this framework the registry.json entries are the blueprint nodes.
- **Automated checkers as the truth gate:** SAT/SMT/prover/Lean output decides
  truth, never prose. Our equivalents: sympy exact arithmetic, hypothesis
  falsification, jacobian's verified operations, and (escalation) Lean.
- **Many hands, one record:** every round's concrete results append to
  journal.md and registry.json — the workspace IS the collaboration memory.

## The round cycle in full

1. Promise: the orchestrator lays the round out as a task DAG on the board
   (explore per sub-problem → ground-truth per claim → attack per
   sub-problem → certify per round).
2. Fan out: fresh blank-context `explorer-<n>` teammates, one or two per
   `explore` task.
3. Ground-truth: the check targets re-derived twice, independently, for a
   load-bearing claim (two fresh `doublechecker-<n>` teammates, different
   means).
4. Attack: the reused `adversary-<n>` audits both tracks, runs the battery,
   hunts counterexamples.
5. Certify: the orchestrator synthesizes from the study record: registry
   update → block/redirect decisions → PASS or next round (with new
   redirections; never an identical relaunch).

Proof and refutation tracks run in parallel: while one agent proves a claim,
another hunts a counterexample. The correct outcome may be impossibility,
non-identifiability, divergence, or a counterexample — record `unknown`
rather than forcing PASS, and tag every claim with its evidence level
(falsification-surviving / independently re-derived / certificate-checked /
formally verified; see lifecycle.md).

## Delegation discipline (hard-lessons L2, L3, L5, the roster, the pool and the cap)

These rules exist because the 20260820 var-expected-return-term run's budget
was consumed by process, not content: six agents produced complete verdict
JSON without ever writing the reports, queued messages produced stale
re-audits of dead documents, and orchestrator-produced numbers went
unaudited. Decision 24 (docs/architecture.md) carries them onto Agent Teams.

- **Brief contract.** Every brief — a `spawn_teammate` prompt or a later
  `send_message` — names the board **task id** it serves, the **snapshot
  hash** (SHA-256) of every artifact the teammate is to judge, and the
  deliverable. The `spawn_teammate` `description` is the role label only
  (`Explorer`, `DoubleChecker`, `Adversary`, …), never the brief: it is shown
  on the roster, and a brief there leaks the assignment to every reader. The
  teammate claims its task by compare-and-swap (`team_task_update` `claim`
  with the revision from `team_task_get`), works under the task's advisory
  write scope in its role's scratch directory, completes the task, and ends
  its turn with its result as the final message.
- **Verdict-first delegation (L2).** The adversarial verdict is structured
  data; the prose report is archival. Every audit/certification brief states
  the deliverable as *"the report, ending with `VERDICT: PASS` or
  `VERDICT: NEEDS-EDITS`"*, and a teammate delivers that verdict as the
  **final message of its turn**, which wakes the orchestrator. (A teammate may
  also `send_message` the orchestrator — its only legal target — for an
  interim finding or a blocking question.) The orchestrator treats a turn that
  ends without a verdict line — in that final message or written — as a failed
  run: read its results once, record the verdict it establishes, and do not
  re-brief for prose. The orchestrator may transcribe an independent
  teammate's structured verdict into the report file; transcription is not
  certification — the producer≠checker constraint is about who *judges*, not
  who *files*.
- **Freeze on audit; brief, never follow up (L3).** An artifact under
  adversarial review is read-only until the verdict lands, and the verdict
  records the audited snapshot's SHA-256. A hash-bound verdict is the only way
  a later reader can tell which document a verdict judged. A reused teammate
  only ever receives a new hash-bound brief, never a follow-up about an
  artifact under audit, and only while the roster shows it idle or inactive —
  if it is running, wait on it first. A `send_message` whose result says
  `queued` is durable: a queued message is already stored; never resend it.
- **Roster policy.** Fresh per brief: `explorer-<n>`, `offgrid-<n>`,
  `doublechecker-<n>` — blank context is the point, and the two independent
  derivations of a load-bearing claim are two fresh DoubleCheckers with
  different means. Reused across rounds by message: `adversary-<n>`,
  `lit-adversary-<n>`, `doc-adversary-<n>`, and each `lit-line-<n>` (`n` = the
  line number; lines are numbered in creation order, so it is also the
  counter) — their accumulated knowledge is the job — only while idle or
  inactive, under L3. `n` is a per-role counter that only increases within a
  study; on resume `list_agents` shows the highest `n` per role.
- **Fan out is bounded by the live-teammate pool.** The host runs at most
  **eight** live teammates at a time (`maxActiveSubagents`, Plugins →
  Subagent, default 8). Teammates are depth-1 and settle when their turn
  ends, so the pool bounds concurrency, not the study's headcount — but a
  round that creates four literature lines, two explorers and a second
  DoubleChecker at once is seven of the eight slots. Batch Fan out to at most
  eight live teammates: the literature lines, the method work and the
  ground-truth work go in waves rather than in one message. A spawn over the
  bound fails with `ACTIVATION_LIMIT_REACHED`, which reads like a transient
  error and is not one: **wait for a teammate to settle, never retry in a
  loop.** Nothing releases a slot but a teammate finishing, so a retry loop
  spends the budget on the error path. (A literature-heavy study may raise
  the setting instead — that is the operator's change, in Plugins, not the
  orchestrator's.)
- **The teammate cap is a BUDGET outcome.** The team's `maxMembers` is a
  lifetime cap that counts every teammate ever created, failed ones included
  (`install.sh` raises it to 64). A `spawn_teammate` that fails on the cap is
  BUDGET-class: checkpoint the study record, report the cap, end the turn; one
  human turn re-arms (and may raise the override). Never reuse a fresh-per-
  brief role to fit under the cap.
- **Orchestrator-produced numbers are audited like teammate-produced numbers
  (L5).** Anything the orchestrator produces that becomes evidence — a
  generator, a table, a verification script, a status claim — goes through the
  same adversarial check as teammate output. The cheapest form: a second
  instrument recomputes the cells; a generator that emits its own tables
  cannot disagree with its formula.
