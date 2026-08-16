# Literature Lane — implementation spec

Status: implemented (2026-08-16) · Owning decision: docs/architecture.md
Decision 14; the global skill install is Decision 15
Class: feature (new model-facing capability)

This spec is the authority for the literature-research lane. It states what the
lane does, the information membrane between lanes, the roles and their enforced
vs procedural boundaries, the traversal protocol, the artifacts and schemas, the
tooling (vendored skills + tiered retrieval), the lifecycle/budget model, the
validator gate, and the acceptance criteria that will falsify the
implementation. The implementation itself lives in the repository (composition,
schemas, rq_check.py, tests, and install.sh); this document is the normative
contract that implementation is checked against.

---

## 1. Problem (solution-independent)

A RigorQuant study cannot reliably answer four questions before spending compute:

1. What is **settled** (proven true) for a sub-problem?
2. What is **impossible** (proven false / known-intractractable) for it?
3. What is **open** (neither settled nor impossible)?
4. Of what we cite, what is **still current** (not retracted, superseded, or
   version-stale)?

Today the only web surface is one web_search row (fetch: false), the
method-track explorers do ad-hoc search, the ground-truth track is only
web_search-denied, there is no citation-provenance gate, and a paper that
says "this paper says nothing" can still carry a bibliography. The consequence
is exactly the failure the repository review named: promises stronger than the
tooling enforces, plus a real risk of hallucinated or stale citations passing
the deliverable gate.

The novel lane (ground-truth oracle + post-toggle explorer) must stay
**un-anchored**: it must not be shown sources, known results, or semi-positive
signals, or it will converge on them instead of deriving. The only literature
information that may reach it is a **verified negative** — a mathematically
proven impossibility that saves it from a dead path.

---

## 2. Goals and non-goals

**Goals**

- G1. Exhaustive, grad-student-grade traversal of the research graph for a
  sub-problem: read a paper, follow what it cites (backward), follow who cites
  it (forward), extract related work, and land on surveys/foundational hubs.
- G2. A committed **known-results map** per sub-problem:
  settled | impossible | superseded | open — every entry with provenance and an
  independent adversarial check.
- G3. A **membrane** that exports ONLY verified negatives (proven
  impossibility) to the novel lane, provenance-stripped, never hints or
  semi-positives.
- G4. Independent literature adversarial verification of **validity** (the
  source really states X) and **freshness** (version, venue, retraction,
  supersession).
- G5. A verified refs.bib seed whose entries trace to a fetched record.
- G6. Runs of 10+ hours are welcome; thoroughness outranks speed; a run must
  not conclude because the model got impatient.

**Non-goals**

- Verifying that a literature claim is *mathematically true* — the math lane
  (ground-truth + math adversary + jacobian) owns that. The literature lane
  certifies "the literature says X, and X is current", never "X is true".
- Scraping Google Scholar (no API, bot-hostile, ToS).
- OCR of PDFs in v1 (the vendored arxiv skill lists
  related_skills: [ocr-and-documents]; that is a future lane).
- Any hardcoded pirate mirror URL shipped in-repo (see §9).

---

## 3. Locked constraints (from the grill)

These are the user decisions this spec is bound by; each is restated so the
implementation cannot drift from them.

| # | Constraint |
|---|---|
| C1 | Blind lane keeps bash; blindness is **tool-enforced** for web_search/web_fetch and delegation, **procedural + audited** for no-curl and no-cross-lane-read. Never described as a "wall". Residual holes are named (§13). |
| C2 | Blind lane gets **delegation tools denied outright** (not just blocked by depth). Blind = ground-truth oracle (always) + explorer (post novelty toggle). Tolerated now; a DSH-core per-role network sandbox is the future upgrade path. |
| C3 | A **verified negative** = a *mathematically proven impossibility/falsehood/known-intractability*. Expert opinion, "big names think unlikely", and absence-of-a-known-result are NOT negatives. |
| C4 | The literature lane briefs the orchestrator; the orchestrator passes the novel lane **negatives only — never hints, never semi-positives**. |
| C5 | Fully-settled sub-problem → no novel lane (answer = citation). Fully-impossible sub-problem → no novel lane (answer = the impossibility). |
| C6 | Paywall bypass is permitted; author-hosted copies are a first-class source. Retrieval is tiered; mirrors are **user-supplied, disabled by default**, legal basis recorded (§9). |
| C7 | Thoroughness > speed. 10+ hours per run is acceptable. Budget is a resume-able safety ceiling, never a finish target; the **completeness gate** is the finish line (§10). |

