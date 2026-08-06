"""Tầng 15 — FILE 3: tách câu có dấu phẩy thành dạng nhiều đáp án.

Mỗi phương án gốc là một danh sách; gom tất cả mục thành pool, mục nào nằm trong
phương án đúng gốc thì là đáp án đúng. Ground truth SUY RA từ correctAnswer gốc.

Chọn ứng viên theo ba lớp:
  1. Lọc tự động — loại dãy có thứ tự, câu xếp hạng, thân câu phủ định, pool toàn
     số, mục gần trùng nhau, thân câu quá cụt, câu lặp.
  2. BLOCKLIST — các câu mà bộ lọc cấu trúc không bắt được nhưng rà tay thấy sai
     ngữ nghĩa (phương án "nhiễu" thực ra vẫn đúng).
  3. HAND_VERIFIED được ưu tiên; phần còn lại lấy tự động theo overlap giảm dần và
     gắn confidence thấp hơn.
"""
from __future__ import annotations

import difflib
import random
import re
from collections import Counter

import lib as L
from stages import NEGATION, ORDER_STEM

LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
TARGET = 50

# Đã rà tay: nhiễu chắc chắn sai, đáp án đúng chắc chắn đúng.
HAND_VERIFIED = [
    1, 910, 909, 1425, 1855, 2330, 1409, 1103, 1301, 4803, 6027,
    7215, 4809, 5616, 757, 1854, 4151, 7410, 9486, 9619, 492,
    4250, 5259, 7534, 1178, 3927, 7764, 402, 457, 1393, 1408, 1859,
    2139, 2675, 2711,
]

# Rà tay thấy hỏng — bộ lọc cấu trúc KHÔNG phát hiện được.
BLOCKLIST = {
    4261: "nhiễu 'xì dầu' thực tế cũng là thực phẩm giàu muối",
    4270: "nhiễu 'tính mức lao động' có thể là một bước hợp lệ",
    3346: "nhiễu 'mầm bệnh' đồng nghĩa với đáp án đúng 'tác nhân gây bệnh'",
    1449: "nhiễu 'Gân' thực tế cũng phụ thuộc cơ vân",
    1833: "trùng câu 1449, cùng lỗi",
    6388: "ba biến thể VanderWaals gần trùng nhau",
    8413: "nhiễu 'chảy nước' gần trùng đáp án 'chảy dịch'",
    3331: "nhiễu 'Staphylococci' là chi của đáp án 'Staphylococus aureus'",
    8407: "nhiễu 'sắn phủ' là lỗi gõ của đáp án 'sẩn phù'",
    8670: "tập đáp án gốc không nhất quán về loại phản ứng",
    5314: "nhiễu 'Dân số', 'bệnh tật' đều là thông tin liên quan sức khoẻ",
    1179: "nhiễu gần trùng đáp án 'có nơi bị teo đét'",
    1571: "trùng câu 1409 đã chọn",
    1824: "trùng câu 1409 đã chọn",
    4965: "nhiễu 'Lợi tiểu', 'trợ tim' đều là điều trị suy tim",
    178: "nhiễu 'Phát hiện sớm người tiếp xúc' gần trùng đáp án",
    2124: "thân câu tối nghĩa, cặp 'xác định'/'phân định' mơ hồ",
    293: "nhiễu 'Nội dã chiến' là bộ phận của đáp án 'Nội – Ngoại dã chiến'",
    6979: "nhiễu chứa nguyên vế của đáp án đúng",
    1570: "trùng câu 1408",
    2671: "nhiễu 'tim' và đáp án 'Tâm' là cùng một tạng trong YHCT",
}


def _near_dup(pool: list[str]) -> bool:
    n = [L.norm_item(p) for p in pool]
    for a in range(len(n)):
        for b in range(a + 1, len(n)):
            x, y = n[a], n[b]
            if x in y or y in x or set(x.split()) == set(y.split()):
                return True
            if difflib.SequenceMatcher(None, x, y).ratio() > 0.80:
                return True
    return False


