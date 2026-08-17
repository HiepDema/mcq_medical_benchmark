"""Tầng 5 — thẩm định vòng 2, trộn, xuất benchmark cuối.

Gộp cả 4 họ vào MỘT file. Mặc định lấy hết, không cân bằng số lượng giữa các họ
(--per-subset N để giới hạn mỗi họ N câu).

Ra hai file khớp 1:1 theo chỉ số:
  processed_data_v2/final_benchmark.json         — bản nhiều đáp án
  processed_data_v2/final_benchmark_single.json  — chính các câu gốc đó, nguyên văn

Nhờ khớp 1:1 nên chênh lệch điểm giữa hai bộ quy hết về ĐỊNH DẠNG, không phải
do bộ này khó hơn bộ kia.
"""
from __future__ import annotations

import random
import re
from collections import Counter

import lib2 as L

SOURCES = [
    ("final_01_ngoai_tru.json", "final_01_ngoai_tru_provenance.json"),
    ("final_02_multi.json", "final_02_multi_provenance.json"),
    ("final_03_multi.json", "final_03_multi_provenance.json"),
    ("final_04_ca_ab.json", "final_04_ca_ab_provenance.json"),
]
XOA_META = ("final_02_xoa_meta.json", "final_02_xoa_meta_provenance.json")


def _labels(rec) -> list[bool]:
    """[phương án thứ i có đang được đánh dấu ĐÚNG không]"""
    letters = [le for le in L.LETTERS if rec.get("answer_option" + le)]
    gold = set(re.findall(r"option([A-Z])", rec["correctAnswer"]))
    return [le in gold for le in letters]


def _consistent(idxs, labels, want_gold: bool) -> list[int]:
    """Giữ lại các chỉ số TRỎ ĐÚNG HƯỚNG.

    "Ô đang đánh dấu ĐÚNG nhưng thực ra SAI" thì bắt buộc phải trỏ vào ô đang
    đánh dấu ĐÚNG. Trỏ vào ô vốn đã đánh dấu SAI là model lẫn hai mảng với nhau,
    phán quyết đó tự mâu thuẫn nên không dùng làm bằng chứng được.

    Đo trên lượt chạy thật: 26,5% chỉ số ở mảng thứ nhất và 42,9% ở mảng thứ hai
    trỏ ngược hướng. Tính cả chúng thì cổng lọc loại oan 1.229 câu.
    """
    return [i for i in idxs or []
            if isinstance(i, int) and 0 <= i < len(labels) and labels[i] is want_gold]


def _audit_gate(pairs, audit: dict):
    """Loại các câu mà LLM thẩm định thấy đáp án chuẩn bị sai."""
    kept, dropped = [], Counter()
    for rec, p in pairs:
        v = audit.get(p["uid"])
        if v is None:
            p["auditStatus"] = "khong_tham_dinh"
            kept.append((rec, p))
            continue
        if not v.get("cau_hoi_ro_rang", True):
            dropped["cau_dan_khong_ro"] += 1; continue
        lab = _labels(rec)
        if _consistent(v.get("danh_dau_dung_thuc_ra_sai"), lab, True):
            dropped["dap_an_dung_thuc_ra_sai"] += 1; continue
        if _consistent(v.get("danh_dau_sai_thuc_ra_dung"), lab, False):
            dropped["nhieu_thuc_ra_dung"] += 1; continue
        p["auditStatus"] = "dat" if v.get("dat") else "dat_co_canh_bao"
        p["auditIndexNoise"] = bool(v.get("danh_dau_dung_thuc_ra_sai")
                                    or v.get("danh_dau_sai_thuc_ra_dung"))
        kept.append((rec, p))
    return kept, dropped


def _reshuffle(rec: dict, uid: str) -> dict:
    """Trộn lại vị trí phương án SAU khi qua cổng thẩm định.

    Cổng thẩm định không trung lập về vị trí: nó giữ lại nhiều hơn những câu có
    phương án sai nằm ở D. Đo trên lượt chạy thật, tỉ lệ phương án sai ở D là
    21,6% trước khi thẩm định và 24,0% sau — tức chính bộ lọc tạo ra rò rỉ vị trí.
    Trộn lại ở đây xoá hẳn hiệu ứng đó. An toàn vì các câu còn lại đều đã được
    thẩm định là không có ô nào gán nhãn ngược.
    """
    letters = [le for le in L.LETTERS if rec.get("answer_option" + le)]
    gold = set(re.findall(r"option([A-Z])", rec["correctAnswer"]))
    opts = [{"text": rec["answer_option" + le], "correct": le in gold} for le in letters]
    random.Random(uid + "|post").shuffle(opts)
    return L.pack(rec["question"], opts, rec)


