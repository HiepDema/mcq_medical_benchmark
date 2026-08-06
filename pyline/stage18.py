"""Tầng 18 — bộ đối chứng MỘT đáp án.

Lấy đúng những câu gốc trong raw_data.json đã được dùng để dựng benchmark_multi.json,
giữ nguyên văn (1 đáp án đúng), xếp theo ĐÚNG THỨ TỰ của bản nhiều đáp án.

Nhờ vậy bản ghi thứ i của benchmark_single.json chính là bản gốc của bản ghi thứ i
trong benchmark_multi.json — so sánh hai bộ chỉ việc đối chiếu theo chỉ số.
"""
from __future__ import annotations

from collections import Counter

import lib as L


def stage18_benchmark_single():
    raw = L.read_raw_data()
    multi = L.read_json("benchmark_multi.json")
    prov = L.read_json("benchmark_multi_provenance.json")

    if len(multi) != len(prov):
        raise SystemExit("benchmark_multi và provenance lệch số bản ghi")

    seen = {}
    out, out_prov = [], []
    for p, m in zip(prov, multi):
        idx = p["sourceIndex"]
        if idx in seen:
            raise SystemExit(
                f"sourceIndex {idx} xuất hiện ở cả vị trí {seen[idx]} và {p['index']} "
                "— hai câu benchmark cùng một câu gốc, ánh xạ 1:1 hỏng")
        seen[idx] = p["index"]

        src = raw[idx]
        out.append(src)
        out_prov.append({
            "index": p["index"],
            "sourceIndex": idx,
            "uid": p["uid"],
            "questionID": src.get("questionID"),
            "subset": p["subset"],
            "singleCorrect": src.get("correctAnswer"),
            "singleOptionCount": len([k for k in src if k.startswith("answer_option")]),
            "multiCorrect": m["correctAnswer"],
            "multiOptionCount": len([k for k in m if k.startswith("answer_option")]),
        })

    L.write_json("benchmark_single.json", out)
    L.write_json("benchmark_single_provenance.json", out_prov)

    n_single = [x["singleOptionCount"] for x in out_prov]
    n_multi = [x["multiOptionCount"] for x in out_prov]
    n_corr = [len(x["multiCorrect"].split(",")) for x in out_prov]
    print(f"Tầng 18 — bộ đối chứng một đáp án: {len(out)} câu")
    print(f"  theo nguồn            : {dict(Counter(x['subset'] for x in out_prov))}")
    print(f"  phương án bản 1 đáp án: {dict(sorted(Counter(n_single).items()))}")
    print(f"  phương án bản nhiều   : {dict(sorted(Counter(n_multi).items()))}")
    print(f"  đáp án đúng bản nhiều : {dict(sorted(Counter(n_corr).items()))}")
    print(f"  ánh xạ 1:1 theo chỉ số: OK ({len(seen)} sourceIndex duy nhất)")

    print("\n  --- cùng một câu, hai định dạng (vị trí 0) ---")
    s, m, p = out[0], multi[0], out_prov[0]
    print(f"  MỘT đáp án  : {s['question'][:100]}")
    print(f"     {p['singleCorrect']} — " +
          " | ".join(f"{le}. {s['answer_option' + le]}"[:40]
                     for le in "ABCD" if s.get("answer_option" + le)))
    print(f"  NHIỀU đáp án: {m['question'][:100]}")
    print(f"     {p['multiCorrect']}")
