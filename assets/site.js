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

// スマホで読むとき：下に読むとヘッダーを隠し、上に戻すと出す（広い画面では何もしない）
(function () {
  var header = document.querySelector(".site-header");
  if (!header || !window.matchMedia) return;
  var narrow = window.matchMedia("(max-width: 759px)");
  var root = document.documentElement;
  var lastY = window.scrollY;
  var hidden = false;
  function setHidden(h) {
    if (h === hidden) return;
    hidden = h;
    header.classList.toggle("is-hidden", h);
    // 一覧の件数の帯（.result-bar）が、出ているヘッダーの下に付くようにする
    root.style.setProperty("--header-offset", h ? "0px" : header.offsetHeight + "px");
  }
  function busy() {
    var nav = document.getElementById("global-nav");
    var form = document.getElementById("header-search");
    return (nav && nav.classList.contains("open")) || (form && !form.hidden) || header.contains(document.activeElement);
  }
  root.style.setProperty("--header-offset", header.offsetHeight + "px");
  window.addEventListener("scroll", function () {
    var y = window.scrollY;
    if (!narrow.matches || busy()) { setHidden(false); lastY = y; return; }
    if (y < 80) setHidden(false);
    else if (y > lastY + 6) setHidden(true);
    else if (y < lastY - 6) setHidden(false);
    lastY = y;
  }, { passive: true });
})();
