#!/usr/bin/env python3
"""Build an isolated staff preview for a custom domain or GitHub project URL.
Does not publish, change Git remotes, or modify the production deployment.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit, unquote
from check_site import Page

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--destination', type=Path, required=True)
parser.add_argument('--url', required=True)
args = parser.parse_args()
base = args.url.rstrip('/') + '/'
url = urlsplit(base)
assert url.scheme == 'https' and url.netloc and not url.query and not url.fragment
prefix = url.path.rstrip('/')
origin = f'{url.scheme}://{url.netloc}/'
destination = args.destination.resolve()
assert destination != ROOT and ROOT not in destination.parents, 'Use a separate output directory outside the source checkout.'
subprocess.run(['hugo', '--source', str(ROOT), '--environment', 'preview', '--baseURL', origin, '--destination', str(destination), '--cleanDestinationDir'], check=True)
subprocess.run(['python3', str(ROOT/'scripts/check_site.py'), str(destination)],check=True)
subprocess.run(['python3', str(ROOT/'scripts/check_search.py'), str(destination)],check=True)
for path in destination.rglob('*.html'):
    html = path.read_text()
    if prefix:
        html = re.sub(r'((?:href|src|action|poster|data-index)=[\"\x27])/(?!/)', lambda m:m[1]+prefix+'/', html)
    # Canonical metadata and the enrolment PDF link must use the preview origin.
    html = html.replace('https://ecole-francaise.nz/', base)
    if prefix:
        html = html.replace(origin, base)
        # The production-origin replacement above may already have added prefix.
        html = html.replace(base + prefix.lstrip('/') + '/', base)
    if 'name="robots"' not in html:
        html = html.replace('</head>', '<meta name="robots" content="noindex, nofollow, noarchive"></head>')
    assert 'googletagmanager.com' not in html and "gtag('config'" not in html
    path.write_text(html)
for path in [destination/'index.json', destination/'fr/index.json']:
    index = json.loads(path.read_text())
    for record in index['pages']:
        record['url'] = prefix + record['url']
    path.write_text(json.dumps(index, ensure_ascii=False))
(destination/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
(destination/'.nojekyll').write_text('')
for metadata in destination.rglob('.DS_Store'):
    metadata.unlink()
if not url.netloc.endswith('.github.io'):
    (destination/'CNAME').write_text(url.netloc+'\n')
else:
    (destination/'CNAME').unlink(missing_ok=True)
# Validate rewritten root links and index destinations at the deployment prefix.
for path in destination.rglob('*.html'):
    page = Page();page.feed(path.read_text())
    for link in page.links:
        target = urlsplit(link)
        if target.scheme or target.netloc or not target.path.startswith('/'):
            continue
        assert target.path.startswith(prefix+'/'), (path,link)
        file = destination / unquote(target.path[len(prefix):]).lstrip('/')
        if file.is_dir() or not file.suffix:
            file /= 'index.html'
        assert file.is_file(), (path,link)
for name in ['index.json','fr/index.json']:
    for record in json.loads((destination/name).read_text())['pages']:
        file = destination / record['url'][len(prefix):].lstrip('/')
        if record['type'] == 'page':file /= 'index.html'
        assert file.is_file(),record['url']
print(f'Preview ready: {base} → {destination}')
