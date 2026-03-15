# /build-benchmark — ドラフトからベンチマーク定義ファイルを生成

`benchmarks/draft/` 内のドラフトファイルを読み込み、`schemas/benchmark.schema.json` に準拠した正式なベンチマーク JSON を `benchmarks/` に生成する。

## 引数

```
/build-benchmark [ドラフトファイル名]
```

- ファイル名を省略した場合は `benchmarks/draft/` 内のファイル一覧を表示して選択を求める
- ファイル名に拡張子は不要（省略可）

---

## 実行手順

### 1. ドラフトの読み込み

`benchmarks/draft/<ファイル名>` を Read ツールで読み込む。
ドラフトの形式は問わない（Markdown / 箇条書き / 自由記述テキスト / 不完全な JSON など）。

### 2. ドラフトの解析

以下の情報を抽出・推論する：

| 抽出対象 | ドラフトに明示されていない場合の補完方針 |
|---------|----------------------------------------|
| ベンチマーク名称 | ドラフトのテーマから命名 |
| ドメイン一覧 | 問題群を能力カテゴリに分類してグルーピング |
| 問題ごとのプロンプト | 記述された評価意図を元に具体的なタスク指示文として展開 |
| 採点基準 (scoring) | 必ず **5/3/1/0** の4段階を定義する（後述のルール参照） |
| 難易度 (difficulty) | ★1〜5 で設定（問題の認知負荷・複合性から判断） |
| タグ | 評価能力を表す名詞2〜4語 |

### 3. JSON の生成ルール

#### benchmark_meta
- `version`: 新規は `"1.0"`
- `created`: 今日の日付 (YYYY-MM-DD)
- `scoring_scale`: 必ず `{ "max": 5, "levels": [5, 3, 1, 0] }`
- `total_domains` / `total_questions`: 生成後に正確に数えて設定する

#### domains[].id
- snake_case、英数字とアンダースコアのみ
- 例: `task_decomp`, `error_handling`, `context_mgmt`

#### domains[].color
ドメインごとに以下のパレットから重複なく割り当てる：
`#1D9E75` `#378ADD` `#E8A838` `#D4537E` `#9B59B6` `#D85A30` `#2ECC71` `#E74C3C`

#### questions[].id
`{domain_id}_{ゼロ埋め2桁連番}` 形式
例: `task_decomp_01`, `task_decomp_02`

#### questions[].prompt
- 冒頭に状況・役割・制約を明示する（例: 「エージェントとして動作してください」）
- 求める出力形式を末尾に指定する
- 曖昧な指示にしない。測定したい能力が問題から明確に問われるようにする
- 長すぎず、必要な情報だけを与える（目安: 150〜400文字）

#### scoring（4段階ルール）
| score | 意味 | ラベルの書き方 |
|------:|------|--------------|
| 5 | 全要件を完全に満たす | 核心的な達成条件を箇条書きで列挙（例: 「〇〇が正確・△△を考慮・□□の計算が正しい」） |
| 3 | おおむね正しいが部分的に不十分 | score=5 と何が違うかを明示（例: 「〇〇は正しいが△△が不完全」） |
| 1 | 方向性は合っているが重要な要件を欠く | 何ができていて何が欠けているかを示す |
| 0 | 要件を完全に無視または根本的に誤っている | 最悪のケースを具体的に示す |

scoring は各問題の評価軸が異なる具体的な記述にする。「正しい/間違い」のような汎用表現は避ける。

### 4. 出力ファイルの保存

出力ファイル名の決め方：
- ドラフトファイル名から `_draft` を除いた名前をベースにする
- snake_case + `_benchmark.json` を付与する
- 例: `draft/my_topic_draft.md` → `benchmarks/my_topic_benchmark.json`

Write ツールで `benchmarks/<filename>.json` に保存する。

### 5. バリデーション

保存後、以下のコマンドでスキーマ検証を実行する：

```bash
source .venv/bin/activate && python3 -c "
import json
from pathlib import Path
from jsonschema import validate
schema = json.loads(Path('schemas/benchmark.schema.json').read_text())
data = json.loads(Path('benchmarks/<生成ファイル名>').read_text())
validate(data, schema)
print('Schema OK')
"
```

バリデーションエラーが出た場合は該当箇所を修正して再保存する。

### 6. 完了報告

以下の形式で出力する：

```
✅ benchmarks/<filename>.json を生成しました

  ドメイン数 : <N>
  問題数     : <N>
  難易度分布 : ★★★ × N  ★★★★ × N  ★★★★★ × N

ドメイン一覧:
  - <domain_id>  「<label>」  <問題数>問
  ...
```
