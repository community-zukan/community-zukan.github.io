(function () {
  // トップのHTMLには最初の24件だけが入っている。残り（data-rest）を読み込んで足してから、絞り込みなどを動かす。
  // 読み込めなかったときは、入っている分だけで動かす
  var listEl = document.getElementById('cards');
  var restUrl = listEl && listEl.getAttribute('data-rest');
  if (restUrl && window.fetch) {
    fetch(restUrl).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (t) { listEl.insertAdjacentHTML('beforeend', t); })
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
    count.textContent = filtering ? cards.length + '件中 ' + shown + '件の事例' : cards.length + '件の事例';
    activeCount.textContent = n ? n + '件の条件' : '';
    reset.hidden = !filtering;
    if (reset3) reset3.hidden = !filtering;
    empty.hidden = shown !== 0;
    if (shown === 0) showRelax(s, words, terms);
    showSearchNote(words, terms);
    countSearch(shown);
    if (pushState) saveUrl(s);
    markTiles(s);
    narrowPurposes(s);
    // コミュニティAIへの案内：結果が少ない（data-few の件数以下）ときだけ囲みで出す
    if (aiHelp) aiHelp.hidden = shown > (parseInt(aiHelp.getAttribute('data-few'), 10) || 5);
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
      apply(true);
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
    apply(true);
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
    savedToggle.addEventListener('click', function () { setSavedOnly(!savedOnly); apply(false); });
  }

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

  boxes.forEach(function (b) { b.addEventListener('change', function () { apply(true); }); });
  var timer;
  q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { apply(true); }, 150); });
  sort.addEventListener('change', function () { doSort(); apply(true); });
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


// トップの「きょうの1件」（2026-11-08 の見本で案D）：観測スコアの高い事例を、日本時間の日付で1件ずつ順に出す（その日はだれが開いても同じ）。
// 🎲を押すと候補の中からランダムに替える。押した数と、事例を開いた数を GoatCounter の today-roll・today/ID で数える
(function () {
  var box = document.getElementById('today');
  var dataEl = document.getElementById('today-data');
  if (!box || !dataEl) return;
  var pool;
  try { pool = JSON.parse(dataEl.textContent); } catch (e) { return; }
  if (!pool || !pool.length) return;
  var link = document.getElementById('today-link');
  var btn = document.getElementById('today-roll');
  var cls = { '社内': 'is-internal', 'ファン・顧客': 'is-fan', '多企業': 'is-multi' };
  var label = { 'ファン・顧客': 'ファン・顧客' };
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function count(path, title) { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: path, title: title, event: true }); }
  var day = Math.floor((Date.now() + 9 * 3600 * 1000) / 86400000);
  var cur = day % pool.length;
  function show(i, flip) {
    var d = pool[i];
    link.href = 'cases/' + encodeURIComponent(d.id) + '/';
    link.setAttribute('data-id', d.id);
    link.innerHTML = '<span class="today-emo"><img src="assets/emoji/' + esc(d.emoji) + '.png" alt="" width="32" height="32"></span>' +
      '<span class="today-meta"><span class="badge ' + (cls[d.type] || 'is-other') + '">' + esc(label[d.type] || d.type) + '</span><span class="today-co">' + esc(d.co) + '</span></span>' +
      '<strong>' + esc(d.title) + '</strong><span class="today-point">' + esc(d.point) + '</span><span class="today-more">事例を読む</span>';
    if (flip) { link.classList.remove('is-flip'); void link.offsetWidth; link.classList.add('is-flip'); }
  }
  if (link.getAttribute('data-id') !== pool[cur].id) show(cur, false);  // 作った日と開いた日がちがうときだけ入れ替える
  link.addEventListener('click', function () { count('today/' + link.getAttribute('data-id'), 'きょうの1件（開いた）'); });
  if (pool.length < 2) return;
  btn.hidden = false;
  btn.addEventListener('click', function () {
    var i;
    do { i = Math.floor(Math.random() * pool.length); } while (i === cur);
    cur = i;
    btn.classList.add('is-rolling');
    setTimeout(function () { btn.classList.remove('is-rolling'); }, 500);
    show(cur, true);
    count('today-roll', 'きょうの1件（ほかの事例をひく）');
  });
})();
