"""Tầng 4 — áp kết quả LLM vòng 1, dựng 3 file nhiều đáp án, rồi đóng gói vòng 2.

Mọi bản ghi phải qua L.validate() mới được ghi ra. Câu nào hỏng thì vào
data_v2/04_rejected.json kèm lý do, không im lặng bỏ qua.

Chế độ --no-llm: bỏ qua vòng 1, chỉ dùng luật cơ học. Vẫn ra được benchmark
nhưng file 2 sẽ không có phương án nhiễu và file 3 không được thẩm định
chuyên môn — các bản ghi khi đó mang cờ chất lượng tương ứng.
"""
from __future__ import annotations

import random
import re
from collections import Counter
from difflib import SequenceMatcher

import lib2 as L
import s3_jobs as J
import stages as S1

MIN_POOL, MAX_POOL = L.MIN_POOL, L.MAX_POOL
_LEAD_MARK = re.compile(r"^\s*(?:[a-eA-E1-9][.)]\s+|[-*•]\s+)")


def _rng(uid: str) -> random.Random:
    return random.Random(uid)          # seed theo uid -> chạy lại luôn ra cùng thứ tự


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, L.norm_item(a), L.norm_item(b)).ratio()


def _need(stem: str, require: bool) -> dict:
    out = L.read_llm_out(stem)
    if out is None:
        if require:
            raise SystemExit(
                f"Thiếu {L.JOBS_DIR.name}/{stem}.out.jsonl.\n"
                f"Chạy gpu/vllm_batch.py trên máy H100 rồi copy file kết quả về,\n"
                f"hoặc chạy lại với --no-llm để dùng luật cơ học.")
        print(f"  ⚠ không có {stem}.out.jsonl — dùng luật cơ học cho lô này")
        return {}
    print(f"  nạp {stem}.out.jsonl: {len(out)} phán quyết")
    return out


# =============================================================== FILE 1
def _build_file1(require: bool):
    rows = L.read_work("03_sent_file1.json")
    said = _need("r1_negation", require)
    out, prov, bad = [], [], []

    for r in rows:
        v = said.get(r["uid"])
        stem, source = r["fallbackStem"], "co_hoc"
        if v:
            if not v.get("la_phu_dinh") or not v.get("ba_phuong_an_deu_dung"):
                bad.append({"uid": r["uid"], "file": "file1", "reason": "llm_tu_choi"})
                continue
            cand = L.strip_prefix(L.collapse(v.get("cau_hoi_moi") or ""))
            # Chỉ nhận câu LLM viết lại khi nó thật sự sạch: còn dấu phủ định,
            # quá ngắn hay quá dài so với câu gốc đều là dấu hiệu model bịa thêm.
            ok = (len(cand) >= 12
                  and not S1.NEG_DETECT.search(cand)
                  and 0.4 * len(r["question"]) <= len(cand) <= 1.8 * len(r["question"])
                  and not any(cand.lower().startswith(p) for p in ("a.", "b.", "c.", "d.")))
            if ok:
                stem, source = cand, "llm"
        elif require:
            bad.append({"uid": r["uid"], "file": "file1", "reason": "thieu_phan_quyet"})
            continue

        opts = [{"text": o, "correct": i != r["correctIndex"]}
                for i, o in enumerate(r["options"])]
        # Bắt buộc trộn: giữ nguyên thứ tự gốc thì phương án SAI duy nhất hay rơi
        # vào D, và chiến lược mù "chọn A,B,C" ăn điểm cao một cách giả tạo.
        _rng(r["uid"]).shuffle(opts)

        rec = L.pack(stem, opts, r)
        errs = L.validate(rec)
        if errs:
            bad.append({"uid": r["uid"], "file": "file1", "reason": ",".join(errs)})
            continue
        out.append(rec)
        prov.append({"uid": r["uid"], "srcFile": r["srcFile"], "srcIndex": r["srcIndex"],
                     "questionID": r["questionID"], "subset": "file1_ngoai_tru",
                     "negationFamily": r["negationFamily"], "stemSource": source,
                     "originalQuestion": r["question"],
                     "originalCorrect": "option" + r["correctLetter"],
                     "correctAnswer": rec["correctAnswer"],
                     "qualityFlag": "llm-verified" if source == "llm" else "rule-only"})

    L.write_out("final_01_ngoai_tru.json", out)
    L.write_out("final_01_ngoai_tru_provenance.json", prov)
    print(f"  FILE 1: {len(out)}/{len(rows)} câu"
          f"  (câu dẫn do LLM viết lại: {sum(1 for p in prov if p['stemSource'] == 'llm')})")
    return out, prov, bad


