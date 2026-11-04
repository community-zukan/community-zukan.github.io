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
