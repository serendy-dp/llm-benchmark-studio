# LLM Agent Orchestration Benchmark

LM Studio のローカル API を使って、LLM のエージェント・オーケストレーション能力を自動評価するベンチマークツールです。

## 概要

8つのドメイン・26問のプロンプトで LLM の能力を体系的に測定します。

| ドメイン | 問数 | 難易度 |
|---|---|---|
| タスク分解 | 3 | 中 |
| ツール選択 | 3 | 中 |
| マルチエージェント | 3 | 高 |
| コンテキスト管理 | 3 | 高 |
| 自己修正・省察 | 3 | 高 |
| 長期プランニング | 3 | 最高 |
| 安全性・判断 | 3 | 最高 |
| ルール遵守・出力制御 | 5 | 中〜高 |

スコアは各問 **0 / 1 / 3 / 5** の4段階で評価します。

## ファイル構成

```
llm-benchmark/
├── llm_agent_orchestration_benchmark.json  # ベンチマーク問題集
├── benchmark_runner.py                     # 実行スクリプト
├── score_viewer.py                         # 結果表示・採点ツール
├── requirements.txt
└── results/                                # 実行結果の保存先（自動生成）
```

## セットアップ

**前提条件:** [LM Studio](https://lmstudio.ai/) がインストール済みで、モデルがロードされていること。

```bash
# 仮想環境を作成・有効化
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

## 使い方

### 1. ベンチマーク実行

LM Studio を起動してモデルをロードしてから実行します。

```bash
# 全26問を実行（モデルは自動検出）
python benchmark_runner.py

# 特定ドメインのみ実行
python benchmark_runner.py --domain task_decomp

# 特定の1問のみ実行
python benchmark_runner.py --question task_decomp_01

# 実行しながらその場で採点する
python benchmark_runner.py --score

# API を呼ばずに動作確認（dry-run）
python benchmark_runner.py --dry-run
```

結果は `results/benchmark_<モデル名>_<日時>.json` に自動保存されます。

### 2. 結果の表示・採点

```bash
# 結果を表示
python score_viewer.py results/benchmark_xxx.json

# 未採点の問題をインタラクティブに採点
python score_viewer.py results/benchmark_xxx.json --score
```

### オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--url` | `http://localhost:1234/v1` | LM Studio の API エンドポイント |
| `--model` | 自動検出 | モデル名を手動指定 |
| `--temperature` | `0.7` | 生成温度 |
| `--max-tokens` | `4096` | 最大生成トークン数 |
| `--domain` | 全ドメイン | 実行するドメインを絞り込む |
| `--question` | 全問題 | 実行する問題 ID を指定 |
| `--score` / `-s` | なし | 実行後にインタラクティブ採点 |
| `--output-dir` | `results/` | 結果の保存先ディレクトリ |
| `--dry-run` | なし | API を呼ばずに構造だけ確認 |

## 採点方法

各問題のスコアは以下の基準で手動採点します。

| スコア | 基準 |
|---|---|
| **5** | 全要件を満たす最高品質の回答 |
| **3** | おおむね正しいが細部に不足あり |
| **1** | 部分的に正しいが重要な要素が欠けている |
| **0** | 要件を満たしていない・誤った回答 |

`--score` オプションを使うとレスポンスと採点基準を並べて表示し、その場でスコアを入力できます。後から `score_viewer.py --score` でまとめて採点することも可能です。

## 結果 JSON の構造

```json
{
  "meta": {
    "model": "モデル名",
    "run_at": "2026-03-15T12:00:00",
    "temperature": 0.7,
    ...
  },
  "domains": [
    {
      "id": "task_decomp",
      "label": "タスク分解",
      "questions": [
        {
          "id": "task_decomp_01",
          "response": "モデルの回答",
          "elapsed_sec": 12.3,
          "usage": { "total_tokens": 1024 },
          "score": 5
        }
      ]
    }
  ]
}
```

## 複数モデルの比較

異なるモデルで実行することで比較ができます。

```bash
# モデル A でテスト
python benchmark_runner.py --model "model-a"

# モデル B でテスト
python benchmark_runner.py --model "model-b"

# それぞれの結果を表示して比較
python score_viewer.py results/benchmark_model-a_xxx.json
python score_viewer.py results/benchmark_model-b_xxx.json
```
