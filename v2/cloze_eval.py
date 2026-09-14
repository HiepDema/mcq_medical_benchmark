#!/usr/bin/env python3
"""Chấm bộ đề ĐIỀN TỪ qua API tương thích OpenAI.

Chấm điểm là chỗ khó nhất của định dạng tự do tiếng Việt: đáp án có đồng nghĩa,
viết tắt, khác thứ tự từ. Ở đây KHÔNG dùng LLM làm giám khảo — làm vậy là biến
điểm số thành mức đồng thuận với model chấm, đúng cái vòng lặp mà cả dự án này
tránh. Thay vào đó dùng ba thang đo minh bạch, báo cáo cả ba:

  EM   khớp tuyệt đối sau chuẩn hoá (NFC, bỏ dấu câu, gộp khoảng trắng, thường hoá)
       -> thang nghiêm khắc, chắc chắn không chấm nhầm thành đúng
  F1   độ phủ token kiểu SQuAD -> điểm từng phần, chịu được khác biệt diễn đạt
  EM~  như EM nhưng BỎ DẤU tiếng Việt -> đo riêng phần model mất dấu

Và một chỉ số chẩn đoán quan trọng:

  TRÚNG NHIỄU   câu trả lời khớp đúng một phương án SAI của câu gốc.
                Đây là bằng chứng model sai THẬT, không phải lỗi chấm điểm do
                đồng nghĩa. Khoảng cách giữa (1 - EM) và tỉ lệ trúng nhiễu cho
                biết thang EM đang khắt khe quá mức bao nhiêu.

Với nhánh multi-hop còn đo thêm sự phụ thuộc giữa hai ô: ô (2) đúng bao nhiêu
phần khi ô (1) đúng, so với khi ô (1) sai.

Chạy:
    python v2/cloze_eval.py --model google/gemini-2.5-flash --dataset multihop
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASETS = {
    "single": "processed_data_v2/final_cloze_single.json",
    "multihop": "processed_data_v2/final_cloze_multihop.json",
}

SYSTEM = ("Bạn là chuyên gia y khoa. Điền vào chỗ trống. Chỉ trả lời nội dung cần điền, "
          "không giải thích, không nhắc lại câu hỏi.")

PROMPT = """Điền nội dung thích hợp vào {n} chỗ trống dưới đây.

{passage}