---

## 4. The membrane

The only literature information that crosses into the novel lane is the
**verified-negatives list**. Everything else stays on the literature side.

**Verified negative (normative).** An entry is a verified negative iff all of:

1. Its category is impossible — the source states a **proof** of
   impossibility/falsehood/known-intractability (a theorem, not a conjecture or
   an opinion).
2. The lit-adversary **independently re-retrieved** the source and confirmed it
   states that proof, with version + access date + retrieval method recorded.
3. The orchestrator judged the negative **load-bearing for an active
   sub-problem** (it would otherwise waste novel-lane rounds). Non-load-bearing
   negatives are stored, not transmitted.

**Transmission form.** The novel lane receives each negative as a
provenance-stripped constraint:

> "It is settled that no method with property P exists for inputs in class C.
> Treat this as a closed path, not a premise and not a clue."

No author, no title, no source id crosses the membrane. Provenance stays in the
orchestrator's literature state. If the study's *conclusion* would rest on the
impossibility (rather than merely routing around it), the negative is
**load-bearing** and escalates to the math lane before the study may rely on it.

**What does NOT cross:**

- open status (transmitting "this is open" is a hint).
- settled results for other sub-problems (answer = citation, resolved by the
  orchestrator; never shown to the novel lane).
- any source, survey, or related-work framing.

**Crossing edges (the complete set).**

~~~
orchestrator ──line hypotheses──▶ lit line-agent (walled)
lit line-agent ──dossier──▶ orchestrator (interim/, never read by novel lane)
orchestrator ──claims list──▶ lit adversary (NOT the dossier prose)
lit adversary ──verdict──▶ orchestrator
orchestrator ──verified negatives (provenance-stripped)──▶ novel lane
~~~

---

## 5. Roles and composition (agent.cordis.yml)

Model-facing tool names, not row ids. toolFilter.deny is the enforcement
mechanism; maxDepth: 1 is the absolute delegation cap.

**Blind deny list (shared by both blind roles):**

~~~
deny: [web_search, web_fetch, skill, subagent, subagent_ground_truth,
       subagent_adversary, subagent_fork, workflow, ralph]
~~~

- skill is denied so the blind role cannot load the literature / arxiv /
  academic-paper-search skills. The blind persona is therefore
  **self-contained** (the Jin derivation protocol is embedded in its persona).
- bash, fs, fs-search remain (compute + own scratch). The residual curl and
  cross-lane-read holes are §13.

**Roles.**

| Role | Row | Web | Delegation | Reads | Writes |
|---|---|---|---|---|---|
| Explorer (open method track) | subagent | search+fetch | maxDepth 1 | own scratch | own scratch |
| **Explorer (novel/blind)** | subagent_novel (new) | **denied** | denied | own scratch + negatives | own scratch |
| **Ground-truth oracle (blind)** | subagent_ground_truth | **denied** | denied | own scratch + negatives | own scratch |
| Math adversary | subagent_adversary | search+fetch | maxDepth 1 | both tracks | audit report |
| **Lit line-agent** | subagent_lit_line (new) | search+fetch | denied | own line dir | own line dir + dossier |
| **Lit adversary** | subagent_lit_adversary (new) | search+fetch | denied | claims list only | verdict |

- Ground-truth's current deny: [web_search] becomes the full blind list (adds
  web_fetch, skill, and delegation). web_fetch must be denied because §9
  enables fetch globally.
- The novelty toggle becomes **enforced**: the orchestrator calls
  subagent_novel instead of subagent when a sub-problem flips to full Jin
  isolation, rather than asking an open role to "pretend" it has no web.
