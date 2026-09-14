#!/usr/bin/env python3
"""Dựng bộ đề ĐIỀN TỪ (cloze) từ kho MCQ một đáp án, gồm hai nhánh.

  Nhánh 1 — MỘT chỗ trống, từ một câu MCQ:
      "Biến chứng nguy hiểm nhất của đặt dụng cụ tử cung tránh thai là ___(1)___."
      (1) = Thủng tử cung

  Nhánh 2 — HAI chỗ trống nối chuỗi (multi-hop), từ một cặp câu A -> B trong đó
  đáp án của A xuất hiện ở thân câu B:
      "(1) Biến chứng nguy hiểm nhất của đặt dụng cụ tử cung tránh thai là ___(1)___.
       (2) ___(1)___ hay gặp nhất trong trường hợp ___(2)___."
      (1) = Thủng tử cung   (2) = Chửa trứng xâm nhập

Vì sao dạng điền từ HỢP với multi-hop hơn dạng MCQ
---------------------------------------------------
Bản MCQ multi-hop chết vì phải thay thực thể cầu nối bằng một cụm mô tả, và
52,8% cụm mô tả đó không định danh duy nhất (xem REPORT_MULTIHOP.md). Ở đây
KHÔNG phải thay gì cả — cả hai thực thể đều bị khoét trống, và ô (1) được nhắc
lại tường minh ở câu thứ hai. Nguồn mơ hồ lớn nhất biến mất.

Ground truth vẫn DERIVE 100%: đáp án mỗi ô chính là phương án đúng của câu gốc.
Không có LLM nào tham gia bước dựng đề này — script thuần luật.

Chạy:
    python v2/cloze_build.py --single 8000 --seed 20260909
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data_v2" / "01_clean.json"
OUT = ROOT / "processed_data_v2"

META = re.compile(
    r"tất cả|các câu|đều đúng|đều sai|không có|không câu|a và b|b và c|câu a|câu b|"
    r"phương án|ý kiến|đáp án|trên đây|nêu trên|kể trên", re.IGNORECASE)
TRUEFALSE = re.compile(r"^(đúng|sai|có|không|true|false)\.?$", re.IGNORECASE)
UNCAT = "Other(No Category)"

# Đáp án rác: còn sót ký hiệu phương án ("B. S"), hoặc chỉ là một chữ cái.
JUNK = re.compile(r"^[A-Ea-e][.,)]?\s*[A-ZĐSa-zđs]?\.?$")

# Bệnh án lâm sàng: dùng được cho nhánh 1, nhưng nối chuỗi thì thành ghép bừa
# hai ca bệnh không liên quan, nên nhánh 2 loại hẳn.
VIGNETTE = re.compile(
    r"\b\d{1,3}\s*tuổi|bệnh\s+nhân\s+(nam|nữ)|sản\s+phụ|thai\s+phụ|bé\s+(trai|gái)|"
    r"nhập\s+viện|vào\s+viện|tiền\s+căn|tiền\s+sử", re.IGNORECASE)

# Đuôi thân câu -> từ nối khi chuyển sang dạng khẳng định. Thứ tự quan trọng:
# mẫu dài phải đứng trước mẫu ngắn.
TAILS: list[tuple[str, str]] = [
    (r"\s*là\s+bao\s+nhiêu\s*[?.:]*\s*$", "là"),
    (r"\s*bao\s+nhiêu\s*[?.:]*\s*$", "là"),
    (r"\s*là\s*gì\s*[?.:]*\s*$", "là"),
    (r"\s*nào\s+sau\s+đây\s*[?.:]*\s*$", "là"),
    (r"\s*nào\s+dưới\s+đây\s*[?.:]*\s*$", "là"),
    (r"\s*bao\s+gồm\s*[?.:]*\s*$", "bao gồm"),
    (r"\s*sau\s+đây\s*[?.:]*\s*$", "là"),
    (r"\s*gồm\s*[?.:]*\s*$", "gồm"),
    (r"\s*là\s*[?.:]*\s*$", "là"),
    (r"\s*nào\s*[?.:]*\s*$", "là"),
    (r"\s*[?:]\s*$", "là"),
]
BLANK = "___({})___"

# Câu phủ định / "chọn câu SAI": đáp án đúng của chúng là một mệnh đề SAI.
# Khoét trống ra sẽ tạo câu khẳng định điều sai -> loại hẳn khỏi bộ cloze.
NEGSTEM = re.compile(
    r"\bchọn\s+(câu\s+)?sai\b|\bnào\s+sai\b|\bkhông\s+đúng\b|\bngoại\s+trừ\b|"
    r"\bkhông\s+phải\b|\bkhông\s+thuộc\b|\bkhông\s+bao\s+gồm\b|\bsai\s*[?:.]*\s*$",
    re.IGNORECASE)

# Số thứ tự sót lại ở đầu thân câu: "Câu 25.", "Câu hỏi 252)", "12."
LEADNUM = re.compile(r"^\s*(câu(\s+hỏi)?\s*)?\d{1,4}\s*[.,)\]:]\s*", re.IGNORECASE)

# Nếu thân câu đã kết thúc bằng giới từ / hệ từ thì KHÔNG chèn thêm "là".
ENDPREP = re.compile(
    r"\b(ở|từ|trong|ngoài|với|cho|của|do|bằng|qua|tới|đến|theo|về|trên|dưới|sau|trước|"
    r"vào|ra|là|gồm|có|thuộc|gặp|dùng)$", re.IGNORECASE)


def nfc(t: str) -> str:
    """Dựng sẵn dấu tiếng Việt.

    0,6% kho đề lưu chữ có dấu ở dạng tổ hợp (NFD): "từ" thành t + ư + dấu rời.
    Hiển thị y hệt nhau nhưng khác chuỗi, nên mọi regex tiếng Việt đều trượt và
    — nghiêm trọng hơn với bộ điền từ — đáp án đúng sẽ bị chấm là sai. Chuẩn hoá
    một lần lúc nạp là xong.
    """
    return unicodedata.normalize("NFC", t or "")


def normalize_rows(rows: list[dict]) -> int:
    n = 0
    for r in rows:
        for k in ("question", "questionClean"):
            if r.get(k) and r[k] != nfc(r[k]):
                r[k] = nfc(r[k])
                n += 1
        if r.get("options"):
            fixed = [nfc(o) for o in r["options"]]
            if fixed != r["options"]:
                r["options"] = fixed
                n += 1
    return n


def norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t or "")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().lower()


def topics(r: dict) -> set[str]:
    t = r.get("medicalTopic")
    return {str(x) for x in (t if isinstance(t, list) else [t]) if x}


def answer_of(r: dict) -> str | None:
    i = r.get("correctIndex")
    o = r.get("options") or []
    return (o[i] or "").strip() if isinstance(i, int) and 0 <= i < len(o) else None


def distractors_of(r: dict) -> list[str]:
    i = r.get("correctIndex")
    return [(o or "").strip() for k, o in enumerate(r.get("options") or []) if k != i]


def to_statement(stem: str, n: int) -> str | None:
    """Biến thân câu hỏi thành câu khẳng định có một chỗ trống ở cuối."""
    s = LEADNUM.sub("", re.sub(r"\s+", " ", stem).strip())
    if NEGSTEM.search(s):
        return None                      # đáp án là mệnh đề sai -> không khoét được
    for pat, joiner in TAILS:
        if re.search(pat, s, re.I):
            head = re.sub(pat, "", s, flags=re.I).strip().rstrip(",;")
            if len(head.split()) < 3:
                return None
            # Tránh "gặp ở LÀ ___" hay "là bao nhiêu LÀ ___".
            if ENDPREP.search(head):
                return f"{head} {BLANK.format(n)}."
            return f"{head} {joiner} {BLANK.format(n)}."
    return None


def usable(r: dict, min_w: int, max_w: int, keep_uncat: bool) -> str | None:
    a = answer_of(r)
    if not a or META.search(a) or TRUEFALSE.match(a) or JUNK.match(a):
        return None
    if not (min_w <= len(a.split()) <= max_w):
        return None
    if not keep_uncat and UNCAT in topics(r):
        return None
    return a


def build_single(rows: list[dict], args) -> list[dict]:
    out = []
    for r in rows:
        a = usable(r, args.min_words, args.max_words, args.keep_uncategorized)
        if not a:
            continue
        stmt = to_statement(r.get("questionClean") or r.get("question") or "", 1)
        if not stmt:
            continue
        # Đáp án không được lộ sẵn trong chính câu dẫn.
        if norm(a) and norm(a) in norm(stmt):
            continue
        out.append({
            "track": "single", "nBlanks": 1, "passage": stmt,
            "blanks": [{"id": 1, "gold": a.rstrip("."), "distractors": distractors_of(r)}],
            "medicalTopic": sorted(topics(r)), "difficultLevel": r.get("difficultLevel"),
            "provenance": {"uid": r["uid"], "srcFile": r.get("srcFile"),
                           "srcIndex": r.get("srcIndex"), "stem": r.get("question")},
        })
    return out


def build_multihop(rows: list[dict], args) -> list[dict]:
    """Ghép cặp A -> B khi đáp án của A nằm trong thân câu B."""
    ans: dict[str, tuple[str, str]] = {}          # uid -> (đáp án chuẩn hoá, đáp án gốc)
    for r in rows:
        a = usable(r, 2, 4, args.keep_uncategorized)
        if a and len(norm(a)) >= 10:
            ans[r["uid"]] = (norm(a), a)
    pool = {n for n, _ in ans.values()}

    where: dict[str, list[str]] = collections.defaultdict(list)
    for r in rows:
        w = norm(r.get("questionClean") or r.get("question") or "").split()
        for k in (2, 3, 4):
            for j in range(len(w) - k + 1):
                g = " ".join(w[j:j + k])
                if g in pool:
                    where[g].append(r["uid"])

    by = {r["uid"]: r for r in rows}
    out = []
    for ua, (bridge, rawA) in ans.items():
        tg = [u for u in dict.fromkeys(where.get(bridge, [])) if u != ua]
        if not tg or len(tg) > args.max_targets:
            continue
        A = by[ua]
        sa = A.get("questionClean") or A.get("question") or ""
        if VIGNETTE.search(sa) or len(sa.split()) > args.max_stem_words:
            continue
        stmtA = to_statement(sa, 1)
        if not stmtA or bridge in norm(stmtA):
            continue
        for ub in tg:
            B = by[ub]
            ansB = usable(B, args.min_words, args.max_words, args.keep_uncategorized)
            if not ansB:
                continue
            nb = norm(ansB)
            if nb == bridge or bridge in nb or nb in bridge:
                continue
            if nb in norm(stmtA):
                continue
            sb = B.get("questionClean") or B.get("question") or ""
            if VIGNETTE.search(sb) or len(sb.split()) > args.max_stem_words:
                continue
            stmtB = to_statement(sb, 2)
            if not stmtB or nb in norm(stmtB):
                continue
            # Cụm cầu nối phải nằm ở nửa đầu thân câu B -> nhiều khả năng là
            # chủ đề của câu, không phải nhắc tới thoáng qua.
            wb = norm(sb).split()
            bw = bridge.split()
            pos = next((j for j in range(len(wb) - len(bw) + 1)
                        if wb[j:j + len(bw)] == bw), None)
            if pos is None or pos / max(len(wb), 1) > 0.5:
                continue
            # Thay cụm cầu nối trong câu B bằng tham chiếu tới ô (1).
            swapped = swap_bridge(stmtB, bridge)
            if swapped is None:
                continue
            out.append({
                "track": "multihop", "nBlanks": 2,
                "passage": f"(1) {stmtA}\n(2) {swapped}",
                "blanks": [
                    {"id": 1, "gold": rawA.rstrip("."), "distractors": distractors_of(A)},
                    {"id": 2, "gold": ansB.rstrip("."), "distractors": distractors_of(B)},
                ],
                "medicalTopic": sorted(topics(A) | topics(B)),
                "difficultLevel": B.get("difficultLevel"),
                "provenance": {"uidA": ua, "uidB": ub, "bridge": rawA,
                               "srcFileA": A.get("srcFile"), "srcFileB": B.get("srcFile"),
                               "stemA": A.get("question"), "stemB": B.get("question")},
            })
    return out


def swap_bridge(stmt: str, bridge: str) -> str | None:
    """Thay cụm cầu nối trong câu B bằng '___(1)___' (khớp theo token đã chuẩn hoá)."""
    words = stmt.split()
    low = [norm(w) for w in words]
    bw = bridge.split()
    for j in range(len(low) - len(bw) + 1):
        if low[j:j + len(bw)] == bw:
            return " ".join(words[:j] + [BLANK.format(1)] + words[j + len(bw):])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", type=int, default=8000, help="số câu nhánh 1 lấy mẫu (0 = tất cả)")
    ap.add_argument("--multihop", type=int, default=0, help="giới hạn nhánh 2 (0 = tất cả)")
    ap.add_argument("--min-words", type=int, default=1)
    ap.add_argument("--max-words", type=int, default=8)
    ap.add_argument("--max-targets", type=int, default=3)
    ap.add_argument("--max-stem-words", type=int, default=25,
                    help="nhánh 2: thân câu dài hơn N từ thì bỏ (bệnh án)")
    ap.add_argument("--keep-uncategorized", action="store_true")
    ap.add_argument("--seed", type=int, default=20260909)
    args = ap.parse_args()

    if not SRC.exists():
        sys.exit(f"Không thấy {SRC}. Chạy `python v2/run.py ingest` trước.")
    rows = json.loads(SRC.read_text(encoding="utf-8"))
    fixed = normalize_rows(rows)
    print(f"Kho sạch: {len(rows):,} câu  (chuẩn hoá NFC: {fixed:,} trường)")

    single = build_single(rows, args)
    print(f"Nhánh 1 (một ô)     : {len(single):,}")
    multi = build_multihop(rows, args)
    print(f"Nhánh 2 (hai ô, chuỗi): {len(multi):,}")

    rng = random.Random(args.seed)
    # Mỗi câu nguồn chỉ dùng một lần ở nhánh 2, tránh trùng lặp nội dung.
    seen: set = set()
    uniq = []
    for m in multi:
        k = m["provenance"]["uidB"]
        pk = norm(m["passage"])
        # Cùng câu A + cùng đáp án ô (2) => cặp trùng nội dung, chỉ khác vài ký
        # tự (ví dụ "a-giao cảm" với "α-giao cảm"). Giữ một.
        ak = (m["provenance"]["uidA"], norm(m["blanks"][1]["gold"]))
        if k in seen or pk in seen or ak in seen:
            continue
        seen.add(k)
        seen.add(pk)
        seen.add(ak)
        uniq.append(m)
    print(f"  sau khi bỏ trùng câu B: {len(uniq):,}")
    multi = uniq
    if args.multihop:
        rng.shuffle(multi)
        multi = multi[: args.multihop]

    # Nhánh 1 không được trùng nguồn với nhánh 2.
    used = {m["provenance"]["uidA"] for m in multi} | {m["provenance"]["uidB"] for m in multi}
    single = [s for s in single if s["provenance"]["uid"] not in used]
    print(f"  nhánh 1 sau khi loại nguồn đã dùng ở nhánh 2: {len(single):,}")
    if args.single:
        rng.shuffle(single)
        single = single[: args.single]

    OUT.mkdir(exist_ok=True)
    for name, data in (("cloze_single", single), ("cloze_multihop", multi)):
        for i, d in enumerate(data):
            d["id"] = f"{name}_{i:06d}"
            d["index"] = i
        (OUT / f"final_{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {OUT / f'final_{name}.json'}  ({len(data):,} câu)")

    print(f"\n{'='*74}\nMẪU — nhánh 1\n{'='*74}")
    for d in single[:3]:
        print(f"\n{d['passage']}")
        print(f"   (1) = {d['blanks'][0]['gold']}")
    print(f"\n{'='*74}\nMẪU — nhánh 2 (multi-hop)\n{'='*74}")
    for d in multi[:4]:
        print(f"\n{d['passage']}")
        print(f"   (1) = {d['blanks'][0]['gold']}")
        print(f"   (2) = {d['blanks'][1]['gold']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
