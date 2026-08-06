#!/usr/bin/env bash
# Chạy TRÊN instance Lambda A10. Đánh giá nhiều model trên CẢ HAI benchmark
# trong cùng một phiên máy để chỉ trả tiền khởi động một lần.
#
# Cách 1 — clone repo (khuyến nghị):
#   git clone https://github.com/HiepDema/mcq_medical_benchmark.git
#   python3 -m venv ~/venv && ~/venv/bin/pip install -U pip && ~/venv/bin/pip install vllm
#   bash mcq_medical_benchmark/lambda/eval_models.sh
#
# Cách 2 — scp file lẻ vào $HOME rồi chạy `bash ~/eval_models.sh`.
#
# Script tự nhận biết đang ở layout nào. Mỗi lần chạy là MỘT TIẾN TRÌNH RIÊNG
# để vLLM giải phóng sạch VRAM; model nạp lại cho mỗi benchmark — chậm hơn vài
# phút nhưng an toàn hơn nhiều so với giữ hai engine trong một tiến trình.

set -uo pipefail          # cố ý KHÔNG dùng -e: một lần chạy lỗi thì vẫn chạy tiếp

# Chạy từ gốc repo nếu script nằm trong repo, ngược lại từ $HOME (luồng scp).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../eval_qwen3vl.py" ]; then
  cd "$SCRIPT_DIR/.." && DATA_DIR="processed_data"
else
  cd "$HOME" && DATA_DIR="."
fi
echo "Thư mục làm việc: $(pwd)   |   dữ liệu: $DATA_DIR"

PY="$HOME/venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "Chưa có venv. Tạo trước:"
  echo "  python3 -m venv ~/venv && ~/venv/bin/pip install -U pip && ~/venv/bin/pip install vllm"
  exit 1
fi

# tag | model_id | gpu_mem | max_model_len
#
# Dùng họ Qwen3 TEXT-ONLY: benchmark này không có ảnh nào, nên vision tower của
# bản -VL chỉ chiếm VRAM vô ích. Họ text cũng có bản 0.6B (họ VL nhỏ nhất là 2B).
# Cách biệt 0.6B -> 4B là ~7x, đủ rộng để đo độ phân biệt.
MODELS=(
  "0.6b|Qwen/Qwen3-0.6B|0.85|2048"
  "4b|Qwen/Qwen3-4B|0.88|2048"
)
# Muốn quay lại bản vision-language thì thay hai dòng trên bằng:
#   "2b|Qwen/Qwen3-VL-2B-Instruct|0.85|2048"
#   "4b|Qwen/Qwen3-VL-4B-Instruct|0.88|2048"
# (Qwen3-VL-8B ở BF16 ~17GB, sát trần A10 24GB — chính là lỗi OOM vừa gặp.)

# tag | file dữ liệu | file provenance | cờ thêm
DATASETS=(
  "multi|$DATA_DIR/benchmark_multi.json|$DATA_DIR/benchmark_multi_provenance.json|"
  "single|$DATA_DIR/benchmark_single.json|$DATA_DIR/benchmark_single_provenance.json|--single"
)

for f in "$DATA_DIR/benchmark_multi.json" "$DATA_DIR/benchmark_single.json"; do
  [ -f "$f" ] || { echo "Không thấy $f — kiểm tra lại thư mục."; exit 1; }
done

echo "=== Bắt đầu $(date '+%H:%M:%S') ==="
for m in "${MODELS[@]}"; do
  IFS='|' read -r mtag model gpumem maxlen <<< "$m"
  for d in "${DATASETS[@]}"; do
    IFS='|' read -r dtag data prov extra <<< "$d"
    out="eval_${dtag}_${mtag}.json"

    echo
    echo "############ $mtag × $dtag — $model ############"
    start=$(date +%s)

    # shellcheck disable=SC2086
    "$PY" eval_qwen3vl.py \
        --data "$data" --provenance "$prov" \
        --model "$model" --gpu-mem "$gpumem" --max-model-len "$maxlen" \
        --out "$out" $extra
    rc=$?

    dur=$(( $(date +%s) - start ))
    if [ $rc -eq 0 ]; then
      echo ">>> $mtag × $dtag XONG sau ${dur}s -> $out"
    else
      echo ">>> $mtag × $dtag LỖI (mã $rc) sau ${dur}s — bỏ qua, chạy tiếp"
    fi
    sleep 5           # để VRAM giải phóng hẳn
  done
done

echo
echo "=== Kết thúc $(date '+%H:%M:%S') ==="
ls -la eval_multi_*.json eval_single_*.json 2>/dev/null
echo
echo "Kéo kết quả về máy:"
echo "  scp -i <key> ubuntu@<ip>:~/eval_multi_*.json ubuntu@<ip>:~/eval_single_*.json ./"
echo "NHỚ TẮT INSTANCE sau khi kéo xong."
