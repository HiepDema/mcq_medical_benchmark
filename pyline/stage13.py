"""Tầng 13 — biến FILE 2 thành dạng nhiều đáp án.

Hai lô:
  A) 20 câu: chỉ xoá phương án "Tất cả đều đúng" -> 3 phương án còn lại đều đúng.
  B) 30 câu: xoá phương án meta, rồi THÊM 1-2 phương án sai do người viết soạn tay.

⚠ Phương án nhiễu ở lô B là NỘI DUNG TỰ SOẠN, chưa được chuyên gia y khoa thẩm định.
  Mọi bản ghi lô B đều mang cờ syntheticDistractors trong file provenance.
"""
from __future__ import annotations

import random
import re
from collections import Counter

import lib as L

LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# --- lô B: phương án sai tự soạn.
# KHOÁ = vị trí trong mảng final_02_tat_ca_deu_dung.json (KHÔNG phải sourceIndex).

DISTRACTORS: dict[int, list[str]] = {
    192: ["Trung với vua.", "Đặt lợi ích cá nhân lên trên hết."],
    73:  ["Cơ cấu tổ chức ngành y tế", "Nguồn kinh phí phòng dịch"],
    54:  ["Độ ẩm không khí xuống thấp", "Người dân ít ra ngoài trời"],
    259: ["Định danh", "Phi cấu trúc"],
    75:  ["Sốt rét ác tính", "Viêm khớp dạng thấp"],
    77:  ["Xơ gan", "Ung thư gan"],
    216: ["Xã hội công xã nguyên thủy", "Xã hội chưa có sở hữu tư nhân"],
    266: ["Phẫu thuật cắt màng phổi thường quy", "Dùng kháng sinh phổ rộng đơn thuần"],
    74:  ["Nhân viên văn phòng", "Trẻ em đã tiêm đủ vắc xin"],
    76:  ["Cafein", "Ethanol"],
    124: ["Hemoglobin.", "Insulin."],
    19:  ["Đục thủy tinh thể tuổi già", "Tật khúc xạ cận thị"],
    31:  ["Sai số ngẫu nhiên", "Sai số do cỡ mẫu nhỏ"],
    111: ["Tiền sử phẫu thuật", "Nhóm máu của bệnh nhân"],
    36:  ["Nghiên cứu mô tả cắt ngang", "Báo cáo ca bệnh"],
    127: ["Nhóm máu của cơ thể", "Giới tính của người bệnh"],
    16:  ["Màu mắt của bệnh nhân", "Số lượng bạch cầu trong máu"],
    15:  ["Sốt cao rét run", "Nổi hạch sau tai"],
    18:  ["Ù tai, chóng mặt", "Sốt cao rét run"],
    186: ["Viện trợ từ bên ngoài.", "Ưu thế về vũ khí hiện đại."],
    11:  ["Tuổi của bệnh nhân", "Nhóm máu người bệnh"],
    84:  ["Nội soi đại tràng", "Chụp CT sọ não"],
    260: ["Xin cấp phép hành nghề", "Tuyển dụng nhân sự"],
    269: ["Khoang màng ngoài tim", "Ổ bụng"],
    135: ["Sự tồn tại độc lập của ý thức.", "Ý muốn chủ quan thuần túy."],
    163: ["Sự tồn tại độc lập của ý thức.", "Ý muốn chủ quan thuần túy."],
    95:  ["Âm lượng giọng nói", "Vốn từ vựng sử dụng"],
    66:  ["Khử trùng nguồn nước", "Diệt côn trùng trung gian"],
    67:  ["Sốt rét thể não", "Viêm gan siêu vi cấp"],
    3:   ["Vận chuyển oxy", "Thực bào vi khuẩn"],
}

_META_LIKE = re.compile(r"cả (hai|ba|\d)|đều (đúng|sai)|tất cả", re.I)
_BLANK = re.compile(r"\.{4,}|_{3,}")


def _norm(s: str) -> str:
    return re.sub(r"^[a-d][.\s]\s*", "", L.collapse(s).lower())


