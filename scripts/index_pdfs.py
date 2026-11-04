#!/usr/bin/env python3
"""Extract local PDFs into Hugo data; only reachable records are published by Hugo.
Requires pypdf; scanned pages also require pdftoppm and Tesseract (eng + fra).
Unchanged documents reuse the checked-in cache, including in CI and local previews.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
VERSION = 1

def extract(document, root=ROOT):
    reader = PdfReader(root / 'static' / document['url'].lstrip('/'))
    passages, links = [], []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        ocr = len(re.sub(r'\W', '', text)) < 30
        if ocr:
            with tempfile.TemporaryDirectory(prefix='efia-pdf-') as directory:
                prefix = str(Path(directory) / 'page')
                subprocess.run([os.environ.get('PDFTOPPM', 'pdftoppm'), '-f', str(number), '-l', str(number), '-singlefile', '-scale-to', '2400', '-png', str(root / 'static' / document['url'].lstrip('/')), prefix], check=True, capture_output=True)
                language = {'fr': 'fra', 'mul': 'eng+fra'}.get(document['language'], 'eng')
                result = subprocess.run(['tesseract', prefix + '.png', 'stdout', '-l', language], check=True, capture_output=True, text=True)
                text = result.stdout
        # Small overlapping passages keep phrase matches and snippets useful.
        text = re.sub(r'\s+', ' ', text).strip()
        for start in range(0, len(text), 850):
            passages.append(dict(text=text[start:start+1100], anchor=f'page={number}', heading=f"{document['title']} · {number}", ocr=ocr))
        for annotation in page.get('/Annots', []):
            action = annotation.get_object().get('/A')
            if action and action.get('/URI'):
                links.append(str(action['/URI']))
    if not passages:
        raise ValueError(f"No searchable text extracted: {document['url']}")
    return dict(passages=passages, links=sorted(set(links)))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if cache does not match source files; do not extract')
    args = parser.parse_args()
    documents = json.loads((ROOT / 'data/documents.json').read_text())
    cache_path = ROOT / 'data/pdf_text.json'
    old = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    cache = {}
    stale = []
    for document in documents:
        path = ROOT / 'static' / document['url'].lstrip('/')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        key = document['url']
        previous = old.get(key, {})
        if previous.get('sha256') == digest and previous.get('version') == VERSION and previous.get('title') == document['title']:
            cache[key] = previous
        elif args.check:
            stale.append(key)
        else:
            print(f'Extracting {key}', flush=True)
            cache[key] = dict(sha256=digest, version=VERSION, title=document['title'], **extract(document))
    if args.check:
        if stale or set(old) != set(cache):
            raise SystemExit('PDF search cache is stale. Run python3 scripts/index_pdfs.py.\n' + '\n'.join(stale))
    else:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + '\n')
    print(f'PDF text cache verified: {len(cache)} documents.')

if __name__ == '__main__':
    main()
