// あとで見る（/saved/）：事例ページで「あとで見る」に入れた事例だけを、入れたのが新しい順に出す
(function () {
  var list = document.getElementById('saved-cards');
  if (!list) return;
  var ids = [];
  try { ids = JSON.parse(localStorage.getItem('zukan-saved') || '[]') || []; } catch (e) { ids = []; }
  var shown = 0;
  ids.slice().reverse().forEach(function (id) {
    var a = list.querySelector('a[href="../cases/' + id + '/"]');
    if (!a) return;  // 公開をやめた事例は出さない
    var li = a.parentNode;
    list.appendChild(li);  // 入れた順（新しいものが先）に並べ直す
    li.hidden = false;
    shown++;
  });
  document.getElementById('saved-count').textContent = shown ? shown + '件の事例' : '';
  document.getElementById('saved-empty').hidden = shown > 0;
})();