def select_candidates(rows, prov):
    """Chọn câu ALL_CORRECT sạch, xếp theo độ ngắn của phương án."""
    cand = []
    for i, (r, p) in enumerate(zip(rows, prov)):
        if p["metaKind"] != "ALL_CORRECT":
            continue
        all_opts = [(le, r.get("answer_option" + le)) for le in "ABCD"]
        all_opts = [(le, t) for le, t in all_opts if t]
        keep = [t for le, t in all_opts if "option" + le != p["correctAnswer"]]
        if len(keep) != 3:
            continue
        if _BLANK.search(r["question"]):
            continue
        if any(_META_LIKE.search(o) for o in keep):
            continue
        if len({_norm(o) for o in keep}) != 3:
            continue
        if any(re.fullmatch(r"[\d\s,.()/-]+", o) for o in keep):
            continue
        cand.append({"i": i, "row": r, "prov": p, "keep": keep,
                     "avg": sum(len(o) for o in keep) / 3})
    cand.sort(key=lambda x: (x["avg"], x["i"]))
    return cand


def _build(c, extra: list[str]):
    """Ghép phương án đúng + nhiễu, trộn vị trí theo seed cố định."""
    opts = [{"text": t, "correct": True} for t in c["keep"]] + \
           [{"text": t, "correct": False} for t in extra]
    random.Random(c["prov"]["sourceIndex"]).shuffle(opts)

    src = c["row"]
    rec = {
        "question": L.strip_prefix(src["question"]),
        "correctAnswer": ", ".join("option" + LETTERS[k]
                                   for k, o in enumerate(opts) if o["correct"]),
        "medicalTopic": src.get("medicalTopic"),
        "difficultLevel": src.get("difficultLevel"),
        "regularFormat": src.get("regularFormat"),
        "questionID": src.get("questionID"),
    }
    for k, o in enumerate(opts):
        rec["answer_option" + LETTERS[k]] = o["text"]
    return rec, opts


def stage13_file2_multi():
    rows = L.read_json("final_02_tat_ca_deu_dung.json")
    prov = L.read_json("final_02_tat_ca_deu_dung_provenance.json")
    cand = select_candidates(rows, prov)
    print(f"Tầng 13 — FILE 2 sang dạng nhiều đáp án: {len(cand)} ứng viên sạch")

    batch_a, batch_b = cand[:20], cand[20:50]
    missing = [c["i"] for c in batch_b if c["i"] not in DISTRACTORS]
    if missing:
        raise SystemExit(f"Thiếu phương án nhiễu tự soạn cho sourceIndex: {missing}")

    out, provenance = [], []

    for c in batch_a:
        rec, opts = _build(c, [])
        out.append(rec)
        provenance.append({
            "questionID": rec["questionID"], "uid": c["prov"]["uid"],
            "sourceIndex": c["prov"]["sourceIndex"], "batch": "A_xoa_meta",
            "syntheticDistractors": [], "removedMetaOption": c["prov"]["metaText"],
            "correctAnswer": rec["correctAnswer"],
            "qualityFlag": "all-options-correct",
        })

    for c in batch_b:
        extra = DISTRACTORS[c["i"]]
        rec, opts = _build(c, extra)
        out.append(rec)
        provenance.append({
            "questionID": rec["questionID"], "uid": c["prov"]["uid"],
            "sourceIndex": c["prov"]["sourceIndex"], "batch": "B_them_nhieu",
            "syntheticDistractors": extra, "removedMetaOption": c["prov"]["metaText"],
            "correctAnswer": rec["correctAnswer"],
            "qualityFlag": "synthetic-distractors-unverified",
        })

    L.write_json("final_02_multi.json", out)
    L.write_json("final_02_multi_provenance.json", provenance)

    print(f"  lô A (chỉ xoá meta, mọi phương án đều đúng) : {len(batch_a)}")
    print(f"  lô B (thêm 1-2 phương án sai tự soạn)       : {len(batch_b)}")
    print(f"  số phương án mỗi câu : "
          f"{dict(Counter(len([k for k in r if k.startswith('answer_option')]) for r in out))}")
    print(f"  số đáp án đúng/câu   : "
          f"{dict(Counter(len(r['correctAnswer'].split(',')) for r in out))}")

    print("\n  --- 1 ví dụ lô B ---")
    rec = out[20]
    p = provenance[20]
    print(f"  {rec['question'][:110]}")
    for le in LETTERS:
        k = "answer_option" + le
        if k in rec:
            mark = "[x]" if ("option" + le) in rec["correctAnswer"] else "[ ]"
            syn = "  <- nhiễu tự soạn" if rec[k] in p["syntheticDistractors"] else ""
            print(f"     {mark} {le}. {rec[k]}{syn}")
