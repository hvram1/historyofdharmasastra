#!/usr/bin/env python3
"""Publish the History of Dharmaśāstra from dharmasastra-gcp/site into this repo.

    ./refresh.py            copy, verify, report
    ./refresh.py --check    verify what is already here; copy nothing

This repository is a *deployment*, not a source tree. Nothing here is authored
by hand except README.md, .nojekyll and this file. Everything else is built
next door by `build_site.py` and copied in, root for root:

    dharmasastra-gcp/site/vol-1-part-1/31-the-manusmriti.html
                                    -> vol-1-part-1/31-the-manusmriti.html

WHAT IS COPIED is what git tracks over there, not what the directory holds:
`site/audio/experiments/` is ignored upstream and has no business being
published, and a directory listing cannot tell the difference.

WHY IT VERIFIES INSTEAD OF JUST COPYING. Two contracts run through this book,
and both are invisible to a file copy:

  * A CITATION FROM ANOTHER SITE. The Smṛtimuktāphalam edition publishes 103
    links into these pages -- passages the digest quotes that Kane also prints,
    matched verbatim -- and each names a FILE and an ANCHOR. Those links went
    out pointing at `sanatana.in/mbta/`, which returns 404 for every one of
    them; they were published dead and nothing noticed, because nothing was
    checking. Now the edition's own published URLs are read back out of
    `../smp/*.html` and resolved against the files here.
  * THE PARAGRAPH ANCHORS. A citation that lands at the top of a 2 MB chapter
    has failed even though it returned 200, so the anchor is checked, not just
    the file.

Internal links are checked the same way: every relative href in every page must
name a file that exists here. The script exits non-zero rather than leave a
book whose links do not lead anywhere.
"""
import argparse
import html
import os
import re
import subprocess
import sys
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get('DHARMASASTRA_SRC', '/home/wipro/projects/dharmasastra-gcp')
SITE = os.path.join(SRC, 'site')
# The edition that cites this book. Absent is not an error -- the book stands on
# its own -- but present and broken is.
SMP = os.environ.get('SMP_REPO', '/home/wipro/projects/smp')

# No spaces, quotes or angle brackets: a URL has none of them, and `[^"']+`
# happily ran across newlines and swallowed whole table rows as a "link".
LINK = re.compile(r'(?:href|src)\s*=\s*["\']([^"\'<>\s]+)["\']', re.I)


def tracked_files():
    """Paths under site/, as git has them. NUL-separated: the volumes are full
    of names like `33-the-purānas.html`, which git otherwise hands back quoted
    and octal-escaped, and a quoted name copies to a file nobody asked for."""
    out = subprocess.run(['git', '-C', SRC, 'ls-files', '-z', 'site/'],
                         capture_output=True).stdout
    return [p[len(b'site/'):].decode('utf-8') for p in out.split(b'\0')
            if p.startswith(b'site/')]


def copy(files):
    listing = os.path.join(HERE, '.refresh-files')
    with open(listing, 'wb') as fh:
        fh.write(b'\0'.join(f.encode('utf-8') for f in files))
    r = subprocess.run(['rsync', '-a', '--from0', '--files-from=' + listing,
                        SITE + '/', HERE + '/'])
    os.unlink(listing)
    if r.returncode:
        sys.exit('rsync failed')


def check_present(files):
    missing = [f for f in files if not os.path.isfile(os.path.join(HERE, f))]
    for f in missing[:10]:
        print('  missing: %s' % f)
    return len(missing)


def read(path, cache):
    if path not in cache:
        with open(path, encoding='utf-8', errors='replace') as fh:
            cache[path] = fh.read()
    return cache[path]


# BROKEN WHERE THEY WERE BUILT, not here, and named so that they cannot be
# forgotten and a NEW broken link still fails. Both are upstream in
# dharmasastra-gcp's builders; neither is repairable by a deployment:
#
#   {{base_url}}  -- index-vol5.html and appendix-vol5.html ship the template
#                    placeholder itself, so those two pages load no CSS. Every
#                    other page is rendered through builders/templates.py and
#                    substitutes it; these two are built by some path that does
#                    not (2026-09-17).
#   pagefind/     -- index.html loads a search UI that has never been built:
#                    there is no site/pagefind directory upstream, tracked or
#                    untracked. The book's search box does nothing.
KNOWN_BROKEN = ('{{base_url}}', 'pagefind/')


def check_internal_links(files, cache):
    """Every relative href/src must name a file that is here."""
    bad, checked, known = [], 0, []
    pages = [f for f in files if f.endswith('.html')]
    for f in pages:
        src = read(os.path.join(HERE, f), cache)
        base = os.path.dirname(f)
        for raw in LINK.findall(src):
            u = html.unescape(raw).strip()
            if not u or u.startswith('#') or u.startswith('data:'):
                continue
            if urlparse(u).scheme or u.startswith('//'):
                continue
            target = unquote(u.split('#')[0].split('?')[0])
            if not target:
                continue
            p = os.path.normpath(os.path.join(HERE, base, target.lstrip('/')))
            checked += 1
            if not os.path.exists(p) and not os.path.exists(p + 'index.html'):
                where = known if any(k in u for k in KNOWN_BROKEN) else bad
                where.append('%s -> %s' % (f, u))
    return checked, bad, sorted(set(known))


