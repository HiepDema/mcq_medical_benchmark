"""Tầng 15 — FILE 3: xử lý 10 câu chọn tay thành dạng nhiều đáp án.

Mỗi phương án gốc là một danh sách; gom tất cả mục lại thành pool, mục nào nằm
trong phương án đúng gốc thì là đáp án đúng, còn lại là nhiễu do người ra đề viết.
Ground truth SUY RA từ correctAnswer gốc, không tự sinh ra.

10 câu được chọn tay sau khi loại các bẫy: dãy có thứ tự, câu xếp hạng, thân câu
phủ định, pool toàn số, và các câu mà mục "nhiễu" thực ra vẫn đúng (liệt kê
không đầy đủ). Danh sách ứng viên đạt mọi tiêu chí tự động là 301 câu.
"""
from __future__ import annotations

import random
from collections import Counter

import lib as L

LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# sourceIndex trong raw_data.json -> lý do chọn
PICKED: dict[int, str] = {
    1:    "câu mẫu kinh điển — 4 phương án là hoán vị của pool 5 loại tế bào",
    910:  "thành phần đuôi cục nghẽn hỗn hợp — pool 4 mục, tách rõ",
    909:  "thành phần thân cục nghẽn hỗn hợp — cặp đối chiếu với câu trên",
    1425: "cơ do dây VII chi phối — nhiễu 'cơ cắn' (dây V) chắc chắn sai",
    1855: "giới hạn tam giác bả vai tam đầu — mốc giải phẫu rõ ràng",
    2330: "suy tim toàn bộ — nhiễu 'tăng gánh nhĩ phải' đối lập với đáp án",
    1409: "phân loại xương theo hình thể — nhiễu là loại mô, không phải hình thể",
    1103: "4 triệu chứng viêm của Celsus — 'mất chức năng' là bổ sung đời sau",
    1301: "thành phần mô đệm của u — nhiễu 'mô cơ', 'mô mỡ' rõ ràng ngoài nhóm",
    4803: "biến chứng còn ống động mạch — nhiễu là biến chứng của bệnh khác",
    6027: "hydrocarbon no — kiểm chứng khách quan bằng công thức phân tử",
}


def stage15_file3_multi():
    raw = L.read_raw_data()
    clean = {r["sourceIndex"]: r for r in L.read_json("01_clean.json")}

    out, prov = [], []
    for idx, why in PICKED.items():
        r = clean.get(idx)
        if r is None:
            raise SystemExit(f"Không tìm thấy sourceIndex {idx} trong 01_clean.json")

        parts = [L.split_items(o) for o in r["options"]]
        surface = {}
        for it in (x for p in parts for x in p):
            surface.setdefault(L.norm_item(it), it)
        pool = list(surface.values())
        norm_pool = [L.norm_item(p) for p in pool]
        correct = {norm_pool.index(L.norm_item(it)) for it in parts[r["correctIndex"]]}

        # Trộn vị trí: nếu giữ thứ tự xuất hiện thì các mục của phương án đúng
        # hay dồn về đầu (hoặc cuối) tuỳ đáp án gốc là A hay D -> lộ đáp án.
        items = [{"text": t, "correct": k in correct} for k, t in enumerate(pool)]
        random.Random(idx).shuffle(items)

        src = raw[idx]
        rec = {
            "question": r["questionClean"],
            "correctAnswer": ", ".join("option" + LETTERS[k]
                                       for k, o in enumerate(items) if o["correct"]),
            "medicalTopic": src.get("medicalTopic"),
            "difficultLevel": src.get("difficultLevel"),
            "regularFormat": src.get("regularFormat"),
            "questionID": src.get("questionID"),
        }
        for k, o in enumerate(items):
            rec["answer_option" + LETTERS[k]] = o["text"]
        out.append(rec)

        prov.append({
            "questionID": src.get("questionID"), "uid": r["uid"], "sourceIndex": idx,
            "selectedBecause": why,
            "originalOptions": r["options"],
            "originalCorrect": "option" + r["correctLetter"],
            "newOptionCount": len(items),
            "correctAnswer": rec["correctAnswer"],
            "derivedFrom": "comma-split",
            "qualityFlag": "derived-from-source-truth",
        })

    L.write_json("final_03_multi.json", out)
    L.write_json("final_03_multi_provenance.json", prov)
    print(f"FILE 3 — tách theo dấu phẩy: {len(out)} câu (chọn tay)")
    print(f"  số phương án mỗi câu : {dict(Counter(p['newOptionCount'] for p in prov))}")
    print(f"  số đáp án đúng/câu   : "
          f"{dict(Counter(len(p['correctAnswer'].split(',')) for p in prov))}")

    print("\n  --- 2 ví dụ ---")
    for n in (0, 5):
        rec, p = out[n], prov[n]
        print(f"\n  {rec['question'][:115]}")
        print(f"  gốc: {' | '.join(p['originalOptions'])[:150]}")
        for le in LETTERS[: p["newOptionCount"]]:
            mark = "[x]" if ("option" + le) in rec["correctAnswer"] else "[ ]"
            print(f"     {mark} {le}. {rec['answer_option' + le]}")
