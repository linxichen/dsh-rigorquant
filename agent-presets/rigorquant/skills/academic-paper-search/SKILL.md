---
name: academic-paper-search
author: linxichen
license: MIT
description: Find academic papers and the best version of an article across arXiv, Crossref, Unpaywall, Semantic Scholar, and Google Scholar. Covers the free open APIs, scripted Scholar scraping with cluster expansion to enumerate every version, block detection with a fallback chain, and a browser/CDP path when scraping is refused. Use when the user asks to find a paper, compare versions (preprint vs published vs OA), verify a DOI, or save a paper into Zotero or a reference manager.
---

# Academic Paper Search

Find a paper and every version of it (arXiv preprint, published journal article, working paper, author copy) so a human can pick the best one.

## Sources (all free, no API keys)

- **arXiv API** (export.arxiv.org/api/query) — Atom XML; `id_list` for an exact arXiv ID, `search_query` for titles.
- **Crossref** (api.crossref.org/works) — published journal versions, DOI resolution. Always include `mailto=`; use `select=DOI,title,container-title,issued` to slim responses.
- **Unpaywall** (api.unpaywall.org/v2) — DOI + email → best open-access PDF location.
- **Semantic Scholar** (api.semanticscholar.org/graph/v1/paper/search) — free, no key (~100 req/5 min unauth); `fields=title,authors,venue,year,externalIds,openAccessPdf`. Merges versions and returns OA PDFs.
- **Google Scholar** — no public API. PSE (Programmable Search Engine) does NOT index scholar.google.com, so it is not a workaround. Scripted scrape recipe: `references/google-scholar-scraping.md`.

## Workflow

1. Search arXiv + Crossref in parallel for a title, DOI, or arXiv ID.
2. To pin the exact published version, query Crossref with `filter=container-title:<Journal Name>` plus `select=DOI,title,container-title,issued`.
3. Add Scholar results (or Semantic Scholar fallback) to catch working papers, author copies, and versions Crossref misses.
4. Group versions by DOI, else normalized title; present a numbered menu; never auto-pick a version silently.
5. Enrich with Unpaywall OA PDF when DOI + email are available.

## Pitfalls

- **Never trust example DOIs in docs** — verify each via Crossref before shipping it in a README or skill. Real example: Moskowitz/Ooi/Pedersen "Time series momentum" (JFE, May 2012) = `10.1016/j.jfineco.2011.11.003`; the frequently-copied `10.1016/j.jfineco.2011.12.005` and `10.1016/j.jfineco.2011.12.008` are different papers.
- **Google PSE is not a Scholar workaround** — its index excludes scholar.google.com.
- **Scholar's HTML is A/B-tested and changes** — 2026-08 broke fixed-closing-sequence block regexes (`gs_r gs_or gs_scl` layout, JS-driven cite button, extra attrs on `gs_or_ggsm`). Parse with lookahead splitting and re-verify after any dry spell. See `references/google-scholar-scraping.md`.
- **arXiv API can return garbage** — under rate limits or with quoted multi-word queries it has been seen returning arbitrary recent submissions (unrelated papers, consecutive arXiv IDs). Guard with a token-overlap relevance filter: drop results whose title shares <2 significant tokens with the query (≥1 for very short titles).
- **Scholar blocks datacenter IPs** — detect block pages, escalate to CDP (auto if Chrome reachable, else `--cdp`), then Semantic Scholar (retry once on 429 with backoff), keep volume low.
- **arXiv DOIs are DataCite** (`10.48550/arXiv.xxxx`) — Unpaywall usually has no OA copy; attach the arXiv PDF instead.
- **Zotero v3 write API** — item creation wants a bare JSON array; PDF upload is a 3-step flow; ingest-time dedup against the library avoids duplicates. Full implementation: `~/gits/zotero-smart-ingest` (public repo, SKILL.md inside).

## Browser/CDP path

When Scholar (or any source) refuses scripted access, the pipeline auto-escalates
through the user's real Chrome via CDP (logged-in state, less fingerprinting) —
same candidate parsing plus Scholar's [PDF] links and BibTeX per result via the
cite popup (force with `--cdp`; Chrome 149+ needs a non-default
`--user-data-dir`, see anti-bot-browser-access). Final fallback: dump rendered
results in the candidate shape and inject via a `--from-json` hook. Details in
`references/google-scholar-scraping.md`.

## References

- `references/google-scholar-scraping.md` — headers, consent cookie, DOM selectors, junk-block filter, cluster expansion, block detection, and the full fallback chain.

---

## DSH vendoring record (RigorQuant, Decision 14)

- Source: user-authored (linxichen), supplied as academic-paper-search-SKILL.md
  (~/Downloads). Vendored 2026-08-16.
- License: MIT (author-confirmed 2026-08-16) — same as this distribution.
- references/google-scholar-scraping.md: SHIPPED 2026-08-16 (user-supplied
  ~/Downloads/google-scholar-scraping.md). The CDP/Scholar-scraping path it
  documents is executable from this checkout when a Chrome with
  --remote-debugging-port is reachable.
- External reference kept as-is: ~/gits/zotero-smart-ingest is the author's own
  public repo, not part of this distribution.
- The tiered retrieval order (scripts/resolve_tiers.py) applies on top of this
  skill's workflow: author personal/institutional page first; open
  repositories/Unpaywall; arXiv/preprint; OpenAlex/CORE; then the user-supplied
  mirror list DSH_LIT_MIRRORS (empty unless set, never hardcoded in-repo).
- Record retrieval_method in the dossier (author-page | open-repo | preprint |
  openalex | user-mirror); a paper reachable only as an abstract is
  'unverifiable', never 'verified-current'.
