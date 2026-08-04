"""Tầng 17 — FILE 1 bước lọc: lấy câu dạng phủ định.

Chưa xử lý gì: giữ nguyên thân câu phủ định, giữ nguyên phương án và đáp án gốc,
đúng format raw_data.json -> đưa vào filter_data/.

Đối xứng với tầng 14 (lọc File 3). Bản ĐÃ xử lý nằm ở tầng 09 -> processed_data/.
"""
from __future__ import annotations

from collections import Counter

import lib as L
from stages import NEG_DETECT, REWRITES


def stage17_file1_filter():
    raw = L.read_raw_data()
    clean = L.read_json("01_clean.json")

    out, prov = [], []
    for r in clean:
        if r["optionCount"] < 4 or not NEG_DETECT.search(r["question"]):
            continue

        # Ghi chú luật viết lại SẼ dùng ở tầng 09, để biết câu nào sẽ xử lý được.
        family = next((name for name, rx, _ in REWRITES if rx.search(r["question"])), None)

        out.append(raw[r["sourceIndex"]])
        prov.append({
            "questionID": r["sourceQuestionID"], "uid": r["uid"],
            "sourceIndex": r["sourceIndex"], "optionCount": r["optionCount"],
            "correctAnswer": "option" + r["correctLetter"],
            "negationFamily": family,
            "willBeProcessed": family is not None,
        })

    L.write_json("final_01_ngoai_tru.json", out)
    L.write_json("final_01_ngoai_tru_provenance.json", prov)

    ok = sum(1 for p in prov if p["willBeProcessed"])
    print(f"FILE 1 (lọc) — câu dạng phủ định: {len(out)}")
    print(f"  sẽ xử lý được ở tầng 09 : {ok}")
    print(f"  không viết lại sạch được: {len(out) - ok}")
    print(f"  theo họ phủ định        : "
          f"{dict(Counter(p['negationFamily'] or 'không khớp luật nào' for p in prov))}")
