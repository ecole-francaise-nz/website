# École Française Internationale Auckland

Bilingual Hugo website for [ecole-francaise.nz](https://ecole-francaise.nz/).
Requires Hugo Extended 0.165.0 (the same version used by GitHub Pages).

## Preview

```sh
hugo server --bind 127.0.0.1 --port 1313 --disableFastRender
```

Open <http://localhost:1313/> or <http://localhost:1313/fr/>. Analytics and
conversion tracking are disabled in the development preview. A normal production
build retains the existing tracking. Pushing to `main` deploys through GitHub Pages.

## Build and check

```sh
hugo --destination /tmp/efia-preview-build --cleanDestinationDir
python3 scripts/check_site.py /tmp/efia-preview-build
```

The check covers internal links, image/script/style destinations, anchor targets,
page languages, image alt attributes, duplicate IDs and page headings. It skips
heading requirements for redirect pages. It does not crawl external services.

## Editing the redesign

- Navigation: `config/_default/menus.en.toml` and `menus.fr.toml`.
- Shared colours, typography and responsive layouts: `assets/css/custom.css`.
- Homepage and page-specific layouts: `layouts/partials/design/`.
- Overview pages: content front matter with `design: hub` and a `cards` array.
- Uniform/campus photos, staff introductions and FAQ answers: their bilingual
  content files. FAQ answers remain in the HTML behind native disclosure controls; galleries also work as ordinary image links without JS.
- Shared interface translations: `data/interface.json`.
- Calendar dates: the English/French term-date content files and the matching
  downloadable files in `static/calendars/`. Keep both languages and downloads
  in sync when updating dates. Calendar event end dates are exclusive, so they
  are one day after the final date displayed on the page.

Existing page URLs remain available. New overview pages group admissions,
parent information, governance, community and enrichment without moving the
original detail pages or PDF documents.

For a team review, start with the homepage, Parent information, School uniform,
Our campus, Meet our team, Governance & reports, FAQs and Dates & school hours.

## Local search

Hugo generates `/index.json` and `/fr/index.json` on every build; no separate
indexing service or build step is needed. Each language uses its own pages and
includes pages from the other language only when a translation is missing.
`layouts/partials/search/page.html` supplies both the displayed HTML and indexed
passages, keeping paragraph anchors aligned (including custom layouts and FAQs).
Generated paragraph anchors can change when paragraphs are reordered; existing
explicit heading IDs are preserved.

`assets/js/search.js` loads the current language index on first search, caches it
for that page visit, and matches normalized words as the visitor types. Accents,
case, and ligatures such as œ/oe and æ/ae are ignored. Results show the best
matching passage per page; FAQ answers open automatically on arrival. Queries
are processed in the browser and are not sent to a search provider.

Only content reachable by following links from the English or French homepage is
published in search. The traversal follows navigation, page content, footer links,
redirects, and local links embedded in PDFs. It does not use the sitemap, directory
contents, or the search index itself as discovery sources. An isolated group of
pages cannot make itself searchable just by linking to each other.

## PDF organisation and search

PDF originals live in `static/{language}/documents/{category}/`. Languages are
`en`, `fr`, and `mul` for bilingual documents; categories include `admissions`,
`international`, `governance`, `school-life`, and `about`.

- `data/documents.json` records titles, languages, canonical URLs, old URLs, and
  compatibility aliases, and optional translation keys. Only give equivalent documents the same translation
  key. Search prefers a reachable version in the reader’s language, with fallback
  to the other language when needed.
- `config/_default/module.toml` mounts the same originals at their old addresses
  for existing shared links, including the former `/documents/{language}/…` layout. Keep site links pointing to the organised URLs.
- `data/pdf_text.json` is a source-only extraction cache, not a public search index.
  It holds text and embedded links with per-file hashes. Hugo publishes only the
  reachable records. Unlinked PDFs remain accessible by direct URL but are omitted
  from both search indexes.
- Text extraction runs locally. Image-only pages use Tesseract OCR. PDF results
  link to `#page=N`; opening at that page depends on the browser’s PDF viewer.
  PDF bytes, signatures, forms, and document contents are unchanged.

After adding/replacing a PDF or editing its search title:

```sh
python3 -m pip install -r scripts/requirements-search.txt
# For scanned documents, install Poppler and Tesseract with eng/fra language data.
python3 scripts/index_pdfs.py
hugo --destination /tmp/efia-preview-build --cleanDestinationDir
```

The extractor accepts `PDFTOPPM` and Tesseract’s `TESSDATA_PREFIX` environment
variables for nonstandard tool locations. Commit the manifest, original, and text
cache together. CI verifies cache hashes before publishing, so stale PDF text
cannot silently deploy. Ordinary Hugo previews need no Python/OCR tools once the
cache is current; links and reachability update automatically on every build.

Additional checks:

```sh
python3 scripts/index_pdfs.py --check
node scripts/test_search.cjs
python3 scripts/check_search.py /tmp/efia-preview-build
python3 scripts/test_search_build.py
```

Search results list all matching website pages before PDF matches, with relevance
ranking within each group. The 12-result display limit applies after this ordering.

## Newsletters from public Google Drive

Staff continue to upload final PDF newsletters to the public folder configured in
`config/newsletters.json`. No Google API key, account cookies or login is used.
Only PDFs listed in this folder (and public child folders) are imported. Shortcuts,
Google Docs and unrelated Drive files are skipped. Keep drafts in a separate folder.

Use filenames such as `NL9 Octobre 2026.pdf`, `NL10 November 2026.pdf`, or
`2027-02.pdf`. French and English month names, accents and decomposed accents are
supported. The issue date comes from the filename, never the upload date. Current
newsletters contain French and English, so the default language is `mul`; append
`[FR]` or `[EN]` to a filename for a single-language issue. PDFs are published under
`/{language}/documents/newsletters/{year}/`. Year subfolders are discovered
recursively. Each folder must contain fewer than 50 items; larger/paginated listings
fail explicitly rather than silently omitting files.

Run locally after installing the PDF tools described above:

```sh
python3 scripts/sync_newsletters.py
python3 scripts/index_pdfs.py --check
python3 scripts/test_newsletters.py
```

The importer downloads new/changed files, validates their PDF bytes and file size,
extracts text (OCR for scanned pages), and creates first-page thumbnails. It stages
all issues before updating the website catalogue. Unchanged files reuse verified
source PDFs and cached text. Google download-confirmation pages are handled, while
login pages, malformed listings and missing dates stop the build. A failed job
leaves the existing deployment intact.

Both the production workflow (when these source changes go live) and the separate
staff preview workflow run nightly at 14:17 UTC (02:17 NZST / 03:17 NZDT), on a push,
or via **Run workflow** in GitHub Actions. GitHub may delay scheduled runs and may
disable schedules on inactive public repositories; Actions displays their status.
Successful builds commit imported PDFs, thumbnails and search data back to the
same repository using `github-actions[bot]`. Those token-authenticated commits do
not start another run; the current run deploys the validated build. A concurrent
source push makes the archive push fail safely; rerun on the newer source.

Previously imported issues remain in the website archive even if removed from
Drive, including if the Actions cache is evicted. To deliberately withdraw an
issue, put its full Drive file ID in `excluded_file_ids` in
`config/newsletters.json`. This removes it from the timeline and search; existing
PDF URLs remain available. For a legal/privacy removal, remove the source PDF and
thumbnail as well, then rebuild/deploy.

Drive's public page format is undocumented. If it changes, update `parse_folder()`
in `scripts/sync_newsletters.py`; the parser and download-confirmation logic have
regression tests in `scripts/test_newsletters.py`. The website itself uses local
PDFs, images and search data, so visitors do not depend on Drive availability.

## Staff review deployment

The review site is separate from production:

- Preview repository: `ecole-francaise-nz/website-preview` (a source snapshot with a preview-only workflow).
- Preview address: `https://preview.ecole-francaise.nz/`.
- Its Pages source is **GitHub Actions**. The workflow builds with the preview
  environment, imports newsletters, validates site/search, and deploys only here.
- Production remains in `ecole-francaise-nz/website`; pushing its `main` branch
  deploys the live school website.

Build a local review snapshot outside this checkout:

```sh
python3 scripts/prepare_preview.py \
  --destination /tmp/efia-staff-preview-site \
  --url https://preview.ecole-francaise.nz/
```

This runs the site/search checks, adds a bilingual staff-review banner, excludes
analytics, writes noindex metadata and a robots exclusion, and generates the
preview CNAME. It also supports a GitHub project URL when no custom domain is
available. The preview remains publicly accessible; robots directives are not
access control.

To update the preview source from this production checkout, first bring any
bot-imported newsletter changes back from the preview repository so its archive
is preserved, then prepare a clean source snapshot:

```sh
python3 scripts/prepare_preview_repository.py --destination /tmp/efia-preview-source
```

Sync that snapshot into a clone of `website-preview`, preserving its `.git`
directory, review the changes, commit and push there. The helper copies known
website source folders, uses the preview CNAME and installs only
`scripts/preview-workflow.yaml` as `.github/workflows/preview.yaml`. It excludes
local settings, unrelated files, build output and caches. Never copy the production
deployment workflow into the preview repository. Neither helper pushes anything.
