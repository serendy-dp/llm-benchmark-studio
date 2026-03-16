"""LLM Benchmark Studio - Web UI Backend"""
import json
import asyncio
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

import httpx
import threading
import queue as _queue
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="LLM Benchmark Studio")

BENCHMARKS_DIR = Path("benchmarks")
BENCHMARKS_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path("results")
SCORED_DIR = RESULTS_DIR / "scored"
UNSCORED_DIR = RESULTS_DIR / "unscored"
REPORTS_DIR = RESULTS_DIR / "reports"
RUNS_REPORTS_DIR = REPORTS_DIR / "runs"
COMPARE_REPORTS_DIR = REPORTS_DIR / "compare"
RESULTS_DIR.mkdir(exist_ok=True)
SCORED_DIR.mkdir(exist_ok=True)
UNSCORED_DIR.mkdir(exist_ok=True)
RUNS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
COMPARE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
PRESETS_DIR = Path("presets")
PRESETS_DIR.mkdir(exist_ok=True)
LM_STUDIO_BASE = "http://localhost:1234"
_mlx_cache: dict = {}


def find_result_path(filename: str) -> Optional[Path]:
    """Find a result file in scored/, unscored/, or legacy root."""
    for d in (SCORED_DIR, UNSCORED_DIR, RESULTS_DIR):
        p = d / filename
        if p.exists():
            return p
    return None


def _is_fully_scored(data: dict) -> bool:
    questions = [q for d in data.get("domains", []) for q in d["questions"]]
    return bool(questions) and all(q.get("score") is not None for q in questions)


def _maybe_promote(path: Path, data: dict) -> Path:
    """If all questions scored and file is in unscored/, move it to scored/."""
    if path.parent == UNSCORED_DIR and _is_fully_scored(data):
        dest = SCORED_DIR / path.name
        path.rename(dest)
        return dest
    return path


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Benchmarks ─────────────────────────────────────────────────

@app.get("/api/benchmarks")
async def list_benchmarks():
    result = []
    for f in sorted(BENCHMARKS_DIR.glob("*.json")):
        try:
            data = load_json(f)
            meta = data.get("benchmark_meta", {})
            result.append({
                "filename": f.name,
                "title": meta.get("title", f.stem),
                "version": meta.get("version", ""),
                "description": meta.get("description", ""),
                "total_questions": meta.get("total_questions", 0),
                "total_domains": meta.get("total_domains", 0),
            })
        except Exception:
            result.append({"filename": f.name, "title": f.stem,
                           "total_questions": 0, "total_domains": 0})
    return result


@app.get("/api/benchmark/{filename}")
async def get_benchmark(filename: str):
    if ".." in filename:
        raise HTTPException(400, "Invalid path")
    path = BENCHMARKS_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return load_json(path)


# ── Results ────────────────────────────────────────────────────

