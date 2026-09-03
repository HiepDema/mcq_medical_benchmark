#!/usr/bin/env python3
"""Chấm model đóng qua OpenRouter (API tương thích OpenAI).

  # 1. đo thử 200 câu, script tự báo chi phí thật rồi ngoại suy cho cả lô
  python eval_openrouter.py --model x-ai/grok-4.3 --dataset mixed --limit 200

  # 2. chạy đủ
  python eval_openrouter.py --model x-ai/grok-4.3 --dataset mixed

Cần OPENROUTER_API_KEY trong biến môi trường.

Đầu ra ghi ra ĐÚNG định dạng của eval_qwen3vl.py nên analyze_results.py,
compare_benchmarks.py và make_figures.py dùng lại được không cần sửa gì.

Ba thứ script này bắt buộc làm, để so được với 4 model mở đã chấm:

  * ÉP ĐỊNH DẠNG bằng json_schema. Các model mở chạy dưới grammar-constrained
    decoding của vLLM; không ép thì model đóng được tự chọn cách trả lời và
    parse_answer phải đoán -> so sánh khập khiễng.
  * temperature = 0 và seed cố định. Grok nhận cả hai (Claude Opus 5 thì không).
  * TẮT reasoning. Bốn model mở chạy enable_thinking=False. Để reasoning bật thì
    vừa đắt gấp 6-8 lần vừa không cùng điều kiện. Script ghi lại số token
    reasoning thực tế để kiểm chứng là đã tắt được thật.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from eval_qwen3vl import (PROMPT, PROMPT_MIXED, PROMPT_SINGLE, load_items,  # noqa: E402
                          load_subsets, parse_answer, report, score)

# ten -> (endpoint, bien moi truong chua khoa, cach tat reasoning)
# Moi nha cung cap tat reasoning mot kieu khac nhau:
#   OpenRouter chuan hoa thanh object "reasoning"
#   Groq dung "reasoning_effort": "none" (xac nhan tu console.groq.com/docs/reasoning)
PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY",
                   {"reasoning": {"enabled": False, "exclude": True}}),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY",
             {"reasoning_effort": "none"}),
    "xai": ("https://api.x.ai/v1/chat/completions", "XAI_API_KEY", {}),
}
P = ROOT / "processed_data_v2"

# tag -> (file dữ liệu, file provenance, prompt, có phải bộ 1 đáp án không)
DATASETS = {
    "multi": ("final_benchmark_9368.json", "final_benchmark_9368_provenance.json", PROMPT, False),
    "mixed": ("final_benchmark_mixed.json", "final_benchmark_mixed_provenance.json", PROMPT_MIXED, False),
    "single": ("final_benchmark_9368_single.json", "final_benchmark_9368_single_provenance.json", PROMPT_SINGLE, True),
    "mixedsingle": ("final_benchmark_mixed_single.json", "final_benchmark_mixed_single_provenance.json", PROMPT_SINGLE, True),
}


def _from_dotenv(name: str) -> str | None:
    """Đọc khoá từ .env cạnh script. Để khoá không phải đi qua dòng lệnh hay log."""
    f = ROOT / ".env"
    if not f.exists():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{name}=") and not line.startswith("#"):
            return line.split("=", 1)[1].strip().strip("'\"")
    return None


def schema_for(letters: list[str], single: bool) -> dict:
    """Ép đầu ra thành {"answers": ["A", ...]} với chữ cái chỉ lấy trong letters."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "mcq_answer", "strict": True,
            "schema": {
                "type": "object", "additionalProperties": False,
                "required": ["answers"],
                "properties": {"answers": {
                    "type": "array", "minItems": 1,
                    "maxItems": 1 if single else len(letters),
                    "items": {"type": "string", "enum": letters}}},
            },
        },
    }


