// あとで見る（/saved/）：事例ページで「あとで見る」に入れた事例だけを、入れたのが新しい順に出す。
// 全事例のカードは saved/cards.html にあり、読み込んでから入れたものだけを出す（ページを軽くするため）。
// /saved/?ids=S01,F02 で開いたときは「送られてきたリスト」として出し、自分の保存は変えない（「入れる」を押したら足す）。観測所と同じ形
(function () {
  var list = document.getElementById('saved-cards');
  if (!list) return;
  var countEl = document.getElementById('saved-count');
  var emptyEl = document.getElementById('saved-empty');
  var importBtn = document.getElementById('saved-import');
  var shareBtn = document.getElementById('saved-share');
  var note = document.getElementById('saved-note');
  var KEY = 'zukan-saved';
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; }
  }
  function store(ids) {
    try { localStorage.setItem(KEY, JSON.stringify(ids)); } catch (e) { /* 保存できない環境では何もしない */ }
  }
  var shared = (new URLSearchParams(location.search).get('ids') || '').split(',')
    .filter(function (id) { return /^[A-Za-z]\d{1,5}$/.test(id); }).slice(0, 100);

  function render() {
    var isShared = shared.length > 0;
    // 自分の保存は入れた順に古いものから並んでいるので、新しいものを先に出す。送られてきたリストは送った人の順のまま
    var ids = isShared ? shared : load().slice().reverse();
    Array.prototype.forEach.call(list.children, function (li) { li.hidden = true; });
    var shown = 0;
    ids.forEach(function (id) {
      var a = list.querySelector('a[href="../cases/' + id + '/"]');
      if (!a) return;  // 公開をやめた事例は出さない
      var li = a.parentNode;
      list.appendChild(li);
      li.hidden = false;
      shown++;
    });
    countEl.textContent = isShared ? '送られてきたリストです（' + shown + '件）'
      : shown ? shown + '件の事例' : '';
    emptyEl.hidden = isShared || shown > 0;
    importBtn.hidden = !isShared || !shown;
    shareBtn.hidden = isShared || !shown;
    shownIds = ids.filter(function (id) { return !!list.querySelector('a[href="../cases/' + id + '/"]'); });
    viewBox.hidden = !shown;
    showView(false);
  }

  // 表で比べる（2026-11-15 の見本で採用）。件数の横の切り替えで、カードと表を切り替える。表の中身は saved/table.json を
  // 表に切り替えたときだけ読み込む。選んだ表示はこのブラウザに残す（zukan-saved-view）
  var viewBox = document.getElementById('saved-view');
  var tableBox = document.getElementById('saved-table');
  var tbody = document.getElementById('saved-tbody');
  var tableWrap = document.getElementById('saved-table-wrap');
  var shownIds = [];
  var tableData = null, tableLoading = false;
  var view = 'card';
  try { view = localStorage.getItem('zukan-saved-view') === 'table' ? 'table' : 'card'; } catch (e) { /* 何もしない */ }
  var TYPE_CLASS = { '社内': 'is-internal', 'ファン・顧客': 'is-fan', '多企業': 'is-multi' };
  function esc(t) { return String(t || '').replace(/[&<>"]/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]; }); }
  function cell(v) { return v ? esc(v) : '<span aria-hidden="true">—</span><span class="visually-hidden">記載なし</span>'; }
  function buildRows() {
    tbody.innerHTML = shownIds.map(function (id, i) {
      var r = tableData[id];
      if (!r) return '';
      var size = r[5] || r[6] ? (r[5] ? '<span class="st-band">' + esc(r[5]) + '</span>' : '') + (r[6] ? '<span class="st-raw">' + esc(r[6]) + '</span>' : '') : cell('');
      var tools = r[9].length ? r[9].map(esc).join('<br>') : cell('');
      var purposes = r[10].length ? '<ul class="tags">' + r[10].map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul>' : cell('');
      return '<tr style="--i:' + i + '"><th scope="row" class="st-name"><span class="st-co">' + esc(r[1]) + '</span><a href="../cases/' + esc(id) + '/">' + esc(r[2]) + '</a></th>' +
        '<td class="st-type"><span class="badge ' + (TYPE_CLASS[r[0]] || 'is-other') + '">' + esc(r[0]) + '</span></td>' +
        '<td class="st-ind">' + cell(r[3]) + '</td><td class="st-year">' + (r[4] ? esc(r[4]) + '年' : cell('')) + '</td>' +
        '<td class="st-size">' + size + '</td><td class="st-stage">' + cell(r[7]) + '</td><td class="st-place">' + cell(r[8]) + '</td>' +
        '<td class="st-tool">' + tools + '</td><td class="st-purpose">' + purposes + '</td><td class="st-point">' + cell(r[11]) + '</td></tr>';
    }).join('');
  }
  function showView(animate) {
    var table = view === 'table' && shownIds.length > 0;
    Array.prototype.forEach.call(viewBox.querySelectorAll('.view-btn'), function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-view') === view ? 'true' : 'false');
    });
    if (table && !tableData) {
      if (!tableLoading) {
        tableLoading = true;
        fetch(list.getAttribute('data-table')).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
          .then(function (d) { tableData = d; showView(animate); })
          .catch(function () { tableLoading = false; view = 'card'; showView(false); note.textContent = '表を読み込めませんでした。時間をおいて開き直してください。'; });
      }
      return;
    }
    list.hidden = table;
    tableBox.hidden = !table;
    if (table) {
      buildRows();
      tableBox.classList.remove('is-enter');
      if (animate) { void tableBox.offsetWidth; tableBox.classList.add('is-enter'); }
    }
  }
  Array.prototype.forEach.call(viewBox.querySelectorAll('.view-btn'), function (b) {
    b.addEventListener('click', function () {
      view = b.getAttribute('data-view');
      try { localStorage.setItem('zukan-saved-view', view); } catch (e) { /* 何もしない */ }
      showView(true);
    });
  });
  tableWrap.addEventListener('scroll', function () { tableWrap.classList.toggle('is-scrolled', tableWrap.scrollLeft > 2); }, { passive: true });

  importBtn.addEventListener('click', function () {
    var mine = load();
    var exists = function (id) { return !!list.querySelector('a[href="../cases/' + id + '/"]'); };  // 公開をやめた事例は入れない
    shared.slice().reverse().forEach(function (id) { if (exists(id) && mine.indexOf(id) === -1) mine.push(id); });
    store(mine);
    shared = [];
    history.replaceState(null, '', location.pathname);
    render();
    note.textContent = '「あとで見る」に入れました。';
    var badge = document.getElementById('header-saved-count');
    if (badge) badge.textContent = String(mine.length);
  });
  shareBtn.addEventListener('click', function () {
    var url = location.origin + location.pathname + '?ids=' + load().slice().reverse().join(',');
    var data = { title: 'あとで見るリスト｜コミュニティ図鑑', url: url };
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(function () { note.textContent = 'URLをコピーしました。ほかの端末や相手に送ってください。'; },
        function () { note.textContent = url; });
    } else {
      note.textContent = url;
    }
  });

  fetch(list.getAttribute('data-src')).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
    .then(function (t) { list.innerHTML = t; if (window.zukanSaved) window.zukanSaved.sync(list); render(); })
    .catch(function () { countEl.textContent = '事例を読み込めませんでした。時間をおいて開き直してください。'; });
})();
