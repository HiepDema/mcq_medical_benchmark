#!/usr/bin/env python3
"""Pipeline v2 — dựng benchmark MCQ nhiều đáp án từ NHIỀU file MCQ 1 đáp án.

Quy trình (2 lần ghé GPU, phần GPU chạy thủ công):

  1. python v2/run.py ingest                  # nạp + khử trùng toàn bộ file nguồn
  2. python v2/run.py route                   # phân 3 họ + lọc cơ học
  3. python v2/run.py jobs [--limit N]        # -> llm_jobs/r1_*.jsonl
     --- trên máy H100 ---
     python gpu/vllm_batch.py llm_jobs/r1_*.jsonl --model Qwen/Qwen3-32B-FP8
     --- copy *.out.jsonl về llm_jobs/ ---
  4. python v2/run.py apply                   # dựng 4 file + -> llm_jobs/r2_audit.jsonl
     --- trên máy H100 ---
     python gpu/vllm_batch.py llm_jobs/r2_audit.jsonl --model Qwen/Qwen3-32B-FP8
     --- copy về ---
  5. python v2/run.py build                   # -> final_benchmark.json (+ bản 1 đáp án)
  6. python v2/run.py mix                     # -> final_benchmark_mixed.json (hỗn hợp 1 + nhiều đáp án)

Chạy thử toàn bộ mà chưa có GPU:
  python v2/run.py ingest route jobs
  python v2/run.py apply --no-llm
  python v2/run.py build --skip-audit

Thư mục (đổi bằng biến môi trường):
  MCQ2_SRC_DIR=source_data   MCQ2_WORK_DIR=data_v2
  MCQ2_JOBS_DIR=llm_jobs     MCQ2_OUT_DIR=processed_data_v2

Không tầng nào ghi đè file nguồn.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lib2 as L                      # noqa: E402
from s1_ingest import s1_ingest       # noqa: E402
from s2_route import s2_route         # noqa: E402
from s3_jobs import s3_jobs           # noqa: E402
from s4_apply import s4_apply         # noqa: E402
from s5_build import s5_build         # noqa: E402
from s6_mix import s6_mix             # noqa: E402

STEPS = ("ingest", "route", "jobs", "apply", "build", "mix")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", nargs="*", help=f"một hoặc nhiều bước: {', '.join(STEPS)}")
    ap.add_argument("--limit", type=int, default=0,
                    help="jobs: số câu tối đa gửi LLM cho MỖI họ (0 = tất cả)")
    ap.add_argument("--no-llm", action="store_true",
                    help="apply: bỏ qua kết quả LLM, chỉ dùng luật cơ học")
    ap.add_argument("--per-subset", type=int, default=0,
                    help="build: giới hạn số câu mỗi nhóm (0 = lấy hết, không cân bằng)")
    ap.add_argument("--seed", type=int, default=20260815, help="build: seed trộn")
    ap.add_argument("--with-xoa-meta", action="store_true",
                    help="build: đưa cả nhóm file2_xoa_meta (mọi phương án đều đúng) vào")
    ap.add_argument("--skip-audit", action="store_true",
                    help="build: bỏ qua thẩm định LLM vòng 2")
    ap.add_argument("--out-name", default="final_benchmark",
                    help="build: tên file đầu ra (mặc định final_benchmark)")
    ap.add_argument("--n-single", type=int, default=2000,
                    help="mix: số câu MỘT đáp án thêm vào (mặc định 2000)")
    ap.add_argument("--shuffle-options", action="store_true",
                    help="mix: trộn vị trí phương án của các câu một đáp án thêm vào "
                         "(mặc định giữ nguyên văn đề gốc)")
    args = ap.parse_args()

    if not args.steps:
        print(__doc__)
        return 1
    unknown = [s for s in args.steps if s not in STEPS]
    if unknown:
        print(f"Bước không tồn tại: {unknown}. Có: {', '.join(STEPS)}")
        return 1

    print(f"nguồn : {L.SRC_DIR if L.SRC_DIR.is_dir() else L.ROOT}"
          f"  ({len(L.source_files())} file)")
    print(f"trung gian: {L.WORK_DIR}\nviệc LLM  : {L.JOBS_DIR}\nthành phẩm: {L.OUT_DIR}\n")

    for s in args.steps:
        print("=" * 68)
        print(f"BƯỚC {s.upper()}")
        print("=" * 68)
        if s == "ingest":
            s1_ingest()
        elif s == "route":
            s2_route()
        elif s == "jobs":
            s3_jobs(limit=args.limit)
        elif s == "apply":
            s4_apply(require_llm=not args.no_llm)
        elif s == "build":
            s5_build(per_subset=args.per_subset, seed=args.seed,
                     with_xoa_meta=args.with_xoa_meta, skip_audit=args.skip_audit,
                     out_name=args.out_name)
        elif s == "mix":
            s6_mix(n=args.n_single, seed=args.seed,
                   shuffle_options=args.shuffle_options)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
