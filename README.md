# History of Dharmaśāstra — the reading edition

P. V. Kane's *History of Dharmaśāstra*, five volumes in eight parts, as a
browsable site: every chapter with numbered paragraph anchors, a glossary, a
timeline, subject and topic indexes, the reference pages for each text it
argues from, and a spoken synopsis for each section.

Published at **https://hvram1.github.io/historyofdharmasastra/**

## This repository is a deployment

Nothing here is authored by hand except `README.md`, `.nojekyll` and
`refresh.py`. The site is built next door and copied in:

    dharmasastra-gcp/site/   ->   this repository, at its root

The loop is the one the other deployments use:

    dharmasastra-gcp$  python3 build_site.py
    historyofdharmasastra$  ./refresh.py
    historyofdharmasastra$  git add -A && git commit -m "refresh" && git push

## Why it has its own repository

Because something else already cites it. The Smṛtimuktāphalam edition
(`hvram1.github.io/smp`) carries a concordance: passages the digest quotes that
Kane also prints, matched verbatim at a 40-character floor. Each of those rows
links to the paragraph in this book where Kane prints the same words — 103 of
them today, across 50 chapters in all eight parts.

An address that is published by one site and served by another is a contract,
and `refresh.py` checks it: every Kane link the edition publishes must resolve
here, to a file that exists and an anchor that is in it. The base of those URLs
is a single constant, `KANE_SITE` in `dharmasastra-gcp/smp/smp_site.py`, so
moving this book is a rebuild of the edition rather than an edit of 103 links.

## The paragraph anchors are the point

A citation into a book is worth nothing if it lands at the top of a 2 MB
chapter. Every paragraph carries `id="p-<chapter-slug>-<n>"` and every footnote
`id="fn-<chapter-slug>-<n>"`, which is what lets another site address a
sentence rather than a file.
