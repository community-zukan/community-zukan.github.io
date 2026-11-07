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
  }

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
    .then(function (t) { list.innerHTML = t; render(); })
    .catch(function () { countEl.textContent = '事例を読み込めませんでした。時間をおいて開き直してください。'; });
})();
