"""Tầng 6 — trộn thêm câu MỘT đáp án vào benchmark để thành bộ HỖN HỢP.

Lấy N câu một đáp án nguyên văn từ bộ nguồn, KHÔNG trùng với bất kỳ câu nào đã
dùng cho bản nhiều đáp án, rồi ghép vào cả hai file:

  final_benchmark_mixed.json         = 9.368 câu nhiều đáp án + N câu một đáp án
  final_benchmark_mixed_single.json  = 9.368 câu gốc của chúng + đúng N câu đó

Hai file vẫn khớp 1:1 theo chỉ số. Với N câu thêm vào thì hai bên giống hệt nhau
(bản một đáp án không có "bản gốc" nào khác chính nó).

Mục đích: model không biết trước câu nào có mấy đáp án, nên phải tự quyết định
chọn bao nhiêu ô — thứ mà bộ thuần nhiều đáp án không đo được.
"""
from __future__ import annotations

import random
import re
from collections import Counter, defaultdict

import lib2 as L

SRC_MULTI = "final_benchmark_9368"
OUT = "final_benchmark_mixed"
SEED = 20260817


def _bucket(k: str):
    return (k[:8], len(k) // 20)


def _pick(clean, used_uid, used_src, bench_keys, n: int, seed: int):
    """Chọn n câu sạch, không trùng và không gần trùng câu nào trong benchmark."""
    # Khối hoá câu hỏi của benchmark để so gần-trùng trong thời gian tuyến tính.
    blocks: dict[tuple, list[str]] = defaultdict(list)
    for k in bench_keys:
        blocks[_bucket(k)].append(k)

    cand, drop = [], Counter()
    for r in clean:
        if r["uid"] in used_uid or (r["srcFile"], r["srcIndex"]) in used_src:
            drop["da_dung_cho_ban_nhieu_dap_an"] += 1; continue
        if r["optionCount"] != 4:
            drop["khong_phai_4_phuong_an"] += 1; continue
        if L.BLANK_STEM.search(r["question"]) or len(r["questionClean"]) < 12:
            drop["than_cau_hong"] += 1; continue
        # Đáp án đúng là "Tất cả đều đúng" -> thực chất là câu nhiều đáp án trá hình.
        if L.meta_kind(r["options"][r["correctIndex"]]):
            drop["dap_an_dung_la_meta"] += 1; continue
        if any(not L.clean_option(o) for o in r["options"]):
            drop["phuong_an_rac"] += 1; continue
        if len({L.norm_item(o) for o in r["options"]}) != 4:
            drop["phuong_an_trung_nhau"] += 1; continue

        k = L.qkey(r["questionClean"])
        b = blocks[_bucket(k)]
        if k in b or any(L.SequenceMatcher(None, k, o).ratio() > 0.90 for o in b[-200:]):
            drop["gan_trung_cau_trong_benchmark"] += 1; continue
        b.append(k)                      # chặn luôn hai câu mới trùng nhau
        cand.append(r)

    # Rải đều theo file nguồn thay vì bốc ngẫu nhiên trên toàn bộ: bốc ngẫu nhiên
    # thì file nào nhiều câu sẽ chiếm phần lớn mẫu.
    by_file: dict[str, list] = defaultdict(list)
    for r in cand:
        by_file[r["srcFile"]].append(r)
    rng = random.Random(seed)
    for v in by_file.values():
        rng.shuffle(v)

    picked, files = [], sorted(by_file)
    while len(picked) < n:
        added = 0
        for f in files:
            if by_file[f] and len(picked) < n:
                picked.append(by_file[f].pop()); added += 1
        if not added:
            raise SystemExit(f"Chỉ gom được {len(picked)}/{n} câu đủ điều kiện")
    return picked, cand, drop


def s6_mix(n: int = 2000, seed: int = SEED, shuffle_options: bool = False):
    multi = L.read_out(f"{SRC_MULTI}.json")
    multi_prov = L.read_out(f"{SRC_MULTI}_provenance.json")
    single = L.read_out(f"{SRC_MULTI}_single.json")
    single_prov = L.read_out(f"{SRC_MULTI}_single_provenance.json")
    clean = L.read_work("01_clean.json")

    print(f"Tầng 6 — bộ hỗn hợp: {len(multi)} câu nhiều đáp án + {n} câu một đáp án")

    used_uid = {p["uid"] for p in multi_prov}
    used_src = {(p["srcFile"], p["srcIndex"]) for p in multi_prov}
    bench_keys = [L.qkey(r["question"]) for r in single] + [L.qkey(r["question"]) for r in multi]

    picked, cand, drop = _pick(clean, used_uid, used_src, bench_keys, n, seed)
    print(f"  ứng viên đủ điều kiện : {len(cand)}  (lấy {len(picked)})")
    print(f"  loại khỏi kho ứng viên: {dict(drop.most_common())}")

    rows, provs = [], []
    for r in picked:
        rec = {
            "question": r["questionClean"],
            "correctAnswer": "option" + r["correctLetter"],
            "medicalTopic": r["medicalTopic"], "difficultLevel": r["difficultLevel"],
            "regularFormat": r["regularFormat"], "questionID": r["questionID"],
        }
        opts = [{"text": t, "correct": i == r["correctIndex"]}
                for i, t in enumerate(r["options"])]
        if shuffle_options:
            random.Random(r["uid"] + "|mix").shuffle(opts)
            rec["correctAnswer"] = ", ".join("option" + L.LETTERS[k]
                                             for k, o in enumerate(opts) if o["correct"])
        for k, o in enumerate(opts):
            rec["answer_option" + L.LETTERS[k]] = o["text"]
        rows.append(rec)
        provs.append({
            "uid": r["uid"], "srcFile": r["srcFile"], "srcIndex": r["srcIndex"],
            "questionID": r["questionID"], "subset": "single_1_dap_an",
            "answerType": "single", "correctAnswer": rec["correctAnswer"],
            "optionCount": 4, "optionsShuffled": bool(shuffle_options),
            "originalCorrect": "option" + r["correctLetter"],
            "qualityFlag": "source-verbatim",
        })

    # Gắn nhãn loại câu cho phần cũ, để chấm điểm tách nhóm được.
    for p in multi_prov:
        p.setdefault("answerType", "multi")
    for p in single_prov:
        p.setdefault("answerType", "single")

    pairs = ([(m, s, pm, ps) for m, s, pm, ps in zip(multi, single, multi_prov, single_prov)]
             + [(r, r, p, {**p}) for r, p in zip(rows, provs)])
    # Không trộn thì 2000 câu một đáp án nằm liền khối ở cuối file — nhìn là biết.
    random.Random(seed).shuffle(pairs)

    out_m, out_s, pr_m, pr_s = [], [], [], []
    for i, (m, s, pm, ps) in enumerate(pairs):
        out_m.append(m); out_s.append(s)
        pr_m.append({**pm, "index": i}); pr_s.append({**ps, "index": i})

    L.write_out(f"{OUT}.json", out_m)
    L.write_out(f"{OUT}_provenance.json", pr_m)
    L.write_out(f"{OUT}_single.json", out_s)
    L.write_out(f"{OUT}_single_provenance.json", pr_s)

    _report(out_m, pr_m, rows, provs)


def _report(out_m, pr_m, rows, provs):
    n_opt = Counter(len([k for k in r if k.startswith("answer_option")]) for r in out_m)
    n_cor = Counter(len(re.findall(r"option[A-Z]", r["correctAnswer"])) for r in out_m)
    print(f"\n  TỔNG: {len(out_m)} câu -> {OUT}.json")
    print(f"  loại câu             : {dict(Counter(p['answerType'] for p in pr_m))}")
    print(f"  số phương án mỗi câu : {dict(sorted(n_opt.items()))}")
    print(f"  số đáp án đúng/câu   : {dict(sorted(n_cor.items()))}")
    print(f"  theo nhóm            : {dict(Counter(p['subset'] for p in pr_m).most_common())}")

    print(f"\n  --- 2000 câu một đáp án vừa thêm ---")
    print(f"  theo file nguồn      : {len(Counter(p['srcFile'] for p in provs))} file, "
          f"mỗi file {min(Counter(p['srcFile'] for p in provs).values())}"
          f"–{max(Counter(p['srcFile'] for p in provs).values())} câu")
    pos = Counter(p["correctAnswer"].replace("option", "") for p in provs)
    n = len(provs)
    print(f"  vị trí đáp án đúng   : {dict(sorted(pos.items()))}"
          f"  -> luôn chọn D ăn {100 * pos['D'] / n:.1f}%")
    print(f"  chủ đề (top 5)       : "
          f"{Counter(t for r in rows for t in (r.get('medicalTopic') or [])).most_common(5)}")
