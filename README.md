# コミュニティ図鑑

ファンコミュニティと社内コミュニティの公開事例集です。
https://community-zukan.github.io/

## 仕組み

1. 事例はGoogleスプレッドシート「コミュニティ図鑑」の「事例一覧」タブに集めます（Claudeが3時間ごとに収集・判定）。
2. 確認状況が「確認済み」の行だけが「公開用」タブに出ます。
3. 「公開用」タブをウェブに公開したCSVを、GitHub Actionsが毎日5:40（日本時間）に読み込み、サイトを作り直します。

## 公開を止める条件

次のときはサイトを更新せず、前の状態のまま残します。

- CSVを取得できない、またはCSVではなくHTMLが返ってきた
- 事例が0件
- 公開中のサイトより件数が半分未満に減った

件数が減ったのが意図どおりなら、Actionsの「サイトを更新」から「Run workflow」を押し、「件数が急に減っても公開する」にチェックを入れて実行します。

## ファイル

- `build.py` サイトを作るスクリプト（Python標準ライブラリのみ。pykakasi があればひらがな検索用の読みを足す）
- `config/` サイトの設定（site.json）、検索の言い換え表（synonyms.json）、組み合わせのページの解説（combo_notes.json）
- `assets/` CSS・JavaScript・ファビコン・共有画像
- `tools/make_og.py` 事例ページごとの共有画像を作る
- `tools/check_links.py` 出典URLのリンク切れを点検する
- `.github/workflows/build.yml` 毎日の更新
- `.github/workflows/check-links.yml` 毎週月曜のリンク切れの点検（要確認があれば Issue を作る）
- `data/latest.csv` 最後に使ったデータ（自動で更新。履歴を「新着と更新」に使う）
- `data/linkcheck.json` 最後のリンク点検の結果（自動で更新）
- `testdata/` 手元で試すためのデータ（public.csv は A〜U 列、public_vy.csv は V〜Y 列つき）

## 手元で試す

```
python3 build.py --csv testdata/public_vy.csv --no-live-check
python3 -m http.server 8765 -d _site
```

手元のCSVで試したときは data/latest.csv を書き換えません。共有画像やひらがな検索まで試すときは、CLAUDE.md の「手元で試す」を見てください。
