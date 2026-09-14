#!/usr/bin/env bash
# Chấm bộ đề ĐIỀN TỪ bằng model mở trên máy GPU, nhiều model trong một phiên
# để chỉ trả tiền khởi động một lần.
#
#   bash lambda/eval_cloze.sh                  # cấu hình A10, cả hai nhánh
#   GPU=a100 bash lambda/eval_cloze.sh         # cấu hình A100 80GB
#   MODELS="4b|Qwen/Qwen3-4B" bash lambda/eval_cloze.sh
#   LIMIT=200 bash lambda/eval_cloze.sh        # chạy thử
#
# Mỗi lượt là MỘT TIẾN TRÌNH RIÊNG để vLLM giải phóng sạch VRAM giữa các model.

set -uo pipefail          # cố ý KHÔNG dùng -e: một lượt lỗi thì vẫn chạy tiếp

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

PY="${PY:-$HOME/venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
[ -x "$PY" ] || { echo "Không tìm thấy python. Tạo venv: python3 -m venv ~/venv && ~/venv/bin/pip install vllm"; exit 1; }
export PATH="$HOME/venv/bin:$PATH"     # tiến trình con của vLLM cần thấy ninja

GPU="${GPU:-a10}"
LIMIT="${LIMIT:-0}"
TP="${TP:-1}"

# Mặc định theo VRAM. Ghi đè bằng biến MODELS="tag|repo tag|repo".
case "$GPU" in
  a10)   DEF_MODELS="qwen3-4b|Qwen/Qwen3-4B gemma3-4b|google/gemma-3-4b-it"
         GPU_MEM="${GPU_MEM:-0.90}"; MAXLEN="${MAXLEN:-1536}"; EXTRA="--enforce-eager" ;;
  a100)  DEF_MODELS="qwen3-8b|Qwen/Qwen3-8B qwen3-14b|Qwen/Qwen3-14B qwen3-32b|Qwen/Qwen3-32B-FP8"
         GPU_MEM="${GPU_MEM:-0.92}"; MAXLEN="${MAXLEN:-2048}"; EXTRA="" ;;
  *)     echo "GPU phải là a10 hoặc a100"; exit 1 ;;
esac
MODELS="${MODELS:-$DEF_MODELS}"

for d in processed_data_v2/final_cloze_single.json processed_data_v2/final_cloze_multihop.json; do
  [ -f "$d" ] || { echo "Thiếu $d — chạy: python v2/cloze_build.py"; exit 1; }
done

LIMIT_ARG=""
[ "$LIMIT" != "0" ] && LIMIT_ARG="--limit $LIMIT"

for spec in $MODELS; do
  TAG="${spec%%|*}"; REPO="${spec#*|}"
  for DS in multihop single; do
    echo
    echo "=================================================================="
    echo "  $TAG  ($REPO)  —  nhánh $DS"
    echo "=================================================================="
    "$PY" v2/cloze_vllm.py --model "$REPO" --dataset "$DS" --tag "$TAG" \
        --gpu-mem "$GPU_MEM" --max-model-len "$MAXLEN" --tp "$TP" \
        $EXTRA $LIMIT_ARG
    echo "[xong] $TAG / $DS (mã thoát $?)"
  done
done

echo
echo "Kết quả nằm ở results_v2/cloze_*.json"