def select_candidates(clean):
    out, seen_q = [], set()
    for r in clean:
        if r["optionCount"] != 4 or not all("," in o for o in r["options"]):
            continue
        parts = [L.split_items(o) for o in r["options"]]
        if not all(len(p) >= 2 for p in parts):
            continue
        flat = [x for p in parts for x in p]
        surf = {}
        for it in flat:
            surf.setdefault(L.norm_item(it), it)
        pool = list(surf.values())

        if any(len({L.norm_item(x) for x in p}) != len(p) for p in parts):
            continue                                   # dãy có thứ tự
        if ORDER_STEM.search(r["question"]) or re.search(
                r"sắp xếp|trình tự|ưu tiên", r["question"], re.I):
            continue
        if len({frozenset(L.norm_item(x) for x in p) for p in parts}) == 1:
            continue                                   # câu xếp hạng
        if any(rx.search(r["question"]) for _, _, rx in NEGATION):
            continue                                   # thân câu phủ định -> đảo nghĩa
        if sum(1 for p in pool if L.is_numericish(p)) / len(pool) > 0.2:
            continue
        if any(L.is_roman(p) for p in pool):
            continue
        npool = [L.norm_item(p) for p in pool]
        corr = sorted({npool.index(L.norm_item(x)) for x in parts[r["correctIndex"]]})
        if not (2 <= len(corr) < len(pool)) or not (4 <= len(pool) <= 8):
            continue
        if max(len(p) for p in pool) > 70:
            continue
        if len(L.strip_prefix(r["question"])) < 25:
            continue
        if _near_dup(pool):
            continue
        q = L.norm_item(L.strip_prefix(r["question"]))
        if q in seen_q:
            continue
        seen_q.add(q)
        out.append({"r": r, "pool": pool, "corr": corr,
                    "overlap": round(1 - len(pool) / len(flat), 3)})
    out.sort(key=lambda c: (-c["overlap"], c["r"]["sourceIndex"]))
    return out


def stage15_file3_multi():
    raw = L.read_raw_data()
    cands = select_candidates(L.read_json("01_clean.json"))
    by_idx = {c["r"]["sourceIndex"]: c for c in cands}
    print(f"Tầng 15 — ứng viên đạt lọc tự động: {len(cands)}")

    chosen, why = [], {}
    for idx in HAND_VERIFIED:
        if idx in BLOCKLIST or idx not in by_idx:
            continue
        chosen.append(by_idx[idx]); why[idx] = "hand-verified"
    for c in cands:
        if len(chosen) >= TARGET:
            break
        idx = c["r"]["sourceIndex"]
        if idx in BLOCKLIST or idx in why:
            continue
        chosen.append(c); why[idx] = "auto-selected"
    if len(chosen) < TARGET:
        raise SystemExit(f"Chỉ gom được {len(chosen)}/{TARGET} câu")

    out, prov = [], []
    for c in chosen:
        r, pool, corr = c["r"], c["pool"], c["corr"]
        idx = r["sourceIndex"]
        items = [{"text": t, "correct": k in set(corr)} for k, t in enumerate(pool)]
        random.Random(idx).shuffle(items)          # tránh lộ đáp án theo vị trí

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
            "selection": why[idx], "overlap": c["overlap"],
            "originalOptions": r["options"],
            "originalCorrect": "option" + r["correctLetter"],
            "newOptionCount": len(items), "correctAnswer": rec["correctAnswer"],
            "derivedFrom": "comma-split",
            "qualityFlag": "derived-from-source-truth",
        })

    L.write_json("final_03_multi.json", out)
    L.write_json("final_03_multi_provenance.json", prov)
    print(f"FILE 3 — tách theo dấu phẩy: {len(out)} câu")
    print(f"  nguồn chọn           : {dict(Counter(p['selection'] for p in prov))}")
    print(f"  chặn tay (lỗi ngữ nghĩa): {len(BLOCKLIST)}")
    print(f"  số phương án mỗi câu : {dict(sorted(Counter(p['newOptionCount'] for p in prov).items()))}")
    print(f"  số đáp án đúng/câu   : "
          f"{dict(sorted(Counter(len(p['correctAnswer'].split(',')) for p in prov).items()))}")
