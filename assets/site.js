// どのページでも使う小さな仕組み：ダーク表示とライト表示の切り替え
(function () {
  var root = document.documentElement;
  var button = document.getElementById("theme-toggle");
  if (!button) return;
  function apply(dark) {
    if (dark) root.setAttribute("data-theme", "dark");
    else root.removeAttribute("data-theme");
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.textContent = dark ? "ライト表示" : "ダーク表示";
  }
  apply(root.getAttribute("data-theme") === "dark");
  button.hidden = false;
  button.addEventListener("click", function () {
    var dark = root.getAttribute("data-theme") !== "dark";
    apply(dark);
    try { localStorage.setItem("zukan-theme", dark ? "dark" : "light"); } catch (e) { /* 保存できなくても切り替えは効く */ }
  });
})();

// ヘッダー：スマホのメニュー、虫めがねの検索、あとで見るの件数
(function () {
  var menu = document.getElementById("menu-btn");
  var nav = document.getElementById("global-nav");
  if (menu && nav) {
    menu.addEventListener("click", function () {
      var open = !nav.classList.contains("open");
      nav.classList.toggle("open", open);
      menu.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  var btn = document.getElementById("header-search-btn");
  var form = document.getElementById("header-search");
  if (btn && form) {
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      var q = document.getElementById("q");
      // 事例一覧では、ページのキーワード欄を使う
      if (q) { q.focus(); q.scrollIntoView({ block: "center" }); return; }
      var open = form.hidden;
      form.hidden = !open;
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) form.querySelector("input").focus();
    });
  }

  var saved = document.getElementById("header-saved");
  if (saved) {
    var n = 0;
    try { n = (JSON.parse(localStorage.getItem("zukan-saved") || "[]") || []).length; } catch (e) { /* 何もしない */ }
    if (n) {
      document.getElementById("header-saved-count").textContent = n;
      saved.setAttribute("title", "あとで見る（" + n + "件）");
    }
  }
})();

// ヘッダーは上に固定している（CSS）。その高さを --header-offset に入れ、一覧の件数の帯や絞り込みの欄がヘッダーの下に付くようにする
(function () {
  var header = document.querySelector(".site-header");
  if (!header) return;
  var root = document.documentElement;
  function update() { root.style.setProperty("--header-offset", header.offsetHeight + "px"); }
  update();
  if (window.ResizeObserver) new ResizeObserver(update).observe(header);
  else window.addEventListener("resize", update);
})();

// あとで見る（どのページでも使う）：保存（localStorage の zukan-saved。入れた順に古いものから並ぶ）、ヘッダーのしおりの件数、
// 一覧のカードのしおりのボタン（2026-11-15 の見本で採用）、入れたときにしおりがヘッダーへ飛ぶ動き（同じく採用）
window.zukanSaved = (function () {
  var KEY = "zukan-saved";
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]") || []; } catch (e) { return []; }
  }
  function store(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); return true; } catch (e) { return false; }
  }
  function has(id) { return load().indexOf(id) !== -1; }
  // 入れる／外す。入れたら true、外したら false、保存できなかったら null
  function toggle(id) {
    var list = load();
    var i = list.indexOf(id);
    if (i === -1) list.push(id); else list.splice(i, 1);
    if (!store(list)) return null;
    document.dispatchEvent(new CustomEvent("zukan-saved-change", { detail: { id: id, on: i === -1, count: list.length } }));
    return i === -1;
  }
  function restart(el, cls) { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  // ヘッダーのしおりの件数。pop のときは数字がポンと大きくなって戻る
  function setHeader(pop) {
    var link = document.getElementById("header-saved");
    var count = document.getElementById("header-saved-count");
    if (!link || !count) return;
    var n = load().length;
    count.textContent = n ? String(n) : "";
    link.setAttribute("title", n ? "あとで見る（" + n + "件）" : "あとで見る");
    if (pop) { restart(count, "is-pop"); restart(link, "is-pop"); }
  }
  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // from（押したボタンの絵）からヘッダーのしおりまで、しおりが弧を描いて飛ぶ（transform と opacity だけ）。
  // 動きを減らす設定・動かせないブラウザ・ヘッダーが見えないときは飛ばさずに、すぐ done
  function fly(from, done) {
    var target = document.querySelector("#header-saved svg");
    if (calm || !from || !target || !Element.prototype.animate) { done(); return; }
    var a = from.getBoundingClientRect(), b = target.getBoundingClientRect();
    if (!a.width || !b.width || b.bottom < 0) { done(); return; }
    var x0 = a.left + a.width / 2, y0 = a.top + a.height / 2, x1 = b.left + b.width / 2, y1 = b.top + b.height / 2;
    var cx = x0 + (x1 - x0) * 0.2, cy = Math.min(y0, y1) - 28;
    var piece = document.createElement("span");
    piece.className = "save-fly";
    piece.setAttribute("aria-hidden", "true");
    piece.appendChild(document.createElement("i"));
    document.body.appendChild(piece);
    var frames = [];
    for (var k = 0, N = 20; k <= N; k++) {
      var u = k / N;
      var t = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
      var x = (1 - t) * (1 - t) * x0 + 2 * (1 - t) * t * cx + t * t * x1;
      var y = (1 - t) * (1 - t) * y0 + 2 * (1 - t) * t * cy + t * t * y1;
      var s = u < 0.25 ? 1 + u / 0.25 * 0.5 : 1.5 - (u - 0.25) / 0.75 * 0.8;
      frames.push({ offset: u, opacity: u > 0.9 ? (1 - u) / 0.1 : 1,
        transform: "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px) rotate(" + (Math.sin(u * Math.PI) * -14).toFixed(1) + "deg) scale(" + s.toFixed(3) + ")" });
    }
    var anim = piece.animate(frames, { duration: 560, easing: "linear", fill: "forwards" });
    var finished = false;
    var end = function () { if (finished) return; finished = true; if (piece.parentNode) piece.parentNode.removeChild(piece); done(); };
    anim.onfinish = end;
    setTimeout(end, 900);  // 動きが止まっても、件数は必ず変える
  }
  // カードのしおりのボタンを、入っているかどうかに合わせる（読み込んだあとに足したカードにも呼ぶ）
  function sync(root) {
    var list = load();
    Array.prototype.forEach.call((root || document).querySelectorAll(".card-save"), function (b) {
      b.setAttribute("aria-pressed", list.indexOf(b.getAttribute("data-id")) !== -1 ? "true" : "false");
    });
  }
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest(".card-save");
    if (!b) return;
    ev.preventDefault();
    var id = b.getAttribute("data-id");
    var on = toggle(id);
    if (on === null) return;
    b.setAttribute("aria-pressed", on ? "true" : "false");
    restart(b, "is-press");
    if (on) {
      if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: "save-card-" + id, title: "あとで見る（一覧のカード）：" + id, event: true });
      fly(b.querySelector("svg"), function () { setHeader(true); });
    } else {
      setHeader(false);
    }
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { sync(); });
  else sync();
  return { load: load, has: has, toggle: toggle, setHeader: setHeader, fly: fly, sync: sync };
})();

