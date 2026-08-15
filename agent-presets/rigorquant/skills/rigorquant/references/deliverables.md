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
sections (the validator checks these markers case-insensitively):

1. **Statement** — the original problem and access models, verbatim from
   `study.json`.
2. **Method** — the validated pipeline with numbered claims (Claim G style),
   ALL hypotheses, per-step costs.
3. **Validity** — the reversibility/stationarity arguments and the mixing
   bound with hypotheses; the evidence level of every load-bearing claim
   (falsification-surviving / independently re-derived / certificate-checked /
   formally verified), quoted from `validity_stages` — **never upgraded in
   prose**.
4. **Certification** — the check battery: gates, bodies, dimensions, seeds,
   cell counts, adjudication summary (e.g. "511/511 adjudicated cells,
   3/3 mutations detected"), references to the results files.
5. **Honest limitations** — every recorded gap: evidence-level caps, scope
   notes (e.g. correctness-but-slow regimes), delegation caveats, d-range.
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

- The text may contain `formally verified` ONLY if some claim in
  `validity_stages` / `registry.json` carries that evidence level.
- The paper must reference the study's `statement` or `broad_criterion` key
  terms (it is about THIS study, not a generic write-up).
- **Compile gate (mandatory at PASS).** The validator locates a TeX engine
  (searching PATH plus `/Library/TeX/texbin`, `/opt/homebrew/bin`, and
  `/usr/local/texlive/*/bin/*`) and actually compiles the paper and the
  slides. A declared PASS is refused if no engine is found, or if compilation
  fails: stage-4 artifacts must compile/render before success is claimed, and
  "the engine was missing" is a blocking gap, never a waiver. Structural
  markers (`\documentclass`, the six sections) are additional checks, not a
  substitute for a successful render.

## Slides — `artifacts/slides/main.tex`

**Positioning: lecture notes, not a talk deck.** The slides are written as
self-contained lecture notes for an **Econ Ph.D. student in their second
graduate course** (completed first-year metrics/micro sequence: measure-based
probability, linear algebra, convex optimization at the level of a first
optimization course, and basic Monte Carlo — but **no** background in
convex-body geometry, geometric MCMC, or complexity of oracles). The deck must
teach the material, not merely summarize the paper for colleagues.

Beamer (`\documentclass{beamer}`). Claims stay a **strict SUBSET of the
paper's content** — same claims, same evidence levels, never upgraded, no new
empirical or theoretical results. Pedagogical exposition is not "new
material": definitions, background, worked examples, intuition, and
pitfall/teaching-moment discussions are allowed and required.

Required structure (on top of the paper-subset rules):

1. **Title + roadmap** — one slide stating the lecture's question and what the
   student should be able to do afterwards (learning objectives).
2. **Statement** — the problem and access models, with concrete economic
   motivations (volume/moment computation, constrained simulation, truncation).
3. **Background frames** (the second-course gap):
   - convex body, interior, closed vs. strict sublevel, the certified sandwich
     `B(x0,r) ⊆ K ⊆ B(x0,R)`, Slater point, with a worked example (p-ball,
     translated quadratic);
   - total-variation distance, Markov kernels, detailed balance/reversibility,
     stationary vs. ergodic (with a concrete non-ergodic warning example);
   - warm start and conductance as intuition;
   - oracle access models M1/M2/M3 with exact per-step costs.
4. **Method** — the walks and the pipeline, each algorithmic step accompanied
   by an intuition slide and an exact-cost slide.
5. **Validity** — reversibility arguments as proof sketches, the pinned
   theorem statements with hypotheses, and evidence levels exactly as in the
   paper.
6. **Certification** — the four-gate battery with a worked gate example (one
   closed form derived on-slide), the seeded-replay and LLN/IAT conventions,
   and the final results table.
7. **Teaching moments** — at least two: each of the study's concrete
   counterexamples (e.g. the fixed-radius sphere lattice with TV = 1, the
   inadmissible inferred-radius cap cut, the leaking finite-bisection chord)
   retold as "why the easy version fails."
8. **Honest limitations** — as in the paper, phrased for students (what is
   conditional, what is only empirical, what is not formally verified).
9. **Self-test questions** — 3–5 check-your-understanding questions whose
   answers follow from the slides.
10. **Reproduction** — seeds, the pinned-lane command, the validator command.
11. **References frame + BibTeX** — the deck ends with a References frame using
    `\bibliography{...}`; it may share the paper's `refs.bib` via a relative
    path (e.g. `\bibliography{../paper/refs}`). `\cite{...}` commands mark
    every load-bearing external theorem. Unresolved citations fail the
    validator.

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
3. `python3 scripts/rq_check.py --study <study-root>` gates the result.

## Document-adversary gate (validator-enforced at PASS)

Stage-4 documents are written for the declared audience's technical level, and
symbol conventions are never assumed:

- **Notation/Definitions section (paper) and frame (slides) are mandatory.**
  Every symbol the document uses must appear there with its convention made
  explicit — `B(x,r)` as the Euclidean ball, `poly(...)` as polynomial
  dependence, `O^*`, `R/r` as the condition number, `\delta`, `\tau`/IAT,
  `TV`, subgradients, `S^{d-1}`, `Unif`, etc. "Everyone knows this" is not a
  definition.
- **Conditional symbol audit.** The validator scans the document for a known
  registry of load-bearing symbols; for each one that appears, the
  Notation/Definitions block must contain its defining witness (e.g. `B(` must
  be witnessed by ``ball''). A used-but-undefined symbol refuses the PASS.
- **Audience statement.** The slides must name their audience and
  prerequisites (e.g. ``Econ Ph.D. students, second graduate course; no
  convex-body geometry assumed''). A document that cannot say who it is for
  fails the gate.
- The gate checks documentation hygiene; it does not certify the mathematics
  (that remains the job of the check battery and the adversary).
