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
  var boxes = Array.prototype.slice.call(document.querySelectorAll('.facet input'));
  var keys = ['type', 'purpose', 'stage', 'activity', 'place', 'industry'];
  var multi = { purpose: true, activity: true };
  cards.forEach(function (c, i) { c.dataset.order = i; });

  function selected() {
    var s = {};
    boxes.forEach(function (b) {
      if (b.checked) (s[b.name] = s[b.name] || []).push(b.value);
    });
    return s;
  }

  function normalize(t) {
    return (t || '').toLowerCase().replace(/[Ａ-Ｚａ-ｚ０-９]/g, function (ch) {
      return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0);
    }).trim();
  }

  function apply(pushState) {
    var s = selected();
    var words = normalize(q.value).split(/\s+/).filter(Boolean);
    var shown = 0;
    cards.forEach(function (c) {
      var ok = keys.every(function (k) {
        if (!s[k]) return true;
        var v = c.dataset[k] || '';
        var vals = multi[k] ? v.split('|') : [v];
        return s[k].some(function (x) { return vals.indexOf(x) !== -1; });
      });
      if (ok && words.length) {
        var hay = c.dataset.search;
        ok = words.every(function (w) { return hay.indexOf(w) !== -1; });
      }
      c.hidden = !ok;
      if (ok) shown++;
    });
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
      if (mode !== 'default') {
        var ya = parseInt(a.dataset.year, 10), yb = parseInt(b.dataset.year, 10);
        var ea = isNaN(ya), eb = isNaN(yb);
        if (ea !== eb) return ea ? 1 : -1; // 開始年が空欄の事例は最後に
        if (!ea && ya !== yb) return mode === 'year-desc' ? yb - ya : ya - yb;
      }
      return a.dataset.order - b.dataset.order;
    });
    arr.forEach(function (c) { list.appendChild(c); });
  }

  function saveUrl(s) {
    var p = new URLSearchParams();
    keys.forEach(function (k) { if (s[k]) p.set(k, s[k].join(',')); });
    if (q.value.trim()) p.set('q', q.value.trim());
    if (sort.value !== 'default') p.set('sort', sort.value);
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
    if (p.get('sort')) sort.value = p.get('sort');
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
})();