@app.get("/api/results")
async def list_results():
    result = []
    all_files = list(SCORED_DIR.glob("benchmark_*.json")) + \
                list(UNSCORED_DIR.glob("benchmark_*.json")) + \
                list(RESULTS_DIR.glob("benchmark_*.json"))  # legacy root
    files = sorted(all_files, key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        try:
            data = load_json(f)
            meta = data.get("meta", {})
            all_scores = [
                q["score"]
                for d in data.get("domains", [])
                for q in d["questions"]
                if q.get("score") is not None
            ]
            total_q = sum(len(d["questions"]) for d in data.get("domains", []))
            result.append({
                "filename": f.name,
                "model": meta.get("model", ""),
                "run_at": meta.get("run_at", "")[:19].replace("T", " "),
                "benchmark_title": meta.get("benchmark_title", ""),
                "benchmark_file": meta.get("benchmark_file", ""),
                "scored": len(all_scores),
                "total": total_q,
                "avg_score": round(sum(all_scores) / len(all_scores), 2) if all_scores else None,
            })
        except Exception:
            result.append({"filename": f.name, "model": "", "run_at": "",
                           "benchmark_title": "", "scored": 0, "total": 0, "avg_score": None})
    return result


@app.delete("/api/result/{filename}")
async def delete_result(filename: str):
    if ".." in filename:
        raise HTTPException(400, "Invalid path")
    path = find_result_path(filename)
    if not path:
        raise HTTPException(404, "Not found")
    path.unlink()
    # Remove HTML too if present
    html = RUNS_REPORTS_DIR / (path.stem + ".html")
    if html.exists():
        html.unlink()
    return {"ok": True}


@app.get("/api/result/{filename}")
async def get_result(filename: str):
    if ".." in filename:
        raise HTTPException(400, "Invalid path")
    path = find_result_path(filename)
    if not path:
        raise HTTPException(404, "Not found")
    return load_json(path)


class ScoreUpdate(BaseModel):
    question_id: str
    score: Optional[int] = None
    score_comment: Optional[str] = None


@app.post("/api/result/{filename}/score")
async def update_score(filename: str, update: ScoreUpdate):
    if ".." in filename:
        raise HTTPException(400, "Invalid path")
    path = find_result_path(filename)
    if not path:
        raise HTTPException(404, "Not found")
    data = load_json(path)
    for domain in data.get("domains", []):
        for q in domain["questions"]:
            if q["id"] == update.question_id:
                if "score" in update.model_fields_set:
                    q["score"] = update.score
                if "score_comment" in update.model_fields_set:
                    q["score_comment"] = update.score_comment
                save_json(path, data)
                _maybe_promote(path, data)
                return {"ok": True}
    raise HTTPException(404, "Question not found")


@app.get("/api/result/{filename}/report")
async def get_report(filename: str):
    if ".." in filename:
        raise HTTPException(400, "Invalid path")
    path = find_result_path(filename)
    if not path:
        raise HTTPException(404, "Not found")
    # 保存済み HTML があればそれを返す
    html_path = RUNS_REPORTS_DIR / (path.stem + ".html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    # なければ動的生成
    data = load_json(path)
    from report_generator import generate_html
    return HTMLResponse(content=generate_html(data))


# ── Compare Reports ────────────────────────────────────────────

_ROOT_DOCS = ["README.md", "TUTORIAL.md"]

@app.get("/api/reports")
async def list_reports():
    files = []
    for f in sorted(COMPARE_REPORTS_DIR.glob("*.md"), reverse=True):
        files.append({
            "filename": f.name,
            "type": "compare",
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
        })
    for name in _ROOT_DOCS:
        p = Path(name)
        if p.exists():
            files.append({
                "filename": name,
                "type": "doc",
                "size": p.stat().st_size,
                "modified": p.stat().st_mtime,
            })
    return files


@app.get("/api/reports/{filename}")
async def get_compare_report(filename: str):
    if ".." in filename:
        raise HTTPException(400, "Invalid path")
    path = COMPARE_REPORTS_DIR / filename
    if not path.exists():
        if filename in _ROOT_DOCS:
            path = Path(filename)
        if not path.exists():
            raise HTTPException(404, "Not found")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=path.read_text(encoding="utf-8"))


# ── Presets ────────────────────────────────────────────────────

class PresetData(BaseModel):
    name: str
    model: str = ""
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    interval: float = 3.0
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repeat_penalty: Optional[float] = None
    min_p: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[str] = None  # comma-separated


@app.get("/api/presets")
async def list_presets():
    result = []
    for f in sorted(PRESETS_DIR.glob("*.json")):
        try:
            data = load_json(f)
            result.append({"filename": f.name, **data})
        except Exception:
            pass
    return result


@app.post("/api/preset")
async def save_preset(preset: PresetData):
    safe = preset.name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    if not safe:
        raise HTTPException(400, "Invalid name")
    path = PRESETS_DIR / f"{safe}.json"
    save_json(path, preset.model_dump())
    return {"filename": path.name}


@app.delete("/api/preset/{filename}")
async def delete_preset(filename: str):
    if ".." in filename:
        raise HTTPException(400, "Invalid path")
    path = PRESETS_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    path.unlink()
    return {"ok": True}


# ── Models ─────────────────────────────────────────────────────

@app.get("/api/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{LM_STUDIO_BASE}/api/v1/models")
            resp.raise_for_status()
            models = [
                {
                    "key": m["key"],
                    "name": m.get("display_name", m["key"]),
                    "loaded": bool(m.get("loaded_instances")),
                }
                for m in resp.json().get("models", [])
                if m.get("type") == "llm"
            ]
            return {"models": models, "connected": True}
    except Exception as e:
        return {"models": [], "connected": False, "error": str(e)}


# ── MLX LM helpers ─────────────────────────────────────────────

def _mlx_stream_tokens(model, tokenizer, prompt: str, gen_kwargs: dict,
                        out_q: "_queue.Queue") -> None:
    """Thread target: streams tokens from mlx_lm.stream_generate into out_q."""
    try:
        from mlx_lm import stream_generate
        for result in stream_generate(model, tokenizer, prompt=prompt, **gen_kwargs):
            out_q.put(result.text)
    except Exception as ex:
        out_q.put(ex)
    finally:
        out_q.put(None)


# ── Run ────────────────────────────────────────────────────────

class RunConfig(BaseModel):
    benchmark_file: str
    model: str
    system_prompt: str = "あなたは優秀なAIエージェントです。指示に従い、構造的・論理的に回答してください。"
    temperature: float = 0.7
    max_tokens: int = 4096
    interval: float = 3.0
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repeat_penalty: Optional[float] = None
    min_p: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[list[str]] = None
    preset_name: Optional[str] = None
    question_ids: Optional[list[str]] = None
    output_prefix: Optional[str] = None
    append_to_file: Optional[str] = None  # 既存ファイルに追記/上書き
    backend: str = "lmstudio"  # "lmstudio" | "mlxlm"
    enable_thinking: bool = False


@app.post("/api/run")
async def run_benchmark(config: RunConfig):
    async def event_stream():
        try:
            bench_path = BENCHMARKS_DIR / config.benchmark_file
            if not bench_path.exists():
                yield f"data: {json.dumps({'type':'error','message':'Benchmark not found'})}\n\n"
                return

            benchmark = load_json(bench_path)
            questions_to_run = [
                (domain, q)
                for domain in benchmark["domains"]
                for q in domain["questions"]
                if config.question_ids is None or q["id"] in config.question_ids
            ]

            if not questions_to_run:
                yield f"data: {json.dumps({'type':'error','message':'No questions selected'})}\n\n"
                return

            total = len(questions_to_run)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = config.model.replace("/", "_").replace(":", "-").replace(" ", "_")
            prefix = f"{config.output_prefix}_" if config.output_prefix else ""

            # 既存ファイルへ追記するか新規作成か決定
            if config.append_to_file:
                out_path = find_result_path(config.append_to_file) or (UNSCORED_DIR / config.append_to_file)
            else:
                out_path = UNSCORED_DIR / f"benchmark_{prefix}{safe}_{ts}.json"

            meta = benchmark["benchmark_meta"]

            # 既存ファイルがあれば読み込んでベースにする
            if config.append_to_file and out_path.exists():
                results = load_json(out_path)
                domain_map: dict = {d["id"]: d for d in results.get("domains", [])}
            else:
                results = {
                    "meta": {
                        "benchmark_title": meta["title"],
                        "benchmark_version": meta.get("version", ""),
                        "benchmark_file": config.benchmark_file,
                        "model": config.model,
                        "base_url": LM_STUDIO_BASE,
                        "run_at": datetime.now().isoformat(),
                        "system_prompt": config.system_prompt,
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                        "top_p": config.top_p,
                        "top_k": config.top_k,
                        "frequency_penalty": config.frequency_penalty,
                        "presence_penalty": config.presence_penalty,
                        "repeat_penalty": config.repeat_penalty,
                        "min_p": config.min_p,
                        "seed": config.seed,
                        "stop": config.stop,
                        "preset_name": config.preset_name,
                        "backend": config.backend,
                    },
                    "domains": [],
                }
                domain_map: dict = {}

            yield f"data: {json.dumps({'type':'start','total':total,'output_file':out_path.name})}\n\n"

            yield f"data: {json.dumps({'type':'warmup'})}\n\n"
            mlx_model_obj = None
            mlx_tokenizer_obj = None
            if config.backend == "mlxlm":
                try:
                    from mlx_lm import load as _mlx_load
                    if config.model not in _mlx_cache:
                        _mlx_cache[config.model] = await asyncio.to_thread(_mlx_load, config.model)
                    mlx_model_obj, mlx_tokenizer_obj = _mlx_cache[config.model]
                except Exception as e:
                    yield f"data: {json.dumps({'type':'error','message':f'MLX LM load failed: {e}'})}\n\n"
                    return
            else:
                # ウォームアップ: モデルロード時間を計測から除外するため空リクエストを送る
                try:
                    warmup_payload = {"model": config.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1, "stream": False}
                    async with httpx.AsyncClient(timeout=60) as wc:
                        await wc.post(f"{LM_STUDIO_BASE}/v1/chat/completions", json=warmup_payload)
                except Exception:
                    pass

            for idx, (domain, q) in enumerate(questions_to_run, 1):
                yield f"data: {json.dumps({'type':'question_start','idx':idx,'total':total,'id':q['id'],'title':q['title'],'domain':domain['label'],'difficulty':q['difficulty']})}\n\n"

                full_response = ""
                error_msg = None
                start_time = time.time()

                if config.backend == "mlxlm":
                    messages = [
                        {"role": "system", "content": config.system_prompt},
                        {"role": "user", "content": q["prompt"]},
                    ]
                    try:
                        try:
                            prompt_str = mlx_tokenizer_obj.apply_chat_template(
                                messages, tokenize=False, add_generation_prompt=True,
                                enable_thinking=config.enable_thinking,
                            )
                        except TypeError:
                            prompt_str = mlx_tokenizer_obj.apply_chat_template(
                                messages, tokenize=False, add_generation_prompt=True,
                            )
                        gen_kwargs: dict = {"max_tokens": config.max_tokens, "temp": config.temperature}
                        if config.top_p is not None:          gen_kwargs["top_p"] = config.top_p
                        if config.repeat_penalty is not None: gen_kwargs["repetition_penalty"] = config.repeat_penalty
                        token_q: _queue.Queue = _queue.Queue()
                        t = threading.Thread(
                            target=_mlx_stream_tokens,
                            args=(mlx_model_obj, mlx_tokenizer_obj, prompt_str, gen_kwargs, token_q),
                            daemon=True,
                        )
                        t.start()
                        while True:
                            try:
                                item = token_q.get_nowait()
                            except _queue.Empty:
                                await asyncio.sleep(0.01)
                                continue
                            if item is None:
                                break
                            if isinstance(item, Exception):
                                raise item
                            full_response += item
                            yield f"data: {json.dumps({'type':'token','idx':idx,'content':item})}\n\n"
                        t.join()
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        error_msg = str(e)
                else:
                    payload = {
                        "model": config.model,
                        "messages": [
                            {"role": "system", "content": config.system_prompt},
                            {"role": "user", "content": q["prompt"]},
                        ],
                        "stream": True,
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                    }
                    if config.top_p is not None:            payload["top_p"] = config.top_p
                    if config.top_k is not None:            payload["top_k"] = config.top_k
                    if config.frequency_penalty is not None: payload["frequency_penalty"] = config.frequency_penalty
                    if config.presence_penalty is not None:  payload["presence_penalty"] = config.presence_penalty
                    if config.repeat_penalty is not None:    payload["repeat_penalty"] = config.repeat_penalty
                    if config.min_p is not None:             payload["min_p"] = config.min_p
                    if config.seed is not None:              payload["seed"] = config.seed
                    if config.stop:                          payload["stop"] = config.stop

                    try:
                        async with httpx.AsyncClient(timeout=600.0) as client:
                            async with client.stream(
                                "POST",
                                f"{LM_STUDIO_BASE}/v1/chat/completions",
                                json=payload,
                            ) as resp:
                                if resp.status_code != 200:
                                    error_msg = f"HTTP {resp.status_code}"
                                else:
                                    async for line in resp.aiter_lines():
                                        if not line.startswith("data:"):
                                            continue
                                        raw = line[5:].strip()
                                        if raw == "[DONE]":
                                            break
                                        try:
                                            chunk = json.loads(raw)
                                            content = (
                                                chunk.get("choices", [{}])[0]
                                                .get("delta", {})
                                                .get("content", "")
                                            )
                                            if content:
                                                full_response += content
                                                yield f"data: {json.dumps({'type':'token','idx':idx,'content':content})}\n\n"
                                        except Exception:
                                            pass
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        error_msg = str(e)

                elapsed = round(time.time() - start_time, 1)
                for marker in ["<|im_end|>", "<|endoftext|>", "</s>"]:
                    full_response = full_response.replace(marker, "")
                full_response = full_response.strip()

                d_id = domain["id"]
                if d_id not in domain_map:
                    domain_map[d_id] = {"id": d_id, "label": domain["label"], "questions": []}

                new_entry = {
                    "id": q["id"], "title": q["title"],
                    "difficulty": q["difficulty"], "tags": q.get("tags", []),
                    "status": "error" if error_msg else "success",
                    "response": full_response if not error_msg else None,
                    "elapsed_sec": elapsed, "usage": {},
                    "error": error_msg, "score": None, "score_comment": None,
                    "scoring_criteria": q.get("scoring", []),
                }
                # 既存エントリがあれば score / score_comment を引き継いだ上で上書き、なければ追加
                existing_qs = domain_map[d_id]["questions"]
                existing_idx = next((i for i, eq in enumerate(existing_qs) if eq["id"] == q["id"]), None)
                if existing_idx is not None:
                    new_entry["score"] = existing_qs[existing_idx].get("score")
                    new_entry["score_comment"] = existing_qs[existing_idx].get("score_comment")
                    existing_qs[existing_idx] = new_entry
                else:
                    existing_qs.append(new_entry)

                results["domains"] = list(domain_map.values())
                save_json(out_path, results)

                yield f"data: {json.dumps({'type':'question_done','idx':idx,'total':total,'id':q['id'],'elapsed':elapsed,'error':error_msg,'output_file':out_path.name})}\n\n"

                if idx < total and config.interval > 0:
                    await asyncio.sleep(config.interval)

            # HTML レポートを自動生成・保存
            report_file = None
            try:
                from report_generator import generate_html
                html_path = RUNS_REPORTS_DIR / (out_path.stem + ".html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(generate_html(load_json(out_path)))
                report_file = html_path.name
            except Exception:
                pass

            yield f"data: {json.dumps({'type':'done','output_file':out_path.name,'report_file':report_file})}\n\n"

        except asyncio.CancelledError:
            yield f"data: {json.dumps({'type':'error','message':'Run cancelled'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Static files ───────────────────────────────────────────────

@app.get("/")
async def index():
    p = Path("static/index.html")
    return HTMLResponse(p.read_text(encoding="utf-8") if p.exists() else "<h1>UI not found</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