# =============================================================== FILE 2
def _valid_distractors(cands, correct: list[str]) -> list[str]:
    keep = []
    for c in cands or []:
        t = L.collapse(_LEAD_MARK.sub("", str(c or "")))
        t = re.sub(r"[\s.;]+$", "", t)
        if not (2 <= len(t) <= 200) or not L.clean_option(t):
            continue
        if any(_similar(t, o) > 0.85 for o in correct + keep):
            continue
        keep.append(t)
    return keep[:2]


def _build_file2(require: bool):
    rows = L.read_work("03_sent_file2.json")
    said = _need("r1_distract", require)
    out, prov, bad = [], [], []
    degen, degen_prov = [], []

    for r in rows:
        v = said.get(r["uid"]) or {}
        extra = _valid_distractors(v.get("nhieu"), r["correctOptions"])

        if not extra:
            # Không có nhiễu hợp lệ -> chỉ xoá phương án meta. Còn 3 phương án và
            # cả 3 đều đúng: chiến lược mù "chọn hết" ăn trọn, nên tách riêng ra
            # khỏi benchmark chính.
            opts = [{"text": o, "correct": True} for o in r["correctOptions"]]
            _rng(r["uid"]).shuffle(opts)
            rec = L.pack(r["questionClean"], opts, r)
            degen.append(rec)
            degen_prov.append({"uid": r["uid"], "srcFile": r["srcFile"],
                               "srcIndex": r["srcIndex"], "questionID": r["questionID"],
                               "subset": "file2_xoa_meta",
                               "removedMetaOption": r["metaText"],
                               "correctAnswer": rec["correctAnswer"],
                               "qualityFlag": "all-options-correct"})
            continue

        opts = [{"text": o, "correct": True} for o in r["correctOptions"]] + \
               [{"text": t, "correct": False} for t in extra]
        _rng(r["uid"]).shuffle(opts)
        rec = L.pack(r["questionClean"], opts, r)
        errs = L.validate(rec)
        if errs:
            bad.append({"uid": r["uid"], "file": "file2", "reason": ",".join(errs)})
            continue
        out.append(rec)
        prov.append({"uid": r["uid"], "srcFile": r["srcFile"], "srcIndex": r["srcIndex"],
                     "questionID": r["questionID"], "subset": "file2_them_nhieu",
                     "removedMetaOption": r["metaText"],
                     "syntheticDistractors": extra,
                     "llmChacChanSai": bool(v.get("chac_chan_sai")),
                     "correctAnswer": rec["correctAnswer"],
                     "qualityFlag": "llm-distractors"})

    L.write_out("final_02_multi.json", out)
    L.write_out("final_02_multi_provenance.json", prov)
    L.write_out("final_02_xoa_meta.json", degen)
    L.write_out("final_02_xoa_meta_provenance.json", degen_prov)
    print(f"  FILE 2: {len(out)}/{len(rows)} câu có nhiễu do LLM sinh"
          f"  ({sum(1 for p in prov if len(p['syntheticDistractors']) == 2)} câu đủ 2 nhiễu)")
    print(f"          {len(degen)} câu chỉ xoá được meta -> để riêng, "
          f"mặc định KHÔNG vào benchmark")
    return out, prov, bad


