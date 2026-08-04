#!/usr/bin/env bash
# Chạy TRÊN instance Lambda A10. Đánh giá lần lượt nhiều model trong CÙNG một
# phiên máy để chỉ trả tiền khởi động một lần.
#
#   scp -i <key> eval_qwen3vl.py lambda/eval_models.sh \
#       processed_data/benchmark_multi.json processed_data/benchmark_multi_provenance.json \
#       ubuntu@<ip>:~/
#   ssh -i <key> ubuntu@<ip> 'bash ~/eval_models.sh'
#
# Mỗi model chạy trong MỘT TIẾN TRÌNH RIÊNG để vLLM giải phóng sạch VRAM
# trước khi nạp model kế tiếp.

set -uo pipefail          # cố ý KHÔNG dùng -e: một model lỗi thì vẫn chạy tiếp model sau

cd "$HOME"
PY="$HOME/venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "Chưa có venv. Tạo trước:"
  echo "  python3 -m venv ~/venv && ~/venv/bin/pip install -U pip && ~/venv/bin/pip install vllm"
  exit 1
fi

# tên_hiển_thị | model_id | gpu_mem | max_model_len
MODELS=(
  "4b|Qwen/Qwen3-VL-4B-Instruct|0.85|2048"
  "8b|Qwen/Qwen3-VL-8B-Instruct|0.92|2048"
  "30b|QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ|0.92|2048"
)

echo "=== Bắt đầu $(date '+%H:%M:%S') ==="
for entry in "${MODELS[@]}"; do
  IFS='|' read -r tag model gpumem maxlen <<< "$entry"
  out="eval_results_${tag}.json"
  echo
  echo "################ $tag — $model ################"
  start=$(date +%s)

  "$PY" eval_qwen3vl.py \
      --data benchmark_multi.json \
      --provenance benchmark_multi_provenance.json \
      --model "$model" \
      --gpu-mem "$gpumem" \
      --max-model-len "$maxlen" \
      --out "$out"
  rc=$?

  dur=$(( $(date +%s) - start ))
  if [ $rc -eq 0 ]; then
    echo ">>> $tag XONG sau ${dur}s -> $out"
  else
    echo ">>> $tag LỖI (mã $rc) sau ${dur}s — bỏ qua, chạy tiếp model sau"
  fi
  # giải phóng VRAM còn treo trước khi nạp model kế tiếp
  sleep 5
done

echo
echo "=== Kết thúc $(date '+%H:%M:%S') ==="
ls -la eval_results_*.json 2>/dev/null
echo
echo "Kéo kết quả về máy:"
echo "  scp -i <key> ubuntu@<ip>:~/eval_results_*.json ./"
echo "NHỚ TẮT INSTANCE sau khi kéo xong."
