"""Tầng 2 — phân luồng mỗi câu vào một trong ba họ, và lọc cơ học.

  file1 — PHỦ ĐỊNH   : "... ngoại trừ", "câu nào SAI"  -> 3 phương án còn lại đều đúng
  file2 — META       : đáp án đúng là "Tất cả đều đúng" -> 3 phương án còn lại đều đúng,
                        cần LLM sinh thêm phương án nhiễu
  file3 — POOL       : mọi phương án đều là danh sách ngăn cách bởi dấu phẩy
                        -> gộp các mục thành pool phương án độc lập

Chỉ giữ lại ứng viên đã qua HẾT các bộ lọc cơ học, để lô việc gửi lên GPU nhỏ và sạch.
Thứ tự ưu tiên: meta > phủ định > pool (một câu chỉ vào đúng một họ).

Đầu ra: data_v2/02_route_{file1,file2,file3}.json + 02_route_stats.json
"""
from __future__ import annotations

import re
from collections import Counter

import lib2 as L
import stages as S1  # NEG_DETECT / REWRITES / ORDER_STEM của v1

MIN_POOL, MAX_POOL = 4, 20


# --------------------------------------------------------------- file 1
def _rewrite_negation(question: str):
    """Bản viết lại cơ học (dự phòng khi LLM từ chối hoặc trả về câu hỏng)."""
    for name, rx, rep in S1.REWRITES:
        if rx.search(question):
            s = L.collapse(rx.sub(rep, question, count=0))
            s = re.sub(r"\s+([:.?])", r"\1", s)
            return re.sub(r"[:\s]*:$", ":", s), name
    return None, None


def _pick_negation(r) -> dict | None:
    if not S1.NEG_DETECT.search(r["question"]):
        return None
    if L.BLANK_STEM.search(r["question"]):
        return None
    if L.meta_kind(r["options"][r["correctIndex"]]):
        return None                      # đáp án gốc là meta -> đảo tập sẽ vô nghĩa
    if any(not L.clean_option(o) for o in r["options"]):
        return None
    if len({L.norm_item(o) for o in r["options"]}) != len(r["options"]):
        return None
    stem, family = _rewrite_negation(r["question"])
    if not stem or len(stem) < 12:
        return None
    keep = [o for i, o in enumerate(r["options"]) if i != r["correctIndex"]]
    if len(keep) < 3:
        return None
    return {**r, "fallbackStem": L.strip_prefix(stem), "negationFamily": family,
            "wrongOption": r["options"][r["correctIndex"]], "correctOptions": keep}


# --------------------------------------------------------------- file 2
def _pick_meta(r) -> dict | None:
    kind = L.meta_kind(r["options"][r["correctIndex"]])
    if not kind or kind["kind"] != "ALL_CORRECT":
        return None
    if L.BLANK_STEM.search(r["question"]):
        return None
    keep = [o for i, o in enumerate(r["options"]) if i != r["correctIndex"]]
    if len(keep) != 3:
        return None                      # chỉ nhận câu 4 phương án cho đều
    if any(not L.clean_option(o) for o in keep):
        return None
    if len({L.norm_item(o) for o in keep}) != 3:
        return None
    return {**r, "metaText": r["options"][r["correctIndex"]], "correctOptions": keep}


# --------------------------------------------------------------- file 3
def _pick_pool(r) -> dict | None:
    if not all("," in o for o in r["options"]):
        return None
    if L.BLANK_STEM.search(r["question"]):
        return None
    if S1.ORDER_STEM.search(r["question"]):
        return None                      # câu hỏi về thứ tự -> tách ra là mất nghĩa

    parts = [L.split_items(o) for o in r["options"]]
    if not all(len(p) >= 2 for p in parts):
        return None                      # dấu phẩy chỉ là dấu thập phân
    if any(len({L.norm_item(x) for x in p}) != len(p) for p in parts):
        return None                      # mục lặp trong cùng một phương án -> dãy có thứ tự
    sets = [frozenset(L.norm_item(x) for x in p) for p in parts]
    if len(set(sets)) != len(sets):
        return None                      # hai phương án cùng tập mục -> câu hỏi xếp hạng

    surface: dict[str, str] = {}
    for it in (x for p in parts for x in p):
        surface.setdefault(L.norm_item(it), it)
    pool = [L.sentence_case(v) for v in surface.values()]
    flat = sum(len(p) for p in parts)

    overlap = round(1 - len(pool) / flat, 3)
    numeric = sum(1 for p in pool if L.is_numericish(p)) / len(pool)
    if numeric > 0.6 and not all(L.is_roman(p) for p in pool):
        return None
    if overlap < 0.2:
        return None
    if not (MIN_POOL <= len(pool) <= MAX_POOL):
        return None
    if any(not L.clean_option(p) for p in pool):
        return None

    norm_pool = [L.norm_item(p) for p in pool]
    correct = sorted({norm_pool.index(L.norm_item(x)) for x in parts[r["correctIndex"]]})
    if len(correct) < 2 or len(correct) >= len(pool):
        return None

    return {**r, "pool": pool, "poolCorrect": correct,
            "overlap": overlap, "numericFrac": round(numeric, 2)}


# --------------------------------------------------------------- điều phối
def s2_route():
    clean = L.read_work("01_clean.json")
    print(f"Tầng 2 — phân luồng: {len(clean)} câu")

    fam: dict[str, list] = {"file1": [], "file2": [], "file3": []}
    reasons = Counter()
    for r in clean:
        hit = _pick_meta(r)
        if hit:
            fam["file2"].append(hit); reasons["file2_meta"] += 1; continue
        hit = _pick_negation(r)
        if hit:
            fam["file1"].append(hit); reasons["file1_phu_dinh"] += 1; continue
        hit = _pick_pool(r)
        if hit:
            fam["file3"].append(hit); reasons["file3_pool"] += 1; continue
        reasons["khong_dung_duoc"] += 1

    stats = {}
    for name, rows in fam.items():
        kept, dropped = L.dedup_near(rows, lambda r: L.qkey(r["questionClean"]))
        kept.sort(key=lambda r: (r["srcFile"], r["srcIndex"]))
        fam[name] = kept
        stats[name] = {"truoc_khu_gan_trung": len(rows), "gan_trung_bi_loai": dropped,
                       "ung_vien": len(kept)}
        L.write_work(f"02_route_{name}.json", kept)

    stats["tong_cau_doc_vao"] = len(clean)
    stats["khong_dung_duoc"] = reasons["khong_dung_duoc"]
    L.write_work("02_route_stats.json", stats)

    print()
    for name in ("file1", "file2", "file3"):
        s = stats[name]
        print(f"  {name}: {s['truoc_khu_gan_trung']:>6} qua lọc cơ học"
              f"  -> {s['ung_vien']:>6} ứng viên"
              f"  (loại {s['gan_trung_bi_loai']} câu gần trùng)")
    total = sum(stats[n]["ung_vien"] for n in ("file1", "file2", "file3"))
    print(f"\n  TỔNG ỨNG VIÊN GỬI LLM: {total}"
          f"  ({100 * total / len(clean):.1f}% số câu nguồn)")
    print(f"  theo file nguồn: "
          f"{dict(Counter(r['srcFile'][:18] for n in fam for r in fam[n]))}")
