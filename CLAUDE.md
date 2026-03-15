# LLM Benchmark Studio

LLMエージェント能力を評価するためのベンチマークツール。
FastAPI バックエンド + バニラJS SPA フロントエンド。LM Studio と連携してローカルモデルを評価する。

## 構成

```
.
├── app.py                  # FastAPI バックエンド (port 8001)
├── report_generator.py     # HTML レポート生成 (app.py から import)
├── requirements.txt        # Python 依存パッケージ
├── static/
│   └── index.html          # SPA フロントエンド
├── benchmarks/             # ベンチマーク定義ファイル (.json)
│   └── draft/              # 原案ファイル置き場 (形式自由)
├── results/
│   ├── scored/             # 全問採点済みの結果
│   ├── unscored/           # 未採点・採点中の結果
│   └── reports/            # /compare で生成したモデル比較レポート (.md)
├── schemas/
│   ├── benchmark.schema.json  # ベンチマーク定義のJSONスキーマ
│   └── result.schema.json     # 実行結果のJSONスキーマ
└── presets/                # 実行設定プリセット (.json)
```

## 起動

```bash
uvicorn app:app --port 8001 --reload
```

## 結果ファイルの構造

```json
{
  "meta": { "model": "...", "benchmark_title": "...", "run_at": "..." },
  "domains": [
    {
      "id": "domain_id",
      "label": "ドメイン名",
      "questions": [
        {
          "id": "q_id",
          "title": "問題タイトル",
          "response": "モデルの回答",
          "score": null,
          "scoring_criteria": [
            { "score": 5, "label": "..." },
            { "score": 3, "label": "..." },
            { "score": 1, "label": "..." },
            { "score": 0, "label": "..." }
          ]
        }
      ]
    }
  ]
}
```

スコアは **0 / 1 / 3 / 5** の4段階。

---

## スキル

| コマンド | トリガー | 説明 | 定義ファイル |
|---------|---------|------|------------|
| `/score` | 「採点して」 | `results/unscored/` の未採点結果を一括採点し `scored/` へ移動 | [`.claude/commands/score.md`](.claude/commands/score.md) |
| `/build-benchmark [ファイル名]` | 「ベンチマークを作成して」 | `benchmarks/draft/` のドラフトファイルを読み、スキーマ準拠の JSON を生成 | [`.claude/commands/build-benchmark.md`](.claude/commands/build-benchmark.md) |
| `/compare [ベンチマークファイル名]` | 「比較して」「モデルを比較」 | 指定ベンチマークの全採点済み結果を横断し、スコア・速度・特性を総合評価してモデル比較レポートを生成 | [`.claude/commands/compare.md`](.claude/commands/compare.md) |
