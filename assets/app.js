(function () {
  // トップのHTMLには最初の24件だけが入っている。残り（data-rest）を読み込んで足してから、絞り込みなどを動かす。
  // 読み込めなかったときは、入っている分だけで動かす
  var listEl = document.getElementById('cards');
  var restUrl = listEl && listEl.getAttribute('data-rest');
  if (restUrl && window.fetch) {
    fetch(restUrl).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (t) { listEl.insertAdjacentHTML('beforeend', t); if (window.zukanSaved) window.zukanSaved.sync(listEl); })
      .catch(function () { /* 入っている分だけで動かす */ })
      .then(zukanListInit);
  } else {
    zukanListInit();
  }
})();

function zukanListInit() {
  var cards = Array.prototype.slice.call(document.querySelectorAll('#cards .card'));
  if (!cards.length) return;
  var list = document.getElementById('cards');
  var q = document.getElementById('q');
  var sort = document.getElementById('sort');
  var count = document.getElementById('result-count');
  var reset = document.getElementById('reset');
  var reset2 = document.getElementById('reset2');
  var reset3 = document.getElementById('reset3');  // 絞り込みの欄の上の「すべて外す」
  var empty = document.getElementById('empty');
  var aiHelp = document.getElementById('ai-help');
  var activeCount = document.getElementById('active-count');
  var details = document.getElementById('filters');
  var more = document.getElementById('more');
  var moreButton = document.getElementById('more-button');
  var PAGE = 24;          // 一度に表示する件数
  var savedToggle = document.getElementById('saved-toggle');
  var savedOnly = false;
  var calmMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;  // 動きを減らす設定
  var sheet = document.getElementById('filter-sheet');   // スマホの絞り込みの板（下の「スマホの絞り込み」）
  var applied = document.getElementById('applied');
  var appliedList = document.getElementById('applied-list');
  // GoatCounter で数える（あとから作るボタンは count.js の data-goatcounter-click が効かないので、ここから送る）
  function gc(path, title) { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: path, title: title || path, event: true }); }

  // 事例ページで「あとで見る」に入れた事例（localStorage）。使えない環境では空として扱う
  function savedIds() {
    try { return JSON.parse(localStorage.getItem('zukan-saved') || '[]') || []; } catch (e) { return []; }
  }
  var saved = savedIds();
  function idOf(c) { return (c.querySelector('a').getAttribute('href') || '').replace(/^cases\/|\/$/g, ''); }
  var limit = PAGE;
  var boxes = Array.prototype.slice.call(document.querySelectorAll('.facet input'));
  var keys = ['type', 'purpose', 'stage', 'activity', 'place', 'industry', 'size', 'tool'];
  var multi = { purpose: true, activity: true, tool: true };
  // ツール（?tool=）は絞り込みの欄に出さない条件。事例ページのツールの札から開く。カードの data-tool と同じ名前で比べる
  var toolSel = '';
  var toolNote = document.getElementById('tool-note');
  cards.forEach(function (c, i) { if (c.dataset.order === undefined) c.dataset.order = i; });

  function selected() {
    var s = {};
    boxes.forEach(function (b) {
      if (b.checked) (s[b.name] = s[b.name] || []).push(b.value);
    });
    if (toolSel) (s.tool = s.tool || []).push(toolSel);
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

  // 1件の事例が、条件 s・検索語 terms・あとで見るだけ（only）に当てはまるか
  function matches(c, s, terms, only) {
    var ok = keys.every(function (k) {
      if (!s[k]) return true;
      var v = c.dataset[k] || '';
      var vals = multi[k] ? v.split('|') : [v];
      return s[k].some(function (x) { return vals.indexOf(x) !== -1; });
    });
    if (ok && only) ok = saved.indexOf(idOf(c)) !== -1;
    if (ok && terms.length) {
      var hay = c.dataset.search;
      ok = terms.every(function (alts) {
        return alts.some(function (w) { return hay.indexOf(w) !== -1; });
      });
    }
    return ok;
  }
  function countWith(s, terms, only) {
    return cards.filter(function (c) { return matches(c, s, terms, only); }).length;
  }

  // 0件のとき：条件を1つ外すと見つかるものを、件数つきで示す
  var relax = document.getElementById('relax');
  var emptyHint = document.getElementById('empty-hint');
  function showRelax(s, words, terms) {
    relax.innerHTML = '';
    var options = [];
    keys.forEach(function (k) {
      (s[k] || []).forEach(function (x) {
        var s2 = {};
        keys.forEach(function (k2) { if (s[k2]) s2[k2] = s[k2].filter(function (y) { return k2 !== k || y !== x; }); if (s2[k2] && !s2[k2].length) delete s2[k2]; });
        options.push({ label: '「' + x + '」を外す', n: countWith(s2, terms, savedOnly), run: function () {
          if (k === 'tool') toolSel = '';
          boxes.forEach(function (b) { if (b.name === k && b.value === x) b.checked = false; });
        } });
      });
    });
    var shownWords = q.value.trim().split(/\s+/);
    words.forEach(function (w, i) {
      var t2 = terms.filter(function (_, j) { return j !== i; });
      options.push({ label: 'キーワード「' + (shownWords[i] || w) + '」を外す', n: countWith(s, t2, savedOnly), run: function () {
        q.value = shownWords.filter(function (_, j) { return j !== i; }).join(' ');
      } });
    });
    if (savedOnly) {
      options.push({ label: '「あとで見る」だけの表示をやめる', n: countWith(s, terms, false), run: function () { setSavedOnly(false); } });
    }
    options = options.filter(function (o) { return o.n > 0; });
    options.sort(function (a, b) { return b.n - a.n; });
    options.slice(0, 5).forEach(function (o) {
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'small-button';
      b.textContent = o.label + '（' + o.n + '件）';
      b.addEventListener('click', function () { o.run(); apply(true); });
      li.appendChild(b);
      relax.appendChild(li);
    });
    relax.hidden = !relax.children.length;
    emptyHint.textContent = relax.children.length ? '次の条件を外すと見つかります。' : '条件を減らすか、キーワードを変えてみてください。';
  }

  // 言い換えで広げて探したときは、その旨を一言そえる
  var searchNote = document.getElementById('search-note');
  function showSearchNote(words, terms) {
    var parts = [];
    words.forEach(function (w, i) {
      var extra = terms[i].filter(function (a) { return a !== w; });
      if (extra.length) parts.push('「' + q.value.trim().split(/\s+/)[i] + '」は「' + extra.slice(0, 3).join('」「') + '」も含めて');
    });
    searchNote.textContent = parts.length ? parts.join('、') + '探しました。' : '';
    searchNote.hidden = !parts.length;
  }

  // 検索された言葉を GoatCounter のイベントとして数える（言い換え表と、データ集めで探すテーマに使う）。
  // 入力が1.5秒止まったときだけ送り、同じ言葉は続けて送らない。0件だった言葉は別に数える
  var searchTimer, lastSent = '';
  function countSearch(shown) {
    clearTimeout(searchTimer);
    var term = q.value.trim().replace(/\s+/g, ' ').slice(0, 50);
    if (!term) return;
    // メールアドレス・電話番号・URLのような、個人につながりうる言葉は記録しない（観測所と同じ見分け方。2026-11-07）
    var nf = term.normalize ? term.normalize('NFKC') : term;
    if (/@|https?:|www\.|\d{2,4}[-‐－ー\s]?\d{2,4}[-‐－ー\s]?\d{3,4}|\d{7,}/.test(nf)) return;
    searchTimer = setTimeout(function () {
      if (term === lastSent || !window.goatcounter || !window.goatcounter.count) return;
      lastSent = term;
      try {
        window.goatcounter.count({ path: (shown ? 'search/' : 'search-zero/') + term, title: (shown ? '検索：' : '検索（0件）：') + term, event: true });
      } catch (e) { /* 数えられなくても検索は続ける */ }
    }, 1500);
  }

  // 絞り込みと検索は全件に効かせ、当てはまった事例のうち先頭の limit 件だけを表示する
  // 種別を選んだら、目的の絞り込みはその種別の小見出しのものだけを出す。種別を選んでいないときは全部。
  // 「その他」の小見出しと、選んでいる目的がある小見出しは隠さない（隠れた条件が効いたままにならないように）
  var purposeGroups = Array.prototype.slice.call(document.querySelectorAll('.purpose-group'));
  function narrowPurposes(s) {
    var types = s.type || [];
    purposeGroups.forEach(function (g) {
      var t = g.getAttribute('data-type');
      var checked = !!g.querySelector('input:checked');
      g.hidden = types.length > 0 && t !== 'その他' && types.indexOf(t) === -1 && !checked;
    });
  }

  // 条件を変えたとき、カードが新しい位置へ動いて見える（2026-11-15 の見本で採用。同じページ内の View Transitions）。
  // 残るカードはすっと動き、外れるカードは薄くなって消え、入るカードはふわっと出る。名前（card-ID）は表示中の先頭24件にだけ付け、終わったら外す。
  // 対応していないブラウザ・動きを減らす設定・キーワードの入力・「もっと見る」では、今までどおりそのまま切り替える
  var vtCur = null;
  function clearCardNames() { cards.forEach(function (c) { if (c.style.viewTransitionName) c.style.viewTransitionName = ''; }); }
  function nameCards() {
    clearCardNames();
    var n = 0;
    Array.prototype.forEach.call(list.children, function (c) {
      if (c.hidden || n >= PAGE) return;
      c.style.viewTransitionName = 'card-' + idOf(c).replace(/[^A-Za-z0-9_-]/g, '');
      n++;
    });
  }
  function withTransition(update) {
    if (calmMotion || !document.startViewTransition || document.hidden || (sheet && sheet.open)) { update(); return; }
    if (vtCur) vtCur.skipTransition();
    nameCards();
    var t = document.startViewTransition(function () { update(); nameCards(); });
    vtCur = t;
    if (t.ready) t.ready.catch(function () {});
    var done = function () { if (vtCur === t) { vtCur = null; clearCardNames(); } };
    t.finished.then(done, done);
    setTimeout(function () { if (vtCur === t) t.skipTransition(); }, 1200);  // 何かで動きが止まっても、操作できない時間を残さない
  }

  // 選んでいる条件の札（2026-11-15 の見本で採用）。絞り込みの欄の札とキーワードを、件数の下に「名前 ×」で並べる。
  // × で1つずつ外し、外したあとは隣の札（なければ「条件で絞り込む」）にフォーカスを移す。ツール（?tool=）は tool-note のまま
  var FACET_LABEL = { type: '種別', purpose: '目的', stage: '段階', activity: '活動の型', place: '場', industry: '業種', size: '規模', tool: 'ツール' };
  var X_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
  function escHtml(t) { return String(t).replace(/[&<>"]/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]; }); }
  function shownWords() { return q.value.trim() ? [q.value.trim()] : []; }
  function buildApplied(filtering, words) {
    if (!applied) return;
    var html = '';
    boxes.forEach(function (b) {
      if (!b.checked) return;
      html += '<li><button type="button" class="applied-chip" data-k="' + escHtml(b.name) + '" data-v="' + escHtml(b.value) + '" aria-label="' +
        escHtml((FACET_LABEL[b.name] || '') + '「' + b.value + '」を外す') + '">' + escHtml(b.value) + X_ICON + '</button></li>';
    });
    words.forEach(function (w) {
      html += '<li><button type="button" class="applied-chip" data-k="q" aria-label="' + escHtml('キーワード「' + w + '」を外す') + '">キーワード：' + escHtml(w) + X_ICON + '</button></li>';
    });
    if (appliedList.innerHTML !== html) appliedList.innerHTML = html;
    applied.hidden = !filtering;
    markOverflow();
  }
  // 札が横にはみ出しているときだけ右端を薄くし、続きがあると分かるようにする（スマホは1行で横にすべらせる）
  function markOverflow() {
    var over = appliedList.scrollWidth > appliedList.clientWidth + 1;
    appliedList.classList.toggle('is-overflow', over && appliedList.scrollLeft + appliedList.clientWidth < appliedList.scrollWidth - 2);
  }
  if (applied) {
    appliedList.addEventListener('scroll', markOverflow, { passive: true });
    window.addEventListener('resize', markOverflow);
    appliedList.addEventListener('click', function (ev) {
      var chip = ev.target.closest('.applied-chip');
      if (!chip) return;
      var chips = Array.prototype.slice.call(appliedList.querySelectorAll('.applied-chip'));
      var at = chips.indexOf(chip);
      var k = chip.getAttribute('data-k');
      if (k === 'q') q.value = '';
      else boxes.forEach(function (b) { if (b.name === k && b.value === chip.getAttribute('data-v')) b.checked = false; });
      gc('filter-chip-remove/' + (k === 'q' ? 'keyword' : FACET_LABEL[k] || k), '条件の札を外す：' + (k === 'q' ? 'キーワード' : FACET_LABEL[k] || k));
      withTransition(function () { apply(true); });
      var rest = appliedList.querySelectorAll('.applied-chip');
      if (rest.length) rest[Math.min(at, rest.length - 1)].focus();
      else details.querySelector('summary').focus();
    });
  }

  // 件数（2026-11-15 の見本で採用）：数字が変わるとき、替わった桁だけ縦にめくれる。増えたら下から、減ったら上から。
  // 読み上げは隠した文字（#result-say）だけで、動く桁は aria-hidden。動きを減らす設定ではそのまま替える
  var say = document.getElementById('result-say');
  var rcPre = document.getElementById('rc-pre');
  var rcNum = document.getElementById('rc-num');
  var curCount = cards.length;
  var flipTimer = 0;
  var countReady = false;   // 読み込んだときの最初の件数はめくらない
  function digitsHtml(str) { return str.split('').map(function (d) { return '<span class="rc-d">' + d + '</span>'; }).join(''); }
  function setCount(filtering, shown) {
    var text = filtering ? cards.length + '件中 ' + shown + '件の事例' : cards.length + '件の事例';
    if (!rcNum) { count.textContent = text; return; }
    if (say.textContent !== text) say.textContent = text;
    rcPre.hidden = !filtering;
    var from = curCount, to = shown;
    curCount = to;
    if (from === to && !flipTimer) return;
    clearTimeout(flipTimer); flipTimer = 0;
    if (calmMotion || from === to || !countReady) { countReady = true; rcNum.className = 'rc-num'; rcNum.innerHTML = digitsHtml(String(to)); return; }
    var a = String(from), b = String(to), len = Math.max(a.length, b.length);
    while (a.length < len) a = ' ' + a;
    while (b.length < len) b = ' ' + b;
    var html = '';
    for (var i = 0; i < len; i++) {
      if (a[i] === b[i]) { html += '<span class="rc-d">' + b[i] + '</span>'; continue; }
      html += '<span class="rc-d is-flip" style="--rc-i:' + i + '"><span class="rc-o">' + (a[i] === ' ' ? '&nbsp;' : a[i]) +
        '</span><span class="rc-n">' + (b[i] === ' ' ? '&nbsp;' : b[i]) + '</span></span>';
    }
    rcNum.className = 'rc-num ' + (to > from ? 'is-up' : 'is-down');
    rcNum.innerHTML = '';
    void rcNum.offsetWidth;   // 付け直して、続けて押されたときも最初から動かす
    rcNum.innerHTML = html;
    // 動き終わったら、ふつうの数字に戻す（空いた桁はここで詰まる）
    flipTimer = setTimeout(function () { flipTimer = 0; rcNum.className = 'rc-num'; rcNum.innerHTML = digitsHtml(String(curCount)); }, 350 + len * 30 + 60);
  }

  // スマホの絞り込み（2026-11-15 の見本で採用）：狭い画面（絞り込みの欄が左に並ばない幅）では、「条件で絞り込む」を押すと
  // 下から板（dialog）が出る。中身は details の .filters-body をそのまま移して使い（札の状態はそのまま）、閉じたら戻す。
  // 札を押すたびに一覧と板の下の「n件を見る」が変わり、押すと0件になる札は薄くする。広い画面は今までどおり左の欄
  var sheetBody = document.getElementById('sheet-body');
  var filtersBody = details.querySelector('.filters-body');
  var narrowMq = window.matchMedia ? window.matchMedia('(max-width: 999px)') : null;
  function updateSheet(s, terms, shown) {
    if (!sheet || !sheet.open) return;
    document.getElementById('sheet-n').textContent = shown;
    document.getElementById('sheet-apply').disabled = shown === 0;
    boxes.forEach(function (b) {
      var zero = false;
      if (!b.checked) {
        var s2 = {};
        Object.keys(s).forEach(function (k) { s2[k] = s[k].slice(); });
        (s2[b.name] = s2[b.name] || []).push(b.value);
        zero = countWith(s2, terms, savedOnly) === 0;
      }
      b.closest('.chip').classList.toggle('is-zero', zero);
    });
  }
  if (sheet && sheet.showModal && narrowMq) {
    details.querySelector('summary').addEventListener('click', function (ev) {
      if (!narrowMq.matches) return;
      ev.preventDefault();
      sheetBody.appendChild(filtersBody);
      sheet.showModal();
      apply(false, true);
      gc('filter-sheet-open', '絞り込みの板を開く');
    });
    sheet.addEventListener('close', function () {
      details.appendChild(filtersBody);
      details.open = false;
      boxes.forEach(function (b) { b.closest('.chip').classList.remove('is-zero'); });
    });
    // 後ろ（板の外）を押しても閉じる。Safari は closedby="any" に対応しないので、ここで閉じる
    sheet.addEventListener('click', function (ev) { if (ev.target === sheet) sheet.close(); });
    document.getElementById('sheet-close').addEventListener('click', function () { sheet.close(); });
    document.getElementById('sheet-clear').addEventListener('click', function () {
      boxes.forEach(function (b) { b.checked = false; });
      toolSel = '';
      apply(true);
    });
    document.getElementById('sheet-apply').addEventListener('click', function () {
      gc('filter-sheet-apply', '絞り込みの板から一覧を見る');
      sheet.close();
      var y = details.getBoundingClientRect().bottom + window.scrollY - (parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-offset'), 10) || 64) - 8;
      window.scrollTo(0, Math.max(0, y));
    });
    var onWide = function () { if (!narrowMq.matches && sheet.open) sheet.close(); };
    if (narrowMq.addEventListener) narrowMq.addEventListener('change', onWide);
  }

  // 入力中の候補（2026-11-15 の見本で採用）。検索欄に文字を入れると、事例（企業名・コミュニティ名・読みに当たったもの。押すと事例ページへ）、
  // ツール（件数つき。押すとそのツールの一覧）、目的・業種など（押すとその条件の一覧）を出す。上下キーで選び Enter で決め、Esc で閉じる。
  // 当たった文字は太さ600と下線で示す（マーカーは使わない）。キーワードの絞り込みは今までどおり裏で効く
  var suggest = document.getElementById('suggest');
  var sgItems = [];
  var sgActive = -1;
  var toolCounts = {};
  cards.forEach(function (c) { (c.dataset.tool || '').split('|').forEach(function (t) { if (t) toolCounts[t] = (toolCounts[t] || 0) + 1; }); });
  var purposeIcon = {};
  Array.prototype.forEach.call(document.querySelectorAll('.tile[data-purpose]'), function (t) {
    var img = t.querySelector('img');
    if (img && t.getAttribute('data-purpose')) purposeIcon[t.getAttribute('data-purpose')] = img.getAttribute('src');
  });
  var facetOpts = boxes.filter(function (b) { return b.name !== 'tool'; }).map(function (b) {
    var small = b.parentNode.querySelector('small');
    return { box: b, name: b.value, kind: FACET_LABEL[b.name] || '', n: small ? small.textContent : '' };
  });
  function sgHl(text, words) {
    var nt = normalize(text);
    if (nt.length !== text.length) return escHtml(text);   // 正規化で文字数が変わる語は印を付けない（位置がずれるため）
    for (var i = 0; i < words.length; i++) {
      var at = words[i] ? nt.indexOf(words[i]) : -1;
      if (at !== -1) return escHtml(text.slice(0, at)) + '<b class="sg-hit">' + escHtml(text.slice(at, at + words[i].length)) + '</b>' + escHtml(text.slice(at + words[i].length));
    }
    return escHtml(text);
  }
  function hitAny(hay, words) { return words.some(function (w) { return w && hay.indexOf(w) !== -1; }); }
  function closeSuggest() {
    if (!suggest || suggest.hidden) return;
    suggest.hidden = true;
    q.setAttribute('aria-expanded', 'false');
    q.removeAttribute('aria-activedescendant');
    sgActive = -1;
  }
  function buildSuggest() {
    if (!suggest) return;
    var raw = q.value.trim();
    var nq = normalize(raw);
    if (!nq) { closeSuggest(); return; }
    var words = alternatives(nq).map(normalize);
    var html = '';
    sgItems = [];
    var add = function (item, inner, cls) {
      var id = 'sg-' + sgItems.length;
      sgItems.push(item);
      html += '<div class="sg-opt' + (cls ? ' ' + cls : '') + '" role="option" id="' + id + '" data-i="' + (sgItems.length - 1) + '" aria-selected="false">' + inner + '</div>';
    };
    // 事例：いまの並び順のまま、名前と読みに当たったものを5件まで
    var hits = Array.prototype.filter.call(list.children, function (c) { return hitAny(c.dataset.name || '', words); }).slice(0, 5);
    if (hits.length) {
      html += '<div class="sg-gh" role="presentation">事例</div>';
      hits.forEach(function (c) {
        var title = (c.querySelector('.card-title') || {}).textContent || '';
        var co = (c.querySelector('.card-company') || {}).textContent || '';
        var badge = c.querySelector('.badge');
        add({ kind: 'case', href: c.querySelector('a').getAttribute('href'), id: idOf(c) },
          (badge ? badge.outerHTML : '') + '<span class="sg-main"><span class="sg-title">' + sgHl(title, words) + '</span><span class="sg-sub">' + sgHl(co, words) + '</span></span>');
      });
    }
    var tools = Object.keys(toolCounts).filter(function (t) { return hitAny(normalize(t), words); })
      .sort(function (a, b) { return toolCounts[b] - toolCounts[a]; }).slice(0, 4);
    if (tools.length) {
      html += '<div class="sg-gh" role="presentation">ツール</div>';
      tools.forEach(function (t) {
        add({ kind: 'tool', value: t }, '<span class="sg-name">' + sgHl(t, words) + '</span><span class="sg-n">' + toolCounts[t] + '件</span>');
      });
    }
    var facets = facetOpts.filter(function (o) { return hitAny(normalize(o.name), words); }).slice(0, 4);
    if (facets.length) {
      html += '<div class="sg-gh" role="presentation">目的・業種など</div>';
      facets.forEach(function (o) {
        var icon = purposeIcon[o.name] ? '<img src="' + escHtml(purposeIcon[o.name]) + '" alt="" width="20" height="20">' : '';
        add({ kind: 'facet', opt: o }, icon + '<span class="sg-name">' + sgHl(o.name, words) + '</span><span class="sg-kind">' + escHtml(o.kind) + '</span><span class="sg-n">' + escHtml(o.n) + '件</span>');
      });
    }
    add({ kind: 'all' }, '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/></svg><span class="sg-name">「' + escHtml(raw) + '」で一覧を絞り込む</span>', 'sg-all');
    suggest.innerHTML = html;
    suggest.hidden = false;
    q.setAttribute('aria-expanded', 'true');
    sgActive = -1;
    q.removeAttribute('aria-activedescendant');
  }
  function moveSuggest(d) {
    if (!sgItems.length) return;
    // -1（どれも選んでいない）→ 0 → … → 最後 → -1 と回る
    var span = sgItems.length + 1;
    sgActive = ((sgActive + 1 + d) % span + span) % span - 1;
    Array.prototype.forEach.call(suggest.querySelectorAll('.sg-opt'), function (o, i) {
      var on = i === sgActive;
      o.classList.toggle('is-active', on);
      o.setAttribute('aria-selected', on ? 'true' : 'false');
      if (on) o.scrollIntoView({ block: 'nearest' });
    });
    if (sgActive >= 0) q.setAttribute('aria-activedescendant', 'sg-' + sgActive); else q.removeAttribute('aria-activedescendant');
  }
  function pickSuggest(i) {
    var it = sgItems[i];
    if (!it) return;
    if (it.kind === 'case') { gc('suggest/case/' + it.id, '候補から事例：' + it.id); location.href = it.href; return; }
    closeSuggest();
    if (it.kind === 'all') { gc('suggest-all', '候補から一覧を絞り込む'); return; }
    q.value = '';
    if (it.kind === 'tool') {
      var box = boxes.filter(function (b) { return b.name === 'tool' && b.value === it.value; })[0];
      if (box) box.checked = true; else toolSel = it.value;
      gc('suggest/tool/' + it.value, '候補からツール：' + it.value);
    } else {
      it.opt.box.checked = true;
      gc('suggest/' + it.opt.box.name + '/' + it.opt.name, '候補から' + it.opt.kind + '：' + it.opt.name);
    }
    withTransition(function () { apply(true); });
  }
  if (suggest) {
    q.addEventListener('input', buildSuggest);
    q.addEventListener('focus', function () { if (q.value.trim()) buildSuggest(); });
    q.addEventListener('blur', function () { setTimeout(closeSuggest, 150); });
    q.addEventListener('keydown', function (ev) {
      if (ev.isComposing || ev.keyCode === 229) return;   // 日本語の変換中の Enter などは使わない
      if (suggest.hidden) { if (ev.key === 'ArrowDown' && q.value.trim()) { buildSuggest(); ev.preventDefault(); } return; }
      if (ev.key === 'ArrowDown') { moveSuggest(1); ev.preventDefault(); }
      else if (ev.key === 'ArrowUp') { moveSuggest(-1); ev.preventDefault(); }
      else if (ev.key === 'Escape') { closeSuggest(); ev.preventDefault(); }
      else if (ev.key === 'Enter') { if (sgActive >= 0) { ev.preventDefault(); pickSuggest(sgActive); } else closeSuggest(); }
    });
    // 押しても検索欄からフォーカスを外さない（外すと blur で閉じてしまう）
    suggest.addEventListener('mousedown', function (ev) { ev.preventDefault(); });
    suggest.addEventListener('click', function (ev) {
      var o = ev.target.closest('.sg-opt');
      if (o) pickSuggest(parseInt(o.getAttribute('data-i'), 10));
    });
  }
  // 「/」キーで検索欄へ（入力欄にいるときは効かない）
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== '/' || ev.ctrlKey || ev.metaKey || ev.altKey || ev.isComposing) return;
    var t = ev.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (sheet && sheet.open) return;
    ev.preventDefault();
    q.focus();
  });

  // キーワードに当たった箇所（2026-11-15 の見本で採用）。題名・企業名に当たったときはその言葉を太さ600と下線に、
  // カードに見えていない項目（主な施策・工夫のポイントの続き・ツール・検索用キーワード）に当たったときは、当たった箇所の前後を1行添える。
  // 本文は search-body.json にあり、初めてキーワードで探したときに読み込む。表示中のカードにだけ付ける
  var bodyUrl = list.getAttribute('data-body');
  var bodyData = null, bodyLoading = false, lastHitArgs = null;
  var HIT_LABEL = ['本文に一致', '本文に一致', 'ツールに一致', 'キーワードに一致'];
  function loadBody() {
    if (bodyData || bodyLoading || !bodyUrl || !window.fetch) return;
    bodyLoading = true;
    fetch(bodyUrl).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { bodyData = d; if (lastHitArgs) showHits(lastHitArgs[0], lastHitArgs[1]); })
      .catch(function () { /* 読み込めなくても、題名・企業名の印だけは付く */ });
  }
  // 要素の中の文字に印を付ける（<wbr> などで分かれた文字をまたぐ当たりには付けない）。元に戻せるよう、最初の中身を覚えておく
  function markIn(el, alts) {
    if (!el) return;
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      if (node.parentNode.classList && node.parentNode.classList.contains('hit-word')) continue;
      var t = node.nodeValue, nt = normalize(t);
      if (nt.length !== t.length) continue;
      for (var i = 0; i < alts.length; i++) {
        var w = normalize(alts[i]), at = w ? nt.indexOf(w) : -1;
        if (at === -1) continue;
        if (el.getAttribute('data-orig') === null) el.setAttribute('data-orig', el.innerHTML);
        var mid = node.splitText(at);
        mid.splitText(w.length);
        var b = document.createElement('b');
        b.className = 'hit-word';
        mid.parentNode.replaceChild(b, mid);
        b.appendChild(mid);
        return;
      }
    }
  }
  function unmark(el) {
    if (el && el.getAttribute('data-orig') !== null) { el.innerHTML = el.getAttribute('data-orig'); el.removeAttribute('data-orig'); }
  }
  function showHits(words, terms) {
    lastHitArgs = [words, terms];
    if (words.length) loadBody();
    Array.prototype.forEach.call(list.children, function (c) {
      var titleEl = c.querySelector('.card-title'), coEl = c.querySelector('.card-company');
      unmark(titleEl); unmark(coEl);
      var old = c.querySelector('.card-hit');
      if (old) old.parentNode.removeChild(old);
      if (c.hidden || !words.length) return;
      terms.forEach(function (alts) { markIn(titleEl, alts); markIn(coEl, alts); });
      var fields = bodyData && bodyData[idOf(c)];
      if (!fields) return;
      var shown = normalize(c.querySelector('a').textContent);
      for (var ti = 0; ti < terms.length; ti++) {
        var alts = terms[ti].map(normalize);
        if (alts.some(function (w) { return w && shown.indexOf(w) !== -1; })) continue;   // カードに見えている文字で当たっている
        for (var fi = 0; fi < fields.length; fi++) {
          var f = fields[fi] || '', nf = normalize(f);
          if (nf.length !== f.length) continue;
          for (var ai = 0; ai < alts.length; ai++) {
            var w = alts[ai], at = w ? nf.indexOf(w) : -1;
            if (at === -1) continue;
            var from = Math.max(0, at - 14), to = Math.min(f.length, at + w.length + 22);
            var text = (from > 0 ? '…' : '') + escHtml(f.slice(from, at)) + '<b class="hit-word">' + escHtml(f.slice(at, at + w.length)) + '</b>' +
              escHtml(f.slice(at + w.length, to)) + (to < f.length ? '…' : '');
            var label = HIT_LABEL[fi] + (w !== words[ti] ? '（言い換え：' + escHtml(f.slice(at, at + w.length)) + '）' : '');
            var p = document.createElement('p');
            p.className = 'card-hit';
            p.innerHTML = '<span class="card-hit-label">' + label + '</span><span class="card-hit-text">' + text + '</span>';
            var tags = c.querySelector('.tags');
            c.querySelector('a').insertBefore(p, tags);
            return;
          }
        }
      }
    });
  }

  function apply(pushState, keepLimit) {
    if (!keepLimit) limit = PAGE;
    // キーワードが変わったら並べ直す（検索の例・「外す」のボタンなど、どこから変わっても）
    if (lastSortKey !== sort.value + '|' + q.value.trim()) doSort();
    var s = selected();
    var words = normalize(q.value).split(/\s+/).filter(Boolean);
    var terms = words.map(alternatives);
    var shown = 0;
    var visible = 0;
    Array.prototype.forEach.call(list.children, function (c) {
      var ok = matches(c, s, terms, savedOnly);
      if (ok) shown++;
      c.hidden = !ok || shown > limit;
      if (!c.hidden) visible++;
    });
    var rest = shown - visible;
    more.hidden = rest <= 0;
    moreButton.textContent = 'もっと見る（残り' + rest + '件）';
    var n = Object.keys(s).reduce(function (a, k) { return a + s[k].length; }, 0);
    var filtering = n > 0 || words.length > 0 || savedOnly;
    setCount(filtering, shown);
    activeCount.textContent = n ? n + '件の条件' : '';
    if (reset3) reset3.hidden = !filtering;
    buildApplied(filtering, shownWords());
    empty.hidden = shown !== 0;
    if (shown === 0) showRelax(s, words, terms);
    showSearchNote(words, terms);
    showHits(words, terms);
    countSearch(shown);
    if (pushState) saveUrl(s);
    markTiles(s);
    narrowPurposes(s);
    // コミュニティAIへの案内：結果が少ない（data-few の件数以下）ときだけ囲みで出す
    if (aiHelp) aiHelp.hidden = shown > (parseInt(aiHelp.getAttribute('data-few'), 10) || 5);
    updateSheet(s, terms, shown);
    if (toolNote) {
      toolNote.hidden = !toolSel;
      toolNote.querySelector('span').textContent = toolSel ? 'ツール「' + toolSel + '」を使っている事例' : '';
    }
  }

  // 目的から探すの帯：選んでいる目的のタイルを空色にする（何も選んでいなければ「すべて」）
  var strip = document.getElementById('purpose-strip');
  var tiles = strip ? Array.prototype.slice.call(strip.querySelectorAll('.tile')) : [];
  function markTiles(s) {
    var chosen = s.purpose || [];
    tiles.forEach(function (t) {
      var v = t.getAttribute('data-purpose');
      var on = v ? chosen.indexOf(v) !== -1 : chosen.length === 0;
      if (on) t.setAttribute('aria-current', 'true'); else t.removeAttribute('aria-current');
    });
  }
  // 押すと、目的の絞り込みをその1つにする（「すべて」は目的の絞り込みを外す）。ほかの条件や検索語はそのまま
  tiles.forEach(function (t) {
    t.addEventListener('click', function (ev) {
      ev.preventDefault();
      var v = t.getAttribute('data-purpose');
      boxes.forEach(function (b) { if (b.name === 'purpose') b.checked = !!v && b.value === v; });
      withTransition(function () { apply(true); });
    });
  });
  // PC では帯の右上の矢印でも動かせる
  var arrows = document.getElementById('strip-arrows');
  if (arrows && strip && window.matchMedia('(min-width: 760px)').matches) {
    arrows.hidden = false;
    Array.prototype.forEach.call(arrows.querySelectorAll('button'), function (b) {
      b.addEventListener('click', function () {
        var dir = parseInt(b.getAttribute('data-dir'), 10);
        var smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        strip.scrollBy({ left: dir * strip.clientWidth * 0.8, behavior: smooth ? 'smooth' : 'auto' });
      });
    });
  }

  // キーワードで探したときは、おすすめ順のなかで、企業名・コミュニティ名に合う事例 → ツール・目的などに合う事例 → 本文に合う事例の順にする
  // （観測所と同じ考え方。2026-11-07）。並び順を自分で変えたときは、そちらに従う
  function currentTerms() {
    return normalize(q.value).split(/\s+/).filter(Boolean).map(alternatives);
  }
  function hitsAll(text, terms) {
    return terms.every(function (alts) { return alts.some(function (w) { return text.indexOf(w) !== -1; }); });
  }
  function tierOf(c, terms) {
    var name = c.dataset.name || '';
    if (hitsAll(name, terms)) return 0;
    if (hitsAll(name + ' ' + (c.dataset.tags || ''), terms)) return 1;
    return 2;
  }
  var lastSortKey = '';
  function doSort() {
    var mode = sort.value;
    var terms = mode === 'score' ? currentTerms() : [];
    lastSortKey = mode + '|' + q.value.trim();
    var arr = cards.slice();
    if (terms.length) cards.forEach(function (c) { c._tier = tierOf(c, terms); });
    arr.sort(function (a, b) {
      if (terms.length && a._tier !== b._tier) return a._tier - b._tier;
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
    // ツールの条件：絞り込みの欄にあるツール（3件以上）なら印を付け、ない（2件の）ツールは欄の外の条件として持つ
    toolSel = p.get('tool') || '';
    if (toolSel && boxes.some(function (b) { return b.name === 'tool' && b.value === toolSel; })) toolSel = '';
    if (p.get('saved') === '1' && saved.length) setSavedOnly(true);
    if (p.get('sort') && sort.querySelector('option[value="' + p.get('sort') + '"]')) sort.value = p.get('sort');
    // 広い画面では絞り込みの欄をいつも開いている。スマホでは条件つきで開いても欄を閉じたままにし、結果の一覧を先に見せる（2026-11-06 黒田さんの判断。下の jumpToResults）
    return any || !!p.get('q') || !!toolSel || p.get('saved') === '1';
  }

  // スマホで、事例ページの札などから条件つきで一覧を開いたとき：見出しや件数の帯を飛ばし、閉じた「条件で絞り込む」と結果の一覧が見える位置まで送る。
  // 戻るボタンで戻ったときはブラウザが元の位置に戻すので、何もしない
  function jumpToResults() {
    var nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
    if (nav && nav.type === 'back_forward') return;
    var y = details.getBoundingClientRect().top + window.scrollY - 64;  // 64：ヘッダーの高さ
    window.scrollTo(0, Math.max(0, y));
  }

  function clearAll() {
    boxes.forEach(function (b) { b.checked = false; });
    toolSel = '';
    setSavedOnly(false);
    q.value = '';
    withTransition(function () { apply(true); });
    q.focus();
  }

  function setSavedOnly(on) {
    savedOnly = on;
    savedToggle.setAttribute('aria-pressed', on ? 'true' : 'false');
    savedToggle.textContent = on ? 'あとで見るを表示中（' + saved.length + '件）' : 'あとで見る（' + saved.length + '件）';
  }
  if (saved.length) {
    savedToggle.hidden = false;
    setSavedOnly(false);
  }
  savedToggle.addEventListener('click', function () { setSavedOnly(!savedOnly); apply(false); });
  // 一覧のカードのしおりで入れたり外したりしたとき（site.js が知らせる）
  document.addEventListener('zukan-saved-change', function () {
    saved = savedIds();
    savedToggle.hidden = !saved.length;
    if (!saved.length && savedOnly) savedOnly = false;
    setSavedOnly(savedOnly);
    if (savedOnly) apply(false, true);
  });

  // 検索の例：読み込むたびに候補から選び直す。実際に検索された言葉（searched）は2つまで混ぜ、残りは運営が選んだ言葉（picked）から。
  // 今のデータで1件も見つからない言葉は出さない
  var examples = document.getElementById('examples');
  var examplesData = document.getElementById('examples-data');
  if (examples && examplesData) {
    try {
      var ex = JSON.parse(examplesData.textContent);
      var hits = function (w) { return countWith({}, normalize(w).split(/\s+/).filter(Boolean).map(alternatives), false) > 0; };
      var shuffle = function (a) {
        a = a.slice();
        for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
        return a;
      };
      var searched = shuffle((ex.searched || []).filter(hits)).slice(0, 2);
      var rest = shuffle((ex.picked || []).filter(function (w) { return searched.indexOf(w) === -1 && hits(w); }));
      var chosen = shuffle(searched.concat(rest.slice(0, ex.shown - searched.length)));
      if (chosen.length) {
        Array.prototype.slice.call(examples.querySelectorAll('a')).forEach(function (a) { a.remove(); });
        chosen.forEach(function (w) {
          var a = document.createElement('a');
          a.href = '?q=' + encodeURIComponent(w);
          a.setAttribute('data-q', w);
          a.textContent = w;
          examples.appendChild(a);
        });
      }
    } catch (e) { /* 選び直せないときは、最初から並んでいる言葉のまま */ }
    examples.classList.add('is-ready');
  }

  // 検索の例：押すと検索欄に入れて探す（ページは読み込み直さない）
  Array.prototype.forEach.call(document.querySelectorAll('.examples a[data-q]'), function (a) {
    a.addEventListener('click', function (ev) {
      ev.preventDefault();
      q.value = a.getAttribute('data-q');
      apply(true);
    });
  });

  // PC の「カード／一覧」の切り替え。選んだ表示はこのブラウザに残す（スマホではカードのまま）
  var viewToggle = document.getElementById('view-toggle');
  if (viewToggle) {
    var setView = function (v) {
      list.classList.toggle('is-list', v === 'list');
      Array.prototype.forEach.call(viewToggle.querySelectorAll('.view-btn'), function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-view') === v ? 'true' : 'false');
      });
    };
    var v0 = 'card';
    try { v0 = localStorage.getItem('zukan-view') === 'list' ? 'list' : 'card'; } catch (e) { /* 何もしない */ }
    setView(v0);
    viewToggle.hidden = false;
    Array.prototype.forEach.call(viewToggle.querySelectorAll('.view-btn'), function (b) {
      b.addEventListener('click', function () {
        var v = b.getAttribute('data-view');
        setView(v);
        try { localStorage.setItem('zukan-view', v); } catch (e) { /* 保存できなくても切り替えは効く */ }
      });
    });
  }

  // 件数の大きな数字を0から数え上げる（動きを減らす設定の端末では、そのまま出す）
  // ページの読み込み（並べ替え・画像・見出しの書体）と重なると数字の増え方がカクカクするので、
  // 読み込みが終わってから始める。待っているあいだは数字を隠し、桁が増えても横にずれないよう幅を先に取っておく
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var counters = Array.prototype.filter.call(document.querySelectorAll('.stat-num[data-count], .tile-num[data-count]'), function (el) {
    return parseInt(el.getAttribute('data-count'), 10) > 0;
  });
  if (!reduceMotion && window.requestAnimationFrame && counters.length) {
    counters.forEach(function (el) {
      el.style.minWidth = el.getAttribute('data-count').length + 'ch';
      el.style.opacity = '0';
    });
    var started = false;
    var startCount = function () {
      if (started) return;
      started = true;
      var t0 = null;
      var step = function (t) {
        if (t0 === null) t0 = t;
        var p = Math.min(1, (t - t0) / 1000);
        var e = 1 - Math.pow(1 - p, 3);
        counters.forEach(function (el) {
          el.textContent = String(Math.round(parseInt(el.getAttribute('data-count'), 10) * e));
        });
        if (p < 1) requestAnimationFrame(step);
      };
      counters.forEach(function (el) { el.textContent = '0'; el.style.opacity = ''; });
      requestAnimationFrame(step);
    };
    var whenLoaded = new Promise(function (ok) {
      if (document.readyState === 'complete') ok(); else window.addEventListener('load', ok);
    });
    var whenFonts = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
    Promise.all([whenLoaded, whenFonts]).then(function () {
      // 読み込みの直後のひと仕事が片づくのを2フレーム待ち、さらに0.4秒おいてから始める
      // （先にラベルと見出しに目が向いてから数字が動くように。2026-11-10 黒田さんの判断）
      requestAnimationFrame(function () { requestAnimationFrame(function () { setTimeout(startCount, 400); }); });
    });
    setTimeout(startCount, 2500);  // 読み込みに時間がかかっても、2.5秒たったら始める
  }

  var wide = window.matchMedia('(min-width: 900px)').matches;
  if (wide) details.open = true;
  var fromLink = loadUrl();
  doSort();
  apply(false);
  if (fromLink && !wide) jumpToResults();

  // 読み込んだときだけ、表示しているカードを上から順にふわっと出す（12件目以降は同時に）
  if (!reduceMotion) {
    Array.prototype.filter.call(list.children, function (c) { return !c.hidden; }).forEach(function (c, i) {
      c.style.animationDelay = (Math.min(i, 12) * 0.05) + 's';
    });
    list.classList.add('is-entering');
    setTimeout(function () {
      list.classList.remove('is-entering');
      Array.prototype.forEach.call(list.children, function (c) { c.style.animationDelay = ''; });
    }, 1600);
  }

  boxes.forEach(function (b) { b.addEventListener('change', function () { withTransition(function () { apply(true); }); }); });
  var timer;
  q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { apply(true); }, 150); });
  sort.addEventListener('change', function () { withTransition(function () { doSort(); apply(true); }); });
  reset.addEventListener('click', clearAll);
  if (toolNote) document.getElementById('tool-clear').addEventListener('click', function () { toolSel = ''; apply(true); });
  reset2.addEventListener('click', clearAll);
  if (reset3) reset3.addEventListener('click', clearAll);
  moreButton.addEventListener('click', function () {
    var first = limit;
    limit += PAGE;
    apply(false, true);
    // 追加した最初の事例にフォーカスを移す（キーボードやスクリーンリーダーで続きから読めるように）
    var shownCards = Array.prototype.filter.call(list.children, function (c) { return !c.hidden; });
    var next = shownCards[first] && shownCards[first].querySelector('a');
    if (next) next.focus({ preventScroll: true });
  });
}


