"""
ベンチマーク結果を HTML レポートとして出力する
Usage: python report_generator.py results/benchmark_xxx.json
"""

import json
import sys
import argparse
from pathlib import Path


SCORE_COLOR = {5: "#1D9E75", 3: "#378ADD", 1: "#E8A838", 0: "#D4537E", None: "#CCCCCC"}
SCORE_LABEL = {5: "5点 (最高)", 3: "3点 (良好)", 1: "1点 (部分)", 0: "0点 (不可)", None: "未採点"}

DOMAIN_COLORS = [
    "#1D9E75", "#378ADD", "#7F77DD", "#D85A30",
    "#BA7517", "#639922", "#D4537E", "#533E80",
]


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def score_bar_html(score) -> str:
    color = SCORE_COLOR.get(score, "#CCC")
    width = {5: 100, 3: 60, 1: 20, 0: 4}.get(score, 0)
    label = {5: "5", 3: "3", 1: "1", 0: "0"}.get(score, "─")
    return f"""
        <div class="score-bar-wrap">
            <div class="score-bar" style="width:{width}%;background:{color}"></div>
            <span class="score-label" style="color:{color}">{label}</span>
        </div>"""


def escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html(data: dict) -> str:
    meta = data.get("meta", {})
    domains = data.get("domains", [])

    # ── 集計 ──────────────────────────────────────
    all_scores = []
    domain_avgs = []
    domain_labels = []
    for domain in domains:
        qs = domain["questions"]
        scores = [q["score"] for q in qs if q["score"] is not None]
        avg = sum(scores) / len(scores) if scores else 0
        domain_avgs.append(round(avg, 2))
        domain_labels.append(domain["label"])
        all_scores.extend(scores)

    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
    total_score = sum(all_scores)
    max_score = 5 * len(all_scores)
    pct = total_score / max_score * 100 if max_score else 0

    scored_count = len(all_scores)
    total_q = sum(len(d["questions"]) for d in domains)

    # ── レーダーチャート用データ ───────────────────
    radar_labels = json.dumps(domain_labels, ensure_ascii=False)
    radar_data   = json.dumps(domain_avgs)
    radar_colors = json.dumps(DOMAIN_COLORS[:len(domains)])

    # ── ドメインカード HTML ────────────────────────
    domain_cards_html = ""
    for i, domain in enumerate(domains):
        color = DOMAIN_COLORS[i % len(DOMAIN_COLORS)]
        qs = domain["questions"]
        scores = [q["score"] for q in qs if q["score"] is not None]
        avg = sum(scores) / len(scores) if scores else None
        avg_str = f"{avg:.1f}" if avg is not None else "─"

        rows_html = ""
        for q in qs:
            score = q["score"]
            sc_color = SCORE_COLOR.get(score, "#CCC")
            sc_badge = f'<span class="badge" style="background:{sc_color}">{score if score is not None else "─"}</span>'
            criteria_html = "".join(
                f'<div class="criterion" style="border-left:3px solid {SCORE_COLOR[s["score"]]}"><b>{s["score"]}点</b> {escape(s["label"])}</div>'
                for s in q.get("scoring_criteria", [])
            )
            response_text = escape((q.get("response") or ""))[:800]
            err = q.get("error")
            response_block = (
                f'<div class="error-block">ERROR: {escape(err)}</div>' if err
                else f'<div class="response-block">{response_text}{"…" if len(q.get("response") or "") > 800 else ""}</div>'
            )
            tps = q.get("usage", {}).get("tokens_per_second", "")
            tps_str = f" · {tps} tok/s" if tps else ""
            tokens = q.get("usage", {}).get("total_tokens", "")
            tokens_str = f" · {tokens} tokens" if tokens else ""

            rows_html += f"""
            <div class="q-card">
                <div class="q-header">
                    <div class="q-title">
                        <span class="q-id">{escape(q['id'])}</span>
                        <span class="q-name">{escape(q['title'])}</span>
                        <span class="q-diff">{escape(q['difficulty'])}</span>
                    </div>
                    <div class="q-meta">{q['elapsed_sec']}秒{tokens_str}{tps_str}</div>
                    {sc_badge}
                </div>
                <details>
                    <summary>レスポンスと採点基準を表示</summary>
                    <div class="q-detail">
                        <div class="detail-section">
                            <div class="detail-label">レスポンス</div>
                            {response_block}
                        </div>
                        <div class="detail-section">
                            <div class="detail-label">採点基準</div>
                            {criteria_html}
                        </div>
                    </div>
                </details>
                {score_bar_html(score)}
            </div>"""

        domain_cards_html += f"""
        <div class="domain-card">
            <div class="domain-header" style="border-left:5px solid {color}">
                <div>
                    <span class="domain-label">{escape(domain['label'])}</span>
                    <span class="domain-count">{len(scores)}/{len(qs)}問採点</span>
                </div>
                <div class="domain-avg" style="color:{color}">{avg_str}<span class="domain-avg-denom">/5</span></div>
            </div>
            {rows_html}
        </div>"""

    # ── バーチャート用データ ───────────────────────
    bar_labels = json.dumps([d["label"] for d in domains], ensure_ascii=False)
    bar_data   = json.dumps(domain_avgs)
    bar_colors = json.dumps([DOMAIN_COLORS[i % len(DOMAIN_COLORS)] for i in range(len(domains))])

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Benchmark Report — {escape(meta.get('model',''))}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --surface2: #22263a;
    --border: #2e3347; --text: #e2e8f0; --muted: #8892a4;
    --accent: #378ADD;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, "Segoe UI", sans-serif; font-size: 14px; }}
  a {{ color: var(--accent); }}

  /* ── ヘッダー ── */
  .header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 24px 32px; }}
  .header h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 6px; }}
  .header-meta {{ color: var(--muted); font-size: 12px; }}
  .header-meta span {{ margin-right: 16px; }}

  /* ── サマリー ── */
  .summary {{ display: flex; gap: 16px; padding: 24px 32px; flex-wrap: wrap; }}
  .stat-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 18px 24px; flex: 1; min-width: 150px;
  }}
  .stat-value {{ font-size: 36px; font-weight: 800; line-height: 1; }}
  .stat-label {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}

  /* ── チャートセクション ── */
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 0 32px 24px; }}
  @media (max-width: 800px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  .chart-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 20px; position: relative;
  }}
  .chart-title {{ font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 12px; }}
  .chart-wrap {{ position: relative; height: 280px; }}

  /* ── ドメインカード ── */
  .domains {{ padding: 0 32px 48px; display: flex; flex-direction: column; gap: 20px; }}
  .domain-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
  }}
  .domain-header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 16px 20px; background: var(--surface2);
  }}
  .domain-label {{ font-weight: 700; font-size: 15px; }}
  .domain-count {{ color: var(--muted); font-size: 12px; margin-left: 8px; }}
  .domain-avg {{ font-size: 28px; font-weight: 800; }}
  .domain-avg-denom {{ font-size: 14px; font-weight: 400; color: var(--muted); }}

  /* ── 問題カード ── */
  .q-card {{ padding: 14px 20px; border-top: 1px solid var(--border); }}
  .q-header {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }}
  .q-title {{ flex: 1; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .q-id {{ color: var(--muted); font-size: 11px; font-family: monospace; }}
  .q-name {{ font-weight: 600; }}
  .q-diff {{ color: var(--muted); font-size: 12px; }}
  .q-meta {{ color: var(--muted); font-size: 11px; }}
  .badge {{
    display: inline-block; min-width: 32px; text-align: center;
    padding: 3px 10px; border-radius: 20px; color: #fff;
    font-size: 13px; font-weight: 700;
  }}

  /* ── スコアバー ── */
  .score-bar-wrap {{ display: flex; align-items: center; gap: 8px; margin-top: 8px; }}
  .score-bar {{ height: 6px; border-radius: 3px; transition: width 0.4s; }}
  .score-label {{ font-size: 11px; font-weight: 700; }}

  /* ── 詳細 ── */
  details summary {{
    cursor: pointer; color: var(--accent); font-size: 12px;
    padding: 4px 0; user-select: none;
  }}
  details summary:hover {{ text-decoration: underline; }}
  .q-detail {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 10px; }}
  @media (max-width: 700px) {{ .q-detail {{ grid-template-columns: 1fr; }} }}
  .detail-section {{ background: var(--surface2); border-radius: 8px; padding: 12px; }}
  .detail-label {{ font-size: 11px; font-weight: 700; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: .05em; }}
  .response-block {{ font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; color: var(--text); }}
  .error-block {{ font-size: 12px; color: #D4537E; white-space: pre-wrap; }}
  .criterion {{ padding: 5px 8px; margin-bottom: 4px; border-radius: 4px; font-size: 12px; background: var(--bg); }}
</style>
</head>
<body>

<div class="header">
  <h1>LLM Agent Orchestration Benchmark</h1>
  <div class="header-meta">
    <span>モデル: <b>{escape(meta.get('model','─'))}</b></span>
    <span>実行日時: {escape(meta.get('run_at','─')[:19].replace('T',' '))}</span>
    <span>v{escape(meta.get('benchmark_version','─'))}</span>
  </div>
</div>

<div class="summary">
  <div class="stat-card">
    <div class="stat-value" style="color:#1D9E75">{pct:.1f}<span style="font-size:18px">%</span></div>
    <div class="stat-label">総合スコア</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{total_score}<span style="font-size:18px"> / {max_score}</span></div>
    <div class="stat-label">合計点</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{overall_avg:.2f}<span style="font-size:18px"> / 5</span></div>
    <div class="stat-label">平均スコア</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{scored_count}<span style="font-size:18px"> / {total_q}</span></div>
    <div class="stat-label">採点済み問数</div>
  </div>
</div>

<div class="charts">
  <div class="chart-card">
    <div class="chart-title">ドメイン別スコア（レーダー）</div>
    <div class="chart-wrap"><canvas id="radarChart"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">ドメイン別平均スコア（バー）</div>
    <div class="chart-wrap"><canvas id="barChart"></canvas></div>
  </div>
</div>

<div class="domains">
  {domain_cards_html}
</div>

<script>
const radarCtx = document.getElementById('radarChart').getContext('2d');
new Chart(radarCtx, {{
  type: 'radar',
  data: {{
    labels: {radar_labels},
    datasets: [{{
      label: 'スコア',
      data: {radar_data},
      backgroundColor: 'rgba(55,138,221,0.15)',
      borderColor: '#378ADD',
      pointBackgroundColor: {radar_colors},
      pointRadius: 5,
      borderWidth: 2,
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{
      r: {{
        min: 0, max: 5, ticks: {{ stepSize: 1, color: '#8892a4', backdropColor: 'transparent' }},
        grid: {{ color: '#2e3347' }},
        angleLines: {{ color: '#2e3347' }},
        pointLabels: {{ color: '#e2e8f0', font: {{ size: 11 }} }},
      }}
    }},
    plugins: {{ legend: {{ display: false }} }},
  }}
}});

const barCtx = document.getElementById('barChart').getContext('2d');
new Chart(barCtx, {{
  type: 'bar',
  data: {{
    labels: {bar_labels},
    datasets: [{{
      label: '平均スコア',
      data: {bar_data},
      backgroundColor: {bar_colors},
      borderRadius: 6,
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{
      y: {{ min: 0, max: 5, ticks: {{ color: '#8892a4' }}, grid: {{ color: '#2e3347' }} }},
      x: {{ ticks: {{ color: '#8892a4', font: {{ size: 10 }} }}, grid: {{ display: false }} }},
    }},
    plugins: {{ legend: {{ display: false }} }},
  }}
}});
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="ベンチマーク結果を HTML レポートとして出力する")
    parser.add_argument("result_file", help="結果 JSON ファイル")
    parser.add_argument("--output", "-o", help="出力先 HTML ファイル（省略時は同ディレクトリに自動生成）")
    args = parser.parse_args()

    data = load(args.result_file)

    out = args.output or str(Path(args.result_file).with_suffix(".html"))
    html = generate_html(data)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[生成完了] {out}")


if __name__ == "__main__":
    main()
