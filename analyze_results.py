#!/usr/bin/env python3
"""Thống kê chi tiết kết quả chấm: theo họ câu hỏi, theo độ khó, theo hiệu chỉnh số ô.

  python analyze_results.py --data processed_data_v2/final_benchmark_mixed.json \
      --prov processed_data_v2/final_benchmark_mixed_provenance.json \
      --result "Qwen3-0.6B=results_v2/eval_mixed_0.6b.json" \
      --result "Qwen3-4B=results_v2/eval_mixed_4b.json"

Trường difficultLevel trong đề gốc có 15 cách viết khác nhau ('2', 'Level 2',
'Level 2 (Moderate)', 'Medium', 'Moderate'...) nên phải quy về một thang chung
trước khi đếm; xem DIFF_MAP.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from eval_qwen3vl import load_items  # noqa: E402

# 15 giá trị thô -> 4 bậc. Tất cả đều là biến thể của cùng một thang 1-4.
DIFF_MAP = {
    "1": 1, "level 1": 1, "level 1 (easy)": 1, "easy": 1,
    "2": 2, "level 2": 2, "level 2 (moderate)": 2, "medium": 2, "moderate": 2,
    "3": 3, "level 3": 3, "level 3 (challenging)": 3, "challenging": 3,
    "4": 4, "level 4": 4, "level 4 (hard)": 4, "hard": 4,
}
DIFF_NAME = {1: "1 — Dễ", 2: "2 — Trung bình", 3: "3 — Khó", 4: "4 — Rất khó", 0: "? — không rõ"}


def difficulty(raw) -> int:
    return DIFF_MAP.get(str(raw or "").strip().lower(), 0)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%".replace(".", ",")


def load_preds(path: Path) -> dict[int, set]:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {x["index"]: set(x["pred"]) for x in d.get("per_item", d)}


def table(rows, headers, aligns=None):
    aligns = aligns or ["<"] + [">"] * (len(headers) - 1)
    w = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
         for i, h in enumerate(headers)]
    line = lambda cells: "  " + "  ".join(
        f"{str(c):{a}{ww}}" for c, a, ww in zip(cells, aligns, w))
    print(line(headers))
    print("  " + "  ".join("-" * ww for ww in w))
    for r in rows:
        print(line(r))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--prov", required=True)
    ap.add_argument("--result", action="append", required=True,
                    help='"Tên model=đường/dẫn/eval.json", lặp lại được')
    ap.add_argument("--json-out", help="ghi toàn bộ số liệu ra file JSON")
    args = ap.parse_args()

    items = {it["index"]: it for it in load_items(ROOT / args.data)}
    raw = json.loads((ROOT / args.data).read_text(encoding="utf-8"))
    prov = json.loads((ROOT / args.prov).read_text(encoding="utf-8"))
    subset = {p["index"]: p.get("subset", "?") for p in prov}
    diff = {i: difficulty(raw[i].get("difficultLevel")) for i in range(len(raw))}

    models = {}
    for spec in args.result:
        if "=" not in spec:
            print(f"--result phải có dạng 'Tên=đường dẫn', nhận được: {spec}")
            return 1
        tag, path = spec.split("=", 1)
        models[tag] = load_preds(ROOT / path)

    N = len(items)
    print(f"Bộ dữ liệu : {args.data}  ({N} câu)")
    print(f"Model      : {', '.join(models)}\n")

    ok = {t: {i: p[i] == items[i]["gold"] for i in items} for t, p in models.items()}
    out = {"data": args.data, "n": N, "models": list(models), "overall": {}, }

    # ------------------------------------------------------------ tổng thể
    print("## Tổng thể (exact match)\n")
    rows = []
    for t in models:
        c = sum(ok[t].values())
        rows.append([t, N, c, N - c, pct(c / N)])
        out["overall"][t] = {"n": N, "dung": c, "sai": N - c, "exact": c / N}
    table(rows, ["Model", "n", "đúng", "sai", "exact"])

    # ------------------------------------------------- theo họ câu hỏi
    print("\n## Theo họ câu hỏi\n")
    groups = sorted({subset[i] for i in items})
    rows, out["theo_ho"] = [], {}
    for g in groups:
        idx = [i for i in items if subset[i] == g]
        r = [g, len(idx)]
        out["theo_ho"][g] = {"n": len(idx)}
        for t in models:
            c = sum(ok[t][i] for i in idx)
            r += [c, pct(c / len(idx))]
            out["theo_ho"][g][t] = {"dung": c, "sai": len(idx) - c, "exact": c / len(idx)}
        rows.append(r)
    hdr = ["Họ", "n"] + [x for t in models for x in (f"{t} đúng", f"{t} exact")]
    table(rows, hdr)

    # ---------------------------------------------------- theo độ khó
    print("\n## Theo độ khó (difficultLevel)\n")
    levels = sorted({diff[i] for i in items}, key=lambda x: (x == 0, x))
    rows, out["theo_do_kho"] = [], {}
    for lv in levels:
        idx = [i for i in items if diff[i] == lv]
        r = [DIFF_NAME[lv], len(idx), pct(len(idx) / N)]
        out["theo_do_kho"][DIFF_NAME[lv]] = {"n": len(idx)}
        for t in models:
            c = sum(ok[t][i] for i in idx)
            r += [c, len(idx) - c, pct(c / len(idx))]
            out["theo_do_kho"][DIFF_NAME[lv]][t] = {
                "dung": c, "sai": len(idx) - c, "exact": c / len(idx)}
        rows.append(r)
    hdr = ["Độ khó", "n", "% bộ"] + [x for t in models
                                     for x in (f"{t} đúng", f"{t} sai", f"{t} exact")]
    table(rows, hdr)

    print("\n  Giá trị thô gộp vào mỗi bậc:")
    byraw = defaultdict(Counter)
    for i in items:
        byraw[diff[i]][str(raw[i].get("difficultLevel"))] += 1
    for lv in levels:
        got = ", ".join(f"{k!r}×{v}" for k, v in byraw[lv].most_common())
        print(f"    {DIFF_NAME[lv]:<16} {got}")

    # --------------------------------------- độ khó × họ (chỉ model cuối)
    last = list(models)[-1]
    print(f"\n## Độ khó × họ câu hỏi — exact match của {last}\n")
    rows = []
    for g in groups:
        r = [g]
        for lv in levels:
            idx = [i for i in items if subset[i] == g and diff[i] == lv]
            r.append(f"{pct(sum(ok[last][i] for i in idx) / len(idx))} ({len(idx)})"
                     if idx else "—")
        rows.append(r)
    table(rows, ["Họ"] + [DIFF_NAME[lv] for lv in levels])

    # ------------------------------------------- hiệu chỉnh số lượng ô
    print("\n## Hiệu chỉnh số lượng ô chọn\n")
    rows, out["so_o_chon"] = [], {}
    for t, p in models.items():
        gold = sum(len(items[i]["gold"]) for i in items) / N
        got = sum(len(p[i]) for i in items) / N
        same = sum(1 for i in items if len(p[i]) == len(items[i]["gold"]))
        cover = sum(1 for i in items if items[i]["gold"] <= p[i])
        rows.append([t, f"{gold:.2f}".replace(".", ","), f"{got:.2f}".replace(".", ","),
                     pct(same / N), pct(cover / N),
                     str(dict(sorted(Counter(len(p[i]) for i in items).items())))])
        out["so_o_chon"][t] = {"chuan_tb": gold, "model_tb": got,
                               "khop_so": same / N, "gold_nam_trong": cover / N}
    table(rows, ["Model", "chuẩn TB", "model TB", "khớp số ô", "gold ⊆ chọn", "phân bố số ô"])

    # ------------------------------------------------ độ phân biệt 2 model
    if len(models) == 2:
        a, b = list(models)
        accs = {t: sum(ok[t].values()) / N for t in models}
        weak, strong = sorted(models, key=lambda t: accs[t])
        c = Counter((ok[weak][i], ok[strong][i]) for i in items)
        print(f"\n## Độ phân biệt — yếu = {weak} ({pct(accs[weak])}) · "
              f"mạnh = {strong} ({pct(accs[strong])})\n")
        rows = [["Cả hai đúng", c[(True, True)], pct(c[(True, True)] / N)],
                ["Mạnh ✓ / Yếu ✗", c[(False, True)], pct(c[(False, True)] / N)],
                ["Yếu ✓ / Mạnh ✗", c[(True, False)], pct(c[(True, False)] / N)],
                ["Cả hai sai", c[(False, False)], pct(c[(False, False)] / N)]]
        table(rows, ["Loại câu", "n", "%"])
        out["do_phan_biet"] = {"yeu": weak, "manh": strong,
                               "ca_hai_dung": c[(True, True)], "manh_dung_yeu_sai": c[(False, True)],
                               "yeu_dung_manh_sai": c[(True, False)], "ca_hai_sai": c[(False, False)]}

    if args.json_out:
        (ROOT / args.json_out).write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print(f"\n-> đã ghi số liệu ra {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