- Lit line-agents and the lit adversary are leaves (delegation denied,
  maxDepth: 1) and never see each other's work; cross-line filesystem reads
  are procedural (per-line dirs, root-only merge) — mirroring the method track.

---

## 6. Traversal protocol (the grad-student loop)

**Line hypotheses.** At intake the orchestrator produces 2–8 crude lines of
research per sub-problem — seed queries, seed papers, or named sub-questions —
from its own prior knowledge plus one shallow web_search. These are diverse by
construction; no line is told it is favored.

**Line-agent procedure (per line, walled, one pass is one round):**

1. Resolve the seed to a paper set (arxiv skill / academic-paper-search).
2. For each paper: read abstract → intro/related work → the load-bearing
   theorem/method → its references.
3. Follow **backward** edges (references) and **forward** edges (citations via
   Semantic Scholar), extract the related-work section, and mark surveys and
   highly-cited foundational hubs as attractors.
4. Deduplicate by arXiv id / DOI / normalized title. A revisit marks a **hub**,
   never a re-read.
5. Write a bounded **dossier** (schema §8). Raw PDFs/HTML live only in
   interim/lit/<line>/fetched/; the dossier carries claims + evidence quotes,
   not full texts.

**"The bottom" of a cyclic graph.** Termination is NOT depth. A line is done
when any of:

- **Leaf-currency:** the lit adversary certifies every leaf is current (no
  retraction, no newer version, no later superseding work).
- **Foundational sink:** the line reached classic/textbook results with no
  further load-bearing references.
- **Citation closure:** one round adds no unvisited paper within scope.

**Completeness checklist (anti-premature-termination).** The orchestrator may
not conclude a line until it has recorded, per line, that it:

- swept forward citations (Semantic Scholar), not only references;
- swept the related-work sections of every hub paper;
- found and read the relevant surveys;
- probed adjacent fields named in the line hypothesis;
- checked retractions (Crossref/Retraction Watch) and newer arXiv versions;
- checked author personal/institutional pages for the load-bearing papers;
- recorded the frontier (unvisited papers) with a reason to stop, or none.

The checklist is a recorded artifact the lit adversary samples, and it is the
mechanism that makes "the model finished early" a *failing* condition, not the
default.

---

## 7. Literature adversary (validity + freshness)

The lit adversary is the producer ≠ checker guarantee, applied to literature.

**Input.** A **claims list** per line — each claim carries the claimed source id
and version. The adversary never receives the dossier prose (a dossier may not
vouch for itself).