def s5_build(per_subset: int = 0, seed: int = 20260815,
             with_xoa_meta: bool = False, skip_audit: bool = False):
    src = list(SOURCES) + ([XOA_META] if with_xoa_meta else [])
    pairs = []
    for data_file, prov_file in src:
        rows, provs = L.read_out(data_file), L.read_out(prov_file)
        if len(rows) != len(provs):
            raise SystemExit(f"{data_file} và {prov_file} lệch số bản ghi")
        pairs.extend(zip(rows, provs))

    print(f"Tầng 5 — dựng benchmark: {len(pairs)} câu đầu vào")

    audit = None if skip_audit else L.read_llm_out("r2_audit")
    if audit is None:
        print("  ⚠ chưa có r2_audit.out.jsonl — bỏ qua bước thẩm định vòng 2."
              if not skip_audit else "  bỏ qua thẩm định vòng 2 theo yêu cầu.")
        for _, p in pairs:
            p["auditStatus"] = "khong_tham_dinh"
    else:
        before = len(pairs)
        pairs, dropped = _audit_gate(pairs, audit)
        print(f"  thẩm định vòng 2: {before} -> {len(pairs)} câu"
              f"  (loại {sum(dropped.values())} {dict(dropped)})")

    by_subset: dict[str, list] = {}
    for pair in pairs:
        by_subset.setdefault(pair[1]["subset"], []).append(pair)

    balanced = []
    for name in sorted(by_subset):
        group = by_subset[name]
        if per_subset and len(group) > per_subset:
            group = random.Random(seed).sample(group, per_subset)
        balanced.extend(group)
    if not per_subset:
        print("  lấy hết mọi họ, không cân bằng số lượng")
    # Trộn để các câu cùng nguồn không nằm liền khối: xếp theo họ thì mọi chỉ số
    # tính trên một lát cắt bất kỳ của file đều lệch theo họ chiếm chỗ ở đó.
    random.Random(seed).shuffle(balanced)

    # Ánh xạ 1:1 sang bản gốc đòi hỏi mỗi câu benchmark là một câu nguồn riêng biệt.
    seen = {}
    for i, (_, p) in enumerate(balanced):
        key = (p["srcFile"], p["srcIndex"])
        if key in seen:
            raise SystemExit(f"{key} xuất hiện ở cả vị trí {seen[key]} và {i}")
        seen[key] = i

    cache = L.SourceCache()
    multi, multi_prov, single, single_prov = [], [], [], []
    for i, (rec, p) in enumerate(balanced):
        orig = cache.get(p["srcFile"], p["srcIndex"])
        rec = _reshuffle(rec, p["uid"])
        p["correctAnswer"] = rec["correctAnswer"]
        multi.append(rec)
        multi_prov.append({"index": i, **p})
        single.append(orig)
        single_prov.append({
            "index": i, "uid": p["uid"], "srcFile": p["srcFile"], "srcIndex": p["srcIndex"],
            "questionID": orig.get("questionID"), "subset": p["subset"],
            "singleCorrect": orig.get("correctAnswer"),
            "singleOptionCount": len([k for k in orig if k.startswith("answer_option")]),
            "multiCorrect": rec["correctAnswer"],
            "multiOptionCount": len([k for k in rec if k.startswith("answer_option")]),
        })

    L.write_out("final_benchmark.json", multi)
    L.write_out("final_benchmark_provenance.json", multi_prov)
    L.write_out("final_benchmark_single.json", single)
    L.write_out("final_benchmark_single_provenance.json", single_prov)

    _report(multi, multi_prov)


def _report(multi, prov):
    n_opts = [len([k for k in r if k.startswith("answer_option")]) for r in multi]
    n_corr = [len(r["correctAnswer"].split(",")) for r in multi]
    print(f"\n  TỔNG: {len(multi)} câu -> final_benchmark.json")
    print(f"  theo nhóm            : {dict(Counter(p['subset'] for p in prov))}")
    print(f"  theo file nguồn      : {dict(Counter(p['srcFile'][:22] for p in prov))}")
    print(f"  số phương án mỗi câu : {dict(sorted(Counter(n_opts).items()))}")
    print(f"  số đáp án đúng/câu   : {dict(sorted(Counter(n_corr).items()))}")
    print(f"  thẩm định vòng 2     : {dict(Counter(p.get('auditStatus') for p in prov))}")

    degen = sum(1 for a, b in zip(n_opts, n_corr) if a == b)
    print(f"  câu MỌI phương án đúng: {degen}"
          f" (chiến lược mù 'chọn hết' ăn {100 * degen / len(multi):.1f}%)")

    # Rò rỉ vị trí: nếu phương án SAI dồn vào một chữ cái thì đoán mù cũng ăn điểm.
    wrong_pos = Counter()
    for r in multi:
        gold = {m.group(1) for m in re.finditer(r"option([A-Z])", r["correctAnswer"])}
        for le in L.LETTERS:
            if r.get("answer_option" + le) and le not in gold:
                wrong_pos[le] += 1
    print(f"  vị trí phương án SAI  : {dict(sorted(wrong_pos.items()))}")
