# Deliverables (stage 4): paper, slides, web

Produced at PASS only, by ASSEMBLING validated records — the registry,
derivations, audits, and battery results. The writer must not introduce new
claims; a claim that is not backed by a passed route / derivation in
`registry.json` does not go in the paper. `rq_check.py` enforces existence,
structure, and the no-overclaim rule.

## Declaration (study.json, at intake)

```json
"deliverables": {
  "paper": "required",
  "slides": "required | not-required:<reason recorded at intake>",
  "web": "optional | required"
}
```

- `paper` — always `"required"`.
- `slides` — `"required"` by default; `"not-required"` only with a reason
  recorded at intake (e.g. the deliverable is a library, no talk planned).
- `web` — `"optional"`; `"required"` when the study will produce
  interactive/visual artifacts (widgets, movies, dashboards).

## White paper — `artifacts/paper/main.tex`

LaTeX article (`\documentclass{article}` with amsmath/amsthm/hyperref). Required
sections — the validator requires each as an actual `\section` heading, not the
word somewhere in the prose:

1. **Statement** — the original problem and its access/data models, verbatim
   from `study.json`.
2. **Method** — the validated pipeline with numbered claims, ALL hypotheses,
   per-step costs.
3. **Validity** — the correctness arguments for the study's own method, with
   hypotheses; the evidence level of every load-bearing claim
   (falsification-surviving / independently re-derived / certificate-checked /
   formally verified), quoted from `validity_stages` — **never upgraded in
   prose**.