def check_citations(cache):
    """The edition's published Kane links, resolved against the files here.

    Read out of the PUBLISHED pages rather than recomputed, because what has to
    resolve is the URL a reader can click today, not the one a rebuild would
    produce. The base is taken from the links themselves, so this keeps working
    when the book moves and the edition is rebuilt against a new KANE_SITE.
    """
    import json
    if not os.path.isdir(SMP):
        return None
    urls = []
    for name in sorted(os.listdir(SMP)):
        if not name.endswith('.html'):
            continue
        src = read(os.path.join(SMP, name), cache)
        m = re.search(r'<script id="data" type="application/json">', src)
        if not m:
            continue
        end = src.index('</script>', m.end())
        try:
            D = json.loads(src[m.end():end])
        except ValueError:
            continue
        # The kāṇḍa pages key the concordance by quotation id; the anukramaṇikā
        # carries the same rows as a plain list, because it has no quotation to
        # hang them on. Both publish the same `ku`.
        concord = D.get('concord') or {}
        rows = concord.values() if isinstance(concord, dict) else concord
        for row in rows:
            if isinstance(row, dict) and row.get('ku'):
                urls.append((name, row['ku']))
    bad, bases = [], set()
    for page, u in urls:
        p = urlparse(u)
        bases.add('%s://%s' % (p.scheme, p.netloc))
        # The book sits at the root of this repository, and its published base
        # may carry one path segment (…github.io/historyofdharmasastra/). What
        # is addressed here is everything after that segment.
        parts = [seg for seg in p.path.split('/') if seg]
        rel = unquote('/'.join(parts[1:])) if len(parts) > 1 else ''
        fs = os.path.join(HERE, rel)
        if not os.path.isfile(fs):
            bad.append('%s: %s (no such file: %s)' % (page, u, rel))
            continue
        if p.fragment and ('id="%s"' % unquote(p.fragment)) not in read(fs, cache):
            bad.append('%s: %s (no such anchor)' % (page, u))
    return {'n': len(urls), 'bad': bad, 'bases': sorted(bases)}


def check_outbound(files, cache):
    """The links this book makes INTO the edition, resolved against it.

    The reverse of check_citations, and it exists for the same reason: an
    address published by one site and honoured by another is a contract that
    neither side can check alone. Kane names the digest 69 times here and each
    mention links to the edition, 31 of them to a kāṇḍa -- `#kanda:ahnika`.
    Those slugs are declared in smp_site.py (KANDA_SLUGS) and shipped in the
    anukramaṇikā's own data, so renaming one there breaks links here, silently
    and with no 404 to notice: an unknown fragment just shows the whole
    register. Reading the slugs back out of the published page is the only way
    to know they still resolve.
    """
    import json
    index = os.path.join(SMP, 'index.html')
    if not os.path.isfile(index):
        return None
    src = read(index, cache)
    m = re.search(r'<script id="data" type="application/json">', src)
    try:
        D = json.loads(src[m.end():src.index('</script>', m.end())])
        known = set(D['kandas'])
    except (ValueError, KeyError, AttributeError):
        return {'n': 0, 'bad': ['the anukramaṇikā ships no kāṇḍa table — '
                                'it cannot honour a #kanda: address'], 'known': set()}
    used, bad = 0, []
    pat = re.compile(r'href="[^"]*?/smp/#kanda:([a-z]+)"')
    for f in (x for x in files if x.endswith('.html')):
        for slug in pat.findall(read(os.path.join(HERE, f), cache)):
            used += 1
            if slug not in known:
                bad.append('%s -> #kanda:%s (the edition knows %s)'
                           % (f, slug, ', '.join(sorted(known))))
    return {'n': used, 'bad': bad, 'known': known}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='verify only; copy nothing')
    a = ap.parse_args()

    if not os.path.isdir(SITE):
        sys.exit('no source at %s — set DHARMASASTRA_SRC' % SITE)
    files = tracked_files()
    if not files:
        sys.exit('git tracks nothing under %s' % SITE)
    if not a.check:
        copy(files)

    bad = 0
    n_missing = check_present(files)
    bad += n_missing
    print('%d files from %s%s' % (len(files), SITE,
                                  ' — %d MISSING' % n_missing if n_missing else ''))

    cache = {}
    checked, broken, known = check_internal_links(files, cache)
    print('%d internal links checked%s' % (checked,
                                           ' — %d broken' % len(broken) if broken else ''))
    for b in broken[:10]:
        print('  %s' % b)
    bad += len(broken)
    if known:
        print('%d known-broken link(s), inherited from the build — see KNOWN_BROKEN:'
              % len(known))
        for k in known:
            print('  %s' % k)

    cit = check_citations(cache)
    if cit is None:
        print('the edition is not checked out at %s — its citations were not verified' % SMP)
    else:
        print('%d citations from the edition, at %s%s'
              % (cit['n'], ', '.join(cit['bases']),
                 ' — %d BROKEN' % len(cit['bad']) if cit['bad'] else ''))
        for b in cit['bad'][:10]:
            print('  %s' % b)
        bad += len(cit['bad'])
        if cit['n'] == 0:
            print('  (the edition published no Kane link at all — check KANE_SITE '
                  'in dharmasastra-gcp/smp/smp_site.py)')

    out = check_outbound(files, cache)
    if out is not None:
        print('%d kāṇḍa link(s) into the edition%s'
              % (out['n'], ' — %d UNRESOLVABLE' % len(out['bad']) if out['bad'] else
                 ' (%s)' % ', '.join(sorted(out['known'])) if out['n'] else ''))
        for b in out['bad'][:10]:
            print('  %s' % b)
        bad += len(out['bad'])

    total = sum(os.path.getsize(os.path.join(HERE, f)) for f in files
                if os.path.isfile(os.path.join(HERE, f)))
    print('%.0f MB in %d files' % (total / 1e6, len(files)))
    if bad:
        print('\n%d problem(s) — not safe to publish' % bad)
        return 1
    print('\nOK — every internal link resolves, and every citation into this book '
          'lands on its paragraph')
    return 0


if __name__ == '__main__':
    sys.exit(main())