// 一覧のカードから事例ページへ、種別の札・企業名がつながって移る（2026-11-15 の見本で採用。ページをまたぐ View Transitions）。
// 題名（コミュニティ名）は移ると違和感があるので動かさない（2026-11-15 黒田さんの判断）。
// 事例ページの札と企業名には CSS で名前（vt-badge・vt-company）を付けてあり、一覧では押したカードにだけ同じ名前を付ける。
// 一覧に戻るときは、戻ってきた事例のカードに名前を付ける。目的の絵（右上の丸）は動かさない（黒田さんのメモ）。
// 一覧と事例ページ、事例ページどうしのとき以外は動かさない。対応していないブラウザ・動きを減らす設定では今までどおり切り替わる
(function () {
  if (!("onpageswap" in window)) return;
  var VT = { ".badge": "vt-badge", ".card-company": "vt-company" };
  function kind(url) {
    var p = new URL(url, location.href).pathname;
    if (/\/cases\/[^/]+\/(index\.html)?$/.test(p)) return "case";
    if (/^\/(index\.html)?$/.test(p)) return "list";
    return "other";
  }
  function caseId(url) { var m = new URL(url, location.href).pathname.match(/\/cases\/([^/]+)\//); return m ? m[1] : ""; }
  function clearNames() {
    Array.prototype.forEach.call(document.querySelectorAll("#cards [style*='view-transition-name']"), function (el) { el.style.viewTransitionName = ""; });
  }
  function nameCard(id) {
    var a = document.querySelector('#cards .card:not([hidden]) a[href="cases/' + id + '/"]');
    if (!a) return false;
    Object.keys(VT).forEach(function (sel) { var el = a.querySelector(sel); if (el) el.style.viewTransitionName = VT[sel]; });
    return true;
  }
  window.addEventListener("pageswap", function (e) {
    if (!e.viewTransition) return;
    var to = e.activation && e.activation.entry ? e.activation.entry.url : "";
    var from = kind(location.href), toKind = to ? kind(to) : "other";
    if (from === "list" && toKind === "case") {
      clearNames();
      if (!nameCard(caseId(to))) e.viewTransition.skipTransition();
    } else if (from === "case" && (toKind === "list" || toKind === "case")) {
      try { sessionStorage.setItem("zukan-vt-from", caseId(location.href)); } catch (err) { /* 何もしない */ }
    } else {
      e.viewTransition.skipTransition();
    }
  });
  window.addEventListener("pagereveal", function (e) {
    if (!e.viewTransition || kind(location.href) !== "list") return;
    clearNames();
    var id = "";
    try { id = sessionStorage.getItem("zukan-vt-from") || ""; sessionStorage.removeItem("zukan-vt-from"); } catch (err) { /* 何もしない */ }
    if (!id || !nameCard(id)) { e.viewTransition.skipTransition(); return; }
    e.viewTransition.finished.then(clearNames, clearNames);
  });
})();
