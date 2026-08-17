"""Hạ tầng dùng chung cho pipeline v2.

Khác v1 ở ba điểm:
  1. Đọc NHIỀU file nguồn (10+ file MCQ 1 đáp án) thay vì đúng raw_data.json.
  2. Khử trùng lặp trên TOÀN BỘ các file gộp lại — các bản export khác nhau của
     cùng một ngân hàng đề trùng nhau rất nhiều.
  3. Phần cần LLM được đóng gói thành file .jsonl để chạy batch trên GPU rời,
     pipeline không tự gọi model.

Dùng lại nguyên các hàm chuẩn hoá/tách mục của v1 (pyline/lib.py) để hai bản
cho cùng một kết quả trên cùng một câu hỏi.
"""
from __future__ import annotations

import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pyline"))
import lib as L1  # noqa: E402

# ------------------------------------------------------------------ thư mục
SRC_DIR = ROOT / os.environ.get("MCQ2_SRC_DIR", "source_data")
WORK_DIR = ROOT / os.environ.get("MCQ2_WORK_DIR", "data_v2")
JOBS_DIR = ROOT / os.environ.get("MCQ2_JOBS_DIR", "llm_jobs")
OUT_DIR = ROOT / os.environ.get("MCQ2_OUT_DIR", "processed_data_v2")

LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# FILE 3: pool = số mục thu được sau khi gộp các phương án dạng danh sách.
# Nhận pool tới MAX_POOL, rồi cắt ngẫu nhiên xuống đúng TARGET_OPTIONS phương án
# (giữ NGUYÊN toàn bộ đáp án đúng, chỉ bỏ bớt nhiễu). Chặn thẳng ở mức 5 thì mất
# 2/3 số ứng viên; cắt sau khi lọc thì giữ được gần gấp đôi mà hình thức vẫn đều.
# Đặt ở đây để tầng lọc (s2) và tầng dựng (s4) không bao giờ lệch nhau.
MIN_POOL, MAX_POOL = 4, 8
TARGET_OPTIONS = 5
MAX_CORRECT = TARGET_OPTIONS - 1      # phải chừa chỗ cho ít nhất một phương án sai

# --- mượn nguyên của v1 -----------------------------------------------------
collapse = L1.collapse
strip_prefix = L1.strip_prefix
split_items = L1.split_items
norm_item = L1.norm_item
meta_kind = L1.meta_kind
is_numericish = L1.is_numericish
is_roman = L1.is_roman
uid_of = L1.uid_of

# Không phải file nguồn: file trung gian / kết quả của chính pipeline.
_NOT_SOURCE = re.compile(
    r"provenance|benchmark|^eval_|_skipped|_rejected|schema|verdict|^0\d_|^1\d_", re.I)


def source_files() -> list[Path]:
    """source_data/ là nguồn duy nhất khi thư mục đó có file.

    Chỉ khi nó trống mới quay về lấy raw_data.json + PIPELINE_*.json ở gốc repo,
    để pipeline vẫn chạy được trên máy chưa dựng source_data/.
    """
    if SRC_DIR.is_dir():
        found = sorted(p for p in SRC_DIR.glob("*.json") if not _NOT_SOURCE.search(p.name))
        if found:
            return found
    found = [ROOT / "raw_data.json"] + sorted(ROOT.glob("PIPELINE_*.json"))
    return [p for p in found if p.exists()]


# ---------------------------------------------------------------------- I/O
def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": Windows mặc định đổi \n -> \r\n, làm file lệch byte giữa hai máy.
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def write_work(name: str, value) -> Path:
    """File trung gian: ghi gọn (không indent) vì có thể tới hàng chục nghìn bản ghi."""
    p = _write(WORK_DIR / name, json.dumps(value, ensure_ascii=False))
    _report(p, value)
    return p


def write_out(name: str, value) -> Path:
    """File thành phẩm: giữ đúng format của v1 (indent=1) để đọc bằng mắt được."""
    p = _write(OUT_DIR / name, json.dumps(value, ensure_ascii=False, indent=1))
    _report(p, value)
    return p


def _report(p: Path, value) -> None:
    n = len(value) if hasattr(value, "__len__") else 1
    print(f"  -> {p.parent.name}/{p.name}  ({n} bản ghi, {p.stat().st_size / 1024:.0f} KB)")


def read_work(name: str):
    return json.loads((WORK_DIR / name).read_text(encoding="utf-8"))


def read_out(name: str):
    return json.loads((OUT_DIR / name).read_text(encoding="utf-8"))


