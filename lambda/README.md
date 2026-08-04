# Chạy Qwen3-VL-30B trên Lambda A10

Bước LLM của FILE 3. Máy local chỉ điều khiển; toàn bộ suy luận chạy trên instance thuê.

## Chuẩn bị một lần

1. Lấy API key ở https://cloud.lambda.ai/api-keys
2. Đăng ký SSH key ở https://cloud.lambda.ai/ssh-keys (nhớ tên key)
3. Đặt biến môi trường (PowerShell):

```powershell
$env:LAMBDA_API_KEY      = "secret_..."
$env:LAMBDA_SSH_KEY_NAME = "ten-key-tren-lambda"
$env:LAMBDA_SSH_KEY_PATH = "$HOME\.ssh\id_ed25519"
# chỉ cần khi dùng --transfer git
$env:GIT_REPO_URL        = "https://github.com/<user>/<repo>.git"
```

## Chạy

```powershell
# 0. tạo đầu vào (nếu chưa có)
node pipeline\11_build_file3_input.js

# 1. kiểm tra cấu hình, KHÔNG bật máy, không tốn tiền
python lambda\run_remote.py --dry-run

# 2. thử 20 câu trước cho chắc (~10 phút máy, ~$0.13)
python lambda\run_remote.py --transfer scp --limit 20

# 3. chạy thật cả 714 câu
python lambda\run_remote.py --transfer scp

# 4. dựng FILE 3 từ kết quả
node pipeline\12_build_file3_output.js
```

`--transfer scp` copy thẳng file lên instance, không cần GitHub. Dùng `--transfer git`
nếu bạn muốn đúng luồng push-lên-GitHub-rồi-clone (repo phải có sẵn remote).

## ⚠ Thiết lập môi trường trên instance — LÀM TRƯỚC

Máy Lambda có sẵn scipy/numpy cài qua apt ở `/usr/lib/python3/dist-packages`.
Nếu `pip install --user vllm`, numpy 2.x sẽ vào `~/.local` và **che** numpy hệ thống,
nhưng scipy hệ thống thì vẫn cũ → gãy khi import:

```
ImportError: cannot import name 'Inf' from 'numpy'
```

(numpy 2 đã bỏ `np.Inf`, scipy cũ vẫn gọi tên đó.)

Luôn cài trong virtualenv riêng để cách ly khỏi package hệ thống:

```bash
python3 -m venv ~/venv        # mặc định KHÔNG thấy /usr/lib/python3/dist-packages
source ~/venv/bin/activate
pip install -U pip
pip install vllm

# kiểm tra trước khi tải model 8GB
python -c "import numpy,scipy,transformers,vllm; print(numpy.__version__, scipy.__version__, vllm.__version__)"
```

Cách chữa nhanh (nếu lỡ cài bằng `--user` rồi): `pip install --user -U scipy`
— scipy mới trong `~/.local` sẽ che bản apt cũ.

## An toàn chi phí

- Lệnh `terminate` nằm trong `finally` → instance vẫn tắt kể cả khi script lỗi hoặc Ctrl-C.
- `--max-minutes` (mặc định 90) đặt `timeout` cho lệnh suy luận trên máy.
- Nếu terminate thất bại 3 lần, script in cảnh báo to — **vào https://cloud.lambda.ai/instances tắt tay ngay**.
- `gpu_1x_a10` khoảng **$0.75/giờ**. Tải model + cài vLLM mất ~10–15 phút, suy luận 714 câu
  thêm ~10–20 phút → tổng thường dưới **$0.50**.

## Ghi chú kỹ thuật

- Model mặc định `QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ` (~17 GB, vừa A10 24 GB).
  Đổi bằng `MODEL_ID=... python3 lambda/gpu_infer.py` hoặc `--model`.
- Prompt thuần văn bản nên đặt `limit_mm_per_prompt={"image":0,"video":0}` để không
  cấp phát bộ nhớ cho ảnh/video.
- Đầu ra ép về đúng `CÓ`/`KHÔNG` bằng guided decoding; nếu bản vLLM không hỗ trợ thì
  rơi về parse text, và trường hợp mơ hồ được tính là `KHÔNG` (an toàn hơn nhận bừa).
- `max_model_len=2048` là dư: payload dài nhất chưa tới 600 token.
