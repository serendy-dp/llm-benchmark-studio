"""
結果 JSON を読み込んでスコアを集計・表示するビューワー
採点済みの結果ファイル、または採点を後から追加したい場合に使用する

Usage:
  python score_viewer.py results/benchmark_xxx.json
  python score_viewer.py results/benchmark_xxx.json --score    # 未採点問題を採点
"""

import json
import sys
import argparse
from pathlib import Path


SCORE_BAR = {5: "█████", 3: "███░░", 1: "█░░░░", 0: "░░░░░", None: "─────"}


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[保存] {path}")


def interactive_score(q: dict) -> int | None:
    print("\n─── 採点 ────────────────────────────────────────")
    print(f"[{q['id']}] {q['title']}  {q['difficulty']}")
    print("\nスコアリング基準:")
    for s in q["scoring_criteria"]:
        print(f"  [{s['score']}点] {s['label']}")
    print("\n実際のレスポンス:")
    print(q["response"] or "(なし)")
    while True:
        raw = input("\nスコアを入力 (0/1/3/5, スキップ=Enter): ").strip()
        if raw == "":
            return None
        if raw in {"0", "1", "3", "5"}:
            return int(raw)
        print("0, 1, 3, 5 のいずれかを入力してください")


def print_report(data: dict):
    meta = data.get("meta", {})
    print("\n" + "=" * 70)
    print(f"  ベンチマーク: {meta.get('benchmark_title', '?')} v{meta.get('benchmark_version', '?')}")
    print(f"  モデル:       {meta.get('model', '?')}")
    print(f"  実行日時:     {meta.get('run_at', '?')}")
    print("=" * 70)

    all_scores = []

    for domain in data["domains"]:
        qs = domain["questions"]
        scores = [q["score"] for q in qs if q["score"] is not None]
        avg = sum(scores) / len(scores) if scores else None
        avg_str = f"{avg:.2f}" if avg is not None else "未採点"

        print(f"\n■ {domain['label']}  （{len(scores)}/{len(qs)}問採点）  平均: {avg_str}")
        print(f"  {'ID':<25} {'難易度':<8} {'スコア':<8} {'時間':>7}  バー")
        print(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*7}  {'─'*5}")

        for q in qs:
            score = q["score"]
            bar = SCORE_BAR.get(score, "─────")
            score_str = str(score) if score is not None else "未採点"
            err_mark = " [ERR]" if q["status"] == "error" else ""
            print(f"  {q['id']:<25} {q['difficulty']:<8} {score_str:<8} {q['elapsed_sec']:>6.1f}s  {bar}{err_mark}")

        all_scores.extend(scores)

    print("\n" + "─" * 70)
    if all_scores:
        overall = sum(all_scores) / len(all_scores)
        max_possible = 5 * len(all_scores)
        pct = (sum(all_scores) / max_possible) * 100
        print(f"  総合スコア:   {sum(all_scores)} / {max_possible}  ({pct:.1f}%)  平均: {overall:.2f} / 5")
    else:
        print("  採点済みの問題がありません")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="ベンチマーク結果ビューワー / 採点ツール")
    parser.add_argument("result_file", help="結果 JSON ファイル")
    parser.add_argument("--score", "-s", action="store_true", help="未採点の問題を採点する")
    args = parser.parse_args()

    data = load(args.result_file)

    if args.score:
        changed = False
        for domain in data["domains"]:
            for q in domain["questions"]:
                if q["score"] is None and q["status"] == "success":
                    score = interactive_score(q)
                    if score is not None:
                        q["score"] = score
                        changed = True
        if changed:
            save(data, args.result_file)

    print_report(data)


if __name__ == "__main__":
    main()
