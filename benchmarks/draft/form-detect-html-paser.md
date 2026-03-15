各Stageのテスト問題を作成します。実際のスクレイピング状況を模したプロンプトです。

---

## Stage2：ナビゲーション判断テスト

### テスト1：標準的なリンク選択
```
以下はあるWebサイトのトップページから収集したリンク一覧です。
お問い合わせフォームページに最も近いと思われるURLを1つだけ選んでください。

サイト: https://example-corp.co.jp
収集したリンク:
- /company（テキスト: 会社概要）
- /service（テキスト: サービス）
- /news（テキスト: ニュース）
- /recruit（テキスト: 採用情報）
- /toiawase（テキスト: お問い合わせ）
- /sitemap（テキスト: サイトマップ）

URLのみ1行で返してください。
```
**期待値:** `/toiawase`
**評価:** 完全一致で正解

---

### テスト2：変則リンクテキスト
```
以下はあるWebサイトのトップページから収集したリンク一覧です。
お問い合わせフォームページに最も近いと思われるURLを1つだけ選んでください。

サイト: https://consulting-firm.co.jp
収集したリンク:
- /about（テキスト: 私たちについて）
- /works（テキスト: 実績）
- /thinking（テキスト: 考え方）
- /connect（テキスト: つながる）
- /members（テキスト: メンバー）
- /journal（テキスト: ブログ）

URLのみ1行で返してください。
```
**期待値:** `/connect`
**評価:** 完全一致で正解。`/about`等を選んだ場合は不正解

---

### テスト3：フッター情報あり
```
以下はあるWebサイトのフッターから収集したリンク一覧です。
お問い合わせフォームページに最も近いと思われるURLを1つだけ選んでください。

サイト: https://manufacturer.jp
収集したリンク（すべてフッター）:
- /privacy（テキスト: プライバシーポリシー）
- /terms（テキスト: 利用規約）
- /sitemap（テキスト: サイトマップ）
- /ir（テキスト: 投資家情報）
- /csr（テキスト: CSR活動）
- /inquiry（テキスト: お取引・ご相談）

URLのみ1行で返してください。
```
**期待値:** `/inquiry`
**評価:** 完全一致で正解

---

### テスト4：候補が複数ある場合
```
以下はあるWebサイトから収集したリンク一覧です。
お問い合わせフォームページに最も近いと思われるURLを1つだけ選んでください。

サイト: https://software-vendor.co.jp
収集したリンク:
- /support（テキスト: サポート）
- /contact（テキスト: Contact）
- /faq（テキスト: よくある質問）
- /docs（テキスト: ドキュメント）
- /contact/sales（テキスト: 営業へのお問い合わせ）
- /contact/support（テキスト: 技術サポート）

URLのみ1行で返してください。
```
**期待値:** `/contact` または `/contact/sales` または `/contact/support`
**評価:** `/contact`系であれば正解。`/support`や`/faq`は不正解

---

### テスト5：罠あり（ノイズが多い）
```
以下はあるWebサイトから収集したリンク一覧です。
お問い合わせフォームページに最も近いと思われるURLを1つだけ選んでください。

サイト: https://media-company.co.jp
収集したリンク:
- /contact-us-story（テキスト: 私たちの歩み）
- /newsletter（テキスト: メルマガ登録）
- /aboutus（テキスト: About Us）
- /reach-out（テキスト: Reach Out）
- /advertise（テキスト: 広告掲載）
- /press（テキスト: プレスリリース）

URLのみ1行で返してください。
```
**期待値:** `/reach-out`
**評価:** `/contact-us-story`を選んだ場合は不正解（URLにcontactが含まれるが内容は会社の歴史）

---

## Stage2：訪問済みページを踏まえた再判断テスト

### テスト6：探索の継続判断
```
お問い合わせフォームを探しています。
以下の状況を踏まえて次に訪問すべきURLを1つ選んでください。

サイト: https://enterprise.co.jp
訪問済みページ:
- / （トップページ、フォームなし）
- /company（会社概要、フォームなし）
- /service（サービス一覧、フォームなし）

未訪問リンク（訪問済みページから収集）:
- /service/detail（テキスト: サービス詳細）
- /company/history（テキスト: 沿革）
- /contact（テキスト: お問い合わせ）
- /news（テキスト: ニュース）
- /partner（テキスト: パートナー）

URLのみ1行で返してください。
```
**期待値:** `/contact`
**評価:** 完全一致で正解

---

