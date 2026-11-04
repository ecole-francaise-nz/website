#!/usr/bin/env python3
"""Check a Hugo build's internal destinations, fragments and basic semantics.

Usage: python3 scripts/check_site.py /tmp/efia-redesign-build
External websites are deliberately not crawled.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
import sys


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.duplicates = set()
        self.h1 = 0
        self.redirect = False
        self.missing_alt = False
        self.language = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html':
            self.language = attrs.get('lang')
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            self.redirect = True
        if tag == 'h1':
            self.h1 += 1
        if 'id' in attrs:
            identifier = attrs['id']
            if identifier in self.ids:
                self.duplicates.add(identifier)
            self.ids.add(identifier)
        if tag == 'img' and 'alt' not in attrs:
            self.missing_alt = True
        if tag in ('a', 'link', 'img', 'script'):
            value = attrs.get('href' if tag in ('a', 'link') else 'src')
            if value:
                self.links.append(value)


def main():
    root = Path(sys.argv[1]).resolve()
    pages = {}
    for path in root.rglob('*.html'):
        page = Page()
        page.feed(path.read_text())
        pages[path] = page
    if not pages:
        raise SystemExit('No HTML pages found; build with Hugo first.')
    errors = set()
    for path, page in pages.items():
        route = '/' + str(path.relative_to(root)).removesuffix('index.html')
        if not page.redirect:
            if page.h1 != 1:
                errors.add(f'{route}: expected one h1, found {page.h1}')
            if page.language not in ('en', 'fr'):
                errors.add(f'{route}: missing or unsupported page language')
        if page.missing_alt:
            errors.add(f'{route}: image missing alt attribute')
        for duplicate in page.duplicates:
            errors.add(f'{route}: duplicate ID {duplicate}')
        for link in page.links:
            url = urlparse(urljoin('https://ecole-francaise.nz' + route, link))
            if url.scheme not in ('http', 'https') or url.netloc != 'ecole-francaise.nz':
                continue
            target = root / unquote(url.path).lstrip('/')
            if target.is_dir() or (not target.exists() and not target.suffix):
                target = target / 'index.html'
            if not target.exists():
                errors.add(f'{route}: missing destination {link}')
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.add(f'{route}: missing fragment {link}')
    for error in sorted(errors):
        print(error)
    print(f'Checked {len(pages)} HTML pages; {len(errors)} issues.')
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
