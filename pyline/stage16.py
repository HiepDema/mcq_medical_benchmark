"""Tầng 16 — gộp FILE 1 + FILE 2 + FILE 3 thành một bộ benchmark duy nhất.

Trộn ngẫu nhiên (seed cố định nên chạy lại luôn ra cùng thứ tự) để các câu
cùng nguồn không nằm liền khối — nếu không, model/người chấm dễ bắt bài theo
vị trí thay vì theo nội dung.

Giữ nguyên format raw_data.json. Thông tin nguồn gốc nằm ở file provenance
đi kèm, ghép cặp theo cùng chỉ số.
"""
from __future__ import annotations

import random
from collections import Counter

import lib as L

SOURCES = [
    ("final_01_ngoai_tru.json", "final_01_ngoai_tru_provenance.json", "file1_ngoai_tru"),
    ("final_02_multi.json", "final_02_multi_provenance.json", None),   # tách A/B theo trường batch
    ("final_03_multi.json", "final_03_multi_provenance.json", "file3_tach_dau_phay"),
]
SEED = 20260805


def _subset(prov: dict, default: str | None) -> str:
    if default:
        return default
    return {"A_xoa_meta": "file2_xoa_meta",
            "B_them_nhieu": "file2_them_nhieu"}.get(prov.get("batch", ""), "file2_khac")


def stage16_merge_benchmark():
    pairs = []
    for data_file, prov_file, default in SOURCES:
        rows = L.read_json(data_file)
        provs = L.read_json(prov_file)
        if len(rows) != len(provs):
            raise SystemExit(f"{data_file} và {prov_file} lệch số bản ghi")
        for r, p in zip(rows, provs):
            pairs.append((r, {**p, "sourceFile": data_file, "subset": _subset(p, default)}))

    random.Random(SEED).shuffle(pairs)

    out, prov = [], []
    for i, (r, p) in enumerate(pairs):
        out.append(r)
        prov.append({"index": i, **p})       # index = vị trí trong file đã trộn

    L.write_json("benchmark_multi.json", out)
    L.write_json("benchmark_multi_provenance.json", prov)

    n_opts = [len([k for k in r if k.startswith("answer_option")]) for r in out]
    n_correct = [len(r["correctAnswer"].split(",")) for r in out]
    print(f"Tầng 16 — bộ benchmark gộp: {len(out)} câu (seed trộn = {SEED})")
    print(f"  theo nguồn           : {dict(Counter(p['subset'] for p in prov))}")
    print(f"  số phương án mỗi câu : {dict(sorted(Counter(n_opts).items()))}")
    print(f"  số đáp án đúng/câu   : {dict(sorted(Counter(n_correct).items()))}")

    degen = sum(1 for r, n in zip(out, n_correct)
                if n == len([k for k in r if k.startswith("answer_option")]))
    print(f"  câu MỌI phương án đều đúng: {degen} "
          f"(chiến lược 'chọn hết' tự động đúng {100*degen/len(out):.0f}% số câu)")
