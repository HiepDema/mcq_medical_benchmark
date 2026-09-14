#!/usr/bin/env python3
"""Bước 4: giám khảo LLM bắt hai lỗi mà luật không bắt được.

Đọc tay output bước 3 cho thấy bộ kiểm nghiêm ngặt (91% cho qua) vẫn để lọt
khoảng một nửa số chuỗi hỏng. Hai lỗi thống trị, và cả hai đều là lỗi NGỮ NGHĨA
nên không có luật cú pháp nào bắt được:

  1. HOP COLLAPSE — câu ghép trả lời được mà không cần đi qua bước 1.
     Ví dụ: "Tiền thân của Bệnh viện Quân y 103 được thành lập tại đâu?"
     không đòi hỏi biết tiền thân đó là "Đội điều trị 3". Chuỗi sụp về 1 bước
     và câu hỏi mất lý do tồn tại.

  2. MÔ TẢ KHÔNG ĐỊNH DANH DUY NHẤT — cụm mô tả lấy từ câu A có thể ứng với
     nhiều thực thể, nên bước 1 không có đáp án xác định và câu ghép mơ hồ.

Giám khảo KHÔNG được chọn đáp án và KHÔNG được sửa câu; nó chỉ trả lời hai câu
hỏi trên. Đáp án vẫn là đáp án gốc của câu B.

Chạy:
    python v2/multihop_judge.py --in data_v2/multihop_checked.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SYSTEM = "Bạn là người thẩm định đề thi y khoa. Bạn không bao giờ trả lời câu hỏi chuyên môn."

PROMPT = """Một câu hỏi multi-hop được ghép từ hai câu hỏi gốc. Ý đồ là người trả lời phải
lần lượt: (bước 1) từ phần mô tả suy ra một thực thể, rồi (bước 2) trả lời về thực thể đó.

CÂU GHÉP: {composed}

Phần mô tả ở bước 1 nhằm chỉ tới: "{answerA}"
Câu hỏi gốc của bước 1: {stemA}

Hãy trả lời hai câu hỏi thẩm định:

1. `dinh_danh_duy_nhat`: Phần mô tả trong CÂU GHÉP có chỉ tới DUY NHẤT "{answerA}" không?
   Đặt false nếu mô tả đó có thể ứng với nhiều thực thể khác nhau, khiến bước 1 không
   có đáp án xác định.

2. `tra_loi_duoc_khong_can_buoc_1`: Có thể trả lời đúng CÂU GHÉP mà KHÔNG cần suy ra
   "{answerA}" hay không? Đặt true nếu câu hỏi vẫn trả lời được trực tiếp — khi đó chuỗi
   đã sụp về một bước và câu hỏi vô dụng.

3. `troi_chay`: Câu ghép có đúng ngữ pháp tiếng Việt và đọc hiểu được không?

