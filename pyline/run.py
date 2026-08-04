#!/usr/bin/env python3
"""Chạy pipeline MCQ (bản Python).

  python pyline/run.py all              # chạy tầng 01 -> 12
  python pyline/run.py 01 02 09         # chạy vài tầng
  python pyline/run.py 12 --assume-yes  # tầng 12 ở chế độ thử

Ghi ra thư mục data/. Đổi đích bằng biến môi trường MCQ_DATA_DIR (dùng để so
sánh với bản Node mà không ghi đè).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lib as L          # noqa: E402
from stages import STAGES  # noqa: E402

# Tầng 12 chạy sau khi có kết quả LLM nên không nằm trong "all".
ALL = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11"]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    assume_yes = "--assume-yes" in sys.argv

    if not args:
        print(__doc__)
        return 1
    wanted = ALL if args == ["all"] else args

    unknown = [s for s in wanted if s not in STAGES]
    if unknown:
        print(f"Tầng không tồn tại: {unknown}. Có: {', '.join(STAGES)}")
        return 1

    print(f"Đọc từ : {L.DATA_DIR}")
    print(f"Ghi vào: {L.OUT_DIR}\n")
    for s in wanted:
        print("=" * 64)
        print(f"TẦNG {s}")
        print("=" * 64)
        fn = STAGES[s]
        fn(assume_yes) if s == "12" else fn()
        print()
    print("Hoàn tất. raw_data.json không bị ghi đè ở bất kỳ tầng nào.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
