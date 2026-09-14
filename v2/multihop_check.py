#!/usr/bin/env python3
"""Bước 3: thẩm định nghiêm ngặt các chuỗi multi-hop mà LLM đã viết lại.

Bộ kiểm ở `multihop_rewrite.py` chỉ bắt được lỗi thô. Đọc tay 10 mẫu đầu cho
thấy hai lỗi NGHIÊM TRỌNG lọt lưới, và cả hai đều làm câu hỏi sai về y khoa
chứ không chỉ xấu về văn phong:

  1. ĐẢO PHỦ ĐỊNH. Nếu thân câu A là câu phủ định ("Biến chứng nào KHÔNG là
     biến chứng muộn...") thì đáp án của A là thứ KHÔNG thoả tính chất đó.
     Khi ghép, phần mô tả bắt buộc phải giữ lại phủ định. Nếu mất, câu ghép
     khẳng định điều ngược hẳn với đề gốc.

  2. VÒNG TRÒN. Có câu B mà đáp án gần như chép lại thân câu ("Khả năng ngưng
     tập của tiểu cầu là:" -> "Là khả năng các tiểu cầu gắn kết lẫn nhau...").
     Ghép xong thì đáp án nằm lộ ngay trong câu hỏi. Khớp chuỗi tuyệt đối
     không bắt được vì lệch vài từ, nên phải đo độ phủ token.

Script này chạy offline trên file pilot đã lưu, không gọi API.

Chạy:
    python v2/multihop_check.py --in data_v2/multihop_pilot.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Dấu hiệu thân câu mang phủ định / loại trừ.
NEG = re.compile(
    r"\bkhông\b|\bngoại\s+trừ\b|\btrừ\b|\bsai\b|\bchọn\s+sai\b|\bloại\s+trừ\b|"
    r"\bkhông\s+phải\b|\bkhông\s+thuộc\b|\bkhông\s+bao\s+gồm\b",
    re.IGNORECASE,
)

STOP = set(
    "là của và ở với cho từ trong khi đến một các những theo được có không nào bị sau "
    "trước trên dưới ra vào này đó đâu gì thì mà nên hay hoặc về do bởi tại vì cũng "
    "sẽ đã đang rất hơn nhất sự việc khả năng".split()
)


def norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t or "")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().lower()


def content_tokens(t: str) -> set[str]:
    return {w for w in norm(t).split() if w not in STOP and len(w) > 1}


def check(r: dict) -> list[str]:
    """Trả về danh sách vi phạm. Rỗng = qua được mọi kiểm tra tự động."""
    bad: list[str] = []
    q = r.get("composed") or ""
    if not r.get("llmOk") or not q.strip():
        return ["llm_tu_choi"]
    nq = norm(q)

    # --- kiểm thô (giữ lại từ bước 2) ---
    if r["bridge"] in nq:
        bad.append("lo_cau_noi")
    if not q.strip().endswith(("?", ":")):
        bad.append("khong_phai_cau_hoi")

    # --- 1. đảo phủ định ---
    if NEG.search(r["stemA"]) and not NEG.search(q):
        bad.append("mat_phu_dinh_A")
    if NEG.search(r["stemB"]) and not NEG.search(q):
        bad.append("mat_phu_dinh_B")

    # --- 2. vòng tròn: đáp án lộ trong câu hỏi ---
    ta, tq = content_tokens(r["answerB"]), content_tokens(q)
    if ta:
        cover = len(ta & tq) / len(ta)
        if cover >= 0.8:
            bad.append(f"dap_an_lo_trong_cau_hoi({cover:.0%})")

    # --- 3. câu ghép phải khác câu B, nếu không thì không có bước 1 ---
    if content_tokens(q) == content_tokens(r["stemB"]):
        bad.append("giong_het_cau_B")

    # --- 4. mô tả bước 1 phải thực sự được đưa vào ---
    #     ít nhất một token nội dung riêng của thân câu A phải xuất hiện.
    only_a = content_tokens(r["stemA"]) - content_tokens(r["stemB"])
    if only_a and not (only_a & tq):
        bad.append("khong_mang_thong_tin_A")

    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data_v2/multihop_pilot.json")
    ap.add_argument("--out", default="data_v2/multihop_checked.json")
    ap.add_argument("--samples", type=int, default=8)
    args = ap.parse_args()

    f = ROOT / args.inp
    if not f.exists():
        print(f"Chưa có {f}. Chạy `python v2/multihop_rewrite.py` trước.")
        return 1
    rows = json.loads(f.read_text(encoding="utf-8"))

    tally: collections.Counter = collections.Counter()
    for r in rows:
        r["strictViolations"] = check(r)
        r["strictOk"] = not r["strictViolations"]
        for v in r["strictViolations"]:
            tally[re.sub(r"\(.*\)", "", v)] += 1

    n = len(rows)
    ok = sum(1 for r in rows if r["strictOk"])
    loose = sum(1 for r in rows if r.get("accepted"))
    print(f"{'='*70}\nTHẨM ĐỊNH NGHIÊM NGẶT ({n} chuỗi)\n{'='*70}")
    print(f"  bộ kiểm lỏng ở bước 2 cho qua : {loose:4d}  ({loose/n*100:5.1f}%)")
    print(f"  bộ kiểm nghiêm ngặt cho qua   : {ok:4d}  ({ok/n*100:5.1f}%)")
    print(f"  -> bộ kiểm lỏng đã BỎ SÓT     : {loose-ok:4d} chuỗi hỏng\n")
    print("  Lý do loại:")
    for k, v in tally.most_common():
        print(f"    {k:34s} {v:4d}  ({v/n*100:5.1f}%)")

    out = ROOT / args.out
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out}")

    good = [r for r in rows if r["strictOk"]]
    print(f"\n{'='*70}\n{min(args.samples, len(good))} chuỗi QUA ĐƯỢC (vẫn cần người đọc)\n{'='*70}")
    for i, r in enumerate(good[: args.samples], 1):
        print(f"\n[{i}] {r['composed']}")
        print(f"    đáp án: {r['answerB']}")
        print(f"    (bước 1: {r['answerA']})")

    killed = [r for r in rows if r.get("accepted") and not r["strictOk"]]
    if killed:
        print(f"\n{'='*70}\n{min(5,len(killed))} chuỗi bộ kiểm lỏng cho qua nhưng THỰC RA HỎNG\n{'='*70}")
        for i, r in enumerate(killed[:5], 1):
            print(f"\n[{i}] {r['composed']}")
            print(f"    đáp án: {r['answerB']}")
            print(f"    vi phạm: {r['strictViolations']}")
            print(f"    A gốc: {r['stemA']} -> {r['answerA']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
