#!/usr/bin/env python3
"""Chấm điểm model trên bộ MCQ nhiều đáp án (mặc định Qwen3-VL-4B).

Ba cách dùng:

  # 1) Chạy model rồi chấm luôn (cần GPU + vLLM)
  python eval_qwen3vl.py

  # 2) Chỉ tính các mốc so sánh, không cần model — chạy được trên laptop
  python eval_qwen3vl.py --baselines-only

  # 3) Chấm lại từ file dự đoán đã có, không nạp model
  python eval_qwen3vl.py --predictions results_raw.json

Chỉ số:
  exact match  — tập đáp án chọn đúng y hệt tập đáp án chuẩn (chỉ số chính)
  Jaccard      — điểm từng phần |giao| / |hợp|, tha thứ cho việc thiếu/thừa 1 lựa chọn
  micro F1     — coi mỗi phương án là một quyết định nhị phân chọn/không chọn

Luôn in kèm các mốc tầm thường ("chọn hết", "chọn 3 phương án đầu", chọn ngẫu
nhiên). Nếu model không vượt được các mốc này thì điểm cao cũng vô nghĩa.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "Qwen/Qwen3-VL-4B-Instruct"
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

PROMPT = """Đây là câu hỏi trắc nghiệm có NHIỀU ĐÁP ÁN ĐÚNG (từ 2 đáp án trở lên).

Câu hỏi: {question}

Các phương án:
{options}

Hãy chọn TẤT CẢ các phương án đúng. Trả lời bằng JSON đúng dạng {{"answers": ["A", "C"]}}, không giải thích gì thêm."""

# Dùng cho bộ đối chứng benchmark_single.json (--single). Phải khác prompt trên:
# hỏi "chọn tất cả" trên câu chỉ có 1 đáp án sẽ làm model chọn thừa và điểm sai lệch.
PROMPT_SINGLE = """Đây là câu hỏi trắc nghiệm có ĐÚNG MỘT đáp án đúng.

Câu hỏi: {question}

Các phương án:
{options}