**Procedure.** For every load-bearing claim it **independently re-retrieves**
the source (its own search/fetch, not the line-agent's copy) and checks:

| Check | Question | Signals / tooling |
|---|---|---|
| Validity | Does the source actually state the claim? | Full text / abstract; quote required |
| Version | Is this the current version? | arXiv v1 vs latest, published venue |
| Retraction | Was it retracted/withdrawn? | Crossref, Retraction Watch |
| Supersession | Did later work disprove/generalize it? | forward citations (Semantic Scholar) |

Verdict per claim: verified-current, verified-stale (with the newer state),
unverifiable (paywalled and only abstract reachable — lower confidence tier,
never "current"), or false-claim (source does not state it).

**Boundary.** The lit adversary certifies "the literature says X, and X is
current." It does NOT certify "X is true." A literature claim that becomes
load-bearing for the *study's own method* escalates to the math lane
(ground-truth re-derivation / math adversary / jacobian), exactly as
escalation.md already prescribes.

---

## 8. Artifacts and schemas

All literature state is schema-validated. Schemas are the single canonical copy
loaded by rq_check.py — never a second hand-written copy.

**Committed (durable).**

- literature/known-results.json — the map, keyed by sub-problem id:

~~~
{
  "SP1": [
    {
      "category": "settled | impossible | superseded | open",
      "claim": "one-sentence statement",
      "negative_export": false,
      "sources": [
        {
          "paper_id": "arXiv:1706.03762 | DOI:10.x/... | normalized-title",
          "version": "v2 | published | ...",
          "access_date": "YYYY-MM-DD",
          "retrieval_method": "arxiv-api | author-page | open-repo | preprint | openalex | user-mirror",
          "adversarial_check": {
            "status": "verified-current | verified-stale | unverifiable | false-claim",
            "checked_by": "lit-adversary",
            "date": "YYYY-MM-DD",
            "evidence": "study-root-relative path to the verdict"
          }
        }
      ]
    }
  ]
}
~~~

- literature/negative-exports.json — the provenance-stripped constraints
  actually sent to the novel lane, plus (orchestrator-side) the source id each
  constraint came from.
- literature/completeness.json — the per-line completeness checklist.
- literature/refs-seed.bib — verified refs.bib seed (category ≠ open entries
  only).

**Scratch (gitignored, interim/lit/).**

- interim/lit/<line-slug>/dossier.json — per-paper notes: paper_id, version,
  title, authors, venue, year, claim, evidence_quote, references[], cited_by[],
  freshness{}, access{date,method}.
- interim/lit/<line-slug>/fetched/ — raw PDF/HTML.
- interim/lit/<line-slug>/verdict.json — the lit adversary's per-claim verdicts.

**study.json addition (literature object).**

~~~
"literature": {
  "phase": "not-run | running | concluded",
  "consulted_at": "YYYY-MM-DD",
  "map_file": "literature/known-results.json",
  "negative_exports_file": "literature/negative-exports.json",
  "completeness_file": "literature/completeness.json",
  "budget": { "max_lines": 8, "max_depth": 4, "max_papers_per_line": 80,
              "max_rounds": 8, "max_cost_usd": null, "max_wall_minutes": null }
}
~~~

New schemas: schemas/known-results.schema.json,
schemas/dossier.schema.json, and a literature object in study.schema.json.
tests/ enforces "exactly one schema per file, next to the validator" exactly as
it already does.

---

## 9. Tooling

**Vendored skills (skills, not MCP servers).** Subagents run them in the pinned
uv lane via bash; no new runtime deps, no MCP rows.

- arxiv — confirmed real, NousResearch/hermes-agent/skills/research/arxiv, MIT,
  curl + Python over the arXiv Atom API, BibTeX generation included. Vendored
  verbatim at agent-presets/rigorquant/skills/arxiv/. Its web_extract calls map
  to DSH web_fetch.
- academic-paper-search — **not a Hermes-official skill** (verified §14);
  pinned from the user-authored SKILL.md (2026-08-16; MIT, author-confirmed).
  Vendored at agent-presets/rigorquant/skills/academic-paper-search/, with the
  spec's tiered resolver appended as the retrieval contract (§9 below).

**Tiered retrieval (academic-paper-search behavior).** Resolution order:

1. Author personal / institutional page.
2. Open repositories and Unpaywall.
3. arXiv / preprint servers.
4. OpenAlex / CORE.
5. **User-supplied mirror list** — runtime config (DSH_LIT_MIRRORS,
   newline-separated endpoints), empty by default, never hardcoded in-repo. The
   legal basis for this tier is recorded in the decision note, not argued here.

The honest capability name is "best *retrievable* version"; the paywall tier is
disabled until the user supplies endpoints.

**Composition prerequisite.** tool-web fetch flips to true (so web_fetch exists
for the lit roles). The blind roles' deny list (§5) is what keeps fetch out of
the novel lane — this is why §5 adds web_fetch to the ground-truth deny list.

**Install scope.** The literature protocol skill (skills/literature/) is
preset-local. install.sh additionally installs arxiv and academic-paper-search
to $DSH_HOME/skills/ so any preset can load them (Decision 15), while the full
preset keeps them preset-local too.

---

## 10. Lifecycle, budget, and resume

- **Mandatory intake sweep** for every study where known/novel is not already
  asserted by the user; skippable only on an explicit user assertion at intake.
- **Re-enterable per round:** the orchestrator may re-enter the literature lane
  on a recorded trigger ("is X still open after the adversary's counterexample?"
  etc.).
- **"Consult human" is a hard stop.** When the orchestrator cannot decide
  (a) new rounds, (b) conclude, (c) unclear — it checkpoints and halts; a human
  turn re-arms. This is not advisory. It is the one honest escape from "silently
  guessing" under a thoroughness mandate.
- **Budget vs thoroughness.** Defaults above (max_lines 8, max_depth 4,
  max_papers_per_line 80, max_rounds 8) are **safety ceilings**,
  intake-overridable. Hitting a ceiling checkpoints and **resumes** — it is not
  a conclusion. The run concludes only on the completeness gate (§6) plus
  adversary certification (§7). max_wall_minutes may be left null to permit
  10+ hour runs.
- **Resume.** After every round the orchestrator checkpoints the map, the
  frontiers, and the completeness checklist. A resumed session reconstructs the
  graph walk from those artifacts; the goal-round driver's "one human turn
  re-arms" contract is unchanged.

---

## 11. Validator gate (rq_check.py)

Follow Decision 13's three rules (a study may not vouch for itself; parse,
never grep; one validator/one schema/both tested).

