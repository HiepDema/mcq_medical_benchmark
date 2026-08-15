"""Tầng 1 — nạp toàn bộ file nguồn, làm sạch, khử trùng lặp trên phạm vi TOÀN BỘ.

Không ghi đè bất kỳ file nguồn nào. Đầu ra: data_v2/01_clean.json
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import lib2 as L


def _load_tolerant(p: Path):
    """Đọc JSON, chịu được ký tự xuống dòng lọt vào giữa chuỗi. Vá trong bộ nhớ."""
    text = p.read_text(encoding="utf-8")
    try:
        return json.loads(text), 0
    except json.JSONDecodeError:
        out, in_str, esc, fixes, i = [], False, False, 0, 0
        while i < len(text):
            c = text[i]
            if esc:
                out.append(c); esc = False
            elif c == "\\" and in_str:
                out.append(c); esc = True
            elif c == '"':
                in_str = not in_str; out.append(c)
            elif in_str and c in "\r\n":
                while i + 1 < len(text) and text[i + 1] in "\r\n \t":
                    i += 1
                out.append(" "); fixes += 1
            else:
                out.append(c)
            i += 1
        return json.loads("".join(out)), fixes


def s1_ingest():
    files = L.source_files()
    if not files:
        raise SystemExit(
            f"Không tìm thấy file nguồn nào.\n"
            f"Đặt các file MCQ 1 đáp án vào {L.SRC_DIR}/ rồi chạy lại.")

    print(f"Tầng 1 — nạp nguồn: {len(files)} file")
    clean, dropped, dupes = [], [], []
    seen_uid: dict[str, int] = {}
    seen_q: dict[str, int] = {}
    per_file = []

    for p in files:
        rows, fixes = _load_tolerant(p)
        if fixes:
            print(f"  ⚠ {p.name}: vá {fixes} chỗ xuống dòng trong chuỗi (chỉ trong bộ nhớ)")
        if not isinstance(rows, list):
            raise SystemExit(f"{p.name} không phải mảng JSON các câu hỏi")
        before = len(clean)

        for i, q in enumerate(rows):
            def drop(reason):
                dropped.append({"srcFile": p.name, "srcIndex": i, "reason": reason})

            if not isinstance(q, dict):
                drop("not_an_object"); continue
            question = L.collapse(q.get("question") or "")
            if not question:
                drop("empty_question"); continue

            slots = [(le, L.collapse(q.get("answer_option" + le) or "")) for le in "ABCDE"]
            slots = [(le, t) for le, t in slots if t]
            if len(slots) < 4:
                drop("fewer_than_four_options"); continue

            m = re.search(r"option([A-E])", str(q.get("correctAnswer") or ""), re.I)
            if not m:
                drop("unparseable_correctAnswer"); continue
            letter = m.group(1).upper()
            idx = next((k for k, (le, _) in enumerate(slots) if le == letter), -1)
            if idx == -1:
                drop("correct_option_is_empty"); continue

            options = [t for _, t in slots]
            uid = L.uid_of(question, options)
            if uid in seen_uid:
                dupes.append({"uid": uid, "srcFile": p.name, "srcIndex": i,
                              "keptAt": seen_uid[uid], "kind": "exact"})
                continue
            # Cùng thân câu + cùng tập phương án nhưng khác thứ tự -> vẫn là một câu.
            key2 = L.qkey(question) + "||" + "|".join(sorted(L.norm_item(o) for o in options))
            if key2 in seen_q:
                dupes.append({"uid": uid, "srcFile": p.name, "srcIndex": i,
                              "keptAt": seen_q[key2], "kind": "reordered"})
                continue

            pos = len(clean)
            seen_uid[uid] = pos
            seen_q[key2] = pos
            clean.append({
                "uid": uid, "srcFile": p.name, "srcIndex": i,
                "questionID": q.get("questionID"),
                "question": question,
                "questionClean": L.strip_prefix(question),
                "options": options,
                "optionLetters": [le for le, _ in slots],
                "optionCount": len(options),
                "correctIndex": idx, "correctLetter": letter,
                "medicalTopic": q.get("medicalTopic") or [],
                "difficultLevel": q.get("difficultLevel"),
                "regularFormat": q.get("regularFormat"),
            })

        per_file.append((p.name, len(rows), len(clean) - before))
        print(f"  {p.name[:52]:<54} {len(rows):>6} câu -> giữ {len(clean) - before:>6}")

    L.write_work("01_clean.json", clean)
    L.write_work("01_duplicates.json", dupes)
    L.write_work("01_dropped.json", dropped)

    total = sum(n for _, n, _ in per_file)
    print(f"\n  tổng đọc vào : {total}")
    print(f"  giữ lại      : {len(clean)}  ({100 * len(clean) / total:.1f}%)")
    print(f"  trùng lặp    : {len(dupes)} {dict(Counter(d['kind'] for d in dupes))}")
    print(f"  loại         : {len(dropped)} {dict(Counter(d['reason'] for d in dropped))}")