# =============================================================== FILE 4
def _build_file4(require: bool):
    rows = L.read_work("03_sent_file4.json")
    said = _need("r1_distract_letters", require)
    out, prov, bad = [], [], []

    for r in rows:
        v = said.get(r["uid"]) or {}
        extra = _valid_distractors(v.get("nhieu"), r["correctOptions"] + r["wrongOptions"])

        opts = [{"text": o, "correct": True} for o in r["correctOptions"]] + \
               [{"text": o, "correct": False} for o in r["wrongOptions"]] + \
               [{"text": t, "correct": False} for t in extra]
        if len(opts) < 4:
            # 2 đúng + 1 nhiễu gốc, LLM không cho thêm được gì -> chỉ 3 phương án.
            bad.append({"uid": r["uid"], "file": "file4", "reason": "khong_du_phuong_an"})
            continue
        _rng(r["uid"]).shuffle(opts)

        rec = L.pack(r["questionClean"], opts, r)
        errs = L.validate(rec)
        if errs:
            bad.append({"uid": r["uid"], "file": "file4", "reason": ",".join(errs)})
            continue
        out.append(rec)
        prov.append({"uid": r["uid"], "srcFile": r["srcFile"], "srcIndex": r["srcIndex"],
                     "questionID": r["questionID"], "subset": "file4_ca_ab",
                     "removedMetaOption": r["metaText"], "metaLetters": r["metaLetters"],
                     "originalDistractors": r["wrongOptions"],
                     "syntheticDistractors": extra,
                     "llmChacChanSai": bool(v.get("chac_chan_sai")),
                     "correctAnswer": rec["correctAnswer"],
                     "qualityFlag": "llm-distractors" if extra else "original-distractors-only"})

    L.write_out("final_04_ca_ab.json", out)
    L.write_out("final_04_ca_ab_provenance.json", prov)
    print(f"  FILE 4: {len(out)}/{len(rows)} câu"
          f"  (LLM thêm nhiễu cho {sum(1 for p in prov if p['syntheticDistractors'])} câu)")
    return out, prov, bad


# =============================================================== FILE 3
def _build_file3(require: bool):
    rows = L.read_work("03_sent_file3.json")
    said = _need("r1_pool", require)
    out, prov, bad = [], [], []

    for r in rows:
        v = said.get(r["uid"])
        if v is None:
            if require:
                bad.append({"uid": r["uid"], "file": "file3", "reason": "thieu_phan_quyet"})
                continue
            v = {"tach_duoc": True, "muc_sai_thuc_ra_dung": [], "do_tin_cay": "khong_tham_dinh"}
        if not v.get("tach_duoc"):
            bad.append({"uid": r["uid"], "file": "file3", "reason": "llm_noi_khong_tach_duoc"})
            continue

        pool, correct = r["pool"], set(r["poolCorrect"])
        # LLM chỉ được phép XOÁ mục nhiễu mà nó cho là thực ra đúng — không được
        # thêm mục vào tập đáp án. Tập đáp án luôn suy ra từ đề gốc.
        remove = {i for i in v.get("muc_sai_thuc_ra_dung") or []
                  if isinstance(i, int) and 0 <= i < len(pool) and i not in correct}
        kept_idx = [i for i in range(len(pool)) if i not in remove]
        new_pool = [pool[i] for i in kept_idx]
        new_correct = [k for k, i in enumerate(kept_idx) if i in correct]

        if not (MIN_POOL <= len(new_pool) <= MAX_POOL):
            bad.append({"uid": r["uid"], "file": "file3", "reason": "pool_sai_kich_thuoc"})
            continue
        if len(new_correct) < 2 or len(new_correct) >= len(new_pool):
            bad.append({"uid": r["uid"], "file": "file3", "reason": "tap_dap_an_khong_hop_le"})
            continue

        # Cắt xuống đúng TARGET_OPTIONS phương án: giữ NGUYÊN mọi đáp án đúng,
        # bỏ bớt nhiễu. Cắt ở đây chứ không phải lúc lọc, để LLM vẫn nhìn thấy
        # toàn bộ pool khi phán xét và chỉ số nó trả về vẫn khớp.
        dropped = []
        if len(new_pool) > L.TARGET_OPTIONS:
            cset = set(new_correct)
            wrong = [k for k in range(len(new_pool)) if k not in cset]
            keep_w = _rng(r["uid"] + "|trim").sample(
                wrong, L.TARGET_OPTIONS - len(new_correct))
            sel = sorted(cset | set(keep_w))
            dropped = [new_pool[k] for k in wrong if k not in keep_w]
            new_correct = [i for i, k in enumerate(sel) if k in cset]
            new_pool = [new_pool[k] for k in sel]

        opts = [{"text": t, "correct": k in set(new_correct)}
                for k, t in enumerate(new_pool)]
        # Thứ tự pool là thứ tự xuất hiện trong đề gốc -> các mục của đáp án đúng
        # dồn về đầu. Phải trộn, nếu không "chọn 3 ô đầu" thành mốc mù rất mạnh.
        _rng(r["uid"]).shuffle(opts)

        rec = L.pack(r["questionClean"], opts, r)
        errs = L.validate(rec)
        if errs:
            bad.append({"uid": r["uid"], "file": "file3", "reason": ",".join(errs)})
            continue
        out.append(rec)
        prov.append({"uid": r["uid"], "srcFile": r["srcFile"], "srcIndex": r["srcIndex"],
                     "questionID": r["questionID"], "subset": "file3_tach_dau_phay",
                     "originalOptions": r["options"],
                     "originalCorrect": "option" + r["correctLetter"],
                     "removedItems": [pool[i] for i in sorted(remove)],
                     "trimmedDistractors": dropped,
                     "overlap": r["overlap"], "llmConfidence": v.get("do_tin_cay"),
                     "correctAnswer": rec["correctAnswer"],
                     "qualityFlag": "llm-screened" if said else "rule-only"})

    L.write_out("final_03_multi.json", out)
    L.write_out("final_03_multi_provenance.json", prov)
    removed = sum(len(p["removedItems"]) for p in prov)
    trimmed = sum(1 for p in prov if p["trimmedDistractors"])
    print(f"  FILE 3: {len(out)}/{len(rows)} câu"
          f"  (LLM gỡ {removed} mục nhiễu thực ra đúng;"
          f" cắt bớt nhiễu ở {trimmed} câu)")
    return out, prov, bad