// トップの「きょうの1件」（2026-11-08 の見本で案D。2026-11-11 の見本で案A：候補を標本カードの扇にした。戻し先のタグ zukan-before-today-fan-2026-11-11）。
// 観測スコアの高い事例を、日本時間の日付で1件ずつ順に手前に出す（その日はだれが開いても同じ）。左右にめくると前後の候補が手前に来る。
// カードの姿勢はすべて「手前にある位置 p」だけで決まる。事例を開いた数を today/ID、めくった数を today-flip（1回の表示で1回だけ）で数える
(function () {
  var box = document.getElementById('today');
  var dataEl = document.getElementById('today-data');
  var fan = document.getElementById('today-fan');
  if (!box || !dataEl || !fan) return;
  var pool;
  try { pool = JSON.parse(dataEl.textContent); } catch (e) { return; }
  if (!pool || !pool.length) return;
  var n = pool.length;
  var cls = { '社内': 'is-internal', 'ファン・顧客': 'is-fan', '多企業': 'is-multi' };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function count(path, title) { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: path, title: title, event: true }); }
  function slot(d) {  // pages.py の today_slot() と同じ形
    return '<a class="today-card" draggable="false" href="cases/' + encodeURIComponent(d.id) + '/" data-id="' + esc(d.id) + '">' +
      '<span class="tc-top"><span class="tc-no">No.' + esc(d.id) + '</span>' +
      '<span class="tc-emo"><img src="assets/emoji/' + esc(d.emoji) + '.png" alt="" width="28" height="28"></span></span>' +
      '<span class="tc-meta"><span class="badge ' + (cls[d.type] || 'is-other') + '">' + esc(d.type) + '</span><span class="tc-co">' + esc(d.co) + '</span></span>' +
      '<strong class="tc-title">' + esc(d.title) + '</strong><span class="tc-point">' + esc(d.point) + '</span>' +
      '<span class="tc-more">事例を読む</span></a>';
  }
  var day = Math.floor((Date.now() + 9 * 3600 * 1000) / 86400000);
  var today = day % n;
  var cur = today;
  var wrap = n >= 8;   // 候補が少ないときは端で止める（輪にすると裏から回り込むのが見えるため）
  fan.innerHTML = pool.map(slot).join('');
  var cards = Array.prototype.slice.call(fan.children);

  function offset(i, p) {
    var d = i - p;
    if (wrap) { d = ((d % n) + n) % n; if (d > n / 2) d -= n; }
    return d;
  }
  function pose(p) {
    var w = fan.clientWidth;
    var g1 = w < 340 ? 40 : 52, g2 = 14;
    cards.forEach(function (el, i) {
      var d = offset(i, p), ad = Math.abs(d), sg = d < 0 ? -1 : 1;
      var x = sg * (ad < 1 ? ad * g1 : g1 + (ad - 1) * g2);
      var y = Math.pow(Math.min(ad, 3), 1.5) * 6;
      var r = Math.max(-18, Math.min(18, d * 5));
      var sc = 1 - Math.min(ad, 3) * .05;
      el.style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px) rotate(' + r.toFixed(2) + 'deg) scale(' + sc.toFixed(3) + ')';
      el.style.zIndex = String(100 - Math.round(ad * 10));
      el.style.visibility = ad > 3.2 ? 'hidden' : '';
      var front = ad < .5;
      el.classList.toggle('is-front', front);
      el.tabIndex = front ? 0 : -1;
      if (front) el.removeAttribute('aria-hidden'); else el.setAttribute('aria-hidden', 'true');
    });
  }
  var flipped = false;
  var back = document.getElementById('today-back');
  function go(i, focus) {
    cur = wrap ? ((i % n) + n) % n : Math.max(0, Math.min(n - 1, i));
    fan.classList.remove('is-dragging');
    pose(cur);
    if (back) back.hidden = cur === today;
    if (prev) prev.disabled = !wrap && cur === 0;
    if (next) next.disabled = !wrap && cur === n - 1;
    if (cur !== today && !flipped) { flipped = true; count('today-flip', 'きょうの1件（めくった）'); }
    if (focus) cards[cur].focus({ preventScroll: true });
  }
  var nav = document.getElementById('today-nav');
  var prev = document.getElementById('today-prev');
  var next = document.getElementById('today-next');
  if (nav && n > 1) {
    nav.hidden = false;
    prev.addEventListener('click', function () { go(cur - 1); });
    next.addEventListener('click', function () { go(cur + 1); });
  }
  if (back) back.addEventListener('click', function () { go(today, true); });
  if (reduce) fan.classList.add('is-still');
  go(today);
  fan.classList.add('is-ready');

  // 手前のカードは事例ページへ。奥のカードを押すと、そのカードが手前に来る
  var dragged = false;
  fan.addEventListener('click', function (e) {
    var a = e.target.closest('.today-card');
    if (!a) return;
    if (dragged) { e.preventDefault(); dragged = false; return; }
    var i = cards.indexOf(a);
    if (i !== cur) { e.preventDefault(); go(i); return; }
    count('today/' + a.getAttribute('data-id'), 'きょうの1件（開いた）');
  });
  fan.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') { go(cur + 1, true); e.preventDefault(); }
    else if (e.key === 'ArrowLeft') { go(cur - 1, true); e.preventDefault(); }
  });

  // 横にドラッグしてめくる（縦のスクロールはそのまま）。リンクや絵をつかんで動かす標準の動きは止める（止めないとめくりが途中で切れる）
  fan.addEventListener('dragstart', function (e) { e.preventDefault(); });
  if (n < 2) return;
  var start = null;
  fan.addEventListener('pointerdown', function (e) {
    if (e.button !== 0) return;
    start = { x: e.clientX, y: e.clientY, t: e.timeStamp, moving: false, id: e.pointerId };
    dragged = false;
  });
  fan.addEventListener('pointermove', function (e) {
    if (!start) return;
    var dx = e.clientX - start.x, dy = e.clientY - start.y;
    if (!start.moving) {
      if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) { start = null; return; }
      if (Math.abs(dx) < 6) return;
      start.moving = true;
      fan.classList.add('is-dragging');
      try { fan.setPointerCapture(start.id); } catch (err) {}
    }
    var p = cur - dx / 90;
    if (!wrap) p = Math.max(-.4, Math.min(n - .6, p));
    pose(p);
    start.lastX = e.clientX; start.lastT = e.timeStamp;
  });
  function end(e) {
    if (!start) return;
    var s = start; start = null;
    if (!s.moving) return;
    dragged = true;
    setTimeout(function () { dragged = false; }, 0);
    var dx = e.clientX - s.x;
    var v = s.lastT && e.timeStamp > s.t ? dx / (e.timeStamp - s.t) : 0;   // px/ms
    var steps = Math.round(dx / 90 + (Math.abs(v) > .5 ? (v > 0 ? .5 : -.5) : 0));
    go(cur - steps);
  }
  fan.addEventListener('pointerup', end);
  fan.addEventListener('pointercancel', function () { if (start && start.moving) { start = null; go(cur); } else start = null; });
  window.addEventListener('resize', function () { pose(cur); });
})();
