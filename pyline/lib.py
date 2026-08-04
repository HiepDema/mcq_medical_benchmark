"""Hàm dùng chung cho pipeline MCQ (bản Python).

Port 1:1 từ pipeline/lib.js. Đầu ra JSON được canh cho GIỐNG HỆT bản Node
(indent=1, không escape unicode) để có thể diff từng byte.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# DATA_DIR: nơi ĐỌC file trung gian.  OUT_DIR: nơi GHI kết quả (mặc định trùng nhau).
# Tách hai biến để xuất file thành phẩm sang thư mục riêng mà vẫn dùng lại
# file trung gian có sẵn:  MCQ_OUT_DIR=processed_data python pyline/run.py 09 10
DATA_DIR = ROOT / os.environ.get("MCQ_DATA_DIR", "data")
OUT_DIR = ROOT / os.environ.get("MCQ_OUT_DIR", os.environ.get("MCQ_DATA_DIR", "data"))

# JS \b chỉ tính ký tự ASCII [A-Za-z0-9_]; \b của Python lại nhận cả chữ Việt.
# Dùng hai lookaround này ở đúng những chỗ JS dùng \b để hai bản cho kết quả
# giống nhau tuyệt đối.
WB = r"(?<![A-Za-z0-9_])"
WE = r"(?![A-Za-z0-9_])"
# \b thật của JS: đúng MỘT bên là ký tự từ ASCII. Chỉ dùng WB hoặc WE lẻ là
# chưa đủ — với "cả " thì cả hai bên đều không phải ký tự từ, JS KHÔNG khớp
# nhưng WE lẻ lại khớp, gây lệch kết quả so với bản Node.
JB = (r"(?:(?<=[A-Za-z0-9_])(?![A-Za-z0-9_])"
      r"|(?<![A-Za-z0-9_])(?=[A-Za-z0-9_]))")


# --------------------------------------------------------------------- I/O
def write_json(name: str, value) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / name
    # newline="\n": Windows mặc định đổi \n -> \r\n, làm file lệch byte so với bản Node.
    p.write_text(json.dumps(value, ensure_ascii=False, indent=1),
                 encoding="utf-8", newline="\n")
    n = len(value)
    print(f"  -> {OUT_DIR.name}/{name}  ({n} bản ghi, {p.stat().st_size / 1024:.0f} KB)")
    return p


def read_json(name: str):
    """Ưu tiên file trong OUT_DIR (do tầng trước vừa ghi), nếu không có thì lấy ở DATA_DIR."""
    p = OUT_DIR / name
    if not p.exists():
        p = DATA_DIR / name
    return json.loads(p.read_text(encoding="utf-8"))


def read_raw_data():
    """Đọc raw_data.json, chịu được lỗi xuống dòng lọt vào giữa chuỗi.
    Vá TRONG BỘ NHỚ, không bao giờ ghi đè file gốc."""
    text = (ROOT / "raw_data.json").read_text(encoding="utf-8")
    try:
        return json.loads(text)
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
        data = json.loads("".join(out))
        print(f"  ⚠  raw_data.json sai cú pháp JSON — đã vá {fixes} chỗ xuống dòng "
              f"trong chuỗi (chỉ trong bộ nhớ, file gốc giữ nguyên)")
        return data


# ------------------------------------------------------------ chuẩn hoá text
def collapse(s) -> str:
    return re.sub(r"\s+", " ", str(s if s is not None else "")).strip()


def uid_of(question: str, options: list[str]) -> str:
    key = collapse(question).lower() + "||" + "|".join(collapse(o).lower() for o in options)
    return "q_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def strip_prefix(q: str) -> str:
    c = collapse(q)
    return re.sub(r"^(?:câu\s*)?\d{1,4}\s*[.:)\-]\s*", "", c, flags=re.I).strip() or c


# --------------------------------------------- tách danh sách trong đáp án
DEC = "\x00"  # sentinel bảo vệ dấu phẩy thập phân (0,5) — KHÔNG phải dấu cách


def split_items(text: str) -> list[str]:
    t = re.sub(r"[.;\s]+$", "", collapse(text))
    t = re.sub(r"(\d)\s*,\s*(\d)", rf"\1{DEC}\2", t)
    out = []
    for x in re.split(r"\s*[,;]\s*|\s+và\s+", t, flags=re.I):
        x = re.sub(r"^[.\-\s]+|[.\s]+$", "", x.replace(DEC, ",").strip())
        if x:
            out.append(x)
    return out


def norm_item(x: str) -> str:
    return re.sub(r"\.+$", "", collapse(x).lower())


HAS_LETTER = re.compile(r"[a-zà-ỹ]", re.I)
_NUMERIC = re.compile(
    r"[\d\s.,%<>=+\-/()]+\s*(g/l|g/dl|mg/l|mg|ml|fl|pg|%|mmhg|u/l|tb|mmol/l|mcg)?\.?",
    re.I)


def is_numericish(x: str) -> bool:
    t = collapse(x)
    if not HAS_LETTER.search(t):
        return True
    return bool(_NUMERIC.fullmatch(t))


def is_roman(x: str) -> bool:
    return bool(re.fullmatch(r"[ivx]+", collapse(x), re.I))


# ------------------------------------- nhận diện đáp án "meta" và tổ hợp
_META_WRONG = re.compile(
    r"đều\s+sai|đều\s+không\s+(đúng|chính xác)|không\s+(có\s+)?(câu|ý|đáp án|phương án)\s+nào")
_META_LETTERS = re.compile(
    r"(?:cả\s+)?([a-e])\s*(?:,|và|&|\+)\s*([a-e])"
    r"(?:\s*(?:,|và|&|\+)\s*([a-e]))?\s*(?:câu\s*)?(?:là\s*)?(?:đều\s*)?(?:đúng)?")
_META_ALL = re.compile(rf"(tất cả|cả|các){JB}.*{JB}đúng")
_META_ALL_FALLBACK = re.compile(r"đều\s+đúng$")


def meta_kind(opt: str):
    t = re.sub(r"[.\s]+$", "", collapse(opt).lower())
    if _META_WRONG.search(t):
        return {"kind": "ALL_WRONG"}
    lm = _META_LETTERS.fullmatch(t)
    if lm:
        return {"kind": "LETTERS", "letters": [g for g in lm.groups() if g]}
    if _META_ALL.fullmatch(t) or _META_ALL_FALLBACK.search(t):
        return {"kind": "ALL_CORRECT"}
    return None


def is_ref_only_option(s: str) -> bool:
    t = collapse(s)
    return bool(t) and bool(re.fullmatch(r"[\d\s(),;.và]+", t, re.I)) and bool(re.search(r"\d", t))


def extract_numbered_statements(question: str):
    q = collapse(question)
    marks = list(re.finditer(r"\(\s*(\d{1,2})\s*\)", q))
    if len(marks) < 2:
        return None
    out = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(q)
        out.append({"n": int(m.group(1)),
                    "text": re.sub(r"^[.\s:)\-]+|[.\s]+$", "", q[start:end])})
    return out
