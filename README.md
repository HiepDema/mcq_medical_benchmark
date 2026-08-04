# MCQ Benchmark — bộ trắc nghiệm y khoa nhiều đáp án

Chuyển ngân hàng câu hỏi trắc nghiệm y khoa **một đáp án** thành bộ đánh giá
**nhiều đáp án**, kèm pipeline xử lý và script chấm điểm mô hình ngôn ngữ.

📄 **[REPORT.md](REPORT.md)** — báo cáo đầy đủ: phương pháp, số liệu từng bước,
các lỗi chất lượng phát hiện được, và kết quả đánh giá.

| | |
|---|---|
| Nguồn | `raw_data.json` — 10.242 câu, 1 đáp án đúng |
| Kết quả | `processed_data/benchmark_multi.json` — 326 câu, 2–5 đáp án đúng |
| Ngôn ngữ | Python 3.10+ (pipeline không cần thư viện ngoài) |

## Cấu trúc

```
raw_data.json          dữ liệu gốc — CHỈ ĐỌC, không tầng nào ghi đè
pyline/                pipeline Python, 16 tầng
  lib.py                 hàm dùng chung (tách chuỗi, nhận diện meta, uid, I/O)
  stages.py              tầng 01–12
  stage13..16.py         tầng dựng 3 bộ dữ liệu + gộp benchmark
  run.py                 CLI
pipeline/              bản Node.js gốc (giữ làm mốc đối chiếu, xem REPORT mục 8)
filter_data/           dữ liệu đã LỌC, chưa xử lý
processed_data/        dữ liệu đã chuyển sang nhiều đáp án + bộ benchmark gộp
eval_qwen3vl.py        chấm điểm model
compare_models.py      so sánh nhiều model, xuất bảng Markdown
lambda/                điều khiển GPU Lambda cho bước chạy model
data/                  file trung gian (không commit — tự sinh lại)
```

## Chạy pipeline

```bash
python pyline/run.py all      # làm sạch, phân loại, sinh file trung gian -> data/

MCQ_OUT_DIR=filter_data    python pyline/run.py 09 10 14
MCQ_OUT_DIR=processed_data python pyline/run.py 09 15
MCQ_DATA_DIR=filter_data MCQ_OUT_DIR=processed_data python pyline/run.py 13
MCQ_DATA_DIR=processed_data MCQ_OUT_DIR=processed_data python pyline/run.py 16
```

Trên PowerShell dùng `$env:MCQ_OUT_DIR="..."` thay cho tiền tố biến môi trường.

`MCQ_DATA_DIR` là nơi đọc (mặc định `data`), `MCQ_OUT_DIR` là nơi ghi (mặc định
trùng nơi đọc).

## Đánh giá model

```bash
python eval_qwen3vl.py --baselines-only        # chỉ mốc so sánh, không cần GPU
python eval_qwen3vl.py                          # chạy model (cần GPU + vLLM)
python eval_qwen3vl.py --predictions <file>     # chấm lại từ kết quả có sẵn
```

Ba chỉ số: **exact match** (chính), **Jaccard**, **micro F1**. Script luôn in kèm
các mốc tầm thường ("chọn hết", "chọn 3 phương án đầu", chọn ngẫu nhiên) — xem
REPORT mục 10 để hiểu vì sao điều này quan trọng.

Chạy nhiều model trên GPU thuê: xem [lambda/README.md](lambda/README.md).

## Nguyên tắc thiết kế

- **Ground truth suy ra, không bịa ra.** Tập đáp án mới đều dẫn xuất bằng quy tắc
  xác định từ `correctAnswer` của đề gốc. Ngoại lệ duy nhất (30 câu có phương án
  nhiễu do LLM sinh) được đánh dấu riêng bằng `qualityFlag`.
- **Không sửa dữ liệu gốc.** Mọi bản ghi bị loại đều nằm trong file `*_rejected` /
  `*_skipped` kèm lý do.
- **Truy vết đầy đủ.** Mỗi file dữ liệu có `*_provenance.json` đi kèm, ghép cặp
  theo chỉ số, cho biết câu đến từ đâu và đã bị biến đổi thế nào.
