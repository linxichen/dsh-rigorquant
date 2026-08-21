# Literature lane

The literature lane answers "what is settled / impossible / open / current"
before compute is spent, and exports ONLY verified negatives (proven
impossibilities) to the novel lane. Locked constraints, membrane edges, and
named residual holes: docs/architecture.md Decision 14. Field procedure: load
the literature skill (skills/literature/SKILL.md).

Key facts (summary only):

- Membrane: only 'impossible' entries, provenance-stripped, cross to the novel
  lane; 'open' and 'settled' never cross. The receiving role is
  `subagent_novel`, whose web/`skill`/delegation deny list is in the
  composition — never an open role asked to pretend.
- Roles: subagent_lit_line (walled traversal) and subagent_lit_adversary
  (independent validity + freshness) — both delegation-denied leaves.
- Artifacts: literature/known-results.json (verified, committed),
  literature/negative-exports.json, literature/completeness.json,
  literature/refs-seed.bib; dossiers in interim/lit/ are advisory.
- Tooling: arxiv (vendored, MIT) + academic-paper-search (tiered retrieval via
  scripts/resolve_tiers.py; mirrors user-supplied via DSH_LIT_MIRRORS, empty by
  default).
- Validator: rq_check.py refuses a 'known' mark without a verified record; an
  `impossible` routing without both a verified impossible record and its
  math-lane escalation; a negative that does not trace to an 'impossible'
  entry; export flags that disagree with the exports file; a missing checklist,
  sweep, or swept line; a phase that under-claims the record; and any bib entry
  (seed or PASS-time) that does not trace to a verified-current, non-open
  record.
- Budget (max_lines / max_depth / max_papers_per_line / max_rounds) is the
  default finish target, not a floor: a line concludes at the budget with the
  strongest completed dossier and its remaining checklist items open. Exceeding
  it requires an explicit user escalation recorded in study.json; the
  completeness checklist gates what a concluded line must have swept.