Trả lời ngắn gọn, mỗi chỗ trống một cụm từ. Không giải thích."""


def schema_for(n: int) -> dict:
    return {
        "type": "object",
        "properties": {str(i): {"type": "string"} for i in range(1, n + 1)},
        "required": [str(i) for i in range(1, n + 1)],
        "additionalProperties": False,
    }


# ---------------------------------------------------------------- chuẩn hoá

def norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t or "")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().lower()


def strip_tones(t: str) -> str:
    t = unicodedata.normalize("NFD", norm(t))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.replace("đ", "d")


def f1(pred: str, gold: str) -> float:
    p, g = norm(pred).split(), norm(gold).split()
    if not p or not g:
        return float(p == g)
    common = collections.Counter(p) & collections.Counter(g)
    same = sum(common.values())
    if same == 0:
        return 0.0
    pr, rc = same / len(p), same / len(g)
    return 2 * pr * rc / (pr + rc)


# ---------------------------------------------------------------- gọi API

def dotenv(name: str) -> str | None:
    f = ROOT / ".env"
    if not f.exists():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return None


def call(model: str, key: str, item: dict, max_tokens: int, retries: int) -> dict:
    n = item["nBlanks"]
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user",
                      "content": PROMPT.format(n=n, passage=item["passage"])}],
        "max_tokens": max_tokens, "temperature": 0, "reasoning": {"enabled": False},
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "cloze", "strict": True,
                                            "schema": schema_for(n)}},
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "mcq-benchmark/1.0"})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            u = d.get("usage") or {}
            return {"pred": json.loads(d["choices"][0]["message"]["content"]),
                    "tok": (u.get("prompt_tokens", 0), u.get("completion_tokens", 0))}
        except Exception as e:                       # noqa: BLE001
            if a == retries - 1:
                return {"pred": None, "err": str(e)[:120], "tok": (0, 0)}
            time.sleep(1.5 * (a + 1))
    return {"pred": None, "err": "het_luot", "tok": (0, 0)}


# ---------------------------------------------------------------- chấm

def grade(item: dict, pred: dict | None) -> dict:
    out = {"blanks": [], "answered": pred is not None}
    for b in item["blanks"]:
        p = (pred or {}).get(str(b["id"]), "") if pred else ""
        g = b["gold"]
        hit_d = any(norm(p) == norm(d) for d in b.get("distractors", []) if d)
        out["blanks"].append({
            "id": b["id"], "pred": p, "gold": g,
            "em": norm(p) == norm(g) and bool(norm(p)),
            "em_notone": strip_tones(p) == strip_tones(g) and bool(strip_tones(p)),
            "f1": round(f1(p, g), 4),
            "distractor": hit_d,
        })
    out["all_em"] = all(b["em"] for b in out["blanks"])
    return out


def report(rows: list[dict], track: str) -> None:
    ans = [r for r in rows if r["answered"]]
    n = len(ans)
    if not n:
        print("Không có câu nào trả lời được.")
        return
    flat = [b for r in ans for b in r["blanks"]]
    print(f"\n{'='*70}\nKẾT QUẢ — {track}  ({n:,}/{len(rows):,} câu trả lời được)\n{'='*70}")
    print(f"  theo TỪNG Ô ({len(flat):,} ô):")
    print(f"    EM  (khớp tuyệt đối)   {sum(b['em'] for b in flat)/len(flat)*100:5.1f}%")
    print(f"    EM~ (bỏ dấu)           {sum(b['em_notone'] for b in flat)/len(flat)*100:5.1f}%")
    print(f"    F1  (phủ token)        {sum(b['f1'] for b in flat)/len(flat)*100:5.1f}%")
    print(f"    trúng nhiễu (sai thật) {sum(b['distractor'] for b in flat)/len(flat)*100:5.1f}%")
    print(f"\n  theo CÂU: đúng hết mọi ô  {sum(r['all_em'] for r in ans)/n*100:5.1f}%")

    wrong = 1 - sum(b["em"] for b in flat) / len(flat)
    dist = sum(b["distractor"] for b in flat) / len(flat)
    print(f"\n  Khoảng cách chấm điểm: EM báo sai {wrong*100:.1f}%, trong đó chỉ "
          f"{dist*100:.1f} điểm là trúng nhiễu (sai chắc chắn).")
    print(f"  {max(0.0, wrong-dist)*100:.1f} điểm còn lại là 'không khớp chuỗi' — "
          f"lẫn cả sai thật lẫn diễn đạt khác.")

    if track == "multihop":
        both = [r for r in ans if len(r["blanks"]) == 2]
        h1 = [r for r in both if r["blanks"][0]["em"]]
        h0 = [r for r in both if not r["blanks"][0]["em"]]
        print(f"\n  PHỤ THUỘC HAI BƯỚC:")
        print(f"    ô(1) đúng -> ô(2) đúng: "
              f"{sum(r['blanks'][1]['em'] for r in h1)/max(len(h1),1)*100:5.1f}%  (n={len(h1)})")
        print(f"    ô(1) sai  -> ô(2) đúng: "
              f"{sum(r['blanks'][1]['em'] for r in h0)/max(len(h0),1)*100:5.1f}%  (n={len(h0)})")
        print("    Chênh lệch càng lớn thì chuỗi càng thực sự phụ thuộc nhau.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/gemini-2.5-flash")
    ap.add_argument("--dataset", required=True, choices=list(DATASETS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--tag")
    args = ap.parse_args()

    key = dotenv("OPENROUTER_API_KEY")
    if not key:
        print("Chưa có OPENROUTER_API_KEY trong .env")
        return 1
    items = json.loads((ROOT / DATASETS[args.dataset]).read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    tag = args.tag or args.model.split("/")[-1].replace(".", "")
    print(f"[chạy] {args.model} | cloze/{args.dataset} | {len(items):,} câu")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        res = list(ex.map(lambda it: call(args.model, key, it, args.max_tokens,
                                          args.retries), items))
    tin = sum(r["tok"][0] for r in res)
    tout = sum(r["tok"][1] for r in res)
    rows = []
    for it, r in zip(items, res):
        g = grade(it, r["pred"])
        g["id"] = it["id"]
        g["index"] = it["index"]
        if r.get("err"):
            g["err"] = r["err"]
        rows.append(g)

    report(rows, args.dataset)
    err = sum(1 for r in rows if not r["answered"])
    if err:
        print(f"\n  ⚠ {err:,} câu KHÔNG lấy được trả lời — đã loại khỏi mọi tỉ lệ ở trên.")
    print(f"\n  token: vào {tin:,} · ra {tout:,} | {time.time()-t0:.0f}s")

    out = ROOT / "results_v2" / f"cloze_{args.dataset}_{tag}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "dataset": args.dataset,
                               "usage": {"prompt": tin, "completion": tout},
                               "per_item": rows}, ensure_ascii=False), encoding="utf-8")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
