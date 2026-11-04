"""Integration tests in an isolated copy: graph exclusions and bilingual fallback."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='efia-search-test-') as directory:
    site = Path(directory)
    for folder in ['assets', 'config', 'content', 'data', 'layouts', 'static']:
        shutil.copytree(ROOT / folder, site / folder)
    def page(language, name, body):
        (site / 'content' / language / (name + '.md')).write_text('+++\ntitle = "' + name + '"\n+++\n' + body)
    page('en', 'search-test-english', 'English-only searchable fixture.')
    fixture_page = site / 'content/en/search-test-english.md'
    fixture_page.write_text(fixture_page.read_text().replace('+++\n', '+++\ndesign = "search-fixture"\n', 1))
    with (site / 'layouts/partials/design/search-fixture.html').open('w') as file:
        file.write('{{ .Content }}' + '\n<div><a href="/about/">StandaloneLinkNeedle</a></div>\n'
                   '<table><tr><th>TableHeaderNeedle</th><td>TableCellNeedle</td></tr></table>\n'
                   '<blockquote>StandaloneQuoteNeedle</blockquote>\n'
                   '<dl><dt>DefinitionTermNeedle</dt><dd>DefinitionTextNeedle</dd></dl>\n')
    page('fr', 'search-test-french', 'Contenu uniquement en français.')
    page('en', 'search-test-private-a', '[B](/search-test-private-b/) [Unlinked PDF](/efia-flyer.pdf)')
    page('en', 'search-test-private-b', '[A](/search-test-private-a/)')
    with (site / 'content/en/about/team.md').open('a') as file:
        file.write('\n[English fixture](/search-test-english/?test=1#main-content)\n[French fixture](/fr/search-test-french/)\n[External](https://example.org/search-test-private-a/)\n')
    def build():
        subprocess.run(['hugo','--source',str(site),'--destination',str(site/'public')],check=True,capture_output=True)
        return [json.loads((site/'public'/name).read_text())['pages'] for name in ['index.json','fr/index.json']]
    en, fr = build()
    for index in [en, fr]:
        fixture = next(p for p in index if p['url'] == '/search-test-english/')
        for term in ['StandaloneLinkNeedle', 'TableHeaderNeedle', 'TableCellNeedle',
                     'StandaloneQuoteNeedle', 'DefinitionTermNeedle', 'DefinitionTextNeedle']:
            assert any(term in p['text'] and p['anchor'] for p in fixture['passages']), term
    for index, url, facts, quote in [
        (en, '/', 'No school zone', 'He has gained confidence'),
        (fr, '/fr/', 'Sans secteur géographique', 'Il retrouve confiance en lui'),
    ]:
        home = next(p for p in index if p['url'] == url)
        assert any(facts in p['text'] for p in home['passages'])
        assert any(quote in p['text'] for p in home['passages'])
    # Featured social cards must remain searchable and link to their visible text.
    for index, url in [(en, '/school-life/news/'), (fr, '/fr/school-life/news/')]:
        news = next(p for p in index if p['url'] == url)
        html = (site / 'public' / url.lstrip('/') / 'index.html').read_text()
        for network in ['Facebook', 'Instagram', 'LinkedIn', 'RedNote', 'YouTube']:
            hits = [p for p in news['passages'] if network in p['text']]
            assert hits, f'{network} missing from {url} search passages'
            assert all(p['anchor'] and f'id="{p["anchor"]}"' in html for p in hits)
    for index in [en,fr]:
        urls={p['url'] for p in index}
        assert '/search-test-english/' in urls and '/fr/search-test-french/' in urls
        assert '/search-test-private-a/' not in urls and '/search-test-private-b/' not in urls
        assert '/en/documents/about/efia-flyer.pdf' not in urls
    assert any(p['url']=='/fr/search-test-french/' and p['language']=='fr' for p in en)
    assert any(p['url']=='/search-test-english/' and p['language']=='en' for p in fr)
    # Linking a legacy URL from a reachable page should index only its canonical PDF.
    with (site / 'content/en/about/team.md').open('a') as file:
        file.write('\n[Linked PDF](/efia-flyer.pdf?t=1#page=1)\n')
    en, fr = build()
    for index in [en,fr]:
        urls={p['url'] for p in index}
        assert '/en/documents/about/efia-flyer.pdf' in urls
        assert '/efia-flyer.pdf' not in urls
    print('Passed orphan-page cycles, orphan PDFs, both language fallbacks, and canonical PDF reachability.')
