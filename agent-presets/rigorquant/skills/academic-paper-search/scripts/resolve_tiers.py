#!/usr/bin/env python3
"""Emit the tiered retrieval plan for one paper, in the order §9 fixes.

docs/literature-lane.md §9 states the resolution order as prose; this script is
that order as something executable, so a line-agent resolves "the best
*retrievable* version" the same way every time and labels its provenance with a
`retrieval_method` the known-results schema will actually accept.

    resolve_tiers.py --doi 10.2307/2975974 [--author-page URL]
    resolve_tiers.py --arxiv 1706.03762
    resolve_tiers.py --title "Portfolio Selection"

Order: author/institutional page → open repositories + Unpaywall → arXiv /
preprint servers → OpenAlex / CORE → user-supplied mirrors.

The mirror tier is EMPTY unless the user sets DSH_LIT_MIRRORS (newline- or
comma-separated endpoints). No mirror endpoint is hardcoded in this repository:
the tier exists, its contents are the user's, and the legal basis for using it
is recorded by the user in the study, not argued here.

Output is JSON on stdout: a list of {tier, retrieval_method, why, attempts[]}.
Nothing is fetched -- the caller does the fetching and records which tier won.
"""

import argparse
import json
import os
import sys
import urllib.parse

MIRROR_ENV = "DSH_LIT_MIRRORS"


def _mirrors():
    raw = os.environ.get(MIRROR_ENV, "")
    parts = [p.strip() for chunk in raw.splitlines() for p in chunk.split(",")]
    return [p for p in parts if p]


def build_plan(doi=None, arxiv=None, title=None, author_page=None, email=None):
    q = urllib.parse.quote(title or "", safe="")
    mail = email or os.environ.get("DSH_LIT_MAILTO", "")
    tiers = []

    if author_page:
        tiers.append({
            "tier": 1,
            "retrieval_method": "author-page",
            "why": "an author-hosted copy is first-class, freshest, and costs the "
                   "publisher nothing",
            "attempts": [author_page],
        })

    open_repo = []
    if doi:
        open_repo.append("https://api.unpaywall.org/v2/%s?email=%s"
                         % (urllib.parse.quote(doi, safe=""), mail or "EMAIL_REQUIRED"))
    if title:
        open_repo.append("https://core.ac.uk/search?q=%s" % q)
    tiers.append({
        "tier": len(tiers) + 1,
        "retrieval_method": "open-repo",
        "why": "open repositories and Unpaywall give a legal full text when one exists",
        "attempts": open_repo,
    })

    preprint = []
    if arxiv:
        preprint.append("http://export.arxiv.org/api/query?id_list=%s"
                        % urllib.parse.quote(arxiv, safe=""))
        preprint.append("https://arxiv.org/abs/%s" % arxiv)
    elif title:
        preprint.append("http://export.arxiv.org/api/query?search_query=ti:%%22%s%%22"
                        "&max_results=10" % q)
    tiers.append({
        "tier": len(tiers) + 1,
        "retrieval_method": "preprint",
        "why": "arXiv/preprint servers; note the version (v1 vs latest) for freshness",
        "attempts": preprint,
    })

    index = []
    if doi:
        index.append("https://api.openalex.org/works/doi:%s" % doi)
    if title:
        index.append("https://api.openalex.org/works?filter=title.search:%s" % q)
    tiers.append({
        "tier": len(tiers) + 1,
        "retrieval_method": "openalex",
        "why": "OpenAlex/CORE resolve metadata, versions, and forward citations "
               "when the full text is not reachable",
        "attempts": index,
    })

    mirrors = _mirrors()
    if mirrors:
        tiers.append({
            "tier": len(tiers) + 1,
            "retrieval_method": "user-mirror",
            "why": "user-supplied mirror endpoints (%s); the user owns the legal "
                   "basis and records it in the study" % MIRROR_ENV,
            "attempts": mirrors,
        })
    return tiers


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--doi")
    ap.add_argument("--arxiv")
    ap.add_argument("--title")
    ap.add_argument("--author-page", dest="author_page")
    ap.add_argument("--email", help="Unpaywall/Crossref mailto (or DSH_LIT_MAILTO)")
    args = ap.parse_args(argv)
    if not (args.doi or args.arxiv or args.title):
        ap.error("give at least one of --doi / --arxiv / --title")
    json.dump(build_plan(args.doi, args.arxiv, args.title, args.author_page, args.email),
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