Hãy chọn phương án đúng duy nhất. Chỉ trả lời bằng một chữ cái, không giải thích gì thêm."""


# ------------------------------------------------------------------ dữ liệu
def load_items(path: Path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for i, r in enumerate(rows):
        letters = [le for le in LETTERS if r.get("answer_option" + le)]
        gold = {m.group(1) for m in re.finditer(r"option([A-Z])", str(r["correctAnswer"]))}
        items.append({
            "index": i,
            "questionID": r.get("questionID"),
            "question": r["question"],
            "letters": letters,
            "options": {le: r["answer_option" + le] for le in letters},
            "gold": gold & set(letters),
        })
    return items


def load_subsets(prov_path: Path, n: int):
    if not prov_path.exists():
        return ["tất cả"] * n
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    return [p.get("subset", "?") for p in prov]


# ------------------------------------------------------------------ chỉ số
def score(items, preds: list[set]):
    """preds[i] = tập chữ cái model chọn cho câu i."""
    em = jac = 0.0
    tp = fp = fn = 0
    per_item = []
    for it, p in zip(items, preds):
        g = it["gold"]
        exact = 1.0 if p == g else 0.0
        inter, union = len(p & g), len(p | g)
        j = inter / union if union else 1.0
        em += exact
        jac += j
        tp += inter
        fp += len(p - g)
        fn += len(g - p)
        per_item.append({"index": it["index"], "questionID": it["questionID"],
                         "gold": sorted(g), "pred": sorted(p),
                         "exact": bool(exact), "jaccard": round(j, 3)})
    n = len(items) or 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"n": len(items), "exact_match": em / n, "jaccard": jac / n,
            "micro_precision": prec, "micro_recall": rec, "micro_f1": f1}, per_item


def baselines(items, single: bool = False):
    rng = random.Random(0)
    if single:                       # bộ 1 đáp án: "chọn hết" vô nghĩa
        return {
            "luôn chọn A": [{it["letters"][0]} for it in items],
            "chọn ngẫu nhiên 1 phương án": [{rng.choice(it["letters"])} for it in items],
        }
    return {
        "chọn hết": [set(it["letters"]) for it in items],
        "chọn 3 phương án đầu": [set(it["letters"][:3]) for it in items],
        "chọn ngẫu nhiên (mỗi phương án 50%)": [
            {le for le in it["letters"] if rng.random() < 0.5} or {it["letters"][0]}
            for it in items],
    }


def report(name, m, indent="  "):
    print(f"{indent}{name:<38} exact={m['exact_match']:6.1%}  "
          f"jaccard={m['jaccard']:6.1%}  microF1={m['micro_f1']:6.1%}  (n={m['n']})")


# ------------------------------------------------------------------ suy luận
THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)


def parse_answer(text: str, letters: list[str]) -> set:
    """Ưu tiên đọc JSON; hỏng thì nhặt chữ cái. Không đoán bừa khi rỗng."""
    # Model dòng Qwen3 sinh khối <think>...</think>; trong đó đầy chữ cái viết hoa
    # kiểu "options are A, B, C, D" -> phải bỏ đi trước khi dò đáp án.
    text = THINK.sub(" ", text or "")
    valid = set(letters)
    try:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            got = json.loads(m.group(0)).get("answers", [])
            picked = {str(x).strip().upper()[:1] for x in got} & valid
            if picked:
                return picked
    except Exception:  # noqa: BLE001
        pass
    return {c for c in re.findall(r"\b([A-Z])\b", text.upper())} & valid


def make_constrained(kind: str, value, max_tokens: int):
    """SamplingParams có ràng buộc cấu trúc. kind = 'choice' | 'json'.

    vLLM đổi API: GuidedDecodingParams (cũ, bị gỡ ở v0.12.0) -> StructuredOutputsParams.
    Thử lần lượt cả hai. KHÔNG âm thầm rơi về sinh tự do — nếu không ràng buộc được
    thì model dòng Qwen3 sẽ sinh khối <think> và toàn bộ kết quả thành rác.
    """
    from vllm import SamplingParams
    try:
        from vllm.sampling_params import StructuredOutputsParams as P
        return SamplingParams(temperature=0.0, max_tokens=max_tokens,
                              structured_outputs=P(**{kind: value})), "structured_outputs"
    except ImportError:
        pass
    try:
        from vllm.sampling_params import GuidedDecodingParams as P
        return SamplingParams(temperature=0.0, max_tokens=max_tokens,
                              guided_decoding=P(**{kind: value})), "guided_decoding"
    except ImportError as e:
        raise RuntimeError(
            "Bản vLLM này không có StructuredOutputsParams lẫn GuidedDecodingParams. "
            "Không ràng buộc được đầu ra -> kết quả sẽ là rác. "
            "Nâng cấp vLLM, hoặc chạy lại với --no-guided nếu bạn chấp nhận parse text tự do."
        ) from e


def run_model(items, model_id: str, max_model_len: int, gpu_mem: float,
              single: bool = False, enforce_eager: bool = False,
              no_guided: bool = False):
    from vllm import LLM, SamplingParams

    # KHÔNG truyền limit_mm_per_prompt: đặt giới hạn 0 làm engine core của vLLM
    # chết khi khởi tạo ("Engine core initialization failed"), cả với model
    # text-only lẫn model vision-language. Đây chỉ là tối ưu VRAM, không bắt buộc.
    kwargs = dict(model=model_id, max_model_len=max_model_len,
                  gpu_memory_utilization=gpu_mem, trust_remote_code=True)
    if enforce_eager:
        kwargs["enforce_eager"] = True      # bỏ CUDA graph, tiết kiệm 1-3 GB VRAM

    print(f"[eval] nạp model: {kwargs}", flush=True)
    llm = LLM(**kwargs)

    convs, sps, api = [], [], None
    template = PROMPT_SINGLE if single else PROMPT
    for it in items:
        opts = "\n".join(f"{le}. {it['options'][le]}" for le in it["letters"])
        convs.append([{"role": "user",
                       "content": template.format(question=it["question"], options=opts)}])
        if no_guided:
            # Không ràng buộc: cần nhiều token để model kịp thoát khối <think>.
            sps.append(SamplingParams(temperature=0.0, max_tokens=512))
        elif single:
            sp, api = make_constrained("choice", it["letters"], 8)
            sps.append(sp)
        else:
            # KHÔNG dùng "uniqueItems": backend guidance của vLLM chưa cài đặt khoá
            # này và sẽ ném "Grammar error: Unimplemented keys". Không cần thiết vì
            # parse_answer() trả về set nên phần tử lặp tự bị gộp.
            schema = {"type": "object", "additionalProperties": False,
                      "required": ["answers"],
                      "properties": {"answers": {
                          "type": "array", "minItems": 1,
                          "maxItems": len(it["letters"]),
                          "items": {"type": "string", "enum": it["letters"]}}}}
            sp, api = make_constrained("json", schema, 64)
            sps.append(sp)
    print(f"[eval] ràng buộc đầu ra: {api or 'KHÔNG (--no-guided)'}", flush=True)

    # Qwen3 mặc định bật chế độ suy nghĩ: sinh <think>...</think> ăn hết token.
    # Tắt qua chat template; bản vLLM cũ không nhận thì bỏ qua (ràng buộc cấu trúc
    # ở trên vẫn chặn được <think> vì grammar không cho phép token đó).
    try:
        outs = llm.chat(convs, sps, chat_template_kwargs={"enable_thinking": False})
    except TypeError:
        print("[eval] vLLM không nhận chat_template_kwargs — bỏ qua tắt thinking", flush=True)
        outs = llm.chat(convs, sps)
    raws = [o.outputs[0].text.strip() for o in outs]

    n_think = sum(1 for t in raws if "<think>" in t.lower())
    if n_think:
        print(f"[eval] ⚠ {n_think}/{len(raws)} câu vẫn còn khối <think> trong đầu ra "
              "— kiểm tra lại trước khi tin kết quả", flush=True)
    preds = []
    for t, it in zip(raws, items):
        got = parse_answer(t, it["letters"])
        if single and len(got) > 1:        # chỉ giữ chữ cái đầu tiên hợp lệ
            got = {next(le for le in it["letters"] if le in got)}
        preds.append(got)
    return preds, raws


# ------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="processed_data/benchmark_multi.json")
    ap.add_argument("--provenance", default="processed_data/benchmark_multi_provenance.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-model-len", type=int, default=2048)
    ap.add_argument("--gpu-mem", type=float, default=0.90)
    ap.add_argument("--out", default="eval_results.json")
    ap.add_argument("--predictions", help="chấm lại từ file dự đoán có sẵn, không nạp model")
    ap.add_argument("--baselines-only", action="store_true")
    ap.add_argument("--single", action="store_true",
                    help="bộ 1 đáp án (benchmark_single.json): đổi prompt + mốc so sánh")
    ap.add_argument("--enforce-eager", action="store_true",
                    help="bỏ CUDA graph — tiết kiệm 1-3 GB VRAM khi model sát trần")
    ap.add_argument("--no-guided", action="store_true",
                    help="tắt ràng buộc cấu trúc, parse text tự do (kết quả kém tin cậy)")
    args = ap.parse_args()

    items = load_items(ROOT / args.data)
    subsets = load_subsets(ROOT / args.provenance, len(items))
    if args.limit:
        items, subsets = items[: args.limit], subsets[: args.limit]
    mode = "MỘT đáp án" if args.single else "NHIỀU đáp án"
    print(f"Bộ dữ liệu: {len(items)} câu — {args.data}  [chế độ {mode}]\n")

    print("MỐC SO SÁNH (không dùng model):")
    for name, preds in baselines(items, args.single).items():
        m, _ = score(items, preds)
        report(name, m)

    if args.baselines_only:
        return 0

    if args.predictions:
        saved = json.loads((ROOT / args.predictions).read_text(encoding="utf-8"))
        by_idx = {d["index"]: set(d["pred"]) for d in saved.get("per_item", saved)}
        preds = [by_idx.get(it["index"], set()) for it in items]
        raws = [""] * len(items)
        tag = f"dự đoán có sẵn ({args.predictions})"
    else:
        preds, raws = run_model(items, args.model, args.max_model_len, args.gpu_mem,
                                single=args.single, enforce_eager=args.enforce_eager,
                                no_guided=args.no_guided)
        tag = args.model + (" [1 đáp án]" if args.single else "")

    m, per_item = score(items, preds)
    print(f"\nKẾT QUẢ MODEL — {tag}:")
    report("tổng thể", m)

    by = defaultdict(list)
    for it, p, s in zip(items, preds, subsets):
        by[s].append((it, p))
    print("\n  theo từng nguồn dữ liệu:")
    for s in sorted(by):
        sub_items = [x[0] for x in by[s]]
        sub_preds = [x[1] for x in by[s]]
        sm, _ = score(sub_items, sub_preds)
        report(s, sm, indent="    ")

    for d, s, raw in zip(per_item, subsets, raws):
        d["subset"] = s
        if raw:
            d["raw"] = raw
    (ROOT / args.out).write_text(
        json.dumps({"model": tag, "data": args.data, "metrics": m, "per_item": per_item},
                   ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"\nĐã ghi chi tiết từng câu -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
