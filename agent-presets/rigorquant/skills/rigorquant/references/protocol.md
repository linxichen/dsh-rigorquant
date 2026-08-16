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
   `subagent_novel` (the novelty toggle) and `subagent_ground_truth` (the
   oracle), and both deny `web_search`, `web_fetch`, `skill` and every
   delegation tool in the composition itself. Never ask an open role to
   *pretend* it has no web — call the walled role instead. What that buys is
   partial and must be stated so: context isolation and the web/delegation deny
   lists are enforced, while filesystem scope and `bash`-level network calls
   stay procedural and audited (the residual holes named under Decision 14 in
   docs/architecture.md) — never describe
   them as a "wall". Because `skill` is denied, a blind role cannot load this
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

1. Explorers fan out (blank-context `subagent` calls).
2. Ground-truth track re-derives the check targets twice, independently (two
   separate `subagent_ground_truth` calls, different means).
3. Adversary audits both tracks, runs the battery, hunts counterexamples.
4. Root synthesizes: registry update → block/redirect decisions → PASS or
   relaunch (with new redirections; never an identical relaunch).

Proof and refutation tracks run in parallel: while one agent proves a claim,
another hunts a counterexample. The correct outcome may be impossibility,
non-identifiability, divergence, or a counterexample — record `unknown`
rather than forcing PASS, and tag every claim with its evidence level
(falsification-surviving / independently re-derived / certificate-checked /
formally verified; see lifecycle.md).
