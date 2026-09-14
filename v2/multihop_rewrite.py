#!/usr/bin/env python3
"""Bước 2 của thử nghiệm multi-hop: LLM viết lại thân câu ghép cho trôi chảy.

Vai trò của LLM ở đây HẸP và có kiểm chứng được:

  * Nó nhận hai câu hỏi gốc cùng đáp án của chúng, và phải viết ra MỘT câu hỏi
    tiếng Việt duy nhất mà muốn trả lời được thì phải đi qua cả hai bước.
  * Nó KHÔNG được chọn đáp án. Đáp án của câu ghép luôn là `answerB`, lấy
    nguyên từ đáp án gốc của câu B, và bốn phương án cũng giữ nguyên của B.
  * Nó được phép TỪ CHỐI (`ok: false`) khi chuỗi vô nghĩa — đây là cách ta đo
    tỉ lệ liên kết giả mà bước khai thác bằng luật không bắt được.

Sau khi LLM trả lời, script tự kiểm ba điều kiện mà một câu multi-hop hợp lệ
bắt buộc phải thoả, và bất kỳ vi phạm nào cũng làm câu đó bị loại:

  1. Câu ghép KHÔNG được chứa cụm cầu nối (đáp án của A). Nếu có, người đọc
     nhảy thẳng tới bước 2 và chuỗi sụp về một bước.
  2. Câu ghép KHÔNG được chứa đáp án của B.
  3. Câu ghép phải còn là một câu hỏi.

Chạy:
    python v2/multihop_rewrite.py --limit 60 --model google/gemini-2.5-flash
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "data_v2" / "multihop_candidates.json"

SYSTEM = (
    "Bạn là biên tập viên đề thi y khoa tiếng Việt. Bạn KHÔNG bao giờ chọn đáp án; "
    "bạn chỉ viết lại câu hỏi."
)

PROMPT = """Dưới đây là hai câu hỏi trắc nghiệm độc lập. Đáp án của CÂU 1 xuất hiện trong thân CÂU 2.

CÂU 1: {stemA}
Đáp án CÂU 1: {answerA}

CÂU 2: {stemB}
Đáp án CÂU 2: {answerB}

Nhiệm vụ: viết MỘT câu hỏi tiếng Việt duy nhất, sao cho muốn trả lời được thì phải lần lượt
trả lời CÂU 1 rồi mới tới CÂU 2. Cách làm: thay cụm "{bridge}" trong CÂU 2 bằng phần mô tả
lấy từ CÂU 1.

Ràng buộc bắt buộc:
- Câu viết ra TUYỆT ĐỐI KHÔNG được chứa cụm "{bridge}" hay bất kỳ cách viết nào của nó.
  Nếu lộ cụm này thì người đọc bỏ qua được bước 1, câu hỏi mất ý nghĩa multi-hop.
- Câu viết ra KHÔNG được chứa đáp án "{answerB}".
- Đáp án đúng của câu mới phải vẫn đúng là "{answerB}", không được đổi nghĩa.
- Viết tự nhiên, đúng ngữ pháp tiếng Việt, giữ thuật ngữ y khoa nguyên vẹn.

