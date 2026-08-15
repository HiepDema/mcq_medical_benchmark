#!/usr/bin/env python3
"""Chạy một hoặc nhiều lô việc LLM bằng vLLM. CHẠY TRÊN MÁY CÓ GPU (H100).

  python gpu/vllm_batch.py llm_jobs/r1_negation.jsonl llm_jobs/r1_distract.jsonl \
         llm_jobs/r1_pool.jsonl --model Qwen/Qwen3-32B-FP8

Mỗi lô gồm 2 file do pipeline sinh ra:
  <tên>.jsonl         mỗi dòng {"id": ..., "prompt": ...}
  <tên>.schema.json   JSON Schema mà đầu ra bị ÉP phải khớp

Kết quả ghi ra <tên>.out.jsonl, mỗi dòng {"id", "ok", "data", "raw"}.

Ba điều bắt buộc, rút ra từ lần chạy hỏng trước:
  1. Không có structured outputs thì DỪNG, không âm thầm sinh tự do. Một lần
     "fallback" như vậy đã làm hỏng trọn một lượt benchmark mà nhìn log không thấy.
  2. Tắt chế độ thinking của Qwen3, nếu không <think> ăn hết ngân sách token.
  3. Ghi ra đĩa theo từng khối và bỏ qua id đã có -> đứt giữa chừng chạy lại được.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

THINK = re.compile(r"<think>.*?</think>\s*", re.S)

# Gợi ý model cho 1×H100 80GB (xem README của v2 để biết vì sao chọn):
DEFAULT_MODEL = "Qwen/Qwen3-32B-FP8"


def read_jobs(p: Path) -> list[dict]:
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def done_ids(p: Path) -> set[str]:
    if not p.exists():
        return set()
    ids = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                ids.add(json.loads(line)["id"])
            except Exception:                                    # noqa: BLE001
                pass
    return ids


def make_sampling(schema: dict, max_tokens: int):
    """SamplingParams có ép JSON Schema. Không hỗ trợ -> ném lỗi, KHÔNG hạ cấp."""
    from vllm import SamplingParams
    try:
        from vllm.sampling_params import StructuredOutputsParams
        return SamplingParams(temperature=0.0, max_tokens=max_tokens,
                              structured_outputs=StructuredOutputsParams(json=schema))
    except ImportError:
        pass
    try:
        from vllm.sampling_params import GuidedDecodingParams
        return SamplingParams(temperature=0.0, max_tokens=max_tokens,
                              guided_decoding=GuidedDecodingParams(json=schema))
    except ImportError:
        pass
    raise SystemExit(
        "vLLM này không có StructuredOutputsParams lẫn GuidedDecodingParams.\n"
        "Không chạy tiếp: sinh tự do sẽ cho ra dữ liệu rác mà vẫn parse được.\n"
        "Cài lại: pip install -U vllm")


def parse(text: str):
    t = THINK.sub("", text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)          # cắt phần thừa hai đầu nếu có
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+", help="các file .jsonl do v2/run.py sinh ra")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tp", type=int, default=1, help="tensor parallel (số GPU)")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-mem", type=float, default=0.90)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--chunk", type=int, default=1024, help="số việc ghi ra đĩa mỗi lần")
    ap.add_argument("--limit", type=int, default=0, help="chỉ chạy N việc đầu mỗi lô")
    ap.add_argument("--dry-run", action="store_true",
                    help="in thử 1 prompt của mỗi lô rồi thoát, không nạp model")
    args = ap.parse_args()

    batches = []
    for j in args.jobs:
        p = Path(j)
        if not p.name.endswith(".jsonl"):
            raise SystemExit(f"{p} không phải file .jsonl")
        stem = p.name[: -len(".jsonl")]
        sp = p.parent / f"{stem}.schema.json"
        if not p.exists() or not sp.exists():
            raise SystemExit(f"Thiếu {p} hoặc {sp}")
        rows = read_jobs(p)
        out_p = p.parent / f"{stem}.out.jsonl"
        skip = done_ids(out_p)
        todo = [r for r in rows if r["id"] not in skip]
        if args.limit:
            todo = todo[: args.limit]
        batches.append((p.name, todo, json.loads(sp.read_text(encoding="utf-8")), out_p,
                        len(rows), len(skip)))
        print(f"[lô] {p.name}: {len(rows)} việc, đã có {len(skip)}, cần chạy {len(todo)}")

    if args.dry_run:
        for name, todo, schema, _, _, _ in batches:
            print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
            print(json.dumps(schema, ensure_ascii=False))
            print("-" * 70)
            print(todo[0]["prompt"] if todo else "(không còn việc)")
        return 0

    if all(not t for _, t, _, _, _, _ in batches):
        print("Không còn việc nào cần chạy.")
        return 0

    from vllm import LLM
    print(f"\n[vllm] nạp {args.model} (tp={args.tp}, max_len={args.max_model_len})")
    llm = LLM(model=args.model, tensor_parallel_size=args.tp,
              max_model_len=args.max_model_len,
              gpu_memory_utilization=args.gpu_mem, trust_remote_code=True)

    # Qwen3 mặc định bật thinking; để nguyên là <think> ăn hết max_tokens.
    chat_kwargs = {"chat_template_kwargs": {"enable_thinking": False}}

    for name, todo, schema, out_p, n_all, n_done in batches:
        if not todo:
            continue
        sampling = make_sampling(schema, args.max_tokens)
        print(f"\n[chạy] {name}: {len(todo)} việc")
        t0, ok_total = time.time(), 0

        for s in range(0, len(todo), args.chunk):
            part = todo[s: s + args.chunk]
            convs = [[{"role": "user", "content": r["prompt"]}] for r in part]
            try:
                outs = llm.chat(convs, sampling, **chat_kwargs)
            except TypeError:
                print("  ⚠ vLLM này không nhận chat_template_kwargs — chạy không tắt "
                      "được thinking; đã tăng max_tokens và vẫn cắt <think> khi parse.")
                chat_kwargs = {}
                sampling = make_sampling(schema, max(args.max_tokens, 1024))
                outs = llm.chat(convs, sampling)

            lines = []
            for r, o in zip(part, outs):
                raw = o.outputs[0].text
                data = parse(raw)
                ok = isinstance(data, dict)
                ok_total += ok
                lines.append(json.dumps(
                    {"id": r["id"], "ok": ok, "data": data,
                     "raw": None if ok else raw[:400]}, ensure_ascii=False))
            with out_p.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(lines) + "\n")
            print(f"  {min(s + args.chunk, len(todo))}/{len(todo)}"
                  f"  ({time.time() - t0:.0f}s)", flush=True)

        dt = time.time() - t0
        print(f"[xong] {name}: {ok_total}/{len(todo)} parse được"
              f" | {len(todo) / max(dt, 1e-9):.1f} việc/s | -> {out_p.name}")

    print("\nCopy các file *.out.jsonl về máy local (thư mục llm_jobs/) rồi chạy tiếp "
          "v2/run.py apply hoặc build.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
