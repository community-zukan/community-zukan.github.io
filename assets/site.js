// どのページでも使う小さな仕組み：暗い表示の切り替え
(function () {
  var root = document.documentElement;
  var button = document.getElementById("theme-toggle");
  if (!button) return;
  function apply(dark) {
    if (dark) root.setAttribute("data-theme", "dark");
    else root.removeAttribute("data-theme");
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.textContent = dark ? "明るい表示にする" : "暗い表示にする";
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
      saved.hidden = false;
    }
  }
})();