Nếu việc ghép là VÔ NGHĨA — ví dụ CÂU 2 chỉ nhắc tới cụm đó thoáng qua chứ không hỏi về nó,
hoặc CÂU 1 có thể có nhiều đáp án đúng nên bước 1 không xác định — hãy đặt ok = false và
nói ngắn gọn lý do. Thà từ chối còn hơn tạo ra câu hỏi hỏng."""

SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "question": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["ok", "question", "reason"],
    "additionalProperties": False,
}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t or "")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().lower()


def dotenv(name: str) -> str | None:
    f = ROOT / ".env"
    if not f.exists():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return None


def call(model: str, key: str, c: dict, max_tokens: int, retries: int) -> dict | None:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": PROMPT.format(**c)},
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
        "reasoning": {"enabled": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "rewrite", "strict": True, "schema": SCHEMA},
        },
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "mcq-benchmark/1.0"},
    )
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            u = d.get("usage") or {}
            out = json.loads(d["choices"][0]["message"]["content"])
            out["_tok"] = (u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            return out
        except Exception as e:                      # noqa: BLE001
            if a == retries - 1:
                return {"ok": False, "question": "", "reason": f"LOI_API: {e}", "_tok": (0, 0)}
            time.sleep(1.5 * (a + 1))
    return None


def validate(c: dict, q: str) -> list[str]:
    """Ba điều kiện bắt buộc. Trả về danh sách vi phạm (rỗng = hợp lệ)."""
    bad = []
    nq = norm(q)
    if c["bridge"] in nq:
        bad.append("lo_cau_noi")                    # chuỗi sụp về 1 bước
    if norm(c["answerB"]) and norm(c["answerB"]) in nq:
        bad.append("lo_dap_an")
    if not q.strip().endswith(("?", ":")):
        bad.append("khong_phai_cau_hoi")
    if len(q.split()) < 5:
        bad.append("qua_ngan")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/gemini-2.5-flash")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--max-tokens", type=int, default=600)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--only-1to1", action="store_true",
                    help="chỉ lấy liên kết 1-1 (sạch nhất)")
    ap.add_argument("--out", default="data_v2/multihop_pilot.json")
    args = ap.parse_args()

    key = dotenv("OPENROUTER_API_KEY")
    if not key:
        print("Chưa có OPENROUTER_API_KEY trong .env")
        return 1
    if not CAND.exists():
        print(f"Chưa có {CAND}. Chạy `python v2/multihop_mine.py` trước.")
        return 1

    cand = json.loads(CAND.read_text(encoding="utf-8"))
    if args.only_1to1:
        cand = [c for c in cand if c["nTargets"] == 1]
    cand = cand[: args.limit]
    print(f"[chạy] {args.model} | {len(cand)} chuỗi | reasoning tắt")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        res = list(ex.map(lambda c: call(args.model, key, c, args.max_tokens, args.retries), cand))

    rows, tin, tout = [], 0, 0
    for c, r in zip(cand, res):
        r = r or {"ok": False, "question": "", "reason": "khong_co_phan_hoi", "_tok": (0, 0)}
        tin += r["_tok"][0]
        tout += r["_tok"][1]
        viol = validate(c, r.get("question", "")) if r.get("ok") else []
        rows.append({**{k: v for k, v in c.items() if not k.startswith("_")},
                     "llmOk": bool(r.get("ok")),
                     "llmReason": r.get("reason", ""),
                     "composed": r.get("question", ""),
                     "violations": viol,
                     "accepted": bool(r.get("ok")) and not viol})

    n = len(rows)
    ref = sum(1 for r in rows if not r["llmOk"])
    viol = sum(1 for r in rows if r["llmOk"] and r["violations"])
    acc = sum(1 for r in rows if r["accepted"])
    print(f"\n{'='*70}\nKẾT QUẢ THỬ NGHIỆM ({n} chuỗi)\n{'='*70}")
    print(f"  LLM từ chối vì chuỗi vô nghĩa : {ref:4d}  ({ref/n*100:5.1f}%)")
    print(f"  LLM nhận nhưng vi phạm ràng buộc: {viol:4d}  ({viol/n*100:5.1f}%)")
    print(f"  QUA ĐƯỢC                       : {acc:4d}  ({acc/n*100:5.1f}%)")
    if viol:
        c = {}
        for r in rows:
            for v in r["violations"]:
                c[v] = c.get(v, 0) + 1
        print(f"  chi tiết vi phạm: {c}")
    print(f"\n  token: vào {tin:,} · ra {tout:,} · {time.time()-t0:.0f}s")

    out = ROOT / args.out
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out}")

    good = [r for r in rows if r["accepted"]]
    print(f"\n{'='*70}\n10 câu multi-hop ĐẠT (đọc tay để thẩm định)\n{'='*70}")
    for i, r in enumerate(good[:10], 1):
        print(f"\n[{i}] {r['composed']}")
        print(f"    đáp án: {r['answerB']}")
        print(f"    bước 1: {r['stemA']} -> {r['answerA']}")
        print(f"    bước 2: {r['stemB']} -> {r['answerB']}")
    bad = [r for r in rows if not r["llmOk"]][:5]
    if bad:
        print(f"\n{'='*70}\n5 chuỗi LLM TỪ CHỐI (kiểm xem từ chối có đúng không)\n{'='*70}")
        for i, r in enumerate(bad, 1):
            print(f"\n[{i}] lý do: {r['llmReason']}")
            print(f"    A: {r['stemA']} -> {r['answerA']}")
            print(f"    B: {r['stemB']} -> {r['answerB']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
