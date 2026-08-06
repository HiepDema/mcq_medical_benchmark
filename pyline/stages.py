"""12 tầng của pipeline MCQ — bản Python, port 1:1 từ pipeline/*.js."""
from __future__ import annotations

import random
import re
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

import lib as L

LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def fixed(x: float, d: int):
    """Bắt chước Number(x.toFixed(d)) của JS: làm tròn nửa lên, số nguyên trả về int
    (để JSON ra "1" chứ không phải "1.0")."""
    v = float(Decimal(x).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
    return int(v) if v == int(v) else v


# ============================================================ 01 — làm sạch
def stage01_clean():
    raw = L.read_raw_data()
    print(f"Tầng 1 — làm sạch: đọc {len(raw)} bản ghi từ raw_data.json")
    clean, dropped, duplicates, seen = [], [], [], {}

    for i, q in enumerate(raw):
        def drop(reason):
            dropped.append({"sourceIndex": i, "reason": reason, "record": q})

        question = L.collapse(q.get("question") or "")
        if not question:
            drop("empty_question"); continue

        slots = [{"letter": le, "text": L.collapse(q.get("answer_option" + le) or "")}
                 for le in "ABCDE"]
        slots = [s for s in slots if s["text"]]
        if len(slots) < 2:
            drop("too_few_options"); continue

        m = re.search(r"option([A-E])", str(q.get("correctAnswer") or ""), re.I)
        if not m:
            drop("unparseable_correctAnswer"); continue
        letter = m.group(1).upper()
        idx = next((k for k, s in enumerate(slots) if s["letter"] == letter), -1)
        if idx == -1:
            drop("correct_option_is_empty"); continue

        options = [s["text"] for s in slots]
        uid = L.uid_of(question, options)
        if uid in seen:
            duplicates.append({"uid": uid, "sourceIndex": i,
                               "keptSourceIndex": seen[uid], "record": q})
            continue
        seen[uid] = i

        clean.append({
            "uid": uid, "sourceIndex": i, "sourceQuestionID": q.get("questionID"),
            "question": question, "questionClean": L.strip_prefix(question),
            "options": options, "optionLetters": [s["letter"] for s in slots],
            "optionCount": len(options), "correctIndex": idx, "correctLetter": letter,
            "medicalTopic": q.get("medicalTopic") or [],
            "difficultLevel": q.get("difficultLevel"),
        })

    L.write_json("01_clean.json", clean)
    L.write_json("01_duplicates.json", duplicates)
    L.write_json("01_dropped.json", dropped)
    print(f"\n  giữ lại   : {len(clean)}\n  trùng lặp : {len(duplicates)}"
          f"\n  loại bỏ   : {len(dropped)} {dict(Counter(d['reason'] for d in dropped))}")
    print(f"  số đáp án : {dict(Counter(r['optionCount'] for r in clean))}")


# ========================================================== 02 — phân loại
def stage02_classify():
    clean = L.read_json("01_clean.json")
    print(f"Tầng 2 — phân loại: {len(clean)} bản ghi")
    out = []

    for r in clean:
        def tag(group, reason, extra=None):
            return {**r, "group": group, "reason": reason, **(extra or {})}

        if r["optionCount"] < 4:
            out.append(tag("none", "insufficient_options")); continue

        metas = [{"i": i, "meta": L.meta_kind(o)} for i, o in enumerate(r["options"])]
        metas = [x for x in metas if x["meta"]]
        if metas:
            hit = next((x for x in metas if x["i"] == r["correctIndex"]), None)
            if not hit:
                out.append(tag("none", "meta_is_distractor")); continue
            if hit["meta"]["kind"] == "ALL_WRONG":
                out.append(tag("none", "meta_all_wrong")); continue
            out.append(tag("meta", hit["meta"]["kind"], {
                "metaIndices": [x["i"] for x in metas],
                "metaLetters": hit["meta"].get("letters"),
            })); continue

        if all(L.is_ref_only_option(o) for o in r["options"]):
            stmts = L.extract_numbered_statements(r["question"])
            if stmts and len(stmts) >= 2:
                out.append(tag("combination", "numbered_stem", {"statements": stmts}))
            else:
                out.append(tag("none", "refs_without_stem"))
            continue

        parts = [L.split_items(o) for o in r["options"]]
        if not all(len(p) >= 2 for p in parts):
            out.append(tag("none", "not_all_lists")); continue

        flat = [it for p in parts for it in p]
        surface = {}
        for it in flat:
            surface.setdefault(L.norm_item(it), it)
        union = list(surface.keys())

        overlap = fixed(1 - len(union) / len(flat), 3)
        numeric_frac = fixed(sum(1 for u in union if L.is_numericish(u)) / len(union), 2)
        all_roman = all(L.is_roman(u) for u in union)

        if numeric_frac > 0.6 and not all_roman:
            out.append(tag("none", "numeric_pool",
                           {"overlap": overlap, "numericFrac": numeric_frac})); continue
        if overlap < 0.2:
            out.append(tag("none", "low_overlap",
                           {"overlap": overlap, "numericFrac": numeric_frac})); continue

        out.append(tag("pool", "overlap_high" if overlap >= 0.4 else "overlap_medium", {
            "poolType": "roman" if all_roman else "lexical",
            "overlap": overlap, "numericFrac": numeric_frac,
            "pool": [surface[k] for k in union],
            "optionItems": [[union.index(L.norm_item(it)) for it in p] for p in parts],
        }))

    L.write_json("02_classified.json", out)
    c = Counter(f"{r['group']}:{r['reason']}" for r in out)
    print("\n  Phân bố nhóm:")
    for k, v in c.most_common():
        print(f"    {v:>5}  {k}")
    conv = sum(1 for r in out if r["group"] != "none")
    print(f"\n  Tổng ứng viên chuyển đổi được: {conv} ({100*conv/len(out):.1f}%)")


# ================================================ 03 — chuyển đổi meta
def stage03_convert_meta():
    rows = [r for r in L.read_json("02_classified.json") if r["group"] == "meta"]
    print(f"Tầng 3 — chuyển đổi meta-option: {len(rows)} ứng viên")
    usable, degenerate, rejected = [], [], []

    for r in rows:
        def reject(reason):
            rejected.append({"uid": r["uid"], "reason": reason,
                             "question": r["question"], "options": r["options"]})

        keep = [{"text": t, "i": i, "letter": r["optionLetters"][i]}
                for i, t in enumerate(r["options"]) if i not in r["metaIndices"]]
        if len(keep) < 2:
            reject("too_few_non_meta_options"); continue

        if r["reason"] == "ALL_CORRECT":
            correct = list(range(len(keep)))
        else:
            wanted = [c.upper() for c in (r.get("metaLetters") or [])]
            idx = [next((k for k, o in enumerate(keep) if o["letter"] == le), -1) for le in wanted]
            if any(k == -1 for k in idx):
                reject("letter_points_to_missing_or_meta_option"); continue
            correct = sorted(set(idx))
            if len(correct) < 2:
                reject("fewer_than_two_letters"); continue

        item = {
            "uid": r["uid"], "sourceQuestionID": r["sourceQuestionID"],
            "sourceIndex": r["sourceIndex"], "question": r["questionClean"],
            "options": [o["text"] for o in keep], "correctAnswers": correct,
            "answerCount": len(correct), "derivedFrom": "meta-option",
            "metaKind": r["reason"], "originalCorrect": "option" + r["correctLetter"],
            "originalOptions": r["options"], "confidence": "high",
            "medicalTopic": r["medicalTopic"], "difficultLevel": r["difficultLevel"],
        }
        if len(correct) >= len(keep):
            item["qualityFlag"] = "all-options-correct"
            item["confidence"] = "review"
            degenerate.append(item)
        else:
            usable.append(item)

    L.write_json("03_multi_meta.json", usable)
    L.write_json("03_meta_all_correct.json", degenerate)
    L.write_json("03_meta_rejected.json", rejected)
    print(f"\n  dùng được ngay          : {len(usable)}")
    print(f"  toàn bộ đáp án đều đúng : {len(degenerate)}")
    print(f"  loại                    : {len(rejected)} {dict(Counter(x['reason'] for x in rejected))}")


# ========================================== 04 — chuyển đổi câu tổ hợp
TAIL = re.compile(r"\s*(hãy\s+)?(chọn|tìm|cho biết)\s+(đáp án|câu|phương án|tổ hợp|ý)\b.*$", re.I)


def _nums_in(s: str) -> list[int]:
    return [int(m.group(0)) for m in re.finditer(r"\d{1,2}", str(s))]


def stage04_convert_combination():
    rows = [r for r in L.read_json("02_classified.json") if r["group"] == "combination"]
    print(f"Tầng 4 — chuyển đổi câu tổ hợp: {len(rows)} ứng viên")
    usable, rejected = [], []

    for r in rows:
        def reject(reason):
            rejected.append({"uid": r["uid"], "reason": reason,
                             "question": r["question"], "options": r["options"]})

        stmts = [{"n": s["n"],
                  "text": re.sub(r"[.\s]+$", "", TAIL.sub("", L.collapse(s["text"])))}
                 for s in r["statements"]]
        if any(not s["text"] for s in stmts):
            reject("empty_statement_text"); continue
        if len(stmts) < 3:
            reject("too_few_usable_statements"); continue

        numbers = [s["n"] for s in stmts]
        if len(set(numbers)) != len(numbers):
            reject("duplicate_statement_numbers"); continue

        referenced = [n for o in r["options"] for n in _nums_in(o)]
        if not referenced or any(n not in numbers for n in referenced):
            reject("option_references_unknown_statement"); continue

        correct_nums = list(dict.fromkeys(_nums_in(r["options"][r["correctIndex"]])))
        if len(correct_nums) < 2:
            reject("correct_option_selects_fewer_than_two"); continue
        if len(correct_nums) >= len(stmts):
            reject("correct_option_selects_everything"); continue

        marker = f"({stmts[0]['n']})"
        stem = L.collapse(r["question"][: r["question"].find(marker)]) or r["questionClean"]

        usable.append({
            "uid": r["uid"], "sourceQuestionID": r["sourceQuestionID"],
            "sourceIndex": r["sourceIndex"], "question": L.strip_prefix(stem),
            "options": [s["text"] for s in stmts],
            "correctAnswers": sorted(numbers.index(n) for n in correct_nums),
            "answerCount": len(correct_nums), "derivedFrom": "combination",
            "originalCorrect": "option" + r["correctLetter"],
            "originalOptions": r["options"], "confidence": "high",
            "medicalTopic": r["medicalTopic"], "difficultLevel": r["difficultLevel"],
        })

    L.write_json("04_multi_combination.json", usable)
    L.write_json("04_combination_rejected.json", rejected)
    print(f"\n  dùng được : {len(usable)}")
    print(f"  loại      : {len(rejected)} {dict(Counter(x['reason'] for x in rejected))}")


# ============================================ 05 — đóng gói nhóm pool
def stage05_prepare_pool():
    rows = [r for r in L.read_json("02_classified.json") if r["group"] == "pool"]
    print(f"Tầng 5 — đóng gói nhóm pool: {len(rows)} ứng viên")
    candidates, rejected = [], []

    for r in rows:
        def reject(reason):
            rejected.append({"uid": r["uid"], "reason": reason, "question": r["question"],
                             "options": r["options"], "pool": r["pool"]})

        proposed = sorted(set(r["optionItems"][r["correctIndex"]]))
        if len(r["pool"]) < 3:
            reject("pool_too_small"); continue
        if len(proposed) < 2:
            reject("correct_option_has_one_item"); continue
        if len(proposed) >= len(r["pool"]):
            reject("correct_option_covers_whole_pool"); continue

        warnings = []
        if max(len(p) for p in r["pool"]) > 120:
            warnings.append("long_pool_item")
        if len({L.norm_item(o) for o in r["options"]}) < len(r["options"]):
            warnings.append("duplicate_source_options")
        if r["numericFrac"] > 0.3:
            warnings.append("mixed_numeric_items")

        candidates.append({
            "uid": r["uid"], "sourceQuestionID": r["sourceQuestionID"],
            "sourceIndex": r["sourceIndex"], "question": r["questionClean"],
            "pool": r["pool"], "proposedCorrect": proposed, "optionItems": r["optionItems"],
            "originalOptions": r["options"], "originalCorrect": "option" + r["correctLetter"],
            "poolType": r["poolType"],
            "tier": "high" if r["reason"] == "overlap_high" else "medium",
            "overlap": r["overlap"], "warnings": warnings,
            "medicalTopic": r["medicalTopic"], "difficultLevel": r["difficultLevel"],
        })

    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["uid", "decision", "pool", "correctAnswers", "confidence"],
        "properties": {
            "uid": {"type": "string"},
            "decision": {"type": "string", "enum": ["accept", "reject"],
                         "description": "reject khi câu không tách được thành nhiều đáp án độc lập"},
            "rejectReason": {"type": "string"},
            "pool": {"type": "array", "minItems": 3, "maxItems": 24,
                     "items": {"type": "string"},
                     "description": "Danh sách mục đã chuẩn hoá, gộp các mục trùng khái niệm. Giữ nguyên thuật ngữ y khoa gốc."},
            "correctAnswers": {"type": "array", "minItems": 1,
                               "items": {"type": "integer", "minimum": 0},
                               "description": "Chỉ số trong pool của các mục đúng"},
            "exhaustive": {"type": "boolean",
                           "description": "true nếu đáp án đúng gốc là liệt kê đầy đủ, nên các mục còn lại chắc chắn là nhiễu"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
    }

    L.write_json("05_pool_candidates.json", candidates)
    L.write_json("05_pool_rejected.json", rejected)
    L.write_json("05_llm_schema.json", schema)
    print(f"\n  sẵn sàng cho LLM : {len(candidates)}")
    print(f"  loại trước LLM   : {len(rejected)} {dict(Counter(x['reason'] for x in rejected))}")


# ======================================== 06 — gộp & kiểm tra bất biến
def stage06_merge_validate():
    ok, bad, seen = [], [], set()
    for f in ("03_multi_meta.json", "04_multi_combination.json"):
        for it in L.read_json(f):
            errs, n, c = [], len(it["options"]), it["correctAnswers"]
            if not isinstance(c, list) or len(c) < 2:
                errs.append("fewer_than_two_correct")
            if len(c) >= n:
                errs.append("all_options_correct")
            if any((not isinstance(i, int)) or i < 0 or i >= n for i in c):
                errs.append("index_out_of_range")
            if len(set(c)) != len(c):
                errs.append("duplicate_correct_index")
            if any(not str(o).strip() for o in it["options"]):
                errs.append("empty_option")
            if len({L.norm_item(o) for o in it["options"]}) != n:
                errs.append("duplicate_options")
            if it["answerCount"] != len(c):
                errs.append("answerCount_mismatch")
            if it["uid"] in seen:
                errs.append("duplicate_uid")
            seen.add(it["uid"])
            (bad if errs else ok).append({**it, "violations": errs} if errs else it)

    ok.sort(key=lambda x: x["sourceIndex"])
    L.write_json("06_multi_ready.json", ok)
    L.write_json("06_validation_failures.json", bad)
    summary = {
        "source": {"file": "raw_data.json", "records": 10242},
        "stages": {
            "clean": {"kept": len(L.read_json("01_clean.json")),
                      "duplicates": len(L.read_json("01_duplicates.json")),
                      "dropped": len(L.read_json("01_dropped.json"))},
            "ruleConverted": {"ready": len(ok), "failedValidation": len(bad),
                              "allOptionsCorrect": len(L.read_json("03_meta_all_correct.json"))},
            "awaitingLLM": {"poolCandidates": len(L.read_json("05_pool_candidates.json"))},
        },
    }
    L.write_json("06_summary.json", summary)
    print(f"Tầng 6 — gộp & kiểm tra\n\n  đạt bất biến : {len(ok)} "
          f"{dict(Counter(x['derivedFrom'] for x in ok))}\n  vi phạm      : {len(bad)}")
    print(f"  số đáp án đúng mỗi câu: {dict(Counter(x['answerCount'] for x in ok))}")


# ============================================ 07 — gom nhóm để kiểm tra
NEGATION = [
    ("A. ngoại trừ / trừ", "strong", re.compile(r"ngoại\s*trừ|,\s*trừ\s*:?\s*$|\btrừ\s*:", re.I)),
    ("B. chọn câu sai", "strong", re.compile(
        r"(câu|ý|đáp án|phương án|điều|nhận định|khẳng định)\s+nào\s+(sau đây\s+)?(là\s+)?sai"
        r"|nào\s+sau\s+đây\s+sai|chọn\s+(câu\s+)?sai|\bsai\s*(là|\?|:)?\s*$", re.I)),
    ("C. không đúng", "strong", re.compile(r"không\s+(đúng|chính xác|phù hợp)", re.I)),
    ("D. không phải", "strong", re.compile(r"không\s+phải\s+(là\s+)?", re.I)),
    ("E. \"không\" khác", "weak", re.compile(rf"{L.JB}không{L.JB}", re.I)),
]
ORDER_STEM = re.compile(r"thứ tự|lần lượt|tương ứng|theo trình tự", re.I)


def _base(r):
    return {
        "uid": r["uid"], "sourceIndex": r["sourceIndex"],
        "sourceQuestionID": r["sourceQuestionID"], "question": r["question"],
        "options": {le: r["options"][i] for i, le in enumerate(r["optionLetters"])},
        "correctAnswer": r["correctLetter"], "correctText": r["options"][r["correctIndex"]],
        "optionCount": r["optionCount"], "pipelineGroup": f"{r['group']}:{r['reason']}",
        "medicalTopic": r["medicalTopic"], "difficultLevel": r["difficultLevel"],
    }


def stage07_inspect_groups():
    rows = L.read_json("02_classified.json")
    print(f"Tầng 7 — gom nhóm để kiểm tra: {len(rows)} bản ghi")

    negation = []
    for r in rows:
        if r["optionCount"] < 4:
            continue
        for family, strength, rx in NEGATION:
            m = rx.search(r["question"])
            if m:
                negation.append({**_base(r), "negationFamily": family,
                                 "negationStrength": strength, "matchedText": m.group(0).strip()})
                break
    negation.sort(key=lambda x: (x["negationFamily"], x["sourceIndex"]))

    meta = []
    for r in rows:
        if r["optionCount"] < 4:
            continue
        hits = [{"i": i, "letter": r["optionLetters"][i], "text": o, "meta": L.meta_kind(o)}
                for i, o in enumerate(r["options"])]
        hits = [h for h in hits if h["meta"]]
        if not hits:
            continue
        on_correct = next((h for h in hits if h["i"] == r["correctIndex"]), None)
        meta.append({**_base(r),
                     "metaOptions": [{"letter": h["letter"], "text": h["text"],
                                      "kind": h["meta"]["kind"],
                                      "letters": h["meta"].get("letters")} for h in hits],
                     "metaIsCorrectAnswer": bool(on_correct),
                     "metaKindOnCorrect": on_correct["meta"]["kind"] if on_correct else None})
    meta.sort(key=lambda x: (not x["metaIsCorrectAnswer"], x["sourceIndex"]))

    pool = []
    for r in rows:
        if r["group"] != "pool":
            continue
        items = [(le, [r["pool"][k] for k in r["optionItems"][i]])
                 for i, le in enumerate(r["optionLetters"])]
        signals = []
        if any(len({L.norm_item(x) for x in it}) != len(it) for _, it in items):
            signals.append("duplicate_item_within_option")
        if ORDER_STEM.search(r["question"]):
            signals.append("order_words_in_stem")
        pool.append({**_base(r), "pool": r["pool"], "itemsPerOption": dict(items),
                     "itemsInCorrectAnswer": [r["pool"][k] for k in r["optionItems"][r["correctIndex"]]],
                     "overlap": r["overlap"],
                     "tier": "high" if r["reason"] == "overlap_high" else "medium",
                     "poolType": r["poolType"], "suspectOrderedSequence": bool(signals),
                     "orderSignals": signals})
    pool.sort(key=lambda x: (-x["overlap"], x["sourceIndex"]))

    L.write_json("07_inspect_negation.json", negation)
    L.write_json("07_inspect_meta.json", meta)
    L.write_json("07_inspect_pool.json", pool)
    print(f"\n1) phủ định : {len(negation)} {dict(Counter(x['negationFamily'] for x in negation))}")
    print(f"2) meta     : {len(meta)} (meta là đáp án đúng: "
          f"{sum(1 for x in meta if x['metaIsCorrectAnswer'])})")
    print(f"3) pool     : {len(pool)} (nghi dãy có thứ tự: "
          f"{sum(1 for x in pool if x['suspectOrderedSequence'])})")


# ============================================== 08 — luật dấu phẩy
def stage08_comma_rule():
    rows = L.read_json("01_clean.json")
    hit = [r for r in rows if all("," in o for o in r["options"])]
    print(f"Tầng 8 — luật dấu phẩy: {len(hit)}/{len(rows)} câu có >=1 dấu phẩy ở MỌI phương án")

    out = []
    for r in hit:
        items = [L.split_items(o) for o in r["options"]]
        flat = [x for p in items for x in p]
        surface = {}
        for it in flat:
            surface.setdefault(L.norm_item(it), it)
        pool = list(surface.values())

        overlap = fixed(1 - len(pool) / len(flat), 3)
        numeric_frac = fixed(sum(1 for p in pool if L.is_numericish(p)) / len(pool), 2)
        all_roman = all(L.is_roman(p) for p in pool)
        dup = any(len({L.norm_item(x) for x in p}) != len(p) for p in items)

        verdict, reason = "keep", None
        if not all(len(p) >= 2 for p in items):
            verdict, reason = "drop", "B2_dấu_phẩy_là_thập_phân"
        elif numeric_frac > 0.6 and not all_roman:
            verdict, reason = "drop", "B3_pool_toàn_số"
        elif overlap < 0.2:
            verdict, reason = "drop", "B4_overlap_thấp"
        elif dup or ORDER_STEM.search(r["question"]):
            verdict, reason = "drop", "B5_dãy_có_thứ_tự"

        out.append({
            "uid": r["uid"], "sourceIndex": r["sourceIndex"],
            "sourceQuestionID": r["sourceQuestionID"], "question": r["question"],
            "options": {le: r["options"][i] for i, le in enumerate(r["optionLetters"])},
            "correctAnswer": r["correctLetter"], "correctText": r["options"][r["correctIndex"]],
            "optionCount": r["optionCount"], "verdict": verdict, "dropReason": reason,
            "itemsPerOption": {le: items[i] for i, le in enumerate(r["optionLetters"])},
            "itemsInCorrectAnswer": items[r["correctIndex"]], "pool": pool,
            "overlap": overlap, "numericFrac": numeric_frac,
            "hasDuplicateItemInOption": dup,
            "orderWordsInStem": bool(ORDER_STEM.search(r["question"])),
            "medicalTopic": r["medicalTopic"], "difficultLevel": r["difficultLevel"],
        })

    rank = {"keep": 0, "drop": 1}
    out.sort(key=lambda x: (rank[x["verdict"]], str(x["dropReason"]), -x["overlap"]))
    L.write_json("08_comma_rule.json", out)
    keep = [x for x in out if x["verdict"] == "keep"]
    print(f"\n  giữ lại : {len(keep)} ({100*len(keep)/len(out):.0f}%)")
    print(f"  bị loại : {len(out)-len(keep)} "
          f"{dict(Counter(x['dropReason'] for x in out if x['dropReason']))}")


# ================================================= 09 — FILE 1 phủ định
REWRITES = [
    ("A. ngoại trừ", re.compile(r"\s*[,;.]?\s*(ngoại|loại)\s*trừ\s*[:.]?\s*$", re.I), ":"),
    ("A. trừ", re.compile(r"\s*[,;.]?\s*trừ\s*[:.]?\s*$", re.I), ":"),
    ("B. chọn sai", re.compile(r"chọn\s+(câu|ý|phương án|đáp án)?\s*sai", re.I), "Chọn các câu đúng"),
    ("B. nào sai", re.compile(rf"{L.JB}sai{L.JB}(?=\s*[:.?]?\s*$)", re.I), "đúng"),
    ("B. nào sau đây sai", re.compile(r"(nào\s+(sau\s+đây\s+)?(là\s+)?)sai", re.I), r"\1đúng"),
    ("C. không đúng", re.compile(r"không\s+(đúng|chính xác|phù hợp)", re.I), r"\1"),
    ("D. không phải", re.compile(r"không\s+phải\s+(là\s+)?", re.I), r"\1"),
]
NEG_DETECT = re.compile(
    r"ngoại\s*trừ|loại\s*trừ|,\s*trừ\s*:?\s*$|chọn\s+(câu|ý|phương án|đáp án)?\s*sai"
    r"|(câu|ý|phương án|đáp án|nhận định|khẳng định|điều)\s+nào\s+(sau\s+đây\s+)?(là\s+)?sai"
    r"|nào\s+sau\s+đây\s+sai|không\s+(đúng|chính xác|phù hợp)|không\s+phải", re.I)


def stage09_file1_negation():
    raw = L.read_raw_data()
    clean = L.read_json("01_clean.json")
    out, prov, skipped = [], [], []

    for r in clean:
        if r["optionCount"] < 4 or not NEG_DETECT.search(r["question"]):
            continue
        rewritten = family = None
        for name, rx, rep in REWRITES:
            if rx.search(r["question"]):
                s = L.collapse(rx.sub(rep, r["question"], count=0))
                s = re.sub(r"\s+([:.?])", r"\1", s)
                rewritten = re.sub(r"[:\s]*:$", ":", s)
                family = name
                break
        if not rewritten or len(rewritten) < 8:
            skipped.append({"uid": r["uid"], "question": r["question"], "reason": "no_clean_rewrite"})
            continue

        # Đảo tập đáp án: mọi phương án TRỪ đáp án gốc.
        # Phải TRỘN vị trí: giữ nguyên thứ tự gốc thì phương án sai duy nhất hay
        # nằm ở D (ngân hàng đề chuộng đáp án D), khiến "luôn chọn A,B,C" ăn 40%.
        items = [{"text": o, "correct": i != r["correctIndex"]}
                 for i, o in enumerate(r["options"])]
        random.Random(r["sourceIndex"]).shuffle(items)

        src = raw[r["sourceIndex"]]
        rec = {
            "question": L.strip_prefix(rewritten),
            "correctAnswer": ", ".join("option" + LETTERS[k]
                                       for k, o in enumerate(items) if o["correct"]),
            "medicalTopic": src.get("medicalTopic"), "difficultLevel": src.get("difficultLevel"),
            "regularFormat": src.get("regularFormat"), "questionID": src.get("questionID"),
        }
        for k, o in enumerate(items):
            rec["answer_option" + LETTERS[k]] = o["text"]
        out.append(rec)
        prov.append({"questionID": src.get("questionID"), "uid": r["uid"],
                     "sourceIndex": r["sourceIndex"], "negationFamily": family,
                     "originalQuestion": r["question"],
                     "originalCorrect": "option" + r["correctLetter"],
                     "newCorrect": rec["correctAnswer"]})

    L.write_json("final_01_ngoai_tru.json", out)
    L.write_json("final_01_ngoai_tru_provenance.json", prov)
    L.write_json("final_01_ngoai_tru_skipped.json", skipped)
    print(f"FILE 1 — câu phủ định: {len(out)} câu")
    print(f"  theo luật viết lại : {dict(Counter(p['negationFamily'] for p in prov))}")
    print(f"  bỏ qua             : {len(skipped)}")


# ==================================================== 10 — FILE 2 meta
def stage10_file2_meta():
    raw = L.read_raw_data()
    clean = L.read_json("01_clean.json")
    out, prov = [], []
    for r in clean:
        if r["optionCount"] < 4:
            continue
        meta = L.meta_kind(r["options"][r["correctIndex"]])
        if not meta or meta["kind"] == "ALL_WRONG":
            continue
        out.append(raw[r["sourceIndex"]])
        prov.append({"questionID": r["sourceQuestionID"], "uid": r["uid"],
                     "sourceIndex": r["sourceIndex"], "metaKind": meta["kind"],
                     "metaLetters": meta.get("letters"),
                     "correctAnswer": "option" + r["correctLetter"],
                     "metaText": r["options"][r["correctIndex"]]})
    L.write_json("final_02_tat_ca_deu_dung.json", out)
    L.write_json("final_02_tat_ca_deu_dung_provenance.json", prov)
    print(f"FILE 2 — giữ nguyên bản gốc: {len(out)} câu "
          f"{dict(Counter(p['metaKind'] for p in prov))}")


# ============================================== 11 — FILE 3 đầu vào LLM
def stage11_file3_input():
    clean = L.read_json("01_clean.json")
    hit = [r for r in clean if all("," in o for o in r["options"])]
    items = [{
        "uid": r["uid"], "sourceIndex": r["sourceIndex"],
        "payload": {
            "question": r["question"],
            "options": {le: r["options"][i] for i, le in enumerate(r["optionLetters"])},
            "correctAnswer": "option" + r["correctLetter"],
        },
    } for r in hit]
    L.write_json("11_file3_llm_input.json", items)
    print(f"FILE 3 bước 1 — lọc dấu phẩy: {len(items)} câu")


# ============================================= 12 — FILE 3 đầu ra cuối
def stage12_file3_output(assume_yes: bool = False):
    raw = L.read_raw_data()
    clean = {r["uid"]: r for r in L.read_json("01_clean.json")}
    inp = L.read_json("11_file3_llm_input.json")

    if assume_yes:
        print('CHẾ ĐỘ THỬ: coi mọi câu là "CÓ" — chỉ để kiểm tra logic biến đổi.\n')
        verdicts = [{"uid": x["uid"], "verdict": "CÓ"} for x in inp]
    else:
        p = L.DATA_DIR / "12_file3_llm_verdicts.json"
        if not p.exists():
            print("Chưa có data/12_file3_llm_verdicts.json.")
            print("Chạy `python lambda/run_remote.py` để lấy kết quả từ Qwen3-VL,")
            print("hoặc chạy lại với --assume-yes để thử logic biến đổi.")
            raise SystemExit(1)
        verdicts = L.read_json("12_file3_llm_verdicts.json")

    said = {v["uid"]: v["verdict"] for v in verdicts}
    out, prov, rejected = [], [], []

    for item in inp:
        if said.get(item["uid"]) != "CÓ":
            continue
        r = clean[item["uid"]]

        def reject(reason):
            rejected.append({"uid": item["uid"], "reason": reason,
                             "question": r["question"], "options": r["options"]})

        parts = [L.split_items(o) for o in r["options"]]
        surface = {}
        for it in (x for p in parts for x in p):
            surface.setdefault(L.norm_item(it), it)
        pool = list(surface.values())
        norm_pool = [L.norm_item(p) for p in pool]
        correct_idx = sorted({norm_pool.index(L.norm_item(it))
                              for it in parts[r["correctIndex"]]
                              if L.norm_item(it) in norm_pool})

        if len(pool) < 3:
            reject("pool_too_small"); continue
        if len(pool) > len(LETTERS):
            reject("pool_too_large"); continue
        if len(correct_idx) < 2:
            reject("fewer_than_two_correct"); continue
        if len(correct_idx) >= len(pool):
            reject("all_options_correct"); continue

        src = raw[r["sourceIndex"]]
        rec = {
            "question": r["questionClean"],
            "correctAnswer": ", ".join("option" + LETTERS[i] for i in correct_idx),
            "medicalTopic": src.get("medicalTopic"), "difficultLevel": src.get("difficultLevel"),
            "regularFormat": src.get("regularFormat"), "questionID": src.get("questionID"),
        }
        for i, p in enumerate(pool):
            rec["answer_option" + LETTERS[i]] = p
        out.append(rec)
        prov.append({"questionID": src.get("questionID"), "uid": r["uid"],
                     "sourceIndex": r["sourceIndex"], "originalOptions": r["options"],
                     "originalCorrect": "option" + r["correctLetter"],
                     "newOptionCount": len(pool), "newCorrect": rec["correctAnswer"]})

    L.write_json("final_03_tach_dau_phay.json", out)
    L.write_json("final_03_tach_dau_phay_provenance.json", prov)
    L.write_json("final_03_tach_dau_phay_rejected.json", rejected)
    yes = sum(1 for v in verdicts if v["verdict"] == "CÓ")
    print(f"FILE 3 — tách từ câu có dấu phẩy\n  LLM trả \"CÓ\" : {yes}/{len(verdicts)}")
    print(f"  biến đổi ok  : {len(out)}")
    print(f"  loại         : {len(rejected)} {dict(Counter(x['reason'] for x in rejected))}")


from stage13 import stage13_file2_multi  # noqa: E402
from stage14 import stage14_file3_filter  # noqa: E402
from stage15 import stage15_file3_multi  # noqa: E402
from stage16 import stage16_merge_benchmark  # noqa: E402
from stage17 import stage17_file1_filter  # noqa: E402
from stage18 import stage18_benchmark_single  # noqa: E402

STAGES = {
    "13": stage13_file2_multi, "14": stage14_file3_filter, "15": stage15_file3_multi,
    "16": stage16_merge_benchmark, "17": stage17_file1_filter,
    "18": stage18_benchmark_single,
    "01": stage01_clean, "02": stage02_classify, "03": stage03_convert_meta,
    "04": stage04_convert_combination, "05": stage05_prepare_pool,
    "06": stage06_merge_validate, "07": stage07_inspect_groups,
    "08": stage08_comma_rule, "09": stage09_file1_negation,
    "10": stage10_file2_meta, "11": stage11_file3_input, "12": stage12_file3_output,
}
