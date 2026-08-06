#!/usr/bin/env python3
"""So sánh bộ MỘT đáp án với bộ NHIỀU đáp án, và đo chất lượng benchmark.

  python compare_benchmarks.py --multi eval_multi_4b.json  --single eval_single_4b.json \
                               --multi eval_multi_8b.json  --single eval_single_8b.json

Hai loại phân tích:

A. HIỆU ỨNG ĐỊNH DẠNG (mỗi model một bảng) — dùng thiết kế cặp: cùng câu hỏi,
   hai định dạng, cùng model. Bảng chéo 2×2 + kiểm định McNemar.

B. ĐỘ PHÂN BIỆT (cần >= 2 model) — câu nào tách được model mạnh khỏi model yếu.
   Câu mà mọi model cùng đúng hoặc cùng sai không mang thông tin.

Không cần thư viện ngoài; p-value của McNemar tính bằng erfc (chính xác với df=1).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from eval_qwen3vl import load_items  # noqa: E402

MULTI = ROOT / "processed_data/benchmark_multi.json"
SINGLE = ROOT / "processed_data/benchmark_single.json"
PROV = ROOT / "processed_data/benchmark_multi_provenance.json"


def correct_map(path: Path, gold: dict[int, set]) -> dict[int, bool]:
    """index -> model trả lời đúng hoàn toàn hay không."""
    d = json.loads(path.read_text(encoding="utf-8"))
    return {x["index"]: set(x["pred"]) == gold[x["index"]] for x in d["per_item"]}


def mcnemar(b: int, c: int) -> tuple[float, float]:
    """b, c = hai ô lệch. Trả về (chi2 hiệu chỉnh liên tục, p-value)."""
    if b + c == 0:
        return 0.0, 1.0
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    return chi2, math.erfc(math.sqrt(chi2 / 2))      # đúng cho df = 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--multi", action="append", default=[], help="file kết quả bộ nhiều đáp án")
    ap.add_argument("--single", action="append", default=[], help="file kết quả bộ một đáp án")
    ap.add_argument("--exclude", action="append", default=[],
                    help="bỏ một nhóm khỏi mọi phép tính, vd --exclude file2_xoa_meta")
    args = ap.parse_args()

    if not args.multi or len(args.multi) != len(args.single):
        print(__doc__)
        return 1

    gold_m = {it["index"]: it["gold"] for it in load_items(MULTI)}
    gold_s = {it["index"]: it["gold"] for it in load_items(SINGLE)}
    prov = json.loads(PROV.read_text(encoding="utf-8"))
    subset = {p["index"]: p["subset"] for p in prov}

    models = {}
    for fm, fs in zip(args.multi, args.single):
        tag = Path(fm).stem.replace("eval_multi_", "")
        models[tag] = (correct_map(Path(fm), gold_m), correct_map(Path(fs), gold_s))
        print(f"nạp {tag}: multi={Path(fm).name}  single={Path(fs).name}")

    common = sorted(set.intersection(*[set(m.keys()) & set(s.keys()) for m, s in models.values()]))
    if args.exclude:
        before = len(common)
        common = [i for i in common if subset[i] not in args.exclude]
        print(f"\nBỏ nhóm {args.exclude}: {before} -> {len(common)} câu")
    print(f"\nSố câu chung: {len(common)}\n")

    # ---------------------------------------------------- A. hiệu ứng định dạng
    print("## A. Hiệu ứng định dạng (thiết kế cặp, cùng câu hỏi)\n")
    print("| Model | Nhóm | n | S✓M✓ | **S✓M✗** | **S✗M✓** | S✗M✗ | single | multi | McNemar p |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for tag, (mc, sc) in models.items():
        groups = {"tất cả": common}
        for i in common:
            groups.setdefault(subset[i], []).append(i)
        for g, idxs in groups.items():
            a = sum(1 for i in idxs if sc[i] and mc[i])
            b = sum(1 for i in idxs if sc[i] and not mc[i])
            c = sum(1 for i in idxs if not sc[i] and mc[i])
            d = sum(1 for i in idxs if not sc[i] and not mc[i])
            chi2, p = mcnemar(b, c)
            sig = "**" if p < 0.05 else ""
            print(f"| {tag} | {g} | {len(idxs)} | {a} | **{b}** | **{c}** | {d} | "
                  f"{(a+b)/len(idxs):.1%} | {(a+c)/len(idxs):.1%} | {sig}{p:.4f}{sig} |")

    print("\n- **S✓M✗** = biết kiến thức nhưng hỏng ở định dạng nhiều đáp án → chi phí định dạng.")
    print("- **S✗M✓** = đáng ngờ; nếu lớn bất thường thì bản nhiều đáp án đang rò rỉ hoặc dễ hơn bản gốc.")
    print("- p < 0,05 (in đậm) = chênh lệch giữa hai định dạng có ý nghĩa thống kê.")

    # ---------------------------------------------------- B. độ phân biệt
    if len(models) < 2:
        print("\n\n## B. Độ phân biệt — cần ít nhất 2 model, bỏ qua.")
        return 0

    print("\n\n## B. Độ phân biệt giữa các model\n")
    tags = list(models)
    for dname, gi in (("nhiều đáp án", 0), ("một đáp án", 1)):
        print(f"\n### Bộ {dname}\n")
        acc = {t: sum(models[t][gi][i] for i in common) / len(common) for t in tags}
        order = sorted(tags, key=lambda t: acc[t])
        weak, strong = order[0], order[-1]
        print(f"Yếu = `{weak}` ({acc[weak]:.1%})  ·  Mạnh = `{strong}` ({acc[strong]:.1%})  "
              f"·  chênh {acc[strong]-acc[weak]:+.1%}\n")

        cells = Counter()
        for i in common:
            cells[(models[weak][gi][i], models[strong][gi][i])] += 1
        both_ok = cells[(True, True)]
        disc = cells[(False, True)]          # mạnh đúng, yếu sai -> câu tốt
        rev = cells[(True, False)]           # ngược -> nhiễu / ground truth đáng ngờ
        both_no = cells[(False, False)]

        print(f"| Loại câu | n | % | Ý nghĩa |")
        print("|---|---:|---:|---|")
        print(f"| Cả hai đúng | {both_ok} | {both_ok/len(common):.1%} | quá dễ, không mang thông tin |")
        print(f"| **Mạnh ✓ / Yếu ✗** | {disc} | {disc/len(common):.1%} | **phân biệt được — phần lõi** |")
        print(f"| Yếu ✓ / Mạnh ✗ | {rev} | {rev/len(common):.1%} | nghịch đảo: nhiễu hoặc đáp án đáng ngờ |")
        print(f"| Cả hai sai | {both_no} | {both_no/len(common):.1%} | quá khó, hoặc ground truth sai |")

        info = disc + rev
        net = disc - rev
        print(f"\nCâu mang thông tin (đúng một model làm được): **{info}/{len(common)} "
              f"= {info/len(common):.1%}**")
        if info:
            print(f"Tín hiệu ròng (mạnh ✓/yếu ✗ trừ chiều ngược): **{net:+d}** "
                  f"({net/info:+.1%} trên số câu mang thông tin)")
        # tự chẩn đoán: hai model có đủ cách biệt không
        if disc and rev / disc > 0.6:
            print("\n> ⚠ Số câu nghịch đảo gần bằng số câu phân biệt → phần lớn khác biệt là "
                  "NHIỄU, không phải cách biệt năng lực. Hai model quá gần nhau; cần một model "
                  "mạnh hơn hẳn để đo được độ phân biệt.")
        elif disc:
            print("\n> ✓ Số câu phân biệt vượt trội so với chiều nghịch đảo → khoảng cách năng "
                  "lực đủ để dùng làm tín hiệu về chất lượng từng câu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
