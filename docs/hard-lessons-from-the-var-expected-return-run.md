# Hard lessons from the 20260820_var-expected-return-term run

*How an 8-round study burned its budget on three structural loops, and the
procedural rules that prevent each one. Written to be implemented by another
agent: every lesson has a symptom, a root cause, a rule, suggested wording for
this repository, and a worked example from the run.*

Source run: `studies/20260820_var-expected-return-term` (repo
`rigorquant_studies`), a VaR drift-modelling literature + specification study.
Outcome: research complete and validator-green; stage-3 claim and both
deliverables **never formally PASSed**, not because the content failed its
gates but because three structural loops consumed the budget and six delegated
agents produced verdict *data* without ever writing the verdict *reports*.

This document is a diagnosis and a patch list. The token-economy decisions
(17–18 in `docs/architecture.md`) fix the *meter*; this file fixes the
*structure*. Budget numbers cap how much a loop burns; only procedural rules
prevent the loop from starting.

---

## 1. The run, in one paragraph

The study's stage-3 claim went through **six adversarial certification rounds**
(rounds 2–6 of an 8-round budget). Each round found a genuine defect:
interval-independence missing → input-truth hypothesis missing → funding
omitted from all four displayed formulas → factor-map hypothesis missing →
BH Euler residual using the log rate instead of the simple funding return →
more. Every fix was applied; every fix triggered a re-certification; every
re-certification found the next defect. Separately, four certifier agents and
two document adversaries produced complete structured verdicts — 36/36 cells
reproduced, attack ledgers, funding-case values — and **never wrote the report
files** those verdicts were supposed to become, so the orchestrator waited on
prose that did not exist. A third loop was the stale-snapshot one: agents
re-audited old hashes ("audited source is unchanged from the prior snapshot")
and the orchestrator's own follow-up messages to finished agents produced
re-reports describing documents that no longer existed.

None of this was the content's fault. The research derivations survived every
audit. The loops were procedural.

---

## 2. Failure catalogue — evidence and root cause

| # | Symptom | Root cause | Existing rule that should have caught it | Why it didn't |
|---|---|---|---|---|
| F1 | Six certification rounds on one claim | Orchestrator patched the general case instead of narrowing scope; each round produced a *new* gap, so the "same gap 3 rounds → BLOCKED" rule never fired | BLOCKED fires on the *gap*, not the *claim* | New gap each round = "not blocked", so patching continued |
| F2 | Six agents produced verdict JSON but no report | Delegation briefs said "write a report" but the report was never made the deliverable; the orchestrator waited | None | The rule "final message must carry the verdict" existed nowhere |
| F3 | "Source unchanged from prior snapshot" repeated | Orchestrator messaged a running/finished agent; queued messages produced stale re-audits | None | No "never message an in-flight or settled agent mid-audit" rule |
| F4 | Concurrent edits invalidated an audit's hash | Orchestrator edited the document while the certifier was reading it | None (freeze was improvised mid-run, worked when applied) | No freeze-on-audit rule |
| F5 | The claim's byte-exact text changed under the auditors (1329 → 1448 bytes) | The record's own claim contained the defect the certifiers found; correcting it invalidated every prior byte comparison | None | No "the record is the source of truth; edits to load-bearing text reopen certification" rule |
| F6 | The orchestrator declared "stage-3 restored" before the ruling landed | Orchestrator certified its own repair on its own summary | Producer ≠ checker, but the producer applied it to *status prose* | Status strings were outside the checkable artifacts |
| F7 | The orchestrator's own generator emitted a wrong table cell (p-clip) | A defensive `min(p, 0.4999)` clipped a valid endpoint | None | No "orchestrator-produced numbers are adversarial-audited like agent-produced ones" rule |
| F8 | Artifacts were "structurally valid, narratively empty" | Subagents wrote to validator gates (sections, notation, citations) not to readers | Document-adversary gate exists | The gate ran *after* three rounds of mechanical patching; the orchestrator never read the artifacts as prose until the human did |
| F9 | Mid-run schema change broke the slug | The skill was reissued with a stricter slug pattern mid-session | None | No "pin the schema at intake" rule |

