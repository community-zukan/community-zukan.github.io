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