4. **Certification** — the check battery: gates, instances, dimensions, seeds,
   cell counts, adjudication summary (e.g. "N/N adjudicated cells, k/k
   mutations detected"), references to the results files.
5. **Honest limitations** — every recorded gap: evidence-level caps, scope
   notes, delegation caveats, the range of parameters actually certified.
6. **Reproduction** — seeds table, the compute-lane command, the validator
   command.
7. **Bibliography (mandatory at PASS).** Load-bearing external claims are
   cited with proper BibTeX: `\cite{...}` commands in the text and a `refs.bib`
   next to `main.tex` with complete entries (author, title, journal, volume,
   pages, year, DOI/URL). The validator compiles the full pipeline including
   `bibtex` and refuses the PASS on missing `.bib` files or unresolved
   citations. Pinned URLs belong in the `.bib` entries, not as bare prose
   links.

No-overclaim rules (validator-enforced):

- The text may assert ANY of the four evidence levels
  (falsification-surviving / independently re-derived / certificate-checked /
  formally verified) ONLY if some claim in `validity_stages` / `registry.json`
  carries that level. Disclaiming a level ("nothing here is formally verified")
  is always allowed; the validator strips negations adjacent to the phrase
  before looking for an assertion.
- The paper must reference the study's `statement` or `broad_criterion` key
  terms (it is about THIS study, not a generic write-up).
- **Compile gate (mandatory at PASS).** The validator locates a TeX engine
  (searching PATH plus `/Library/TeX/texbin`, `/opt/homebrew/bin`, and
  `/usr/local/texlive/*/bin/*`) and actually compiles the paper and the
  slides. A declared PASS is refused if no engine is found, or if compilation
  fails: stage-4 artifacts must compile/render before success is claimed, and
  "the engine was missing" is a blocking gap, never a waiver. Structural
  markers (`\documentclass`, the six sections) are additional checks, not a
  substitute for a successful render. Compilation runs on a throwaway copy of
  `artifacts/`, so no `.aux`/`.log`/`.pdf` build products land in the study's
  committed tree.

## Slides — `artifacts/slides/main.tex`

**Positioning: lecture notes, not a talk deck.** The slides teach the material
to the audience the consultation confirmed; they do not merely summarize the
paper for colleagues. The audience, its prerequisites, and what may be assumed
known come from `deliverables.audience.slides` — **this file does not name an
audience**, because the right one depends on the study.

Beamer (`\documentclass{beamer}`). Claims stay a **strict SUBSET of the
paper's content** — same claims, same evidence levels, never upgraded, no new
empirical or theoretical results. Pedagogical exposition is not "new
material": definitions, background, worked examples, intuition, and
pitfall/teaching-moment discussions are allowed and required.

Required structure (on top of the paper-subset rules):

1. **Title + roadmap** — one slide stating the lecture's question and what the
   audience should be able to do afterwards (learning objectives).
2. **Statement** — the problem and its access/data models, with concrete
   motivations drawn from the study's own domain.
3. **Background frames** — one frame per prerequisite the audience spec does
   *not* list in `assume_known`, each with a worked example. This is the gap
   between what the reader knows and what the method needs; derive it from the
   spec, never from a fixed list.
4. **Method** — the pipeline, each algorithmic step accompanied by an intuition
   slide and an exact-cost slide.
5. **Validity** — the arguments as proof sketches, the pinned theorem
   statements with hypotheses, and evidence levels exactly as in the paper.
6. **Certification** — the four-gate battery with a worked gate example (one
   closed form derived on-slide), the seeded-replay and LLN conventions, and
   the final results table.
7. **Teaching moments** — at least two: the study's own concrete
   counterexamples, each retold as "why the easy version fails."
8. **Honest limitations** — as in the paper, phrased for the audience (what is
   conditional, what is only empirical, what is not formally verified).
9. **Self-test questions** — 3–5 check-your-understanding questions whose
   answers follow from the slides.
10. **Reproduction** — seeds, the pinned-lane command, the validator command.
11. **References frame + BibTeX** — the deck ends with a References frame using
    `\bibliography{...}`; it may share the paper's `refs.bib` via a relative
    path (e.g. `\bibliography{../paper/refs}`). `\cite{...}` commands mark
    every load-bearing external theorem. Unresolved citations fail the
    validator.

> **Worked example of a filled-in spec** (from a convex-sampling study — an
> illustration of the shape, never a requirement for your study):
> `role: "Econ Ph.D. student, second graduate course"`;
> `assume_known: ["measure-based probability", "linear algebra", "basic Monte Carlo"]`;
> `must_define: ["B(", "TV", "O*", "R/r"]`;
> `symbols: {"B(": {"pattern": "B\\(", "witnesses": ["ball"]}, "R/r": {"witnesses": ["condition number", "aspect ratio"]}}`.
> Its background frames were convex bodies, TV distance and Markov kernels, and
> oracle models — because *that* spec did not assume them known.

The validator's structural gate (`\documentclass{beamer}`, existence) plus the
mandatory compile gate above are the machine checks; the pedagogical
requirements above are the authoring standard. The slides must compile before
a PASS can be claimed.

## Web — `artifacts/web/index.html` (when required)

One self-contained HTML page (no build step) exposing the interactive/visual
artifacts: e.g. embed the battery figures, a widget driving the sampler
parameters, or movies of the walks. It must state the provenance of every
number it displays (which artifact file, which seed). Optional otherwise.
When required, the validator also checks that the page parses as HTML
(no unexpected/mis-nested closing tags, and an `</html>` close), since an
artifact must render before success is claimed. The page must carry a
**References section** (`id="references"` or a References heading) listing
every external source with properly labeled anchors (author, title, year, and
URL as the `href`); bare URLs with no anchor text fail the check.

## Assembly workflow

1. Writer (subagent or orchestrator) reads ONLY: `study.json`, `registry.json`,
   `artifacts/*.md` results, `derivations/`, `audits/` — never `interim/`
   scratch reports as sources of new claims.
2. Writer emits the .tex files; no numerical value enters the paper unless it
   appears in one of those records.
3. `python3 <skill-dir>/scripts/rq_check.py --study <study-root>` gates the result.

## Audience consultation (post-research, one-time, per deliverable)

Research always runs at the maximum technical level; the audience is chosen
only after the study is considered done. The lifecycle therefore has an
explicit **`research-complete`** state: every subproblem route `passed`,
`validity_stages` stage-3 + stage-5 recorded, and `rq_check.py` accepting the
state with deliverable gates suppressed.

At `research-complete`, before any deliverable is crafted:

1. A **consulting subagent** reads `study.json`, `registry.json`, the
   `artifacts/*.md` results, and the existing artifacts, and drafts — per
   declared deliverable (paper / slides / web) — an **audience spec**:
   `role`, `level`, `sentence` (the one-sentence audience statement the
   artifact must state verbatim), `assume_known[]` (prerequisites to take for
   granted), `must_define[]` (symbol keys that must be defined in the
   Notation block), `avoid[]` (conventions that must not be used outside the
   definition), `depth` (proof sketches vs. full proofs), and `format`. Each
   draft carries a justification tied to the artifact content it read.
2. The **user accepts or edits** each draft — this is the consultation. It is
   the user's decision, never auto-filled, and never time-out-accepted.
3. The confirmed specs are persisted as
   `deliverables.audience.<name>` in `study.json`; `consultation_pending`
   is cleared; a `consultation_record` (agent id, date, artifact hashes read)
   is written; `last_accepted` retains the previous spec across a dial-back.

**Fail-closed / resume.** The full questionnaire (drafts + justifications) is
checkpointed into `study.json` before asking. If no answerer is available,
approvals are disabled, or the session ends mid-consultation, the study stays
`research-complete` with `consultation_pending: true`, and the next human turn
re-presents the same checkpoint (re-drafting only if the artifacts changed
since). Partial answers persist; only the unanswered deliverables re-present.

**Dial-back.** The user may roll the study back to `active` at any time. This
sets `consultation_pending: true` and retains the audience spec as
`last_accepted`, but it does **not** mark verified, correct artifacts or PASS
evidence stale. Artifacts lose validity only when new research changes a
load-bearing claim (claim-driven invalidation via the existing
"superseded" mechanism); they are then re-crafted and re-verified.

**Enforcement at PASS (two tiers).**

- *Hard (validator):* the artifact states its confirmed audience `sentence`
  (in the rendered text — a LaTeX comment does not count, and a spec with no
  `sentence` is itself refused); a Notation/Definitions block exists; every
  symbol that APPEARS is defined there (see the conditional symbol audit below);
  every `avoid` key is absent from the text outside the block; the artifact
  compiles/renders. `consultation_pending: true` or a missing audience spec
  refuses the PASS.
- *Soft (document adversary):* a subagent reads the artifact and its spec and
  returns PASS or needs-edits with concrete reasons (proof depth,
  motivation, worked examples, appropriateness for the level). needs-edits is
  a blocking gap. The report is committed as
  `audits/document-adversary-<name>.md` (name in `paper`, `slides`, `web`) and
  ends with an explicit `VERDICT: PASS` or `VERDICT: NEEDS-EDITS` line. The
  validator refuses a PASS when a required report is missing or its final
  verdict is NEEDS-EDITS.

## Document-adversary gate (validator-enforced at PASS)

Stage-4 documents are written for the declared audience's technical level, and
symbol conventions are never assumed:

- **Notation/Definitions section (paper) and frame (slides) are mandatory.**
  Every symbol the document uses must appear there with its convention made
  explicit. "Everyone knows this" is not a definition.
- **The symbol registry has two halves.** `rq_check.py` ships a small
  *cross-domain* default registry — conventions that are load-bearing in any
  quantitative field and routinely left undefined: `O^*`, `poly(...)`, `TV` /
  total-variation, `w.h.p.`, `\lesssim`. **Study-specific notation is declared
  in the audience spec**, not in the validator:

  ```json
  "symbols": {
    "B(":  { "pattern": "B\\(", "witnesses": ["ball"] },
    "R/r": { "witnesses": ["condition number", "aspect ratio"] }
  }
  ```

  A bare list of witnesses is also accepted (`"tau": ["autocorrelation"]`), in
  which case the key itself is the search pattern. This is why a portfolio study
  and a convex-geometry study can share one validator.
- **Conditional symbol audit.** The validator scans the document for every
  symbol in the merged registry; for each one that appears, the
  Notation/Definitions block must contain its defining witness (e.g. `B(` must
  be witnessed by ``ball''). A used-but-undefined symbol refuses the PASS.
- **Audience statement.** Every deliverable must state, in its rendered text,
  the `sentence` its audience spec carries (e.g. ``Econ Ph.D. students, second
  graduate course; no convex-body geometry assumed''). A spec with no
  `sentence`, or a document that states it only inside a comment, fails the
  gate: a document that cannot say who it is for is not finished.
- The gate checks documentation hygiene; it does not certify the mathematics
  (that remains the job of the check battery and the adversary).
