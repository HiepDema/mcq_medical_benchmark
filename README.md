# MCQ Benchmark — bộ trắc nghiệm y khoa nhiều đáp án

Chuyển ngân hàng câu hỏi trắc nghiệm y khoa **một đáp án** thành bộ đánh giá
**nhiều đáp án**, kèm pipeline xử lý và script chấm điểm mô hình ngôn ngữ.

📄 **[REPORT.md](REPORT.md)** — báo cáo đầy đủ: phương pháp, số liệu từng bước,
các lỗi chất lượng phát hiện được, và kết quả đánh giá.

📝 **[iclr2027_vietnamese_medical_benchmark.tex](iclr2027_vietnamese_medical_benchmark.tex)**
— bản thảo bài báo (ICLR 2027) viết trên kết quả của pipeline v2.

Repo có **hai pipeline**. v2 là bản đang dùng; v1 giữ lại làm mốc đối chiếu.

| | v1 (`pyline/`) | v2 (`v2/`) |
|---|---|---|
| Nguồn | `raw_data.json` — 10.242 câu | `source_data/` — 17 bộ đề, 160.194 câu (không commit) |
| Khử trùng lặp | trong 1 file | toàn bộ 17 file gộp lại → còn 122.017 câu |
| Bộ nhiều đáp án | `processed_data/benchmark_multi.json` — 200 câu | `processed_data_v2/final_benchmark_9368.json` — 9.368 câu |
| Bộ trộn (giấu số đáp án) | — | `processed_data_v2/final_benchmark_mixed.json` — 11.368 câu |
| Bộ đối chứng 1 đáp án | `benchmark_single.json`, khớp chỉ số | `final_benchmark_*_single.json`, khớp chỉ số |

Ngôn ngữ: Python 3.10+ (pipeline không cần thư viện ngoài).

## Cấu trúc

```
raw_data.json          dữ liệu gốc v1 — CHỈ ĐỌC, không tầng nào ghi đè
pyline/                pipeline v1, Python, 17 tầng
  lib.py                 hàm dùng chung (tách chuỗi, nhận diện meta, uid, I/O)
  stages.py              tầng 01–12
  stage13..17.py         tầng lọc/dựng 3 bộ dữ liệu + gộp benchmark
  run.py                 CLI
v2/                    pipeline v2 — xem [v2/README.md](v2/README.md)
  s1..s6_*.py            ingest, route, jobs, apply, build, mix
  cloze_*.py             nhánh thử nghiệm bộ đề điền từ
  multihop_*.py          nhánh thử nghiệm multi-hop
pipeline/              bản Node.js gốc (giữ làm mốc đối chiếu, xem REPORT mục 8)
filter_data/           dữ liệu đã LỌC, chưa xử lý
processed_data/        kết quả v1
processed_data_v2/     kết quả v2 + bộ benchmark gộp
results_v2/            dự đoán từng câu của các model đã chấm
eval_qwen3vl.py        chấm model chạy cục bộ qua vLLM
eval_openrouter.py     chấm model API qua giao diện OpenAI-compatible
compare_models.py      so sánh nhiều model, xuất bảng Markdown
gpu/                   script chạy lô trên máy GPU thuê
lambda/                điều khiển GPU Lambda cho bước chạy model
data/, data_v2/        file trung gian (không commit — tự sinh lại)
source_data/           17 bộ đề nguồn (không commit — repo public)
```

## Chạy pipeline

Pipeline v2 (bản đang dùng) có hướng dẫn riêng ở [v2/README.md](v2/README.md).
Phần dưới là pipeline v1.

```bash
python pyline/run.py all      # làm sạch, phân loại, sinh file trung gian -> data/

MCQ_OUT_DIR=filter_data    python pyline/run.py 17 10 14
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
python eval_openrouter.py                       # chấm model API
```

Ba chỉ số: **exact match** (chính), **Jaccard**, **micro F1**. Script luôn in kèm
các mốc tầm thường ("chọn hết", "chọn 3 phương án đầu", chọn ngẫu nhiên) — xem
REPORT mục 10 để hiểu vì sao điều này quan trọng.

Dự đoán từng câu của các model đã chấm nằm ở `results_v2/`; bảng so sánh tổng hợp
xem [REPORT_MODELS_V2.md](REPORT_MODELS_V2.md).

Chạy nhiều model trên GPU thuê: xem [lambda/README.md](lambda/README.md).

## Nguyên tắc thiết kế

- **Ground truth suy ra, không bịa ra.** Tập đáp án mới đều dẫn xuất bằng quy tắc
  xác định từ `correctAnswer` của đề gốc. LLM chỉ lọc ứng viên, viết lại câu dẫn
  và sinh phương án nhiễu — không bao giờ được chọn đâu là đáp án đúng. Câu có
  phương án nhiễu do LLM sinh (1.985 câu ở bộ trộn v2) mang `qualityFlag:
  llm-distractors` trong file `*_provenance.json` để lọc ra được.
- **Không sửa dữ liệu gốc.** Mọi bản ghi bị loại đều nằm trong file `*_rejected` /
  `*_skipped` kèm lý do.
- **Truy vết đầy đủ.** Mỗi file dữ liệu có `*_provenance.json` đi kèm, ghép cặp
  theo chỉ số, cho biết câu đến từ đâu và đã bị biến đổi thế nào.
