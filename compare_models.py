#!/usr/bin/env python3
"""So sánh nhiều model trên cùng bộ benchmark, xuất bảng Markdown dán thẳng vào REPORT.md.

  python compare_models.py eval_results_4b.json eval_results_8b.json eval_results_30b.json

Tự tính lại mọi chỉ số từ trường per_item nên không phụ thuộc vào phần tóm tắt
đã ghi trong file, và luôn in kèm các mốc so sánh tính trên đúng tập câu đó.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from eval_qwen3vl import baselines, load_items, score  # noqa: E402

DATA = ROOT / "processed_data/benchmark_multi.json"
PROV = ROOT / "processed_data/benchmark_multi_provenance.json"


def label(path: Path) -> str:
    return path.stem.replace("eval_results_", "").replace("eval_results", "model")


def main() -> int:
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        print(__doc__)
        return 1

    items = load_items(DATA)
    prov = json.loads(PROV.read_text(encoding="utf-8"))
    subsets = [p["subset"] for p in prov]
    by_index = {it["index"]: it for it in items}

    runs = {}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        per = {x["index"]: set(x["pred"]) for x in d["per_item"]}
        # chỉ chấm trên đúng những câu model đã chạy (phòng khi số câu lệch nhau)
        idxs = sorted(per)
        runs[label(f)] = (idxs, per, d.get("model", "?"))
        print(f"{label(f):<6} {d.get('model','?')}  — {len(idxs)} câu")

    common = set.intersection(*[set(v[0]) for v in runs.values()])
    print(f"\nSố câu chung giữa mọi lần chạy: {len(common)}\n")

    groups = {"Tổng thể": sorted(common)}
    for i, s in zip(range(len(items)), subsets):
        if i in common:
            groups.setdefault(s, []).append(i)

    base_all = baselines(items)
    cols = ["Chọn hết", "Chọn 3 đầu"] + list(runs)

    print("| Nhóm | n | " + " | ".join(f"{c}<br>exact / jacc / F1" for c in cols) + " |")
    print("|---|---:|" + "---|" * len(cols))
    for g, idxs in groups.items():
        sub = [by_index[i] for i in idxs]
        cells = []
        for name, key in (("Chọn hết", "chọn hết"), ("Chọn 3 đầu", "chọn 3 phương án đầu")):
            m, _ = score(sub, [base_all[key][i] for i in idxs])
            cells.append(f"{m['exact_match']:.1%} / {m['jaccard']:.1%} / {m['micro_f1']:.1%}"
                         .replace("%", "").replace(".", ","))
        for tag, (_, per, _m) in runs.items():
            m, _ = score(sub, [per[i] for i in idxs])
            cells.append(f"**{m['exact_match']:.1%}** / {m['jaccard']:.1%} / {m['micro_f1']:.1%}"
                         .replace("%", "").replace(".", ","))
        print(f"| {g} | {len(sub)} | " + " | ".join(cells) + " |")

    # chẩn đoán lệch chọn thiếu / chọn thừa
    print("\n\nChẩn đoán xu hướng chọn:")
    print(f"| Model | TB số ô chọn | TB số ô đúng | Thiếu (FN) | Thừa (FP) |")
    print("|---|---:|---:|---:|---:|")
    for tag, (_, per, _m) in runs.items():
        sub = [by_index[i] for i in sorted(common)]
        preds = [per[i] for i in sorted(common)]
        npred = sum(len(p) for p in preds) / len(sub)
        ngold = sum(len(it["gold"]) for it in sub) / len(sub)
        fn = sum(len(it["gold"] - p) for it, p in zip(sub, preds))
        fp = sum(len(p - it["gold"]) for it, p in zip(sub, preds))
        print(f"| {tag} | {npred:.2f} | {ngold:.2f} | {fn} | {fp} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
