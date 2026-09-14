#!/usr/bin/env python3
"""Khai thác chuỗi multi-hop 2 bước từ kho đề MCQ 1 đáp án.

Ý tưởng
-------
Hai câu hỏi độc lập nối được thành một câu multi-hop khi **đáp án của câu A
xuất hiện làm chủ đề trong thân câu B**:

    A: "Thuốc đầu tay điều trị tăng huyết áp ở bệnh nhân đái tháo đường?"  -> ức chế men chuyển
    B: "Tác dụng phụ thường gặp của ức chế men chuyển?"                     -> ho khan
    => "Tác dụng phụ thường gặp của thuốc đầu tay điều trị tăng huyết áp
        ở bệnh nhân đái tháo đường là gì?"                                  -> ho khan

Điểm mấu chốt về phương pháp: câu ghép **giữ nguyên toàn bộ phương án và đáp án
của câu B**. Chỉ thân câu đổi. Nên đáp án vẫn được DERIVE từ đáp án gốc của B,
đúng như bộ MCQ đa đáp án hiện tại — LLM (nếu dùng ở bước sau) chỉ viết lại cách
diễn đạt cho trôi, không bao giờ quyết định đáp án.

Script này CHỈ dùng luật, không gọi LLM. Đầu ra là danh sách ứng viên kèm đủ
thành phần để bước sau viết lại thân câu.

Chạy:
    python v2/multihop_mine.py --out data_v2/multihop_candidates.json --samples 25
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

# Phương án "meta" không phải thực thể -> không nối được.
META = re.compile(
    r"tất cả|các câu|đều đúng|đều sai|không có|không câu|a và b|b và c|câu a|câu b|"
    r"phương án|ý kiến|đáp án|trên đây|nêu trên|kể trên",
    re.IGNORECASE,
)

# Cụm quá chung chung: là danh từ thường gặp chứ không phải thực thể y khoa.
# Những cụm này khớp hàng nghìn thân câu và sinh liên kết giả.
GENERIC = {
    "bệnh nhân", "điều trị", "chẩn đoán", "triệu chứng", "nguyên nhân", "biến chứng",
    "xét nghiệm", "phẫu thuật", "tất cả", "chỉ định", "tác dụng", "cơ chế", "tiên lượng",
    "dự phòng", "yếu tố", "biểu hiện", "thể lâm sàng", "giai đoạn", "mức độ", "trường hợp",
}

# Câu Đúng/Sai: đáp án không phải thực thể, nối vào thành vô nghĩa.
TRUEFALSE = re.compile(r"^(đúng|sai|có|không|true|false)\.?$", re.IGNORECASE)

# Bệnh án lâm sàng: thân câu A kể một ca cụ thể nên KHÔNG rút thành cụm danh từ
# định danh được ("bệnh nhân nam 45 tuổi..." không phải là tên một thực thể).
VIGNETTE = re.compile(
    r"\b\d{1,3}\s*tuổi|bệnh\s+nhân\s+(nam|nữ)|sản\s+phụ|thai\s+phụ|bé\s+(trai|gái)|"
    r"nhập\s+viện|vào\s+viện|khám\s+thấy|tiền\s+căn|tiền\s+sử",
    re.IGNORECASE,
)

# Từ để hỏi ở đầu/cuối thân câu A, cần bóc khi biến A thành cụm danh từ.
LEAD = re.compile(
    r"^(hãy\s+)?(cho\s+biết\s+)?(theo\s+\w+,?\s+)?(đâu\s+là|nào\s+là|những|các|một)\s+",
    re.IGNORECASE,
)
TAIL = re.compile(
    r"\s*(là\s+gì|là\s+những\s+gì|nào\s+sau\s+đây|nào\s+dưới\s+đây|nào|gì|sau\s+đây|"
    r"dưới\s+đây|kể\s+trên|là)\s*[?:.]*\s*$",
    re.IGNORECASE,
)


def norm(t: str) -> str:
    """Chuẩn hoá để so khớp: bỏ dấu câu, gộp khoảng trắng, về chữ thường."""
    t = unicodedata.normalize("NFC", t or "")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().lower()


def load_rows() -> list[dict]:
    if not SRC.exists():
        sys.exit(f"Không thấy {SRC}. Chạy `python v2/run.py ingest` trước.")
    return json.loads(SRC.read_text(encoding="utf-8"))


def answer_text(r: dict) -> str | None:
    i = r.get("correctIndex")
    opts = r.get("options") or []
    if not isinstance(i, int) or not (0 <= i < len(opts)):
        return None
    return (opts[i] or "").strip()


def stem(r: dict) -> str:
    return (r.get("questionClean") or r.get("question") or "").strip()


def to_noun_phrase(s: str) -> str:
    """Biến thân câu hỏi của A thành cụm danh từ để nhét vào thân câu B.

    Thuần luật nên KHÔNG phải lúc nào cũng trôi chảy — đó chính là việc dành cho
    bước viết lại bằng LLM. Hàm này tạo bản nháp và đánh dấu độ sạch.
    """
    s = re.sub(r"\s+", " ", s).strip().rstrip("?:.").strip()
    s = LEAD.sub("", s)
    s = TAIL.sub("", s)
    return s.strip()


def topics(r: dict) -> set[str]:
    t = r.get("medicalTopic")
    return {str(x) for x in (t if isinstance(t, list) else [t]) if x}


# Kho de khong thuan y khoa: co ca tai chinh, luat, tin hoc, hoa dai cuong...
# Chung deu duoc gan nhan "Other(No Category)", nen loai nhan nay la du.
UNCAT = "Other(No Category)"


def build(rows: list[dict], max_targets: int, min_chars: int,
          max_stem_words: int, keep_uncat: bool) -> list[dict]:
    """Tìm mọi cặp (A, B) nối được, sau khi lọc nhiễu."""
    # 1. Ứng viên "cầu nối": đáp án của A, đủ cụ thể để định danh một thực thể.
    bridges: dict[str, str] = {}          # uid_A -> đáp án đã chuẩn hoá
    raw_of: dict[str, str] = {}           # uid_A -> đáp án gốc (chưa chuẩn hoá)
    for r in rows:
        a = answer_text(r)
        if not a or META.search(a):
            continue
        n = norm(a)
        if not (2 <= len(n.split()) <= 4) or len(n) < min_chars or n in GENERIC:
            continue
        bridges[r["uid"]] = n
        raw_of[r["uid"]] = a
    pool = set(bridges.values())

    # 2. Cụm cầu nối nào xuất hiện ở thân câu nào (quét n-gram 2..4).
    in_stem: dict[str, list[str]] = collections.defaultdict(list)
    pos_in_stem: dict[tuple[str, str], float] = {}
    for r in rows:
        w = norm(stem(r)).split()
        if not w:
            continue
        for k in (2, 3, 4):
            for j in range(len(w) - k + 1):
                g = " ".join(w[j : j + k])
                if g in pool:
                    in_stem[g].append(r["uid"])
                    # vị trí tương đối: gần 0 = đầu câu, thường là chủ đề
                    pos_in_stem.setdefault((g, r["uid"]), j / max(len(w), 1))

    by_uid = {r["uid"]: r for r in rows}
    out = []
    for ua, bridge in bridges.items():
        targets = [u for u in dict.fromkeys(in_stem.get(bridge, [])) if u != ua]
        if not targets or len(targets) > max_targets:
            continue                       # không nối được, hoặc quá mơ hồ
        A = by_uid[ua]
        na, sa = norm(stem(A)), stem(A)
        if bridge in na:
            continue                       # đáp án đã nằm sẵn trong thân câu A
        # Thân câu A phải là câu hỏi định nghĩa, không phải bệnh án kể ca.
        if VIGNETTE.search(sa) or not (4 <= len(sa.split()) <= max_stem_words):
            continue
        if not keep_uncat and UNCAT in topics(A):
            continue
        for ub in targets:
            B = by_uid[ub]
            ansB = answer_text(B)
            if not ansB or META.search(ansB) or TRUEFALSE.match(ansB.strip()):
                continue
            # Phương án của B cũng không được là Đúng/Sai.
            if sum(1 for o in (B.get("options") or []) if TRUEFALSE.match((o or "").strip())) >= 2:
                continue
            nb_ans = norm(ansB)
            # Đáp án hai bước không được trùng/lồng nhau -> chuỗi tự lộ.
            if nb_ans == bridge or bridge in nb_ans or nb_ans in bridge:
                continue
            if nb_ans in na:
                continue                   # đáp án B đã có trong thân câu A
            if A.get("srcFile") == B.get("srcFile") and A.get("srcIndex") == B.get("srcIndex"):
                continue
            if not keep_uncat and UNCAT in topics(B):
                continue
            np_ = to_noun_phrase(sa)
            if len(np_.split()) < 3:
                continue                   # cụm danh từ quá ngắn, vô nghĩa
            out.append({
                "uidA": ua, "uidB": ub,
                "stemA": sa, "answerA": raw_of[ua],
                "stemB": stem(B), "answerB": ansB,
                "optionsB": B.get("options"),
                "correctIndexB": B.get("correctIndex"),
                "bridge": bridge,
                "bridgeNounPhrase": np_,
                "nTargets": len(targets),
                "bridgePos": round(pos_in_stem.get((bridge, ub), 1.0), 3),
                "topicA": A.get("medicalTopic"), "topicB": B.get("medicalTopic"),
                "sameTopic": (A.get("medicalTopic") or "?") == (B.get("medicalTopic") or "?"),
                "composedDraft": compose(stem(B), bridge, np_),
            })
    return out


def compose(stem_b: str, bridge: str, noun_phrase: str) -> str | None:
    """Thay cụm cầu nối trong thân câu B bằng mô tả lấy từ A (bản nháp theo luật)."""
    pat = re.compile(
        r"\s+".join(re.escape(w) for w in bridge.split()), re.IGNORECASE
    )
    if not pat.search(norm(stem_b)):
        # Thân câu gốc có dấu/hoa-thường khác bản chuẩn hoá; thử khớp lỏng.
        words = stem_b.split()
        low = [norm(w) for w in words]
        bw = bridge.split()
        for j in range(len(low) - len(bw) + 1):
            if low[j : j + len(bw)] == bw:
                return " ".join(words[:j] + [noun_phrase] + words[j + len(bw):])
        return None
    return pat.sub(noun_phrase, stem_b, count=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data_v2/multihop_candidates.json")
    ap.add_argument("--max-targets", type=int, default=3,
                    help="cụm cầu nối khớp quá N thân câu thì bỏ (mơ hồ)")
    ap.add_argument("--min-chars", type=int, default=10)
    ap.add_argument("--max-stem-words", type=int, default=25,
                    help="thân câu A dài hơn N từ thì bỏ (thường là bệnh án)")
    ap.add_argument("--keep-uncategorized", action="store_true",
                    help="giữ cả câu gắn nhãn Other(No Category) — phần lớn KHÔNG phải y khoa")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260909)
    args = ap.parse_args()

    rows = load_rows()
    print(f"Kho sạch: {len(rows):,} câu")
    cand = build(rows, args.max_targets, args.min_chars, args.max_stem_words,
                 args.keep_uncategorized)
    print(f"Ứng viên chuỗi 2 bước: {len(cand):,}")
    if not cand:
        return 1

    ok = [c for c in cand if c["composedDraft"]]
    print(f"  ghép được thân câu bằng luật: {len(ok):,} ({len(ok)/len(cand)*100:.1f}%)")
    print(f"  liên kết 1-1                : {sum(1 for c in ok if c['nTargets']==1):,}")
    print(f"  cầu nối nằm ở nửa đầu thân B: {sum(1 for c in ok if c['bridgePos']<=0.5):,}"
          f" ({sum(1 for c in ok if c['bridgePos']<=0.5)/len(ok)*100:.1f}%)")
    print(f"  cùng medicalTopic           : {sum(1 for c in ok if c['sameTopic']):,}"
          f" ({sum(1 for c in ok if c['sameTopic'])/len(ok)*100:.1f}%)")

    # Ưu tiên: liên kết càng ít mơ hồ, cầu nối càng gần đầu thân B, cùng chủ đề.
    ok.sort(key=lambda c: (c["nTargets"], c["bridgePos"], not c["sameTopic"]))
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ok, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out}")

    print(f"\n{'='*78}\n{args.samples} ứng viên tốt nhất (để đọc tay)\n{'='*78}")
    for i, c in enumerate(ok[: args.samples], 1):
        print(f"\n[{i}] cầu nối: '{c['bridge']}'  (khớp {c['nTargets']} thân câu, "
              f"vị trí {c['bridgePos']}, cùng chủ đề: {c['sameTopic']})")
        print(f"  A: {c['stemA']}")
        print(f"     -> {c['answerA']}")
        print(f"  B: {c['stemB']}")
        print(f"     -> {c['answerB']}")
        print(f"  GHÉP: {c['composedDraft']}")
        print(f"     -> đáp án: {c['answerB']}  (giữ nguyên 4 phương án của B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
