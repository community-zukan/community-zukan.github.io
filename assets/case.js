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