The literature gate refuses a PASS unless:

- a sub-problem marked known or routed-away impossible has a verified
  literature record (source id + version + access date + retrieval method +
  adversarial check status verified-current or, for impossibility,
  verified-current plus the load-bearing escalation rule of §4);
- every \cite{...} key and every refs.bib entry traces to a verified
  literature record (category ≠ open); a refs.bib entry without a matching
  record is refused — this is the fabricated-citation gate;
- negative_exports are a subset of known-results entries with
  category: impossible (a negative cannot appear from nowhere);
- the completeness checklist exists and has no empty mandatory sweep;
- a concluded lane with any verified non-open record has a
  literature/refs-seed.bib whose entries trace to those records.

Dossiers in interim/lit/ are advisory evidence, never counted as verified
records — verified state lives only in literature/.

---

## 12. Acceptance criteria (falsifying evidence)

Each criterion names the layer where it can fail and the evidence that would
falsify it.

- **A1 — blind role is actually blind (tool layer).** Static check that
  agent.cordis.yml gives subagent_ground_truth and subagent_novel a deny list
  containing web_search, web_fetch, skill, and the four delegation tool names.
  Evidence: tests/test_blind_deny_list.py asserts the exact list, and
  test_blind_personas_carry_the_protocol_they_cannot_load asserts the denied
  `skill` is compensated by the persona. Fails if the list omits any tool.
- **A2 — one schema, one validator.** known-results.schema.json,
  dossier.schema.json, negative-exports.schema.json and
  completeness.schema.json live next to rq_check.py and nowhere else -- and all
  four are loaded by it, none is decoration;
  tests/test_repo_consistency.py test_exactly_one_validator_is_shipped and
  test_schemas_live_next_to_the_validator cover the new files.
- **A3 — fabricated citation is refused.** A forged study whose refs.bib has an
  entry with no matching verified literature record must FAIL rq_check.py; the
  golden study (with a verified record) must PASS. Evidence:
  tests/test_literature_gate.py (golden-study pattern from conftest.py).
- **A4 — a negative cannot appear from nowhere.** negative_exports containing a
  non-impossible or unmapped entry must FAIL. Same test file.
- **A5 — the vendored skills survive install.** install.sh copies arxiv and
  academic-paper-search to $DSH_HOME/skills/;
  tests/test_repo_consistency.py
  test_install_script_installs_literature_skills requires both, in both install
  modes.
