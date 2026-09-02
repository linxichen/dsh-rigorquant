---
name: literature
description: >
  RigorQuant literature lane: walled, grad-student-style citation-graph
  traversal per research line, an independent literature adversary for validity
  + freshness, and the verified-negative membrane that keeps the off-grid
  lane (the OffGridThinker) un-anchored. Load for known/novel intake, deep
  literature review, or when the orchestrator needs 'what is settled /
  impossible / open / current'.
---

# Literature lane — operating procedure

Owning decision: docs/architecture.md Decision 14, which holds the locked
constraints (C1-C7), the membrane's crossing edges, and the named residual
holes. This skill is the field procedure; the schemas and rq_check.py are the
enforcement.

## The membrane (non-negotiable)

Only VERIFIED NEGATIVES cross to the off-grid lane. A verified negative is a
mathematically proven impossibility (category 'impossible'), independently
re-retrieved by the lit-adversary, judged load-bearing for an active
sub-problem. It is transmitted provenance-stripped ("closed path, not a
premise and not a clue") — no author, title, or source id. 'open' and 'settled'
never cross. If the study's conclusion would REST on a negative, escalate to the
math lane before relying on it.

## Step 0 — line hypotheses

The orchestrator forms 2–4 crude lines per sub-problem (seed queries, seed
papers, sub-questions) from prior knowledge + one shallow web_search. No line is
told it is favored.

## Step 1 — walled line agents (parallel)

Launch subagent_lit_line per line, blank context, each in its own
interim/lit/<line-slug>/ dir. Per line: resolve the seed (arxiv +
academic-paper-search), read abstract → intro/related work → load-bearing
theorem/method → references, then follow backward (references) and forward
(citations via Semantic Scholar). Deduplicate by arXiv id / DOI / title; a
revisit marks a hub, never a re-read. Write interim/lit/<line-slug>/dossier.json
(schema: schemas/dossier.schema.json). Never read another line's dossier.
Batch independent web queries: on DSH >= 0.1.1-rc.1, one web_search call
accepts a `queries` array (up to the configured `searchMaxQueries`, default 4)
run in parallel and merged — batch rather than serialize; a single-query
schema accepts one query per call.

## Step 2 — literature adversary (independent)

For each line, send the lit-adversary (subagent_lit_adversary) the CLAIMS LIST
only — never the dossier prose. It re-retrieves each load-bearing source itself
and returns one verdict per claim: verified-current | verified-stale |
unverifiable | false-claim, with source id, version, access date, retrieval
method. It certifies "the literature says X and X is current", never "X is true".

## Step 3 — synthesize

The orchestrator merges verdicts into literature/known-results.json (schema:
schemas/known-results.schema.json), keyed by sub-problem id, each entry
settled | impossible | superseded | open with sources. Also write, all four
under literature/ and all four validator-enforced:

- negative-exports.json — the provenance-stripped constraints sent to the
  off-grid lane (schema: schemas/negative-exports.schema.json). Every export must trace
  to an `impossible` entry with a verified-current source, and that entry must
  carry `negative_export: true`: the map and the exports file record ONE fact.
- completeness.json — the per-line checklist (schema:
  schemas/completeness.schema.json), one line per swept research line. A
  sub-problem with a non-open record and no completeness line is refused.
- refs-seed.bib — the verified bibliography seed. Entries whose question is
  still `open` may not appear: the seed carries results, not reading lists.
- study.json `literature.phase` — set `concluded` only when the map holds
  verified state; `not-run`/`running` with verified records is refused. The
  sweep is mandatory at intake: the only way past it is `phase: "skipped"` with
  the user's verbatim assertion in `skip_reason`.

Transmission to the off-grid lane is by tool, not by tone: call
`subagent_offgrid` (the OffGridThinker; web, `skill`, and delegation denied in
the composition) and pass the constraint text only. If a sub-problem's ANSWER
is the impossibility, mark it `status: "impossible"` in study.json and record
the math lane's acceptance in
the entry's `escalation` path — the literature lane certifies that the
literature says X, never that X is true.

## Completeness checklist (anti-premature-termination)

A line may not conclude until the orchestrator records that it swept: forward
citations; related-work sections of every hub; relevant surveys; adjacent fields
named in the hypothesis; retractions (Crossref/Retraction Watch) and newer arXiv
versions; author pages for load-bearing papers; and the frontier with a reason
to stop (or none). "The model finished early" is a failing condition.

## Termination and budget

Done when the adversary certifies every leaf is current, or a foundational sink
/ citation closure is reached. The budget (max_lines / max_depth /
max_papers_per_line / max_rounds) is the **default finish target, not a
floor**: a line concludes at the budget with the strongest completed dossier
and its remaining completeness-checklist items recorded as open. Exceeding the
budget requires an **explicit user escalation** recorded in study.json
(`literature.budget`) — a silent overrun is a defect. Checkpoint map +
frontiers + checklist after every round; a resumed session continues the walk.
When the orchestrator cannot decide (new rounds / conclude / unclear), it is a
HARD STOP: checkpoint and ask the human.

## Retrieval order (executable)

Resolve the best *retrievable* version through the tiers below, in order, and
record which tier won as the source's `retrieval_method`:

```
python3 <academic-paper-search skill dir>/scripts/resolve_tiers.py \
    --doi 10.2307/2975974 [--arxiv 1706.03762] [--title "..."] [--author-page URL]
```

It emits the ordered plan (author-page → open-repo → preprint → openalex →
user-mirror). The mirror tier is EMPTY unless the user sets `DSH_LIT_MIRRORS`;
no mirror endpoint is hardcoded in this repository, and the legal basis for
using one is the user's to record. A paper reachable only as an abstract is
`unverifiable` — a lower confidence tier, never `verified-current`, never
load-bearing.

## Provenance (validator-enforced)

rq_check.py refuses: a 'known' mark without a verified-current record; a
sub-problem routed away as `impossible` without a verified impossible record
AND its math-lane `escalation`; a declared escalation path that does not exist;
a negative export that does not trace to an 'impossible' verified entry; a map
whose `negative_export` flags disagree with the exports file; a missing
completeness checklist, a missing or empty mandatory sweep, or a mapped
sub-problem no line swept; a `literature.phase` that claims less than the record
on disk; and any refs-seed.bib or PASS-time refs.bib entry that does not trace
to a verified-current, non-open record. Dossiers in interim/lit/ are advisory —
never counted as verified records, though a malformed one is still a defect.
