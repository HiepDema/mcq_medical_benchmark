#!/usr/bin/env python3
"""Chấm bộ đề ĐIỀN TỪ bằng model mở chạy cục bộ qua vLLM.

Dùng lại nguyên phần chấm điểm của `cloze_eval.py` (EM / F1 / EM~ / trúng nhiễu)
nên số của lượt GPU và lượt API so thẳng được với nhau.

Khác với chấm MCQ, ở đây đầu ra là VĂN BẢN TỰ DO chứ không phải chữ cái, nên
ràng buộc cấu trúc chỉ ép *hình dạng* JSON (mỗi ô một chuỗi), không ép nội dung.
Vẫn cần ép, vì không có nó thì model hay trả lời kèm giải thích dài dòng và
phần chấm phải đoán đâu là đáp án.

Gợi ý model theo VRAM
---------------------
    A10 24GB   Qwen/Qwen3-4B                (an toàn)
               Qwen/Qwen3-8B                (--gpu-mem 0.92 --max-model-len 1536)
               google/gemma-3-4b-it
    A100 40GB  Qwen/Qwen3-14B
               Qwen/Qwen3-32B-AWQ
    A100 80GB  Qwen/Qwen3-32B-FP8           (cùng model đã dùng dựng bộ MCQ)

Lưu ý về tính công bằng: Qwen3-32B từng chạy trong pipeline dựng bộ MCQ nhiều
đáp án, nhưng bộ điền từ này do `cloze_build.py` dựng THUẦN LUẬT, không có LLM
nào tham gia. Nên chấm Qwen3-32B trên bộ điền từ là hợp lệ.

Chạy trên máy GPU:
    python v2/cloze_vllm.py --model Qwen/Qwen3-4B --dataset multihop
    python v2/cloze_vllm.py --model Qwen/Qwen3-4B --dataset single --limit 2000
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Nạp cloze_eval.py để dùng chung hàm chấm — tránh hai bản logic lệch nhau.
_spec = importlib.util.spec_from_file_location("cloze_eval", ROOT / "v2" / "cloze_eval.py")
CE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CE)

PROMPT = """Điền nội dung thích hợp vào {n} chỗ trống dưới đây.

{passage}

Trả lời ngắn gọn, mỗi chỗ trống một cụm từ. Không giải thích."""


def make_sampling(schema: dict, max_tokens: int):
    """SamplingParams có ép JSON Schema.

    vLLM đổi API giữa các bản: GuidedDecodingParams (cũ, gỡ ở v0.12.0) ->
    StructuredOutputsParams. Thử lần lượt, không hỗ trợ thì ném lỗi chứ KHÔNG
    hạ cấp im lặng — chạy không ràng buộc sẽ cho số không so được với lượt khác.
    """
    from vllm import SamplingParams
    try:
        from vllm.sampling_params import StructuredOutputsParams
        return SamplingParams(temperature=0.0, max_tokens=max_tokens,
                              structured_outputs=StructuredOutputsParams(json=schema)), \
            "structured_outputs"
    except ImportError:
        pass
    try:
        from vllm.sampling_params import GuidedDecodingParams
        return SamplingParams(temperature=0.0, max_tokens=max_tokens,
                              guided_decoding=GuidedDecodingParams(json=schema)), \
            "guided_decoding"
    except ImportError:
        pass
    raise SystemExit(
        "Bản vLLM này không có StructuredOutputsParams lẫn GuidedDecodingParams.\n"
        "Nâng cấp vLLM: pip install -U vllm")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="vd Qwen/Qwen3-4B")
    ap.add_argument("--dataset", required=True, choices=list(CE.DATASETS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-model-len", type=int, default=2048)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--gpu-mem", type=float, default=0.90)
    ap.add_argument("--tp", type=int, default=1, help="tensor parallel (số GPU)")
    ap.add_argument("--enforce-eager", action="store_true",
                    help="bỏ CUDA graph, tiết kiệm 1-3 GB VRAM")
    ap.add_argument("--tag")
    args = ap.parse_args()

    f = ROOT / CE.DATASETS[args.dataset]
    if not f.exists():
        sys.exit(f"Chưa có {f}. Chạy `python v2/cloze_build.py` trước.")
    items = json.loads(f.read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    tag = args.tag or args.model.split("/")[-1].replace(".", "").lower()
    print(f"[cloze] {args.model} | {args.dataset} | {len(items):,} câu", flush=True)

    from vllm import LLM

    kwargs = dict(model=args.model, max_model_len=args.max_model_len,
                  gpu_memory_utilization=args.gpu_mem, tensor_parallel_size=args.tp,
                  trust_remote_code=True)
    if args.enforce_eager:
        kwargs["enforce_eager"] = True
    print(f"[cloze] nạp model: {kwargs}", flush=True)
    llm = LLM(**kwargs)

    convs, sps, api = [], [], None
    for it in items:
        convs.append([{"role": "user",
                       "content": PROMPT.format(n=it["nBlanks"], passage=it["passage"])}])
        sp, api = make_sampling(CE.schema_for(it["nBlanks"]), args.max_tokens)
        sps.append(sp)
    print(f"[cloze] ràng buộc đầu ra: {api}", flush=True)

    # Qwen3 mặc định bật chế độ suy nghĩ và sẽ ăn hết ngân sách token vào
    # <think>...</think>. Bản vLLM cũ không nhận tham số này thì bỏ qua.
    t0 = time.time()
    try:
        outs = llm.chat(convs, sps, chat_template_kwargs={"enable_thinking": False})
    except TypeError:
        print("[cloze] vLLM không nhận chat_template_kwargs — bỏ qua tắt thinking", flush=True)
        outs = llm.chat(convs, sps)
    dt = time.time() - t0

    rows, bad = [], 0
    for it, o in zip(items, outs):
        txt = o.outputs[0].text if o.outputs else ""
        try:
            pred = json.loads(txt)
            if not isinstance(pred, dict):
                raise ValueError
        except Exception:                            # noqa: BLE001
            pred, bad = None, bad + 1
        g = CE.grade(it, pred)
        g["id"], g["index"] = it["id"], it["index"]
        if pred is None:
            g["raw"] = txt[:200]
        rows.append(g)

    CE.report(rows, args.dataset)
    if bad:
        print(f"\n  ⚠ {bad:,} câu không parse được JSON — đã loại khỏi mọi tỉ lệ ở trên.")
    print(f"\n  {len(items)/max(dt,1e-9):.1f} câu/s ({dt:.0f}s)")

    out = ROOT / "results_v2" / f"cloze_{args.dataset}_{tag}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "dataset": args.dataset,
                               "backend": "vllm", "per_item": rows},
                              ensure_ascii=False), encoding="utf-8")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
