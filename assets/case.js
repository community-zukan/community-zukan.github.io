// 事例ページ：あとで見る・URLのコピー
(function () {
  // あとで見るの保存は site.js の zukanSaved（どのページでも同じ仕組み）
  var save = document.getElementById('save');
  var saved = window.zukanSaved;
  if (save && saved) {
    var id = save.getAttribute('data-id');
    var label = save.querySelector('.save-label');
    var tip = document.getElementById('save-tip');
    var render = function () {
      var on = saved.has(id);
      save.setAttribute('aria-pressed', on ? 'true' : 'false');
      label.textContent = on ? 'あとで見るに入れました' : 'あとで見る';
    };
    save.hidden = false;
    render();
    saved.setHeader(false);
    document.addEventListener('zukan-saved-change', render);
    // 入れると、ボタンのしおりが弧を描いてヘッダーのしおりへ飛び、着いたところで件数が切り替わる（2026-11-15 の見本で採用。site.js の fly）。
    // 外すときは飛ばない。初めて入れたときだけ、開き方を一行添える（一度出したことはこのブラウザに残す）
    save.addEventListener('click', function () {
      var on = saved.toggle(id);
      if (on === null) { label.textContent = 'このブラウザでは保存できませんでした'; return; }
      render();
      if (!on) { saved.setHeader(false); if (tip) tip.hidden = true; return; }
      saved.fly(save.querySelector('.save-icon'), function () { saved.setHeader(true); });
      var taught = false;
      try { taught = localStorage.getItem('zukan-save-tip') === '1'; localStorage.setItem('zukan-save-tip', '1'); } catch (e) { /* 何もしない */ }
      if (tip && !taught) { tip.hidden = false; tip.classList.remove('is-in'); void tip.offsetWidth; tip.classList.add('is-in'); }
    });
  }

  // 役に立った・いまひとつ（2026-11-15 の見本で採用）：「あなたの会社なら」の直後の白い箱。押した回数は GoatCounter が数える（data-goatcounter-click）。
  // 押すと、その場所にお礼と次の一歩を出す。押したことはこのブラウザにだけ残し、次に開いたときもお礼の形で出す
  var useful = document.getElementById('useful');
  if (useful) {
    var yes = document.getElementById('useful-button');
    var no = document.getElementById('notuseful-button');
    var choice = document.getElementById('useful-choice');
    var doneBox = document.getElementById('useful-done');
    var thanks = document.getElementById('useful-thanks');
    var usave = document.getElementById('useful-save');
    var ureport = document.getElementById('useful-report');
    var UKEY = 'zukan-useful';
    var cid = yes.getAttribute('data-id');
    var loadU = function () { try { return JSON.parse(localStorage.getItem(UKEY) || '[]') || []; } catch (e) { return []; } };
    var renderSave = function () {
      if (!usave || !window.zukanSaved) return;
      var on = window.zukanSaved.has(cid);
      usave.setAttribute('aria-pressed', on ? 'true' : 'false');
      usave.querySelector('.save-label').textContent = on ? 'あとで見るに入れました' : 'あとで見るにも入れる';
    };
    var done = function (good, fresh) {
      thanks.textContent = good ? 'ありがとうございました' : 'ありがとうございました。足りない点があれば教えてください';
      if (usave) usave.hidden = !good || !window.zukanSaved;
      if (ureport) ureport.hidden = good;
      renderSave();
      choice.hidden = true;
      doneBox.hidden = false;
      if (fresh) {
        doneBox.classList.remove('is-in'); void doneBox.offsetWidth; doneBox.classList.add('is-in');
        thanks.focus({ preventScroll: true });
      }
    };
    useful.hidden = false;
    var past = loadU();
    if (past.indexOf(cid) !== -1) done(true, false);
    else if (past.indexOf(cid + ':no') !== -1) done(false, false);
    var press = function (good) {
      try {
        var l = loadU();
        l.push(good ? cid : cid + ':no');
        localStorage.setItem(UKEY, JSON.stringify(l));
      } catch (e) { /* 保存できなくても数えるのは続ける */ }
      // GoatCounter の数え上げがクリックの処理を終えてから切り替える
      setTimeout(function () { done(good, true); }, 0);
    };
    yes.addEventListener('click', function () { press(true); });
    no.addEventListener('click', function () { press(false); });
    if (usave && window.zukanSaved) {
      usave.addEventListener('click', function () {
        var on = window.zukanSaved.toggle(cid);
        if (on === null) return;
        if (on) window.zukanSaved.fly(usave.querySelector('.save-icon'), function () { window.zukanSaved.setHeader(true); });
        else window.zukanSaved.setHeader(false);
      });
      document.addEventListener('zukan-saved-change', renderSave);
    }
  }

  // 一覧の前後の事例（2026-11-15 の見本で採用）：一覧で事例を開いたとき（app.js が sessionStorage に並びを入れる）だけ、
  // 見出しの上に「絞り込んだ結果 n件中 m件目」、ページの下に前と次の事例と「一覧に戻る（条件はそのまま）」を出す
  (function () {
    var nav = document.getElementById('trail');
    var pos = document.getElementById('trail-pos');
    var src = document.getElementById('save') || document.getElementById('useful-button');
    var me = src && src.getAttribute('data-id');
    if (!nav || !me) return;
    var t = null;
    try { t = JSON.parse(sessionStorage.getItem('zukan-trail') || 'null'); } catch (e) { t = null; }
    if (!t || !t.ids) return;
    var i = t.ids.indexOf(me);
    if (i === -1) return;
    var esc = function (x) { return String(x || '').replace(/[&<>"]/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]; }); };
    var count = function (path, title) { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: path, title: title, event: true }); };
    var label = t.filtering ? '絞り込んだ結果' : '一覧';
    pos.textContent = label + ' ' + t.total + '件中 ' + (i + 1) + '件目';
    pos.hidden = false;
    var link = function (id, dir) {
      if (!id) return '<span class="trail-card is-empty" aria-hidden="true"></span>';
      var info = t.info[id] || ['', ''];
      return '<a class="trail-card is-' + dir + '" href="../' + esc(id) + '/" data-trail="' + dir + '"><span class="trail-dir">' + (dir === 'prev' ? '← 前の事例' : '次の事例 →') + '</span>' +
        '<small>' + esc(info[0]) + '</small><strong>' + esc(info[1]) + '</strong></a>';
    };
    nav.innerHTML = '<div class="trail-cards">' + link(t.ids[i - 1], 'prev') + link(t.ids[i + 1], 'next') + '</div>' +
      '<a class="trail-back" href="../../' + esc(t.search || '') + '" data-trail="back">一覧に戻る（条件はそのまま）</a>';
    nav.hidden = false;
    nav.addEventListener('click', function (ev) {
      var a = ev.target.closest('[data-trail]');
      if (!a) return;
      var d = a.getAttribute('data-trail');
      count(d === 'back' ? 'case-back-list' : 'case-' + d, d === 'back' ? '一覧に戻る（前後の事例から）' : (d === 'next' ? '次の事例' : '前の事例'));
    });
  })();

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
      '<strong>' + esc(d.title) + '</strong><span class="rel-point">' + esc(d.point || '') + '</span></a>';  // ポイントが空でも高さをそろえるため枠は置く
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

