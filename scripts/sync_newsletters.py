#!/usr/bin/env python3
"""Import PDFs reachable from a public Drive folder. No API key or login.

Drive's undocumented page format is deliberately isolated in parse_folder().
Only complete, validated imports replace the local catalogue. Publication is a
separate CI step, so a failed import can never replace the deployed website.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

from pypdf import PdfReader
from index_pdfs import ROOT, VERSION, extract

PDF = 'application/pdf'
FOLDER = 'application/vnd.google-apps.folder'
ID = re.compile(r'^[\w-]{10,100}$')
MONTHS = [
    ('january', 'janvier'), ('february', 'fevrier'), ('march', 'mars'),
    ('april', 'avril'), ('may', 'mai'), ('june', 'juin'), ('july', 'juillet'),
    ('august', 'aout'), ('september', 'septembre'), ('october', 'octobre'),
    ('november', 'novembre'), ('december', 'decembre'),
]


def parse_folder(html, folder_id):
    """Read Drive's initial listing; refuse truncated listings or changed formats.

    Folders with 50+ children must be split into year folders. We intentionally
    fail rather than silently miss issues when Drive paginates its public page.
    """
    match = re.search(r"window\['_DRIVE_ivd'\]\s*=\s*'((?:\\.|[^'\\])*)'", html)
    if not match:
        raise ValueError('Public Drive listing not found (private folder or changed page format).')
    encoded = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16)), match[1])
    data = json.loads(encoded.replace("\\'", "'").replace('\\/', '/'))
    if not isinstance(data, list) or len(data) < 4 or not isinstance(data[0], list):
        raise ValueError('Unrecognised Drive listing structure.')
    if len(data[0]) >= 50 or any(data[1:4]):
        raise ValueError('Possibly paginated Drive folder; split it into year folders (under 50 items each).')
    entries = []
    for item in data[0]:
        if not isinstance(item, list) or len(item) < 14 or not ID.fullmatch(str(item[0])):
            raise ValueError('Unrecognised file metadata in public Drive listing.')
        if folder_id not in (item[1] or []):
            raise ValueError('Drive returned a file outside the requested folder.')
        entries.append(dict(id=item[0], name=item[2], mime=item[3], modified=item[10], size=item[13]))
    return entries


def fetch(url, opener=None):
    # No account cookies or credentials: this is exactly the public website.
    for attempt in range(3):
        try:
            request = Request(url, headers={'User-Agent': 'EFIA-newsletter-sync/1.0'})
            with (opener or build_opener()).open(request, timeout=120) as response:
                if urlsplit(response.url).hostname == 'accounts.google.com':
                    raise ValueError('Drive requested a login; newsletter must be public.')
                if int(response.headers.get('Content-Length', 0)) > 80 * 1024 * 1024:
                    raise ValueError('Newsletter exceeds the 80 MB import limit.')
                data = response.read(80 * 1024 * 1024 + 1)
                if len(data) > 80 * 1024 * 1024:
                    raise ValueError('Newsletter exceeds the 80 MB import limit.')
                return data
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


class DownloadForm(HTMLParser):
    """Handle Google's public virus-scan confirmation, never a login form."""
    def __init__(self, html):
        super().__init__()
        self.action, self.params, self.in_form = None, {}, False
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if tag == 'form' and a.get('id') == 'download-form':
            self.action, self.in_form = a.get('action'), True
        if tag == 'input' and self.in_form and a.get('name'):
            self.params[a['name']] = a.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.in_form = False


def download(file_id):
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    data = fetch('https://drive.google.com/uc?' + urlencode(dict(export='download', id=file_id)), opener)
    if not data.startswith(b'%PDF-'):
        form = DownloadForm(data.decode('utf-8', errors='replace'))
        target = urlsplit(form.action or '')
        if target.scheme != 'https' or target.hostname != 'drive.usercontent.google.com' or form.params.get('id') != file_id:
            raise ValueError(f'No public PDF download for {file_id}; received HTML instead.')
        data = fetch(form.action + '?' + urlencode(form.params), opener)
    if not data.startswith(b'%PDF-'):
        raise ValueError(f'Invalid PDF download for {file_id}.')
    return data