### テスト7：打ち切り判断
```
お問い合わせフォームを探しています。
以下の状況を踏まえて次のアクションを判断してください。

サイト: https://closed-corp.co.jp
訪問済みページ（30ページ）:
- / /about /company /service /service/a /service/b
  /service/c /news /news/1〜20 /recruit /recruit/detail
  /ir /ir/report /csr /csr/activity /sitemap /privacy /terms

未訪問リンク:
- /news/21〜50（テキスト: ニュース記事）

状況: 30ページ訪問済み。フォームは未発見。
残りリンクはすべてニュース記事ページ。

次のアクションを以下から選び、理由を1行で添えてください。
A: 引き続きニュース記事ページを探索する
B: このサイトにはお問い合わせフォームがない可能性が高いため探索を終了する
C: 別の手法（JSレンダリング等）に切り替える

アルファベット1文字と理由を返してください。
```
**期待値:** `B` または `C`
**評価:** `A`は不正解。BとCはどちらも正解だが理由の妥当性も評価

---

## Stage3（フォーム内容理解）テスト

### テスト8：フォームの用途判断
```
以下のHTMLはあるWebページから抽出したフォームです。
このフォームの用途を以下から1つ選んでください。

A: 一般的なお問い合わせフォーム
B: 採用応募フォーム
C: 資料請求フォーム
D: 会員登録フォーム

HTMLフォーム:
<form action="/recruit/apply" method="POST">
  <input type="text"  name="name"     placeholder="氏名">
  <input type="email" name="email"    placeholder="メールアドレス">
  <input type="text"  name="school"   placeholder="学校名">
  <select name="position">
    <option>エンジニア職</option>
    <option>営業職</option>
  </select>
  <input type="file"  name="resume"   accept=".pdf">
  <textarea           name="pr"       placeholder="自己PR"></textarea>
  <button type="submit">応募する</button>
</form>

アルファベット1文字のみ返してください。
```
**期待値:** `B`
**評価:** 完全一致で正解

---

### テスト9：複数フォームの優先判断
```
以下のHTMLには複数のフォームが含まれています。
一般的なお問い合わせフォームはどれか、番号を1つ返してください。

フォーム1:
<form action="/newsletter/subscribe">
  <input type="email" name="email" placeholder="メールアドレス">
  <button>メルマガ登録</button>
</form>

フォーム2:
<form action="/search">
  <input type="text" name="q" placeholder="サイト内検索">
  <button>検索</button>
</form>

フォーム3:
<form action="/contact/send" method="POST">
  <input type="text"  name="company"  placeholder="会社名">
  <input type="text"  name="name"     placeholder="お名前">
  <input type="email" name="email"    placeholder="メールアドレス">
  <textarea           name="message"  placeholder="お問い合わせ内容"></textarea>
  <button type="submit">送信する</button>
</form>

数字1文字のみ返してください。
```
**期待値:** `3`
**評価:** 完全一致で正解

---

### テスト10：曖昧なフォームの判断
```
以下のHTMLフォームが「一般的なお問い合わせフォーム」である可能性を
0〜100のスコアで返してください。

<form action="/api/v1/lead" method="POST">
  <input type="text"  name="full_name"    placeholder="Your Name">
  <input type="email" name="work_email"   placeholder="Work Email">
  <input type="text"  name="company"      placeholder="Company">
  <input type="text"  name="job_title"    placeholder="Job Title">
  <select name="employees">
    <option>1-10</option>
    <option>11-50</option>
    <option>51-200</option>
    <option>201+</option>
  </select>
  <textarea name="use_case" placeholder="Tell us about your use case"></textarea>
  <button type="submit">Request a Demo</button>
</form>

数値のみ返してください。
```
**期待値:** 30〜60の範囲
**評価:** お問い合わせ寄りではなくリード獲得・デモ申込フォームと判断できているかを見る。70以上は過大評価で減点

---

## テスト評価マトリクス

| テスト | Stage | 難易度 | 評価軸 |
|---|---|---|---|
| 1 | 2 | 易 | 基本的なキーワード認識 |
| 2 | 2 | 中 | 変則テキストの意味理解 |
| 3 | 2 | 易 | フッターリンクの選択 |
| 4 | 2 | 中 | 複数候補からの絞り込み |
| 5 | 2 | 難 | ノイズURLの除外 |
| 6 | 2 | 中 | 訪問履歴を踏まえた判断 |
| 7 | 2 | 難 | 打ち切り判断・メタ認知 |
| 8 | 3 | 易 | フォーム用途の分類 |
| 9 | 3 | 中 | 複数フォームの優先順位 |
| 10 | 3 | 難 | 曖昧なフォームのスコアリング |

テスト1〜4が通れば実用最低ラインで、テスト5・7・10が通れば本番投入可能と判断できます。