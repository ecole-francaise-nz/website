"""Independently crawl the built site and validate search inclusion and destinations."""
import json
import sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

class HTML(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links = set(), []
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            value = attrs.get('content', '')
            if 'url=' in value.lower():
                self.links.append(value[value.lower().index('url=')+4:])

def validate(root, source):
    documents = json.loads((source / 'data/documents.json').read_text())
    text = json.loads((source / 'data/pdf_text.json').read_text())
    aliases = {alias:d['url'] for d in documents for alias in [d['legacy']] + d.get('aliases', [])}
    def local(href, base):
        url = urlsplit(urljoin('https://ecole-francaise.nz' + base, href))
        if url.scheme not in ('http', 'https') or url.hostname not in ('ecole-francaise.nz','www.ecole-francaise.nz','localhost','127.0.0.1'):
            return None
        path = unquote(url.path)
        path = aliases.get(path,path)
        if not Path(path).suffix and not path.endswith('/'):
            path += '/'
        return path
    visited, queue = set(), ['/', '/fr/']
    while queue:
        url = queue.pop()
        if url in visited:
            continue
        path = root / url.lstrip('/')
        if url.endswith('/'):
            path /= 'index.html'
        if not path.is_file():
            continue
        visited.add(url)
        links = text.get(url, {}).get('links', []) if url.endswith('.pdf') else HTML(path.read_text()).links if path.suffix == '.html' else []
        queue.extend(link for href in links if (link := local(href,url)))
    count = 0
    for name in ['index.json', 'fr/index.json']:
        index = json.loads((root / name).read_text())
        urls = set()
        for page in index['pages']:
            url = page['url']
            assert url in visited, f'Unreachable item leaked into {name}: {url}'
            assert url not in urls, url
            urls.add(url)
            path = root / unquote(urlsplit(url).path).lstrip('/')
            if page['type'] == 'pdf':
                assert path.read_bytes().startswith(b'%PDF-'), url
                anchors = {p['anchor'] for p in text[url]['passages']}
            else:
                anchors = HTML((path / 'index.html').read_text()).ids
            for passage in page['passages']:
                assert not passage['anchor'] or passage['anchor'] in anchors, (url, passage['anchor'])
                count += 1
    # Legacy addresses remain byte-identical, without adding them to either index.
    for doc in documents:
        for alias in [doc['legacy']] + doc.get('aliases', []):
            assert (root / alias.lstrip('/')).read_bytes() == (root / doc['url'].lstrip('/')).read_bytes()
    print(f'Checked {count} search passages, reachability, and {len(documents)} legacy PDF URLs.')

if __name__ == '__main__':
    validate(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).resolve().parent.parent)
