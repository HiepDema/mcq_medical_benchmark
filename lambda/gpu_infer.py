#!/usr/bin/env python3
"""Chạy TRÊN instance Lambda A10.

Đọc data/11_file3_llm_input.json, hỏi Qwen3-VL-30B từng câu có tách được
thành dạng nhiều đáp án hay không, ghi ra data/12_file3_llm_verdicts.json.

Đầu ra bị ép về đúng "CÓ" / "KHÔNG" bằng guided decoding nên luôn parse được.
"""
import argparse, json, os, sys, time
from pathlib import Path

# AWQ 4-bit ~17GB, vừa A10 24GB. Bản text-only là drop-in: đổi biến này thành
# "Qwen/Qwen3-30B-A3B-Instruct-2507" (hoặc bản AWQ tương ứng) nếu muốn bỏ vision tower.
DEFAULT_MODEL = os.environ.get("MODEL_ID", "QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ")

PROMPT_TEMPLATE = '''Xét câu hỏi này: {"question": "Tạo máu nguyên thủy cung cấp các loại tế bào nào?", "answer_optionA": "Hồng cầu, bạch cầu hạt, tiểu cầu nguyên thủy",
"answer_optionB": "Hồng cầu, bạch cầu lympho, tiểu cầu nguyên thủy",
"answer_optionC": "Hồng cầu, bạch cầu hạt, đại thực bào",
"answer_optionD": "Hồng cầu, đại thực bào, tiểu cầu nguyên thủy", "correctAnswer": "optionD",
}. Câu hỏi này có thể tách thành dạng nhiều đáp án, với các phương án lần lượt là "hồng cầu", "bạch cầu lympho", "bạch cầu hạt", "tiểu cầu nguyên thủy", "đại thực bào" và khi đó các đáp án mới là "hồng cầu", "tiểu cầu nguyên thủy" và "đại thực bào". 
Hãy suy nghĩ logic tương tự, không xét kiến thức chuyên môn, hãy cho biết câu hỏi sau đây có tách thành dạng nhiều đáp án hay không. CHỈ TRẢ LỜI "CÓ" HOẶC "KHÔNG", KHÔNG CẦN GIẢI THÍCH VÀ HÃY SUY NGHĨ NHANH. 
Câu hỏi như sau:{payload}'''

CHOICES = ["CÓ", "KHÔNG"]


def normalize(text: str) -> str:
    """Phòng khi guided decoding không khả dụng: rút CÓ/KHÔNG từ text tự do."""
    t = (text or "").strip().upper()
    if t.startswith("KHÔNG") or t.startswith("KHONG") or t.startswith("NO"):
        return "KHÔNG"
    if t.startswith("CÓ") or t.startswith("CO") or t.startswith("YES"):
        return "CÓ"
    return "KHÔNG"          # không rõ ràng -> loại, an toàn hơn là nhận bừa


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/11_file3_llm_input.json")
    ap.add_argument("--output", default="data/12_file3_llm_verdicts.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-model-len", type=int, default=2048)
    ap.add_argument("--gpu-mem", type=float, default=0.92)
    ap.add_argument("--limit", type=int, default=0, help="chỉ chạy N câu đầu (để thử prompt)")
    args = ap.parse_args()

    items = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    print(f"[infer] {len(items)} câu | model={args.model}", flush=True)

    from vllm import LLM, SamplingParams

    llm = LLM(
        model=args.model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_mem,
        # Prompt của ta thuần văn bản -> không cấp phát bộ nhớ cho ảnh/video.
        limit_mm_per_prompt={"image": 0, "video": 0},
        trust_remote_code=True,
    )

    # Ép đầu ra vào đúng 2 lựa chọn. Nếu bản vLLM không hỗ trợ thì rơi về parse text.
    guided_ok = True
    try:
        from vllm.sampling_params import GuidedDecodingParams
        sampling = SamplingParams(
            temperature=0.0, max_tokens=8,
            guided_decoding=GuidedDecodingParams(choice=CHOICES),
        )
    except Exception as e:                                   # noqa: BLE001
        guided_ok = False
        print(f"[infer] guided decoding không dùng được ({e}); rơi về parse text", flush=True)
        sampling = SamplingParams(temperature=0.0, max_tokens=8)

    convs = [
        [{"role": "user", "content": PROMPT_TEMPLATE.format(
            payload=json.dumps(it["payload"], ensure_ascii=False))}]
        for it in items
    ]

    t0 = time.time()
    outs = llm.chat(convs, sampling)                          # vLLM tự batch cả lô
    dt = time.time() - t0

    results = []
    for it, o in zip(items, outs):
        raw = o.outputs[0].text.strip()
        results.append({
            "uid": it["uid"],
            "sourceIndex": it["sourceIndex"],
            "verdict": raw if (guided_ok and raw in CHOICES) else normalize(raw),
            "rawOutput": raw,
        })

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    yes = sum(1 for r in results if r["verdict"] == "CÓ")
    print(f"[infer] xong {len(results)} câu trong {dt:.1f}s "
          f"({len(results)/max(dt,1e-9):.1f} câu/s)", flush=True)
    print(f"[infer] CÓ={yes}  KHÔNG={len(results)-yes}  -> {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