def write_jobs(stem: str, rows: list[dict], schema: dict) -> None:
    """Ghi một lô việc cho GPU: <stem>.jsonl + <stem>.schema.json đi kèm."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    _write(JOBS_DIR / f"{stem}.jsonl", body)
    _write(JOBS_DIR / f"{stem}.schema.json", json.dumps(schema, ensure_ascii=False, indent=1))
    print(f"  -> {JOBS_DIR.name}/{stem}.jsonl  ({len(rows)} việc)"
          f" + {stem}.schema.json")


def read_llm_out(stem: str) -> dict[str, dict] | None:
    """Đọc kết quả GPU. Trả None nếu chưa chạy — để tầng gọi tự quyết định."""
    p = JOBS_DIR / f"{stem}.out.jsonl"
    if not p.exists():
        return None
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("ok") and isinstance(rec.get("data"), dict):
            out[rec["id"]] = rec["data"]
    return out


# ------------------------------------------------------------ chuẩn hoá text
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def sentence_case(s: str) -> str:
    """Viết hoa chữ cái đầu. Mục tách ra từ giữa câu bị viết thường, để nguyên thì
    hình thức của phương án lại tương quan với vị trí nó nằm trong đáp án gốc."""
    s = collapse(s)
    return s[:1].upper() + s[1:] if s else s


def qkey(s: str) -> str:
    """Khoá so khớp câu hỏi: bỏ dấu câu, gộp khoảng trắng, hạ chữ thường."""
    return collapse(_PUNCT.sub(" ", collapse(s).lower()))


def dedup_near(rows: list, keyfn, thresh: float = 0.90, window: int = 200) -> tuple[list, int]:
    """Khử gần-trùng theo khối.

    So từng đôi trên 51k bản ghi là O(n²) nên không khả thi. Chia khối theo
    (8 ký tự đầu, dải độ dài) rồi chỉ so trong khối — đủ bắt các bản export
    lặp lại nhau chỉ khác dấu câu, mà vẫn tuyến tính trên thực tế.
    """
    buckets: dict[tuple, list[str]] = {}
    kept, dropped = [], 0
    for r in rows:
        k = keyfn(r)
        b = (k[:8], len(k) // 20)
        seen = buckets.setdefault(b, [])
        if any(SequenceMatcher(None, k, o).ratio() > thresh for o in seen[-window:]):
            dropped += 1
            continue
        seen.append(k)
        kept.append(r)
    return kept, dropped


# --------------------------------------------------- bộ lọc phương án rác
META_LIKE = re.compile(r"cả (hai|ba|\d|[a-e])|đều (đúng|sai)|tất cả|không câu nào", re.I)
JUNK_OPT = re.compile(r"^(none|null|không có|không|n/?a|\.+|-+)$", re.I)
BLANK_STEM = re.compile(r"\.{4,}|_{3,}")
NUMERIC_ONLY = re.compile(r"^[\d\s,.()/%<>=+-]+$")


def clean_option(text: str) -> bool:
    """Phương án có phải nội dung thật hay không."""
    t = collapse(text)
    if len(t) < 2:
        return False
    if JUNK_OPT.fullmatch(t.rstrip(".")):
        return False
    if META_LIKE.search(t):
        return False
    if NUMERIC_ONLY.fullmatch(t):
        return False
    return True


# --------------------------------------------------------- cổng kiểm bất biến
def validate(rec: dict) -> list[str]:
    """Điều kiện một bản ghi phải thoả trước khi vào benchmark."""
    errs = []
    letters = [le for le in LETTERS if rec.get("answer_option" + le)]
    gold = {m.group(1) for m in re.finditer(r"option([A-Z])", str(rec.get("correctAnswer", "")))}

    if len(collapse(rec.get("question", ""))) < 8:
        errs.append("stem_too_short")
    if len(letters) < 4:
        errs.append("fewer_than_four_options")
    if len(letters) > 20:
        errs.append("too_many_options")
    if not gold:
        errs.append("no_correct_answer")
    if gold - set(letters):
        errs.append("correct_points_to_missing_option")
    if len(gold) < 2:
        errs.append("fewer_than_two_correct")
    if gold and len(gold) >= len(letters):
        errs.append("all_options_correct")
    texts = [collapse(rec["answer_option" + le]) for le in letters]
    if len({norm_item(t) for t in texts}) != len(texts):
        errs.append("duplicate_options")
    if any(not clean_option(t) for t in texts):
        errs.append("junk_or_meta_option")
    return errs


def pack(question: str, opts: list[dict], src: dict) -> dict:
    """opts = [{"text":..., "correct":bool}] đã trộn sẵn -> bản ghi format raw_data."""
    rec = {
        "question": collapse(question),
        "correctAnswer": ", ".join("option" + LETTERS[k]
                                   for k, o in enumerate(opts) if o["correct"]),
        "medicalTopic": src.get("medicalTopic"),
        "difficultLevel": src.get("difficultLevel"),
        "regularFormat": src.get("regularFormat"),
        "questionID": src.get("questionID"),
    }
    for k, o in enumerate(opts):
        rec["answer_option" + LETTERS[k]] = collapse(o["text"])
    return rec


# ----------------------------------------------------- truy xuất bản ghi gốc
class SourceCache:
    """Đọc lại bản ghi NGUYÊN VĂN từ file nguồn (dùng dựng bộ đối chứng 1 đáp án)."""

    def __init__(self):
        self._cache: dict[str, list] = {}

    def get(self, src_file: str, src_index: int) -> dict:
        if src_file not in self._cache:
            p = next((f for f in source_files() if f.name == src_file), None)
            if p is None:
                raise SystemExit(f"Không tìm thấy file nguồn {src_file}")
            self._cache[src_file] = json.loads(p.read_text(encoding="utf-8"))
        return self._cache[src_file][src_index]
