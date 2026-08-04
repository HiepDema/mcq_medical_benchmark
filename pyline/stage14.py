"""Tầng 14 — FILE 3 bước lọc: lấy câu có >= 1 dấu phẩy ở MỌI phương án.

Chưa xử lý gì, giữ nguyên format raw_data.json -> đưa vào filter_data/.
"""
from __future__ import annotations

from collections import Counter

import lib as L


def stage14_file3_filter():
    raw = L.read_raw_data()
    clean = L.read_json("01_clean.json")
    hit = [r for r in clean if all("," in o for o in r["options"])]

    out = [raw[r["sourceIndex"]] for r in hit]
    prov = [{
        "questionID": r["sourceQuestionID"], "uid": r["uid"],
        "sourceIndex": r["sourceIndex"], "optionCount": r["optionCount"],
        "correctAnswer": "option" + r["correctLetter"],
    } for r in hit]

    L.write_json("final_03_dau_phay.json", out)
    L.write_json("final_03_dau_phay_provenance.json", prov)
    print(f"FILE 3 (lọc) — câu có dấu phẩy ở mọi phương án: {len(out)}")
    print(f"  theo số phương án: {dict(Counter(p['optionCount'] for p in prov))}")