---

## 3. The lessons — each with the rule, reasoning, wording, and worked example

### L1 — Narrow before patch (the certification loop)

**Symptom.** One claim consumed rounds 2–6. The orchestrator knew the pattern
by round 3 ("the spec asserts conventions compose when they only compose in
the linear case") and even wrote the correct fix — *narrow the declared scope
to the linear case* — but kept patching the general case instead.

**Root cause.** The BLOCKED rule keys on the *gap* ("same exact gap for 3
rounds"), so a run of *different* gaps is never blocked, and patching is never
forced to stop. The correct unit is the *claim*.

**Rule.** *After two consecutive NEEDS-EDITS on the same claim or section, the
next submission MUST either (a) narrow the claim's declared scope to what is
certified, or (b) declare BLOCKED with the exact gap. A re-patch that changes
the mechanism but not the scope is refused.*

**Reasoning.** Repeated independent failures on one claim are evidence the
claim's scope exceeds what is provable — not that the next patch will land.
Narrowing is a strictly cheaper and more honest exit than a sixth patch:
narrowed claims pass; patched-then-rejected claims burn a round each.

**Suggested wording for `references/lifecycle.md` (BLOCKED section):**

> BLOCKED is keyed on the *claim*, not the gap. Two consecutive NEEDS-EDITS on
> the same claim or section require the next round to either narrow the
> claim's declared scope or declare BLOCKED with the exact gap; a re-patch
> that changes only the mechanism, not the scope, is a defect. Rationale:
> repeated independent failures on one claim are evidence of over-scoping,
> and narrowing is cheaper than the next patch.

**Worked example.** The §8 claim's scope should have been narrowed after the
round-3 NEEDS-EDITS to: *"the drift-component aggregation is exact under the
linear BH convention; the nonlinear conventions are separately derived results
with individually stated hypotheses."* That version had a passing path. The
general version did not, and never will within budget.

---

### L2 — Report-first delegation (the report-writing failure)

**Symptom.** Six agents produced complete verdict JSON (36/36 cells, funding
cases, attack ledgers) and no report. The orchestrator waited, then
re-dispatched, then eventually learned to read the JSON. Each wait was a dead
round.

**Root cause.** Briefs said "write a report" but the report was not made the
*deliverable*; nothing checked for it; nothing time-boxed it.

**Rule.** *A delegated verdict is a single artifact: the report with the
`VERDICT:` line. The JSON is a side effect. A run whose final message lacks the
verdict line is a failed run: read its interim artifacts once, record what the
structured data establishes, and do not re-dispatch for prose.*

**Reasoning.** The verdict is the structured data. Transcribing an independent
agent's structured verdict into a report file is *transcription*, not
self-certification — the producer≠checker constraint is about who *judges*,
not who *files*. Waiting for an agent to convert data into prose is pure
overhead.

**Suggested wording for `references/protocol.md` (delegation):**

> The adversarial verdict is structured data; the prose report is archival.
> Every audit/certification brief states the deliverable as "the report,
> ending with `VERDICT: PASS` or `VERDICT: NEEDS-EDITS`", and the orchestrator
> treats a settled run without the verdict line as a failed run: read the
> results JSON once, record the verdict it establishes, and do not re-dispatch
> for prose. The orchestrator may transcribe an independent agent's structured
> verdict into the report file; transcription is not certification.

**Worked example.** The round-5 certifier's results JSON contained the full
verdict; the report never landed. The orchestrator read the JSON, applied the
five successful attacks as fixes, and proceeded. That is the correct pattern
and it should be the default, not the last resort.

---

### L3 — Freeze during audit; never message an in-flight agent (the stale-snapshot loop)

**Symptom.** "Audited source is unchanged from the prior snapshot" — repeatedly
— and report hashes that did not match the files. Concurrent edits during
audits invalidated digests; queued follow-up messages produced re-reports of
dead documents.

**Root cause.** The orchestrator edited documents under audit and messaged
agents mid-flight; nothing enforced immutability of the audited object.

**Rule.** *An artifact under adversarial audit is read-only until the verdict
lands. The verdict is hash-bound to the audited snapshot. Follow-up messages
to a settled or running agent are prohibited until it settles; a settled
agent's queued messages are stale by construction and are discarded without
action.*

**Reasoning.** A hash-bound verdict is the only way a later reader (or a later
orchestrator) can tell which document a verdict judged. The freeze costs
nothing and eliminates the whole class of "is this finding about the current
file?" disputes — which were a large fraction of the run's overhead.

**Suggested wording for `references/deliverables.md` or `protocol.md`:**

> Freeze on audit: an artifact under adversarial review is read-only until
> the verdict lands, and the verdict records the audited snapshot's SHA-256.
> Do not send follow-up messages to a settled or running agent; queued
> messages delivered after settlement describe a prior state and are
> discarded without action.

**Worked example.** The SP6 freeze at hash `723662c7` worked exactly as
designed: the round-4 report was bound to it, and later stale reports could be
recognised instantly as describing a dead snapshot. The slide-deck audits
suffered because the orchestrator kept editing between passes — the fix is to
make the freeze mandatory, not improvised.

---

### L4 — The verdict is not the status; status waits for the verdict (the self-certification-by-prose error)

**Symptom.** The orchestrator wrote "stage-3 restored on the round-4
certification" into `study.json.status` before the round-4 report existed. The
report then ruled `NO`. The audit recorded the status string as a separate
killed claim.

**Root cause.** Producer≠checker was respected for mathematics but not for
*status prose*: the orchestrator certified its own repair in a status field.

**Rule.** *No status string may assert a certification outcome that no
independent verdict has established. Status is written from verdicts, never
before them; a verdictless status claim is a defect and the validator or the
next auditor should flag it.*

**Reasoning.** Status prose is what a resumed session reads first. If it lies,
every subsequent decision inherits the lie. The fix costs one sentence of
discipline.

**Worked example.** The corrected pattern, which the run eventually used:
*"stage-3 recorded at falsification-surviving **on the round-4 certification of
frozen hash X**; the round-5 re-certification rules NEEDS-EDITS on items 1–3,
all now fixed; stage-3 PROVISIONAL pending round-6."* Every clause names its
verdict.

---

### L5 — Orchestrator-produced numbers are audited like agent-produced numbers

**Symptom.** The orchestrator's generator emitted a wrong §6 table cell
(`p`-clip manufactured a −0.00025 error in a table described as
"machine-verified"), and a verification script fed the wrong funding gross
before being corrected.

**Root cause.** Producer≠checker was applied to agents, not to the
orchestrator's own outputs. Self-verification of one's own arithmetic is
exactly the failure mode the constraint exists to prevent.

**Rule.** *Anything the orchestrator produces that becomes evidence — a
generator, a table, a verification script, a status claim — goes through the
same adversarial check as agent output. The cheapest form: a second instrument
recomputes the cells; a generator that emits its own tables cannot disagree
with its formula.*

**Reasoning.** This run's error ledger was roughly half orchestrator errors.
Every one of them cost a certification round. The asymmetry — agents audited,
orchestrator trusted — was the single largest avoidable cost.

**Worked example.** The §6 tables were eventually *emitted by a generator
script* rather than typed; the adversary then recomputed all 36 cells and
found one discrepancy — which was in the generator itself. The generator
pattern (machine-emitted tables) is the right one; the residual gap was that
the generator was not audited like a third-party artifact.

---

### L6 — The record is the source of truth; edits to load-bearing text reopen certification

**Symptom.** The stage-3 claim field held the defect the certifiers kept
finding (`r_f` as the BH simple funding residual). Correcting it changed the
byte length (1329 → 1448) and invalidated every earlier byte-exact comparison.

**Root cause.** Load-bearing text existed in two places (the record and the
documents) and the record's copy was not treated as the arbiter.

**Rule.** *Load-bearing text — claims, audience sentences, evidence levels —
lives once, in the state file, and the documents quote it. A change to such
text reopens the certification it participates in; the change is recorded with
its reason and its new digest.*

**Reasoning.** The run's cheapest and most robust verification was the diff of
the paper's §8 against the claim field in `study.json`. That worked because
the text existed in the state file. Keeping it in only one place makes the
diff impossible; changing it silently makes the diff lie.

---

### L7 — Schema and tool versions are pinned at intake

**Symptom.** The skill was reissued mid-run with a stricter slug pattern; the
study's slug broke validation at the end.

**Rule.** *At intake, record the schema and validator digests; a mid-run
reissue that rejects the study is a re-intake event, not an on-the-fly
repair.*

**Worked example.** The slug fix was correct and cheap; the point is that it
should never have been needed — the intake should have pinned what the schema
would accept.

---

### L8 — Documents are written for readers, then gated

**Symptom.** Artifacts written by subagents against validator gates
(sections, notation, citations) were "structurally valid, narratively empty";
the human review found them unusable, matching the document adversaries'
verdicts which had been recorded but not acted on.

**Rule.** *Prose deliverables are written by whoever holds the narrative (the
orchestrator, or a writer whose output the orchestrator reads as prose before
the gate). The document-adversary pass budget is capped (two); the gate exists
to verify, not to iterate the document into existence.*

**Reasoning.** The document adversaries did their job — they predicted the
human review almost exactly. The failure was that their verdicts were
*recorded and not fixed* because the budget had been consumed by the
certification loop. Cap the adversary passes, and fix the narrative before
the first pass, not after the third.

---

## 4. Implementation checklist for the next agent

Ordered by cost/benefit:

1. **`references/lifecycle.md`** — add the L1 claim-keyed BLOCKED rule
   (narrow-before-patch) and the L4 status-waits-for-verdict rule.
2. **`references/protocol.md`** — add L2 report-first delegation
   (verdict line is the deliverable; JSON is data; transcription is not
   certification) and L3 freeze-on-audit + no-message-in-flight.
3. **`references/deliverables.md`** — add the document-adversary pass cap (2)
   and the narrative-first authoring requirement (L8).
4. **`docs/architecture.md`** — record Decisions 19–20: claim-keyed blocking,
   and verdict-data-as-deliverable.
5. **`rq_check.py`** — two cheap checks: (a) a `status` string containing a
   certification claim must reference a verdict file that exists;
   (b) a study whose stage-3 claim field was edited after its last audit
   record is flagged "needs re-certification" (compare a recorded digest).
6. **Schema** — the YYYYMMDD slug pattern is already enforced (Decision 17);
   add a note that intake records the schema digest (L7).

## 5. What NOT to do

- Do not add a rule that blocks all re-certification: the certifiers found
  genuine defects every round, and the first three rounds were the run's most
  valuable work. The problem was rounds 4–6, where the fixes should have been
  a scope narrowing, not a re-patch.
- Do not make the orchestrator's verdict reading a free pass: reading the
  structured data is only legitimate because the data came from an
  independent agent. The orchestrator's *own* numbers still need a second
  instrument (L5).
- Do not remove the document-adversary gate: it correctly predicted the
  human review. Cap it, feed it better documents, but keep it.

## 6. Measure of success

A study that hits any of these loops should now fail *fast and cheap*:

- Certification loop → claim-keyed BLOCKED after two NEEDS-EDITS, with a
  narrowed claim, inside budget.
- Report-writing failure → the orchestrator reads the verdict JSON once,
  records it, and never waits for prose; zero dead rounds.
- Stale-snapshot loop → impossible by construction: freeze on audit, no
  messages in flight, hash-bound verdicts.
- Status overclaims → validator-refusable.
- Orchestrator arithmetic → second-instrument checked, like everything else.

The 20260820 run's research was sound; its budget was consumed by process.
These rules convert that process into procedure.
