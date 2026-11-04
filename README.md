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

- `build.py` サイトを作るスクリプト（Python標準ライブラリのみ）
- `config/site.json` サイト名、CSVのURL、運営者、業種のまとめ方
- `assets/` CSSとJavaScript
- `.github/workflows/build.yml` 毎日の更新
- `data/latest.csv` 最後に使ったデータ（自動で更新）

## 手元で試す

```
python3 build.py --csv testdata/public.csv --no-live-check
python3 -m http.server -d _site
```