class Runner:
    def __init__(self, model: str, key: str, max_tokens: int, retries: int, reasoning_off: bool,
                 api: str, off_params: dict, reasoning_on: str | None = None):
        self.model, self.key, self.api, self.off_params = model, key, api, off_params
        self.max_tokens, self.retries = max_tokens, retries
        self.reasoning_off, self.reasoning_on = reasoning_off, reasoning_on
        self.lock = threading.Lock()
        self.usage = {"prompt": 0, "completion": 0, "reasoning": 0}
        self.errors: list[str] = []

    def one(self, it: dict, tpl: str, single: bool) -> dict:
        opts = "\n".join(f"{le}. {it['options'][le]}" for le in it["letters"])
        body = {
            "model": self.model,
            "messages": [{"role": "user",
                          "content": tpl.format(question=it["question"], options=opts)}],
            "max_tokens": self.max_tokens,
            "temperature": 0,
            "seed": 20260815,
            "response_format": schema_for(it["letters"], single),
        }
        if self.reasoning_on:
            body["reasoning"] = {"effort": self.reasoning_on}
        elif self.reasoning_off:
            body.update(self.off_params)

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.api, data=data, headers={
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            # BAT BUOC: Cloudflare truoc api.groq.com chan thang User-Agent mac dinh
            # cua urllib ("Python-urllib/3.x") bang loi 403 code 1010. Kiem chung
            # bang curl: UA cua curl -> 200, UA gia lap urllib -> 403.
            "User-Agent": "mcq-benchmark/1.0",
            "HTTP-Referer": "https://github.com/HiepDema/mcq_medical_benchmark",
            "X-Title": "MCQ medical benchmark",
        })

        last = ""
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.loads(r.read().decode("utf-8"))
                if "error" in d:                      # OpenRouter trả lỗi trong body, HTTP vẫn 200
                    last = str(d["error"])[:200]
                else:
                    u = d.get("usage") or {}
                    det = u.get("completion_tokens_details") or {}
                    with self.lock:
                        self.usage["prompt"] += u.get("prompt_tokens", 0)
                        self.usage["completion"] += u.get("completion_tokens", 0)
                        self.usage["reasoning"] += det.get("reasoning_tokens", 0)
                    txt = (d["choices"][0]["message"].get("content") or "").strip()
                    return {"index": it["index"], "raw": txt}
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
                if e.code in (400, 401, 402, 404):    # lỗi không đáng thử lại
                    break
            except Exception as e:                    # noqa: BLE001 — mạng, timeout
                last = f"{type(e).__name__}: {e}"
            time.sleep(min(2 ** attempt, 30))
        with self.lock:
            self.errors.append(f"index {it['index']}: {last}")
        return {"index": it["index"], "raw": ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="vd qwen/qwen3-32b")
    ap.add_argument("--provider", default="openrouter", choices=list(PROVIDERS))
    ap.add_argument("--dataset", required=True, choices=list(DATASETS))
    ap.add_argument("--tag", help="hậu tố tên file kết quả (mặc định suy từ --model)")
    ap.add_argument("--limit", type=int, default=0, help="chỉ chạy N câu đầu (đo thử)")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--keep-reasoning", action="store_true",
                    help="KHÔNG gửi tham số tắt reasoning (dùng mặc định của nhà cung cấp)")
    ap.add_argument("--reasoning-effort", choices=["low", "medium", "high"],
                    help="BẬT reasoning tường minh. Bỏ tham số đi là KHÔNG đủ — đo thật "
                         "cho thấy mặc định của OpenRouter với gemini-2.5-flash là TẮT. "
                         "Kết quả khác điều kiện với các model chấm reasoning tắt.")
    args = ap.parse_args()

    api, env_name, off_params = PROVIDERS[args.provider]
    key = os.environ.get(env_name) or _from_dotenv(env_name)
    if not key:
        print(f"Chưa có {env_name} (provider {args.provider}).")
        print("Đặt biến môi trường, hoặc thêm vào file .env cạnh script:")
        print(f"  {env_name}=...")
        print("(.env đã nằm trong .gitignore)")
        return 1

    fdata, fprov, tpl, single = DATASETS[args.dataset]
    items = load_items(P / fdata)
    subsets = load_subsets(P / fprov, len(items))
    if args.limit:
        items, subsets = items[: args.limit], subsets[: args.limit]

    tag = args.tag or args.model.split("/")[-1].replace(".", "")
    out_path = ROOT / "results_v2" / f"eval_{args.dataset}_{tag}.json"
    partial = ROOT / "results_v2" / f".partial_{args.dataset}_{tag}.jsonl"
    partial.parent.mkdir(exist_ok=True)

    # Chạy lại được: bỏ qua câu đã có trong file tạm.
    done: dict[int, str] = {}
    if partial.exists():
        for line in partial.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["index"]] = r["raw"]
        print(f"[resume] đã có {len(done)} câu trong {partial.name}")
    todo = [it for it in items if it["index"] not in done]

    print(f"[chạy] {args.provider}:{args.model} | {args.dataset} | {len(todo)}/{len(items)} câu"
          f" | reasoning {('BẬT ' + args.reasoning_effort) if args.reasoning_effort else ('mặc định' if args.keep_reasoning else 'tắt')}")
    runner = Runner(args.model, key, args.max_tokens, args.retries,
                    not (args.keep_reasoning or args.reasoning_effort), api, off_params,
                    reasoning_on=args.reasoning_effort)
    t0 = time.time()
    if todo:
        with partial.open("a", encoding="utf-8", newline="\n") as fh, \
                ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            for k, r in enumerate(ex.map(lambda it: runner.one(it, tpl, single), todo), 1):
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                done[r["index"]] = r["raw"]
                if k % 250 == 0:
                    fh.flush()
                    print(f"  {k}/{len(todo)}  ({time.time() - t0:.0f}s)", flush=True)
    dt = time.time() - t0

    preds, raws = [], []
    for it in items:
        raw = done.get(it["index"], "")
        got = parse_answer(raw, it["letters"])
        if single and len(got) > 1:
            got = {next(le for le in it["letters"] if le in got)}
        preds.append(got)
        raws.append(raw)

    m, per_item = score(items, preds)
    for d, s, raw in zip(per_item, subsets, raws):
        d["subset"], d["raw"] = s, raw[:300]
    out_path.write_text(json.dumps(
        {"model": f"{args.model} [{args.dataset}]", "provider": args.provider, "data": f"processed_data_v2/{fdata}",
         "metrics": m, "usage": runner.usage, "per_item": per_item},
        ensure_ascii=False), encoding="utf-8", newline="\n")

    print(f"\nKẾT QUẢ — {args.model} trên {args.dataset}:")
    report("tổng thể", m)
    empty = sum(1 for r in raws if not r)
    print(f"  câu không lấy được trả lời : {empty}")
    if runner.errors:
        print(f"  lỗi ({len(runner.errors)}), 3 cái đầu:")
        for e in runner.errors[:3]:
            print(f"    {e}")

    u = runner.usage
    n_done = max(len(todo), 1)
    print(f"\n  token thực tế: vào {u['prompt']:,} · ra {u['completion']:,}"
          f" · reasoning {u['reasoning']:,}".replace(",", "."))
    if args.reasoning_effort and not u["reasoning"]:
        print(f"  ⚠ đã yêu cầu reasoning={args.reasoning_effort} nhưng đo được 0 token — "
              f"nhà cung cấp KHÔNG bật. Kết quả không khác gì bản reasoning tắt.")
    if u["reasoning"]:
        print(f"  ⚠ reasoning VẪN CHẠY ({u['reasoning'] / n_done:.0f} token/câu) — "
              f"chi phí và điều kiện so sánh đều lệch. Kiểm tra lại tham số reasoning.")
    print(f"  tốc độ: {len(todo) / max(dt, 1e-9):.1f} câu/s ({dt:.0f}s)")
    if args.limit:
        full = len(load_items(P / fdata))
        k = full / n_done
        print(f"\n  Ngoại suy cho đủ {full} câu: vào ~{u['prompt'] * k / 1e6:.2f}M token,"
              f" ra ~{u['completion'] * k / 1e6:.2f}M token")
        print(f"  Nhân với giá của {args.model} trên openrouter.ai/models để ra chi phí.")
    print(f"\n-> {out_path.relative_to(ROOT)}")
    if not runner.errors and not empty:
        partial.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
