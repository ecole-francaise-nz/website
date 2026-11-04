#!/usr/bin/env python3
"""Public-page parsing, download confirmation and transactional archive regressions."""
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
import sync_newsletters as sync

FOLDER = 'publicFolder123'
FILE = 'publicNewsletter123'


def folder_html(items, token=None):
    records = [[i['id'], [FOLDER], i['name'], i.get('mime', sync.PDF), 0, None, 0, 0, 0,
                1000, i.get('modified', 2000), None, None, i.get('size')] for i in items]
    # Same outer JS string + inner JSON structure as the public Drive page.
    value = json.dumps([records, token, None, None, [], 1], ensure_ascii=False)
    value = value.replace('\\', '\\\\').replace("'", "\\'").replace('[', r'\x5b').replace(']', r'\x5d').replace('"', r'\x22')
    return "<script>window['_DRIVE_ivd'] = '" + value + "';</script>"


class NewsletterTests(unittest.TestCase):
    def test_public_listing_and_issue_dates(self):
        name = 'NL1 Fe\u0301vrier 2026.pdf'
        item = sync.parse_folder(folder_html([dict(id=FILE, name=name)]), FOLDER)[0]
        self.assertEqual(item['name'], name)
        self.assertEqual(item['modified'], 2000)  # modified, not creation timestamp
        self.assertEqual(sync.issue_metadata(name, 'mul'), dict(date='2026-02-01', issue=1, language='mul'))
        self.assertEqual(sync.issue_metadata('NL5 June 2026 [EN].pdf', 'mul')['language'], 'en')
        self.assertEqual(sync.issue_metadata('NL7 Août 2026.pdf', 'mul')['date'], '2026-08-01')
        self.assertEqual(sync.issue_metadata('2027_03_FR.pdf', 'mul')['date'], '2027-03-01')
        for bad in ['Draft.pdf', 'Newsletter 2026.pdf']:
            with self.assertRaises(ValueError):
                sync.issue_metadata(bad, 'mul')
        with self.assertRaises(ValueError):
            sync.parse_folder('<html>Sign in</html>', FOLDER)
        with self.assertRaises(ValueError):
            sync.parse_folder(folder_html([], token='next-page'), FOLDER)
        with self.assertRaises(ValueError):
            sync.parse_folder(folder_html([dict(id=FILE, name=name)] * 50), FOLDER)
        with self.assertRaises(ValueError):
            sync.parse_folder(folder_html([dict(id=FILE, name=name)]), 'differentFolder')

    def test_download_validation_and_confirmation(self):
        html = f'''<form id="download-form" action="https://drive.usercontent.google.com/download">
        <input name="id" value="{FILE}"><input name="confirm" value="t"></form>'''.encode()
        with patch.object(sync, 'fetch', side_effect=[html, b'%PDF-1.4 test']):
            self.assertTrue(sync.download(FILE).startswith(b'%PDF-'))
        with patch.object(sync, 'fetch', return_value=html.replace(b'drive.usercontent.google.com', b'example.org')):
            with self.assertRaises(ValueError):
                sync.download(FILE)
        with patch.object(sync, 'fetch', return_value=b'<html>Sign in</html>'):
            with self.assertRaises(ValueError):
                sync.download(FILE)

    def test_archive_reuse_updates_and_failed_import(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        stream = io.BytesIO()
        writer.write(stream)
        pdf = stream.getvalue()
        items = [dict(id=FILE, name='NL1 Février 2026.pdf', size=len(pdf))]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ['config', 'data', 'static']:
                (root / folder).mkdir()
            (root / 'config/newsletters.json').write_text(json.dumps(dict(folder_id=FOLDER, default_language='mul', excluded_file_ids=[])))
            (root / 'data/documents.json').write_text(json.dumps([dict(url='/existing.pdf')]))
            (root / 'data/pdf_text.json').write_text(json.dumps({'/existing.pdf': {'passages': []}}))

            def render(command, **kwargs):
                Path(command[-1] + '.jpg').write_bytes(b'test-thumbnail')

            with patch.object(sync, 'ROOT', root), patch('sys.argv', ['sync_newsletters.py']), \
                 patch.object(sync, 'fetch', side_effect=lambda url: folder_html(items).encode()), \
                 patch.object(sync, 'download', return_value=pdf) as download, \
                 patch.object(sync.subprocess, 'run', side_effect=render), \
                 patch.object(sync, 'extract', return_value=dict(passages=[dict(text='school fixture', anchor='page=1')], links=[])):
                sync.main()
                first = json.loads((root / 'data/newsletters.json').read_text())[0]
                self.assertEqual(first['date'], '2026-02-01')
                self.assertEqual(download.call_count, 1)
                sync.main()
                self.assertEqual(download.call_count, 1)  # no repeat download/extraction
                shutil.rmtree(root / '.cache')
                sync.main()
                self.assertEqual(download.call_count, 1)  # a lost cache reuses verified source PDFs
                items[0]['modified'] = 3000
                sync.main()
                self.assertEqual(download.call_count, 2)
                # Fresh checkout with only the cache still retains missing Drive issues.
                for path in (root / 'static').rglob('*.pdf'):
                    path.unlink()
                (root / 'data/newsletters.json').unlink()
                items[:] = [dict(id='newPublicNewsletter', name='NL2 Mars 2026.pdf', size=len(pdf))]
                sync.main()
                records = json.loads((root / 'data/newsletters.json').read_text())
                self.assertEqual({r['id'] for r in records}, {FILE, 'newPublicNewsletter'})
                self.assertTrue((root / 'static' / first['url'].lstrip('/')).exists())
                self.assertIn('/existing.pdf', json.loads((root / 'data/pdf_text.json').read_text()))
                original = {p.name: p.read_bytes() for p in (root / 'data').glob('*.json')}
                items[:] = [dict(id='brokenNewsletter', name='No date.pdf')]
                with self.assertRaises(ValueError):
                    sync.main()
                self.assertEqual(original, {p.name: p.read_bytes() for p in (root / 'data').glob('*.json')})
                items[:] = []
                with self.assertRaises(ValueError):
                    sync.main()
                # Deliberate withdrawal removes an issue from catalogue and index.
                config = json.loads((root / 'config/newsletters.json').read_text())
                config['excluded_file_ids'] = [FILE]
                (root / 'config/newsletters.json').write_text(json.dumps(config))
                items[:] = [dict(id='newPublicNewsletter', name='NL2 Mars 2026.pdf', size=len(pdf))]
                sync.main()
                self.assertEqual(len(json.loads((root / 'data/newsletters.json').read_text())), 1)
                self.assertNotIn(first['url'], json.loads((root / 'data/pdf_text.json').read_text()))


if __name__ == '__main__':
    unittest.main()
