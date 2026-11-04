(function () {
  var cards = Array.prototype.slice.call(document.querySelectorAll('#cards .card'));
  if (!cards.length) return;
  var list = document.getElementById('cards');
  var q = document.getElementById('q');
  var sort = document.getElementById('sort');
  var count = document.getElementById('result-count');
  var reset = document.getElementById('reset');
  var reset2 = document.getElementById('reset2');
  var empty = document.getElementById('empty');
  var activeCount = document.getElementById('active-count');
  var details = document.getElementById('filters');
  var more = document.getElementById('more');
  var moreButton = document.getElementById('more-button');
  var PAGE = 24;          // 一度に表示する件数
  var limit = PAGE;
  var boxes = Array.prototype.slice.call(document.querySelectorAll('.facet input'));
  var keys = ['type', 'purpose', 'stage', 'activity', 'place', 'industry', 'size'];
  var multi = { purpose: true, activity: true };
  cards.forEach(function (c, i) { c.dataset.order = i; });

  function selected() {
    var s = {};
    boxes.forEach(function (b) {
      if (b.checked) (s[b.name] = s[b.name] || []).push(b.value);
    });
    return s;
  }

  // build.py の normalize と同じ：全角英数を半角に、小文字に、ひらがなをカタカナに
  function normalize(t) {
    t = (t || '');
    if (t.normalize) t = t.normalize('NFKC');
    return t.toLowerCase().replace(/[ぁ-ゖ]/g, function (ch) {
      return String.fromCharCode(ch.charCodeAt(0) + 0x60);
    }).trim();
  }

  // 言い換え表（config/synonyms.json）。検索語がグループの言葉か読みに当たれば、グループの言葉でも探す
  var synonyms = [];
  try { synonyms = JSON.parse(document.getElementById('synonyms').textContent) || []; } catch (e) { synonyms = []; }
  function alternatives(term) {
    var alts = [term];
    synonyms.forEach(function (g) {
      var hit = g.words.concat(g.readings).some(function (w) {
        return w === term || (term.length >= 2 && w.indexOf(term) !== -1);
      });
      if (hit) g.words.forEach(function (w) { if (alts.indexOf(w) === -1) alts.push(w); });
    });
    return alts;
  }

  // 絞り込みと検索は全件に効かせ、当てはまった事例のうち先頭の limit 件だけを表示する
  function apply(pushState, keepLimit) {
    if (!keepLimit) limit = PAGE;
    var s = selected();
    var words = normalize(q.value).split(/\s+/).filter(Boolean);
    var terms = words.map(alternatives);
    var shown = 0;
    var visible = 0;
    Array.prototype.forEach.call(list.children, function (c) {
      var ok = keys.every(function (k) {
        if (!s[k]) return true;
        var v = c.dataset[k] || '';
        var vals = multi[k] ? v.split('|') : [v];
        return s[k].some(function (x) { return vals.indexOf(x) !== -1; });
      });
      if (ok && words.length) {
        var hay = c.dataset.search;
        ok = terms.every(function (alts) {
          return alts.some(function (w) { return hay.indexOf(w) !== -1; });
        });
      }
      if (ok) shown++;
      c.hidden = !ok || shown > limit;
      if (!c.hidden) visible++;
    });
    var rest = shown - visible;
    more.hidden = rest <= 0;
    moreButton.textContent = 'もっと見る（残り' + rest + '件）';
    var n = Object.keys(s).reduce(function (a, k) { return a + s[k].length; }, 0);
    var filtering = n > 0 || words.length > 0;
    count.textContent = filtering ? cards.length + '件中 ' + shown + '件の事例' : cards.length + '件の事例';
    activeCount.textContent = n ? n + '件の条件' : '';
    reset.hidden = !filtering;
    empty.hidden = shown !== 0;
    if (pushState) saveUrl(s);
  }

  function doSort() {
    var mode = sort.value;
    var arr = cards.slice();
    arr.sort(function (a, b) {
      if (mode === 'year-desc' || mode === 'year-asc') {
        var ya = parseInt(a.dataset.year, 10), yb = parseInt(b.dataset.year, 10);
        var ea = isNaN(ya), eb = isNaN(yb);
        if (ea !== eb) return ea ? 1 : -1; // 開始年が空欄の事例は最後に
        if (!ea && ya !== yb) return mode === 'year-desc' ? yb - ya : ya - yb;
      }
      if (mode === 'score') {
        // 観測スコアの高い順。スコアが空欄の事例は最後に、同点は確認日の新しい順
        var sa = parseInt(a.dataset.score, 10), sb = parseInt(b.dataset.score, 10);
        var na = isNaN(sa), nb = isNaN(sb);
        if (na !== nb) return na ? 1 : -1;
        if (!na && sa !== sb) return sb - sa;
      }
      if (mode === 'checked-desc' || mode === 'score') {
        var d = byChecked(a, b);
        if (d) return d;
      }
      return a.dataset.order - b.dataset.order;
    });
    arr.forEach(function (c) { list.appendChild(c); });
  }

  // 確認日の新しい順。確認日が空欄の事例は最後に回す
  function byChecked(a, b) {
    var ca = a.dataset.checked || '', cb = b.dataset.checked || '';
    if (!ca !== !cb) return ca ? -1 : 1;
    return ca === cb ? 0 : (ca < cb ? 1 : -1);
  }

  function saveUrl(s) {
    var p = new URLSearchParams();
    keys.forEach(function (k) { if (s[k]) p.set(k, s[k].join(',')); });
    if (q.value.trim()) p.set('q', q.value.trim());
    if (sort.value !== 'score') p.set('sort', sort.value);
    var qs = p.toString();
    history.replaceState(null, '', qs ? '?' + qs : location.pathname);
  }

  function loadUrl() {
    var p = new URLSearchParams(location.search);
    var any = false;
    boxes.forEach(function (b) {
      var v = p.get(b.name);
      b.checked = !!v && v.split(',').indexOf(b.value) !== -1;
      if (b.checked) any = true;
    });
    if (p.get('q')) q.value = p.get('q');
    if (p.get('sort') && sort.querySelector('option[value="' + p.get('sort') + '"]')) sort.value = p.get('sort');
    if (any) details.open = true;
  }

  function clearAll() {
    boxes.forEach(function (b) { b.checked = false; });
    q.value = '';
    apply(true);
    q.focus();
  }

  if (window.matchMedia('(min-width: 900px)').matches) details.open = true;
  loadUrl();
  doSort();
  apply(false);

  boxes.forEach(function (b) { b.addEventListener('change', function () { apply(true); }); });
  var timer;
  q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { apply(true); }, 150); });
  sort.addEventListener('change', function () { doSort(); apply(true); });
  reset.addEventListener('click', clearAll);
  reset2.addEventListener('click', clearAll);
  moreButton.addEventListener('click', function () {
    var first = limit;
    limit += PAGE;
    apply(false, true);
    // 追加した最初の事例にフォーカスを移す（キーボードやスクリーンリーダーで続きから読めるように）
    var shownCards = Array.prototype.filter.call(list.children, function (c) { return !c.hidden; });
    var next = shownCards[first] && shownCards[first].querySelector('a');
    if (next) next.focus({ preventScroll: true });
  });
})();