Chỉ nhận (`nhan` = true) khi: định danh duy nhất = true, trả lời được không cần bước 1 =
false, và trôi chảy = true. Hãy nghiêm khắc — thà loại nhầm còn hơn giữ lại câu hỏng."""

SCHEMA = {
    "type": "object",
    "properties": {
        "dinh_danh_duy_nhat": {"type": "boolean"},
        "tra_loi_duoc_khong_can_buoc_1": {"type": "boolean"},
        "troi_chay": {"type": "boolean"},
        "nhan": {"type": "boolean"},
        "ly_do": {"type": "string"},
    },
    "required": ["dinh_danh_duy_nhat", "tra_loi_duoc_khong_can_buoc_1",
                 "troi_chay", "nhan", "ly_do"],
    "additionalProperties": False,
}


def dotenv(name: str) -> str | None:
    f = ROOT / ".env"
    if not f.exists():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return None


def credits(key: str) -> float | None:
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/credits",
            headers={"Authorization": f"Bearer {key}", "User-Agent": "mcq-benchmark/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())["data"]
        return d["total_credits"] - d["total_usage"]
    except Exception:                                # noqa: BLE001
        return None


def call(model: str, key: str, r: dict, retries: int) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": PROMPT.format(**r)}],
        "max_tokens": 400, "temperature": 0, "reasoning": {"enabled": False},
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "judge", "strict": True, "schema": SCHEMA}},
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "mcq-benchmark/1.0"})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read())
            u = d.get("usage") or {}
            out = json.loads(d["choices"][0]["message"]["content"])
            out["_tok"] = (u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            return out
        except Exception as e:                       # noqa: BLE001
            if a == retries - 1:
                return {"nhan": False, "ly_do": f"LOI_API: {e}", "_tok": (0, 0)}
            time.sleep(1.5 * (a + 1))
    return {"nhan": False, "ly_do": "het_luot", "_tok": (0, 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data_v2/multihop_checked.json")
    ap.add_argument("--out", default="data_v2/multihop_final.json")
    ap.add_argument("--model", default="google/gemini-2.5-flash")
    ap.add_argument("--concurrency", type=int, default=24)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-credit", type=float, default=0.25,
                    help="dừng trước nếu số dư dưới ngưỡng này")
    args = ap.parse_args()

    key = dotenv("OPENROUTER_API_KEY")
    if not key:
        print("Chưa có OPENROUTER_API_KEY trong .env")
        return 1
    rows = json.loads((ROOT / args.inp).read_text(encoding="utf-8"))
    todo = [r for r in rows if r.get("strictOk")]
    if args.limit:
        todo = todo[: args.limit]

    bal = credits(key)
    est = len(todo) * 0.00020
    print(f"[giám khảo] {args.model} | {len(todo):,} chuỗi | số dư ${bal if bal is None else round(bal,2)}"
          f" | ước tính ${est:.2f}")
    if bal is not None and bal - est < args.min_credit:
        print(f"KHÔNG ĐỦ TIỀN: cần ~${est:.2f}, còn ${bal:.2f}, giữ lại ${args.min_credit}.")
        print(f"Giảm bớt bằng --limit {int((bal - args.min_credit) / 0.00020)}")
        return 1

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        res = list(ex.map(lambda r: call(args.model, key, r, args.retries), todo))

    tin = tout = 0
    tally: collections.Counter = collections.Counter()
    for r, v in zip(todo, res):
        tin += v["_tok"][0]
        tout += v["_tok"][1]
        r["judge"] = {k: val for k, val in v.items() if k != "_tok"}
        r["finalOk"] = bool(v.get("nhan"))
        if not r["finalOk"]:
            if not v.get("dinh_danh_duy_nhat", True):
                tally["mo_ta_khong_dinh_danh_duy_nhat"] += 1
            if v.get("tra_loi_duoc_khong_can_buoc_1"):
                tally["hop_collapse"] += 1
            if not v.get("troi_chay", True):
                tally["khong_troi_chay"] += 1
            if "LOI_API" in str(v.get("ly_do", "")):
                tally["loi_api"] += 1

    n = len(todo)
    ok = sum(1 for r in todo if r["finalOk"])
    print(f"\n{'='*70}\nGIÁM KHẢO ({n:,} chuỗi vào)\n{'='*70}")
    print(f"  NHẬN : {ok:5,}  ({ok/n*100:5.1f}%)")
    print(f"  LOẠI : {n-ok:5,}  ({(n-ok)/n*100:5.1f}%)")
    for k, v in tally.most_common():
        print(f"    {k:34s} {v:5,}  ({v/n*100:5.1f}%)")
    cost = tin / 1e6 * 0.30 + tout / 1e6 * 2.50
    print(f"\n  token: vào {tin:,} · ra {tout:,} | ~${cost:.2f} | {time.time()-t0:.0f}s")

    out = ROOT / args.out
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out}")

    good = [r for r in todo if r["finalOk"]]
    print(f"\n{'='*70}\n10 chuỗi QUA CẢ BỐN BƯỚC\n{'='*70}")
    for i, r in enumerate(good[:10], 1):
        print(f"\n[{i}] {r['composed']}")
        print(f"    đáp án: {r['answerB']}   (bước 1: {r['answerA']})")
    bad = [r for r in todo if not r["finalOk"] and r["judge"].get("tra_loi_duoc_khong_can_buoc_1")]
    print(f"\n{'='*70}\n5 chuỗi bị loại vì HOP COLLAPSE\n{'='*70}")
    for i, r in enumerate(bad[:5], 1):
        print(f"\n[{i}] {r['composed']}")
        print(f"    lý do: {r['judge'].get('ly_do','')[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