def issue_metadata(name, default_language):
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', name.lower()) if not unicodedata.combining(c)).replace('_', '-')
    year = re.search(r'\b(20\d{2})\b', normalized)
    month = next((i for i, names in enumerate(MONTHS, 1) if any(re.search(r'\b' + n + r'\b', normalized) for n in names)), None)
    numeric = re.search(r'\b20\d{2}[-_](0[1-9]|1[0-2])\b', normalized)
    if not month and numeric:
        month = int(numeric[1])
    if not year or not month:
        raise ValueError(f'Use a month and year in the newsletter filename: {name}')
    issue = re.search(r'\bnl\s*(\d+)\b', normalized)
    language = re.search(r'(?:^|[\s_\[(\-])(fr|en|mul)(?=[\s_\])\.\-]|$)', normalized)
    return dict(date=date(int(year[1]), month, 1).isoformat(), issue=int(issue[1]) if issue else None,
                language=language[1] if language else default_language)


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, default=ROOT / '.cache/newsletters')
    args = parser.parse_args()
    config = json.loads((ROOT / 'config/newsletters.json').read_text())
    excluded = set(config['excluded_file_ids'])
    files, visited, queue = {}, set(), [config['folder_id']]
    while queue:
        folder = queue.pop()
        if folder in visited:
            continue
        if not ID.fullmatch(folder) or len(visited) >= 100:
            raise ValueError('Invalid or unexpectedly large folder tree.')
        visited.add(folder)
        html = fetch(f'https://drive.google.com/drive/folders/{folder}').decode('utf-8')
        for item in parse_folder(html, folder):
            if item['id'] in excluded:
                continue
            if item['mime'] == FOLDER:
                queue.append(item['id'])
            elif item['mime'] == PDF:
                files[item['id']] = item
            else:
                print(f"Skipping non-PDF: {item['name']}")
    if not files:
        raise ValueError('No public newsletter PDFs found; refusing to replace the catalogue.')

    cache = args.cache_dir.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    catalogue_path = ROOT / 'data/newsletters.json'
    previous = json.loads(catalogue_path.read_text()) if catalogue_path.exists() else []
    previous = {item['id']: item for item in previous}
    # Cache the archive too: a scheduled build starts from a clean checkout.
    archive_path = cache / 'catalogue.json'
    archive = json.loads(archive_path.read_text()) if archive_path.exists() else []
    previous = {**previous, **{item['id']: item for item in archive}}
    source_texts = json.loads((ROOT / 'data/pdf_text.json').read_text())
    for file_id, item in previous.items():
        if file_id not in files and file_id not in excluded:
            print(f"Retaining archived newsletter: {item['name']}")
            files[file_id] = dict(id=file_id, name=item['name'], modified=item['modified'], archived=True)

    def prepare(item):
        file_id = item['id']
        metadata = issue_metadata(item['name'], config['default_language'])
        old = previous.get(file_id, {})
        stem = f"{metadata['date'][5:7]}-nl{metadata['issue']}" if metadata['issue'] else metadata['date'][:7]
        url = old.get('url') or f"/{metadata['language']}/documents/newsletters/{metadata['date'][:4]}/{stem}-{file_id[:8]}.pdf"
        title = 'Newsletter · ' + metadata['date'][:7]
        if metadata['issue']:
            title += f" · #{metadata['issue']}"
        pdf = cache / (file_id + '.pdf')
        state_path = cache / (file_id + '.json')
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.exists() else None
        if not digest or state.get('modified') != item['modified'] or state.get('sha256') != digest:
            source = ROOT / 'static' / url.lstrip('/')
            if source.exists() and old.get('modified') == item['modified'] and hashlib.sha256(source.read_bytes()).hexdigest() == source_texts.get(url, {}).get('sha256'):
                data = source.read_bytes()
            elif item.get('archived'):
                raise ValueError(f"Archived issue missing from cache and source: {item['name']}")
            else:
                print(f"Downloading {item['name']}", flush=True)
                data = download(file_id)
                if item.get('size') and len(data) != int(item['size']):
                    raise ValueError(f"Drive size changed during download: {item['name']}; retry sync.")
            pdf.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
        reader = PdfReader(pdf)
        if reader.is_encrypted or not reader.pages:
            raise ValueError(f"Unreadable newsletter: {item['name']}")
        document = dict(url=url, legacy=url, aliases=[], language=metadata['language'], category='newsletters',
                        title=title, sha256=digest, source='newsletter')
        thumbnail_url = f'/images/newsletters/{file_id}.jpg'
        thumbnail = cache / (file_id + '.jpg')
        if state.get('sha256') != digest or not thumbnail.exists():
            original = ROOT / 'static' / thumbnail_url.lstrip('/')
            if original.exists() and source_texts.get(url, {}).get('sha256') == digest:
                shutil.copyfile(original, thumbnail)
            else:
                subprocess.run([os.environ.get('PDFTOPPM', 'pdftoppm'), '-f', '1', '-l', '1', '-singlefile',
                                '-scale-to', '800', '-jpeg', str(pdf), str(thumbnail.with_suffix(''))], check=True, capture_output=True)
        text = state.get('text') or source_texts.get(url, {})
        if text.get('sha256') != digest or text.get('title') != title or text.get('version') != VERSION:
            # Extract against an isolated staging tree before touching site files.
            with tempfile.TemporaryDirectory(prefix='efia-newsletter-') as directory:
                stage = Path(directory)
                destination = stage / 'static' / url.lstrip('/')
                destination.parent.mkdir(parents=True)
                shutil.copyfile(pdf, destination)
                text = dict(sha256=digest, version=VERSION, title=title, **extract(document, root=stage))
        atomic_json(state_path, dict(modified=item['modified'], sha256=digest, text=text))
        record = dict(id=file_id, name=item['name'], modified=item['modified'], url=url,
                      thumbnail=thumbnail_url, pages=len(reader.pages), bytes=pdf.stat().st_size, **metadata)
        return record, document, text, pdf, thumbnail

    with ThreadPoolExecutor(max_workers=3) as pool:
        prepared = list(pool.map(prepare, files.values()))
    if len({record['url'] for record, *_ in prepared}) != len(prepared):
        raise ValueError('Newsletter URL collision; use distinct file IDs in the URL generator.')
    # Nothing in the website changes until every public file validates/extracts.
    documents = json.loads((ROOT / 'data/documents.json').read_text())
    documents = [d for d in documents if d.get('source') != 'newsletter']
    texts = json.loads((ROOT / 'data/pdf_text.json').read_text())
    old_urls = {r['url'] for r in previous.values()}
    for url in old_urls:
        texts.pop(url, None)
    records = []
    for record, document, text, pdf, thumbnail in prepared:
        destination = ROOT / 'static' / document['url'].lstrip('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, destination)
        image = ROOT / 'static' / record['thumbnail'].lstrip('/')
        image.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(thumbnail, image)
        documents.append(document)
        texts[document['url']] = text
        records.append(record)
    records.sort(key=lambda r: (r['date'], r['issue'] or 0, r['id']), reverse=True)
    atomic_json(ROOT / 'data/documents.json', documents)
    atomic_json(ROOT / 'data/pdf_text.json', texts)
    atomic_json(catalogue_path, records)
    atomic_json(archive_path, records)
    print(f'Imported {len(records)} newsletters from {len(visited)} public folders.')


if __name__ == '__main__':
    main()
