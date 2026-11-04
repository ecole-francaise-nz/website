/* Search schema: documents have title, url, language, type and anchored passages.
   PDF passages use browser-native #page=N destinations. */
const SiteSearch = (() => {
  const fold = value => value.toLowerCase().replace(/[œæßøłđðþ]/g, c => ({œ:'oe',æ:'ae',ß:'ss',ø:'o',ł:'l',đ:'d',ð:'d',þ:'th'})[c]).normalize('NFKD').replace(/\p{M}/gu, '');
  function prepare(pages) {
    return pages.map(page => ({...page, foldedTitle: fold(page.title), passages: page.passages.map(p => ({...p, foldedText: fold(p.text), foldedHeading: fold(p.heading)}))}));
  }
  function search(pages, query) {
    const terms = [...new Set(fold(query).match(/[\p{L}\p{N}]+/gu) || [])];
    if (!terms.length) return [];
    const phrase = fold(query).trim();
    return pages.flatMap(page => {
      let best;
      for (const passage of page.passages) {
        const combined = `${page.foldedTitle} ${passage.foldedHeading} ${passage.foldedText}`;
        if (!terms.every(term => combined.includes(term))) continue;
        const score = terms.reduce((sum, term) => sum + (passage.foldedText.includes(term) ? 4 : 0) + (page.foldedTitle.includes(term) ? 3 : 0), 0) + (passage.foldedText.includes(phrase) ? 5 : 0) + (passage.anchor ? 1 : 0);
        if (!best || score > best.score) best = {...passage, score};
      }
      return best ? [{...page, match: best, score: best.score}] : [];
    }).sort((a,b) => Number(a.type === 'pdf') - Number(b.type === 'pdf') || b.score - a.score || a.title.localeCompare(b.title));
  }
  return {fold, prepare, search};
})();

(() => {
  const panel = document.getElementById('site-search-panel');
  if (!panel) return;
  const input = document.getElementById('site-search-query');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const fr = document.documentElement.lang === 'fr';
  const hint = fr ? 'Recherchez une information sur l’école.' : 'Find information about the school.';
  let indexPromise, generation = 0, timer;
  status.textContent = hint;
  function load() {
    if (!indexPromise) indexPromise = fetch(panel.dataset.index).then(response => {
      if (!response.ok) throw new Error('Search index unavailable');
      return response.json();
    }).then(index => SiteSearch.prepare(index.pages)).catch(error => { indexPromise = null; throw error; });
    return indexPromise;
  }
  async function update() {
    const request = ++generation;
    const query = input.value.trim();
    results.replaceChildren();
    if (!SiteSearch.fold(query).match(/[\p{L}\p{N}]/u)) { status.textContent = hint; return; }
    status.textContent = fr ? 'Recherche…' : 'Searching…';
    try {
      const pages = await load();
      if (request !== generation) return;
      const matches = SiteSearch.search(pages, query);
      const shown = matches.slice(0, 12);
      status.textContent = matches.length ? (fr ? `${matches.length} résultat(s)` : `${matches.length} result${matches.length === 1 ? '' : 's'}`) + (matches.length > 12 ? (fr ? ' — les 12 premiers sont affichés.' : ' — showing the first 12.') : '') : (fr ? 'Aucun résultat. Essayez d’autres mots.' : 'No results. Try different words.');
      for (const page of shown) {
        const li = document.createElement('li');
        const link = document.createElement('a');
        link.href = page.url + (page.match.anchor ? '#' + (page.type === 'pdf' ? page.match.anchor : encodeURIComponent(page.match.anchor)) : '');
        link.hreflang = page.language;
        const title = document.createElement('strong');
        title.textContent = page.title;
        link.append(title);
        if (page.type === 'pdf') {
          const format = document.createElement('span');
          format.className = 'search-language';
          format.textContent = 'PDF · page ' + page.match.anchor.replace('page=', '');
          link.append(format);
        }
        if (page.language !== document.documentElement.lang && page.language !== 'mul') {
          const badge = document.createElement('span');
          badge.className = 'search-language';
          badge.textContent = page.language === 'fr' ? 'Français' : 'English';
          link.append(badge);
        }
        const snippet = document.createElement('span');
        snippet.className = 'search-snippet';
        const text = page.match.text;
        const terms = SiteSearch.fold(query).match(/[\p{L}\p{N}]+/gu) || [];
        const position = Math.max(0, Math.min(...terms.map(t => SiteSearch.fold(text).indexOf(t)).filter(i => i >= 0)));
        const start = Number.isFinite(position) ? Math.max(0, position - 65) : 0;
        snippet.textContent = (start ? '…' : '') + text.slice(start, start + 220) + (text.length > start + 220 ? '…' : '');
        link.append(snippet);
        li.append(link);
        results.append(li);
      }
    } catch (_) {
      if (request === generation) status.textContent = fr ? 'La recherche est indisponible. Réessayez en saisissant votre recherche.' : 'Search is unavailable. Type your query again to retry.';
    }
  }
  input.addEventListener('input', () => { ++generation; clearTimeout(timer); timer = setTimeout(update, 100); });
  panel.querySelector('form').addEventListener('submit', event => { event.preventDefault(); clearTimeout(timer); update(); });
  input.addEventListener('focus', () => { load().catch(() => {}); });
  results.addEventListener('click', event => {
    const link = event.target.closest('a');
    // Keep the list available when opening several results in other tabs/windows.
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || (link.target && link.target !== '_self') || link.hasAttribute('download')) return;
    panel.hidden = true;
    document.getElementById('site-search-toggle').setAttribute('aria-expanded', 'false');
  });
})();

// A search hit inside a collapsed FAQ must become visible on arrival.
(() => {
  function reveal() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
    if (!id) return;
    const target = document.getElementById(id);
    if (!target) return;
    let ancestor = target.closest('details');
    while (ancestor) { ancestor.open = true; ancestor = ancestor.parentElement.closest('details'); }
    requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
  }
  window.addEventListener('hashchange', reveal);
  reveal();
})();