- **A6 — docs don't over-claim enforcement.** No shipped text calls the blind
  lane a "wall" or claims bit-level isolation; the residual holes (§13) appear
  wherever isolation is described. Evidence: a doc scan in the consistency
  suite (the repo's established defect class is unenforced prose claims).
- **A7 — real assembled path.** One end-to-end dry run: a study intake produces
  a known-results.json + negative-exports.json + a verified refs-seed.bib, and
  <skill-dir>/scripts/rq_check.py --study <root> accepts them. Evidence: a runnable example fixture
  checked by tests/test_integration.py (extended), not just a leaf unit test.
- **A8 — external services.** arXiv / Semantic Scholar / Crossref access is a
  real network boundary; tests/test_retrieval_boundary.py exercises it and
  SKIPS with an explicit "UNVERIFIED BOUNDARY" message when the environment
  cannot reach it, rather than translating "not run" into "passed". The tier
  ORDER is separately checkable offline: tests/test_retrieval_tiers.py drives
  skills/academic-paper-search/scripts/resolve_tiers.py.

---

## 13. Risks and named residual holes

- **Bash curl hole.** The blind lane keeps bash; nothing today prevents it from
  curling export.arxiv.org. This is a procedural boundary audited by the math
  adversary (a blind output that cites or recalls an external result it could
  not have derived is flagged). C2 records the future DSH-core network sandbox
  as the enforcement upgrade.
- **Cross-lane filesystem read.** No per-role fs scope exists; a blind child
  could read literature/ or a sibling's interim/lit/. Procedural + audited,
  same class as the existing ground-truth hole the repository review named.
- **Mirror rot and exposure.** Mirrors rotate domains and break unattended
  runs. The user-supplied, disabled-by-default tier (§9) removes hardcoded URLs
  from the repo and makes the legal basis a recorded, user-owned fact.
- **Paywalled full text.** Where no tier yields full text, the lit adversary
  records unverifiable (abstract-only), and such entries are a lower confidence
  tier — never verified-current and never load-bearing.
- **10+ hour cost.** Thoroughness-first runs burn tokens. max_cost_usd /
  max_wall_minutes remain available as ceilings; the completeness gate is what
  prevents both premature and runaway termination.
- **Hallucinated dossiers.** The lit adversary's independent re-retrieval plus
  the provenance gate (§11) is the defense; a dossier may never vouch for
  itself.
- **API rate limits.** Semantic Scholar and Crossref are rate-limited; the
  retrieval scripts must back off and record partial sweeps honestly rather
  than fabricate coverage.
- **Resume drift.** A resumed graph walk must re-anchor on the checkpointed
  frontier; the completeness checklist carries the "what was swept" state so a
  resumed run cannot silently skip a sweep.

---

## 14. Open items

1. **Pin academic-paper-search — RESOLVED.** Vendored from the user-supplied
   academic-paper-search-SKILL.md (2026-08-16), MIT (author-confirmed). The
   referenced references/google-scholar-scraping.md is also shipped (2026-08-16),
   so the CDP/Scholar path is executable from this checkout.
2. **Default ceilings — CONFIRMED.** max_lines 8, max_depth 4,
   max_papers_per_line 80, max_rounds 8 shipped as the documented defaults
   (schemas/study.schema.json `literature.budget`, lifecycle.md). They are
   safety ceilings, intake-overridable, and the validator does not treat a
   ceiling as a conclusion — the completeness gate is the finish line.
3. **OCR of PDFs.** Explicitly deferred (non-goal); revisit only if
   abstract-only verification proves insufficient in practice.

---

## Repo map (as implemented)

~~~
agent-presets/rigorquant/
  agent.cordis.yml           3 lit/novel roles, fetch: true, blind deny lists + embedded blind protocol
  skills/rigorquant/         references/literature.md; SKILL.md Step 2b + the routed novelty toggle
    schemas/                 known-results, dossier, negative-exports, completeness (+ study.literature)
    scripts/rq_check.py      the literature gate (§11)
  skills/literature/         literature-lane protocol (preset-local)
  skills/arxiv/              vendored (MIT, NousResearch/hermes-agent)
  skills/academic-paper-search/  vendored (MIT, author-confirmed) + scripts/resolve_tiers.py
docs/literature-lane.md      this spec
docs/architecture.md         Decisions 14-15
tests/                       test_literature_gate.py, test_blind_deny_list.py, test_retrieval_tiers.py,
                             test_retrieval_boundary.py; consistency + integration extended
install.sh                   installs arxiv/academic-paper-search to $DSH_HOME/skills/
~~~
