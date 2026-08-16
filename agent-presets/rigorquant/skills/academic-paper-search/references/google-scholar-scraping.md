# Google Scholar scraping recipe

> Vendored 2026-08-16 into dsh-rigorquant. Author: linxichen. License: MIT
> (same as this distribution).

Learned while building zotero-smart-ingest (reference implementation:
`~/gits/zotero-smart-ingest/scripts/scholar.py`). Verified working from a
residential IP in 2026-08; datacenter IPs are often blocked — see the
fallback chain at the bottom.

## Why scrape at all

Scholar has no public API. Google PSE (Programmable Search Engine / Custom
Search JSON API) does **not** index scholar.google.com — a CSE query returns
nothing useful. Scraping with a real Chrome User-Agent plus the consent
cookie is the practical path.

## Request

- URL: `https://scholar.google.com/scholar?hl=en&q=<query>&start=<0|10|20>`
  (~10 results per page; cap around 30 results total)
- Headers:
  - `User-Agent`: full Chrome UA string (not a library name)
  - `Accept-Language: en-US,en;q=0.9`
  - `Cookie: CONSENT=YES+cb.20220419-08-p0.en+FX+700` (avoids the EU consent wall)

## Parsing (regex with DOTALL is fine) — layout as of 2026-08

Scholar A/B-tests its HTML. Two layout facts that broke earlier scrapers:

- **Result blocks are `class="gs_r gs_or gs_scl"`** (a `gs_scl` suffix), and
  the div nesting depth varies. A regex that demands a fixed closing sequence
  (`</div>\s*</div>\s*</div>\s*</div>`) silently matches ONE block or
  truncated garbage. Match each block lazily and SPLIT on the next block /
  page footer instead:
  `<div class="gs_r gs_or[^"]*".*?(?=<div class="gs_r gs_or|<div class="gs_r gs_alrt|<div id="gs_res_ccl_bot|$)`
- **The PDF strip (`gs_or_ggsm`) now carries extra attributes** — match
  `<div class="gs_or_ggsm"[^>]*>`, not the bare tag.
- Title + link: `<h3 class="gs_rt">...<a href="URL">TITLE</a>` (attrs between
  class and href are fine — use `.*?`).
- Authors / venue / year: `<div class="gs_a">A1, A2 - Venue, Year</div>`
  — split on " - ", then regex `\b(19|20)\d{2}\b` for the year; venue is the
  text before the year match.
- Snippet: `<div class="gs_rs">`.
- Cluster id: any link containing `cluster=<digits>` (the "All N versions"
  link).

## Cite / BibTeX (changed 2026-08)

The cite button is now `href="javascript:void(0)"` — the real per-article ID
lives in the **"Cited by" link**: `href="/scholar?cites=<digits>"`. Build the
citation popup URL as `/scholar?cites=<id>&as_sdt=2005&sciodt=0,5&hl=en&output=citation`,
then find `href="/scholar.bib?q=info:..."` inside the popup and fetch that
URL — it returns raw BibTeX. Via CDP: `document.body.innerText` on the
scholar.bib URL. The old `gs_or_cit` href is no longer a real URL.

## Junk-block filter (critical)

Scholar's sidebar renders "Save", "Cite", "Export", Gmail buttons AND
author-profile cards ("V Zakamulin" style, URL containing `citations?user=`)
as bare blocks matching the gs_r pattern. Reject candidates whose title is in
{save, cite, export, gmail}, whose URL starts with `javascript:`, or whose
URL contains `citations?user=`.

## Cluster expansion — the "all versions" superpower

`https://scholar.google.com/scholar?cluster=<id>` lists EVERY known version
of the article (journal, preprint, working paper, author copy). Expanding the
top ~3 clusters is what lets a human pick the best version instead of only
seeing the first hit. This is the main reason to prefer Scholar over
Crossref alone.

## Block detection

Blocked when: HTTP 403, OR the HTML contains "unusual traffic" / "captcha" /
"not a robot" AND contains no `gs_r` blocks.

## Fallback chain

1. Scripted scrape (headers + consent cookie), with cluster expansion.
2. **Chrome CDP** — auto-escalate when the scrape is blocked and a Chrome
   with `--remote-debugging-port` is reachable (default `http://127.0.0.1:9222`).
   Drives the user's real Chrome (logged-in state, real fingerprint): same
   candidate parsing PLUS the [PDF] links Scholar shows PLUS BibTeX via the
   cite popup (above). Force with `--cdp`. Chrome 149+ needs a non-default
   `--user-data-dir` (copy of the Default profile) — see the
   anti-bot-browser-access skill.
3. **Semantic Scholar graph API** (free, no key; `x-api-key` header with a
   free key raises limits) when both fail — merges versions and provides OA
   PDFs, but loses cluster enumeration. The unauthenticated shared pool 429s
   easily: retry once with 5-10s backoff before giving up.
4. **`--from-json`**: agent captures results in a browser and injects them
   in the candidate shape.

## PDF hunting when Unpaywall has no OA copy

1. Semantic Scholar `openAccessPdf` for the DOI:
   `https://api.semanticscholar.org/graph/v1/paper/DOI:<doi>?fields=openAccessPdf`.
2. Scholar `[PDF]` links (author copies, course sites) — best via CDP.
3. Author homepage / working-paper series (RePEc/IDEAS list other versions).
4. Institutional repositories (e.g. UNC Carolina Digital Repository hosts
   postprints) — live downloads may sit behind a JS bot challenge; the
   Wayback snapshot of the exact `/downloads/<id>` URL bypasses it.
5. Wayback Machine for dead author pages (CDX-search
   `web.stanford.edu/~peterhansen*` style paths).
6. SSRN `Delivery.cfm` needs a session cookie from first visiting the
   abstract page — curl alone gets HTML; use a real browser.

JSTOR stable URLs map to the published DOI via Crossref
(`query.bibliographic` + `filter=container-title:`).

## Politeness

1s pacing between requests; expand at most 3 clusters per search; never
retry in a tight loop when blocked — back off to the fallback instead.

## Zotero ingest (reference implementation)

`~/gits/zotero-smart-ingest` (public: linxichen/zotero-smart-ingest) — the
full pipeline incl. Zotero v3 API write quirks: item creation needs a BARE
JSON array (`[{...}]`, not `{"items": [...]}`), PDF upload is a 3-step flow
(create attachment item → authorize with md5/filename/filesize/mtime +
`If-None-Match: *` → POST prefix+bytes+suffix to the storage URL → register
`upload=<uploadKey>`), and ingest-time library dedup matches by DOI or fuzzy
title (>=80% token overlap), stopping with "nothing to ingest" when every
found version already exists.
