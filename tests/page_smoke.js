// Test de fumée de l'application : charge docs/index.html dans un navigateur simulé (jsdom), exécute ses scripts,
// simule un portefeuille et un journal, et échoue (code 1) à la moindre erreur JavaScript ou si un onglet ne se remplit pas.
// Usage : npm install --no-save jsdom@24 && node tests/page_smoke.js docs/index.html
// Pourquoi : du 8 au 9 novembre 2026, une déclaration placée dans un `switch` (zone morte temporelle) arrêtait le script :
// le tableau des actions, les secteurs, Mon portefeuille et le Journal restaient vides sans que rien ne le signale.
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const file = process.argv[2] || 'docs/index.html';
const html = fs.readFileSync(file, 'utf8');
const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(String(e.detail || e.message || e)));
const DAY = 864e5, now = Date.now();
const journal = [{ id: 'a1', created: new Date(now - 101 * DAY).toISOString(), confirmed: new Date(now - 100 * DAY).toISOString(),
  asset: 'sp500', assetName: 'S&P 500', ticker: '', action: 'acheter', amount: 5000, thesis: 't', inval: 'i',
  answers: ['1', '2', '3', '4', '5'], snapshot: { color: 'orange', trend_broken: false, price: 1, drawdown: 0.05 }, status: 'confirmé' }];
const portfolio = { lines: [
  { label: 'ETF x2', kind: 'ndx', ticker: '', amount: 10000, lev: 2, acct: 'PEA' },
  { label: 'Action', kind: 'stock', ticker: 'NVDA', amount: 9000, lev: 1, acct: 'CTO' },
  { label: 'Livret', kind: 'safe', ticker: '', amount: 10000, lev: 1, acct: 'Livret / cash' }],
  targets: { equity: 60, stock: 15, btc: 10, safe: 15, monthly: 1000 } };
const dom = new JSDOM(html, {
  runScripts: 'dangerously', virtualConsole: vc, url: 'https://example.org/feux/',
  beforeParse(w) {
    w.localStorage.setItem('feux-journal', JSON.stringify(journal));
    w.localStorage.setItem('feux-portfolio', JSON.stringify(portfolio));
    w.HTMLElement.prototype.scrollIntoView = function () {};
  },
});
const w = dom.window, d = w.document, $ = s => d.querySelector(s), $$ = s => Array.from(d.querySelectorAll(s));
const fails = [];
const expect = (ok, what) => { if (!ok) fails.push(what); };
try {
  expect($$('section.card').length >= 4, 'cartes du jour (≥ 4)');
  expect($$('#stocks-table tr').length > 50, 'tableau des actions (> 50 lignes)');
  expect($$('#sectors .sec').length >= 11, 'secteurs et thèmes (≥ 11)');
  expect($$('#pf-table tr').length >= 4, 'Mon portefeuille : tableau des lignes');
  expect(/Exposition réelle/.test($('#pf-table').textContent), 'Mon portefeuille : colonnes');
  expect($('#pf-analysis').innerHTML.length > 200, 'Mon portefeuille : analyse');
  expect(!!$('#j-list button[data-a="review"]'), 'Journal : revue à 90 jours proposée');
  expect(/revue/.test($('nav.tabs button[data-t="journal"]').textContent), 'Journal : compteur de revues');
  expect(!$('#sanity') || $('#sanity').innerHTML === '' || $$('#sanity tr').length > 3, 'Validation : témoins');
  // un clic sur une société ouvre sa fiche
  const row = $('#stocks-table tr[data-key]'); if (row) row.click();
  expect(($('#stock-detail').textContent || '').length > 100, 'fiche société');
  // vente du Bitcoin : questions de vente obligatoires
  $('#j-asset').value = 'btc'; $('#j-asset').dispatchEvent(new w.Event('change'));
  $('#j-action').value = 'vendre'; $('#j-action').dispatchEvent(new w.Event('change'));
  expect($('#j-sell').style.display === 'block', 'Journal : questions de vente affichées');
  $$('#j-questions input').forEach(i => { i.value = 'x'; });
  $('#j-add').click();
  expect(/questions de vente/.test($('#j-add-msg').textContent), 'Journal : questions de vente exigées');
  $$('#j-questions input').forEach(i => { i.value = 'x'; });
  $$('#j-sell input').forEach(i => { i.value = 'y'; });
  $('#j-add').click();
  const J = JSON.parse(w.localStorage.getItem('feux-journal'));
  const it = J[J.length - 1];
  expect(it.action === 'vendre' && Array.isArray(it.sell) && it.delay_h >= 48, 'Journal : intention de vente enregistrée');
  // revue à 90 jours
  $$('#j-list input[data-rq]').forEach(i => { i.value = 'r'; });
  const rb = $('#j-list button[data-a="review"]'); if (rb) rb.click();
  expect(!!JSON.parse(w.localStorage.getItem('feux-journal'))[0].review, 'Journal : revue enregistrée');
  // onglets
  $$('nav.tabs button').forEach(b => b.click());
} catch (e) {
  errors.push('test : ' + e);
}
if (errors.length || fails.length) {
  console.error('ÉCHEC du test de fumée de ' + file);
  errors.forEach(e => console.error('  erreur JavaScript : ' + e));
  fails.forEach(f => console.error('  non rendu : ' + f));
  process.exit(1);
}
console.log('Test de fumée OK : ' + file);