# =============================================================== vòng 2
def _make_audit(built):
    jobs = []
    for rec, p in built:
        letters = [le for le in L.LETTERS if rec.get("answer_option" + le)]
        gold = {m.group(1) for m in re.finditer(r"option([A-Z])", rec["correctAnswer"])}
        lines = "\n".join(
            f"{i}. {rec['answer_option' + le]}"
            f"   [{'ĐÚNG' if le in gold else 'SAI'}]"
            for i, le in enumerate(letters))
        jobs.append({"id": p["uid"],
                     "prompt": J.AUDIT_PROMPT.format(question=rec["question"], options=lines)})
    L.write_jobs("r2_audit", jobs, J.AUDIT_SCHEMA)


# =============================================================== điều phối
def s4_apply(require_llm: bool = True):
    print(f"Tầng 4 — dựng 3 file nhiều đáp án"
          f"{'' if require_llm else '  [CHẾ ĐỘ --no-llm]'}")
    o1, p1, b1 = _build_file1(require_llm)
    o2, p2, b2 = _build_file2(require_llm)
    o4, p4, b4 = _build_file4(require_llm)
    o3, p3, b3 = _build_file3(require_llm)

    bad = b1 + b2 + b3 + b4
    L.write_work("04_rejected.json", bad)

    built = (list(zip(o1, p1)) + list(zip(o2, p2))
             + list(zip(o3, p3)) + list(zip(o4, p4)))
    _make_audit(built)

    print(f"\n  tổng dựng được : {len(built)}")
    print(f"  bị loại        : {len(bad)} {dict(Counter(b['reason'][:34] for b in bad))}")
    print(f"\n  Bước tiếp theo (khuyến nghị, để thẩm định lại toàn bộ) — trên H100:")
    print(f"    python gpu/vllm_batch.py llm_jobs/r2_audit.jsonl "
          f"--model Qwen/Qwen3-32B-FP8 --max-tokens 128")
    print(f"  Rồi: python v2/run.py build")
