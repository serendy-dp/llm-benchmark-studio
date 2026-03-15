"""
LLM Agent Orchestration Benchmark Runner
LM Studio の /api/v1/chat エンドポイントを使ってベンチマークを実行する
"""

import json
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── 設定 ─────────────────────────────────────────
DEFAULT_BASE_URL  = "http://localhost:1234"
DEFAULT_MODEL     = None          # None = ロード済みモデルを自動検出
DEFAULT_BENCHMARK = "llm_agent_orchestration_benchmark.json"
DEFAULT_OUTPUT_DIR = "results"
DEFAULT_MAX_TOKENS  = 4096
DEFAULT_TEMPERATURE = 0.7
# ─────────────────────────────────────────────────


def load_benchmark(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detect_loaded_model(base_url: str) -> str:
    """ロード済み（loaded_instances が空でない）モデルを返す"""
    resp = requests.get(f"{base_url}/api/v1/models", timeout=5)
    resp.raise_for_status()
    models = resp.json().get("models", [])
    for m in models:
        if m.get("type") == "llm" and m.get("loaded_instances"):
            key = m["key"]
            name = m.get("display_name", key)
            print(f"[検出されたモデル] {name} ({key})")
            return key
    raise RuntimeError("ロード済みの LLM モデルが見つかりません。LM Studio でモデルをロードしてください。")


def clean_content(text: str) -> str:
    """モデルが出力するトークン末尾ゴミを除去する"""
    for marker in ["<|im_end|>", "<|endoftext|>", "</s>"]:
        text = text.replace(marker, "")
    return text.strip()


def run_question(
    base_url: str,
    model: str,
    question: dict,
    max_tokens: int,
    temperature: float,
) -> dict:
    """1 問を実行して結果を返す"""
    payload = {
        "model": model,
        "system_prompt": (
            "あなたは優秀なAIエージェントです。"
            "指示に従い、構造的・論理的に回答してください。"
        ),
        "input": question["prompt"],
    }
    start = time.time()
    try:
        resp = requests.post(
            f"{base_url}/api/v1/chat",
            json=payload,
            timeout=600,
        )
        resp.raise_for_status()
        elapsed = time.time() - start
        data = resp.json()

        # レスポンスから本文を取り出す
        content = ""
        for chunk in data.get("output", []):
            if chunk.get("type") == "message":
                content += chunk.get("content", "")
        content = clean_content(content)

        stats = data.get("stats", {})
        usage = {
            "prompt_tokens":     stats.get("input_tokens", 0),
            "completion_tokens": stats.get("total_output_tokens", 0),
            "total_tokens":      stats.get("input_tokens", 0) + stats.get("total_output_tokens", 0),
            "tokens_per_second": round(stats.get("tokens_per_second", 0), 1),
        }
        return {
            "status": "success",
            "response": content,
            "elapsed_sec": round(elapsed, 2),
            "usage": usage,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "status": "error",
            "response": None,
            "elapsed_sec": round(elapsed, 2),
            "usage": {},
            "error": str(e),
        }


def print_result_preview(domain_label: str, q: dict, result: dict, idx: int, total: int):
    icon = "✓" if result["status"] == "success" else "✗"
    tps = result["usage"].get("tokens_per_second", "")
    tps_str = f"  {tps} tok/s" if tps else ""
    tokens = result["usage"].get("total_tokens", "")
    tokens_str = f"  {tokens} tokens" if tokens else ""

    print(f"\n[{idx}/{total}] {icon} [{domain_label}] {q['id']} - {q['title']}")
    print(f"  難易度: {q['difficulty']}  タグ: {', '.join(q['tags'])}")
    print(f"  時間: {result['elapsed_sec']}秒{tokens_str}{tps_str}")

    if result["status"] == "error":
        print(f"  [ERROR] {result['error']}")
    else:
        preview = (result["response"] or "")[:200].replace("\n", " ")
        print(f"  レスポンス冒頭: {preview}...")


def interactive_score(q: dict, result: dict) -> Optional[int]:
    if result["status"] == "error":
        return None

    print("\n─── 採点 ────────────────────────────────────────")
    print("スコアリング基準:")
    for s in q["scoring"]:
        print(f"  [{s['score']}点] {s['label']}")

    if "expected_output" in q:
        print(f"\n期待出力:\n{q['expected_output']}")

    print("\n実際のレスポンス:")
    print(result["response"])

    while True:
        raw = input("\nスコアを入力 (0/1/3/5, スキップ=Enter): ").strip()
        if raw == "":
            return None
        if raw in {"0", "1", "3", "5"}:
            return int(raw)
        print("0, 1, 3, 5 のいずれかを入力してください")


def make_output_path(output_dir: str, model_name: str) -> Path:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = model_name.replace("/", "_").replace(":", "-")
    return Path(output_dir) / f"benchmark_{safe}_{ts}.json"


def flush_results(results: dict, out_path: Path):
    """現在の結果を即座にファイルへ書き込む"""
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def print_summary(results: dict):
    print("\n" + "=" * 60)
    print("  ベンチマーク結果サマリー")
    print("=" * 60)
    all_scores, total_time = [], 0.0
    for domain in results["domains"]:
        scores = [q["score"] for q in domain["questions"] if q["score"] is not None]
        avg = f"{sum(scores)/len(scores):.2f}" if scores else "未採点"
        n = len(domain["questions"])
        print(f"  {domain['label']:<20} {len(scores)}/{n}問採点  平均: {avg} / 5")
        all_scores.extend(scores)
        for q in domain["questions"]:
            total_time += q.get("elapsed_sec", 0)
    if all_scores:
        overall = sum(all_scores) / len(all_scores)
        print(f"\n  総合平均スコア: {overall:.2f} / 5  ({len(all_scores)}問採点済み)")
    print(f"  合計実行時間:   {total_time:.1f}秒")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="LM Studio /api/v1/chat を使って LLM Agent Orchestration Benchmark を実行する"
    )
    parser.add_argument("--url",        default=DEFAULT_BASE_URL)
    parser.add_argument("--model",      default=DEFAULT_MODEL, help="モデルキー（省略時は自動検出）")
    parser.add_argument("--benchmark",  default=DEFAULT_BENCHMARK)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-tokens", type=int,   default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--temperature",type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--domain",     help="実行するドメイン（カンマ区切りで複数指定可: task_decomp,tool_selection）")
    parser.add_argument("--question",   help="特定の問題のみ実行（例: task_decomp_01）")
    parser.add_argument("--interval",   type=float, default=5.0, help="問題間の待機秒数（デフォルト: 5秒）")
    parser.add_argument("--score", "-s",action="store_true", help="実行後にインタラクティブ採点")
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()

    model = args.model
    if not args.dry_run:
        model = model or detect_loaded_model(args.url)
    else:
        model = model or "dry-run-model"

    print(f"[設定] モデル: {model}")
    print(f"[設定] エンドポイント: {args.url}")
    print(f"[設定] max_tokens={args.max_tokens}  temperature={args.temperature}")

    benchmark = load_benchmark(args.benchmark)
    meta = benchmark["benchmark_meta"]
    print(f"\n[ベンチマーク] {meta['title']} v{meta['version']}")
    print(f"  {meta['total_domains']}ドメイン / {meta['total_questions']}問\n")

    results = {
        "meta": {
            "benchmark_title":   meta["title"],
            "benchmark_version": meta["version"],
            "model":        model,
            "base_url":     args.url,
            "run_at":       datetime.now().isoformat(),
            "max_tokens":   args.max_tokens,
            "temperature":  args.temperature,
        },
        "domains": [],
    }

    domains_filter = set(args.domain.split(",")) if args.domain else None
    questions_to_run = []
    for domain in benchmark["domains"]:
        if domains_filter and domain["id"] not in domains_filter:
            continue
        for q in domain["questions"]:
            if args.question and q["id"] != args.question:
                continue
            questions_to_run.append((domain, q))

    total = len(questions_to_run)
    out_path = make_output_path(args.output_dir, model)
    print(f"[実行予定] {total}問")
    print(f"[出力先]   {out_path}\n")

    domain_results: dict[str, dict] = {}

    for idx, (domain, q) in enumerate(questions_to_run, 1):
        if args.dry_run:
            result = {"status": "dry-run", "response": "[dry-run]", "elapsed_sec": 0.0, "usage": {}, "error": None}
        else:
            result = run_question(args.url, model, q, args.max_tokens, args.temperature)

        print_result_preview(domain["label"], q, result, idx, total)

        score = None
        if args.score and not args.dry_run:
            score = interactive_score(q, result)

        d_id = domain["id"]
        if d_id not in domain_results:
            domain_results[d_id] = {"id": d_id, "label": domain["label"], "questions": []}

        domain_results[d_id]["questions"].append({
            "id":              q["id"],
            "title":           q["title"],
            "difficulty":      q["difficulty"],
            "tags":            q["tags"],
            "status":          result["status"],
            "response":        result["response"],
            "elapsed_sec":     result["elapsed_sec"],
            "usage":           result["usage"],
            "error":           result["error"],
            "score":           score,
            "scoring_criteria": q["scoring"],
        })

        # 1問ごとに即書き込み
        results["domains"] = list(domain_results.values())
        flush_results(results, out_path)
        print(f"  → 保存済み ({idx}/{total})")

        # 次の問題まで待機（最終問は不要）
        if idx < total and not args.dry_run:
            print(f"  　{args.interval:.0f}秒待機中...", end="\r")
            time.sleep(args.interval)
            print(" " * 20, end="\r")  # 待機メッセージを消す

    print(f"\n[完了] {out_path}")
    print_summary(results)


if __name__ == "__main__":
    main()
