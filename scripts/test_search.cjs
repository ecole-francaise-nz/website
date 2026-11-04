const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/js/search.js', 'utf8').split('\n(() => {')[0];
const search = vm.runInNewContext(source + '\nSiteSearch;');
assert.equal(search.fold('ÉCOLE Ç œ Æ à ü ß'), 'ecole c oe ae a u ss');
const pages = search.prepare([{title:'École',url:'/test/',passages:[{text:'Le cœur des élèves français',heading:'Bienvenue',anchor:'paragraph'}]}]);
assert.equal(search.search(pages,'COEUR francais')[0].match.anchor,'paragraph');
assert.equal(search.search(pages,'école élèves').length,1);
assert.equal(search.search(pages,'no match').length,0);
assert.equal(search.search(pages,'!?').length,0);
assert.equal(search.search(pages,'fran').length,1);
console.log('Search normalization, multi-word matching, prefix matching and empty queries passed.');
const mixed = search.prepare([
  {title:'Insurance', type:'pdf', url:'/en/documents/test.pdf', passages:[{text:'insurance insurance',heading:'Insurance',anchor:'page=1'}]},
  {title:'School information', type:'page', url:'/info/', passages:[{text:'Insurance is available.',heading:'Information',anchor:'info'}]},
]);
const ranked = search.search(mixed, 'insurance');
assert.equal(ranked[0].type, 'page');
assert.equal(ranked[1].type, 'pdf');
assert.ok(ranked[1].score > ranked[0].score, 'Pages must precede PDFs even when the PDF is more relevant');
console.log('Website results precede higher-scoring PDF results.');
