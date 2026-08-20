#!/usr/bin/env bash
# Chấm Qwen3-0.6B và Qwen3-4B trên các bộ benchmark v2, trong cùng một phiên máy
# để chỉ trả tiền khởi động một lần.
#
#   bash lambda/eval_v2.sh              # bộ HỖN HỢP + bản một đáp án của nó
#   bash lambda/eval_v2.sh 9368         # bộ 9.368 nhiều đáp án + bản một đáp án
#   bash lambda/eval_v2.sh all          # cả bốn
#   LIMIT=300 bash lambda/eval_v2.sh    # chạy thử 300 câu đầu mỗi bộ
#
# Mỗi lượt là MỘT TIẾN TRÌNH RIÊNG để vLLM giải phóng sạch VRAM; model nạp lại cho
# mỗi bộ — chậm hơn vài phút nhưng an toàn hơn giữ hai engine trong một tiến trình.

set -uo pipefail          # cố ý KHÔNG dùng -e: một lượt lỗi thì vẫn chạy tiếp

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../eval_qwen3vl.py" ]; then
  cd "$SCRIPT_DIR/.." && DATA_DIR="processed_data_v2"
else
  cd "$HOME" && DATA_DIR="."          # luồng scp: mọi thứ nằm phẳng trong $HOME
fi

PY="$HOME/venv/bin/python"
[ -x "$PY" ] || { echo "Chưa có venv: python3 -m venv ~/venv && ~/venv/bin/pip install vllm"; exit 1; }
export PATH="$HOME/venv/bin:$PATH"     # tiến trình con của vLLM cần thấy ninja

WHICH="${1:-mixed}"
LIMIT="${LIMIT:-0}"
GPU_MEM="${GPU_MEM:-0.90}"
MAXLEN="${MAXLEN:-2048}"

# tag | model_id
# Họ Qwen3 text-only: benchmark không có ảnh nào nên vision tower chỉ tốn VRAM.
# Cách biệt 0.6B -> 4B khoảng 7 lần, đủ rộng để đo độ phân biệt của bộ đề.
MODELS=(
  "0.6b|Qwen/Qwen3-0.6B"
  "4b|Qwen/Qwen3-4B"
)

# tag | file dữ liệu | file provenance | cờ chế độ
#   (không cờ) = bộ thuần nhiều đáp án
#   --mixed    = bộ hỗn hợp, prompt KHÔNG tiết lộ câu nào có mấy đáp án
#   --single   = bộ thuần một đáp án
DS_MIXED=(
  "mixed|final_benchmark_mixed.json|final_benchmark_mixed_provenance.json|--mixed"
  "mixedsingle|final_benchmark_mixed_single.json|final_benchmark_mixed_single_provenance.json|--single"
)
DS_9368=(
  "multi|final_benchmark_9368.json|final_benchmark_9368_provenance.json|"
  "single|final_benchmark_9368_single.json|final_benchmark_9368_single_provenance.json|--single"
)
case "$WHICH" in
  mixed) DATASETS=("${DS_MIXED[@]}") ;;
  9368)  DATASETS=("${DS_9368[@]}") ;;
  all)   DATASETS=("${DS_MIXED[@]}" "${DS_9368[@]}") ;;
  *)     echo "Tham số phải là: mixed | 9368 | all"; exit 1 ;;
esac

for d in "${DATASETS[@]}"; do
  IFS='|' read -r _ data _ _ <<< "$d"
  [ -f "$DATA_DIR/$data" ] || { echo "Không thấy $DATA_DIR/$data"; exit 1; }
done

echo "Thư mục: $(pwd) | dữ liệu: $DATA_DIR | bộ: $WHICH"
[ "$LIMIT" != "0" ] && echo "CHẠY THỬ: chỉ $LIMIT câu đầu mỗi bộ"
echo "=== Bắt đầu $(date '+%H:%M:%S') ==="

for m in "${MODELS[@]}"; do
  IFS='|' read -r mtag model <<< "$m"
  for d in "${DATASETS[@]}"; do
    IFS='|' read -r dtag data prov extra <<< "$d"
    out="eval_${dtag}_${mtag}.json"
    log="log_${dtag}_${mtag}.txt"
    lim=""; [ "$LIMIT" != "0" ] && lim="--limit $LIMIT"

    echo
    echo "############ $mtag × $dtag — $model ############"
    start=$(date +%s)
    # shellcheck disable=SC2086
    "$PY" eval_qwen3vl.py \
        --data "$DATA_DIR/$data" --provenance "$DATA_DIR/$prov" \
        --model "$model" --gpu-mem "$GPU_MEM" --max-model-len "$MAXLEN" \
        --out "$out" $extra $lim 2>&1 | tee "$log"
    rc=${PIPESTATUS[0]}

    dur=$(( $(date +%s) - start ))
    if [ $rc -eq 0 ]; then
      echo ">>> $mtag × $dtag XONG sau ${dur}s -> $out"
    else
      echo ">>> $mtag × $dtag LỖI (mã $rc) sau ${dur}s — bỏ qua, chạy tiếp"
      # Nguyên nhân gốc của vLLM nằm PHÍA TRÊN traceback, in từ tiến trình con.
      echo ">>> nguyên nhân gốc, xem đầy đủ ở $log:"
      grep -n -i -m1 -B2 -A25 'error\|Traceback' "$log" | head -40 || tail -40 "$log"
    fi
    sleep 5           # để VRAM giải phóng hẳn
  done
done

echo
echo "=== Kết thúc $(date '+%H:%M:%S') ==="
ls -la eval_*.json 2>/dev/null

cat <<'MSG'

Kéo kết quả về máy local:
  scp lambda-gpu:'~/mcq/eval_*.json' .
So sánh hai định dạng trên cùng bộ câu hỏi:
  python compare_benchmarks.py --multi eval_mixed_0.6b.json --single eval_mixedsingle_0.6b.json \
                               --multi eval_mixed_4b.json   --single eval_mixedsingle_4b.json \
                               --data processed_data_v2/final_benchmark_mixed.json \
                               --single-data processed_data_v2/final_benchmark_mixed_single.json \
                               --prov processed_data_v2/final_benchmark_mixed_provenance.json
NHỚ TẮT INSTANCE sau khi kéo xong.
MSG
