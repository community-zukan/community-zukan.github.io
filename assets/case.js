// 事例ページ：あとで見る・URLのコピー
(function () {
  var KEY = 'zukan-saved';

  // localStorage が使えない環境（プライベートブラウズなど）でも、ページは壊さない
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; }
  }
  function store(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); return true; } catch (e) { return false; }
  }

  var save = document.getElementById('save');
  if (save) {
    var id = save.getAttribute('data-id');
    var label = save.querySelector('.save-label');
    var render = function () {
      var on = load().indexOf(id) !== -1;
      save.setAttribute('aria-pressed', on ? 'true' : 'false');
      label.textContent = on ? 'あとで見るに入れました' : 'あとで見る';
      // ヘッダーのしおりの件数も合わせる
      var count = document.getElementById('header-saved-count');
      if (count) { var n = load().length; count.textContent = n ? n : ''; }
    };
    save.hidden = false;
    render();
    save.addEventListener('click', function () {
      var list = load();
      var i = list.indexOf(id);
      if (i === -1) list.unshift(id); else list.splice(i, 1);
      if (!store(list)) {
        label.textContent = 'このブラウザでは保存できませんでした';
        return;
      }
      render();
    });
  }

  // 役に立った・いまひとつ：押した回数は GoatCounter が数える（data-goatcounter-click）。押したことはこのブラウザにだけ残す
  var useful = document.getElementById('useful');
  if (useful) {
    var yes = document.getElementById('useful-button');
    var no = document.getElementById('notuseful-button');
    var thanks = document.getElementById('useful-thanks');
    var UKEY = 'zukan-useful';
    var cid = yes.getAttribute('data-id');
    var loadU = function () { try { return JSON.parse(localStorage.getItem(UKEY) || '[]') || []; } catch (e) { return []; } };
    var done = function (good) {
      yes.disabled = true;
      no.disabled = true;
      (good ? yes : no).setAttribute('aria-pressed', 'true');
      thanks.textContent = good ? 'ありがとうございました。' : 'ありがとうございました。足りない点は「この事例の誤りを知らせる」からも送れます。';
    };
    useful.hidden = false;
    var past = loadU();
    if (past.indexOf(cid) !== -1) done(true);
    else if (past.indexOf(cid + ':no') !== -1) done(false);
    var press = function (good) {
      if (yes.disabled) return;
      try {
        var l = loadU();
        l.push(good ? cid : cid + ':no');
        localStorage.setItem(UKEY, JSON.stringify(l));
      } catch (e) { /* 保存できなくても数えるのは続ける */ }
      // GoatCounter の数え上げがクリックの処理を終えてからボタンを止める
      setTimeout(function () { done(good); }, 0);
    };
    yes.addEventListener('click', function () { press(true); });
    no.addEventListener('click', function () { press(false); });
  }

  var copy = document.getElementById('copy-url');
  if (copy) {
    var status = document.getElementById('copy-status');
    copy.hidden = false;
    copy.addEventListener('click', function () {
      var url = copy.getAttribute('data-url');
      var done = function () { status.textContent = 'URLをコピーしました'; setTimeout(function () { status.textContent = ''; }, 3000); };
      var fail = function () { status.textContent = 'コピーできませんでした。アドレスバーのURLをお使いください'; };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, fail);
        return;
      }
      try {
        var t = document.createElement('textarea');
        t.value = url;
        t.setAttribute('readonly', '');
        t.style.position = 'absolute';
        t.style.left = '-9999px';
        document.body.appendChild(t);
        t.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(t);
        if (ok) { done(); } else { fail(); }
      } catch (e) { fail(); }
    });
  }
})();

// 近い事例：切り口のタブ（押すとその切り口の4件に切り替え、カードをふわっと出す）と「ほかの事例をひく」
(function () {
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.rel-tab'));
  tabs.forEach(function (t) {
    t.addEventListener('click', function () {
      tabs.forEach(function (x) {
        var on = x === t;
        x.setAttribute('aria-selected', on ? 'true' : 'false');
        var panel = document.getElementById(x.getAttribute('aria-controls'));
        if (!panel) return;
        panel.hidden = !on;
        if (on) panel.querySelectorAll('.rel').forEach(function (r) {
          r.classList.remove('is-new'); void r.offsetWidth; r.classList.add('is-new');
        });
      });
    });
  });

  var box = document.getElementById('rel-pick');
  if (!box || !window.fetch) return;
  var me = box.getAttribute('data-id');
  var btn = document.getElementById('rel-pick-button');
  var slot = document.getElementById('rel-pick-card');
  var deck = null, last = -1;
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function count(path, title) {
    if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: path, title: title, event: true });
  }
  function draw() {
    if (!deck || !deck.length) return;
    var i;
    do { i = Math.floor(Math.random() * deck.length); } while (i === last && deck.length > 1);
    last = i;
    var d = deck[i];
    var cls = { '社内': 'is-internal', 'ファン・顧客': 'is-fan', '多企業': 'is-multi' }[d.type] || 'is-other';
    slot.innerHTML = '<a class="rel is-flip" href="../' + esc(d.id) + '/">' +
      '<span class="rel-emo"><img src="../../assets/emoji/' + esc(d.emoji) + '.png" alt="" width="28" height="28"></span>' +
      '<span class="rel-top"><span class="badge ' + cls + '">' + esc(d.type) + '</span></span><small>' + esc(d.co) + '</small>' +
      '<strong>' + esc(d.title) + '</strong>' + (d.point ? '<span class="rel-point">' + esc(d.point) + '</span>' : '') + '</a>';
    slot.querySelector('a').addEventListener('click', function () { count('related-pick-open/' + d.id, 'ほかの事例をひく（開いた）'); });
  }
  fetch('../../pick.json').then(function (r) { return r.json(); }).then(function (list) {
    deck = list.filter(function (d) { return d.id !== me; });
    if (!deck.length) return;
    box.hidden = false;
    draw();
    btn.addEventListener('click', function () {
      btn.classList.add('is-rolling');
      setTimeout(function () { btn.classList.remove('is-rolling'); }, 500);
      draw();
      count('related-pick', 'ほかの事例をひく');
    });
  }).catch(function () { /* 読めないときは出さない */ });
})();

