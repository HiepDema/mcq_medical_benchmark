# Dựng benchmark MCQ nhiều đáp án từ 17 bộ đề gốc

Báo cáo quá trình tạo `final_benchmark_9368.json` — **9.368 câu hỏi nhiều đáp án**,
sinh tự động từ 17 bộ đề trắc nghiệm y khoa một đáp án, kèm bộ đối chứng là chính
các câu gốc đó.

| | |
|---|---|
| Nguồn | 17 file trong `source_data/`, 160.194 câu |
| Kết quả | `processed_data_v2/final_benchmark_9368.json` — **9.368 câu** |
| Đối chứng | `processed_data_v2/final_benchmark_9368_single.json` — 9.368 câu gốc, khớp 1:1 |
| Model | `Qwen/Qwen3-32B-FP8` trên vLLM 0.27.1, 1×H100 SXM5 80 GB |
| Lượt gọi LLM | 9.779 |
| Thời gian GPU | ~15 phút, gồm cả nạp model |
| Mã nguồn | [v2/](v2/), [gpu/vllm_batch.py](gpu/vllm_batch.py) |

---

## 1. Nạp và khử trùng lặp

```
tổng đọc vào : 160.194
giữ lại      : 122.017  (76,2%)
trùng lặp    :  30.913  
loại         :   7.264  (7.221 câu dưới 4 phương án, 43 câu hỏng khác)
```

**Khử trùng lặp phải làm trên toàn bộ 17 file gộp lại.** Các bộ đề này là những bản
export chồng lấn của cùng một ngân hàng câu hỏi — gần một phần tư số câu là trùng.

---

## 2. Bốn loại câu hỏi

Mỗi câu chỉ vào đúng một họ, ưu tiên meta → meta chữ cái → phủ định → pool.

| Họ | Dấu hiệu | Cách biến đổi | Ứng viên |
|---|---|---|---:|
| **file1** phủ định | `"... NGOẠI TRỪ:"`, `"câu nào SAI"` | đảo tập đáp án: 3 phương án còn lại đều đúng | **4.729** |
| **file2** meta | đáp án đúng là `"Tất cả đều đúng"` | xoá phương án meta, LLM viết thêm 2 nhiễu | **1.102** |
| **file3** pool | mọi phương án là danh sách ngăn bởi dấu phẩy | gộp các mục thành phương án độc lập | **3.048** |
| **file4** meta chữ cái | đáp án đúng là `"Cả A và B đều đúng"` và tương tự| đáp án suy từ chữ cái, LLM viết thêm nhiễu | **900** |
| | | | **9.779** |

9.779 ứng viên trên 122.017 câu nguồn — **8,0%**.

### Ví dụ mỗi họ

**file1** — `"Đâu KHÔNG PHẢI là tổn thương do rối loạn sinh sản tế bào:"`, đáp án gốc
`"Loạn sản"`. Viết lại phần dẫn thành khẳng định, giữ nguyên cả 4 phương án, đánh dấu
3 phương án không phải đáp án gốc là đúng.

**file2** — `"Các yếu tố thuận lợi của thủng ổ loét dạ dày tá tràng:"` với A/B/C đúng
và D là `"Tất cả đều đúng"`. Xoá D, LLM viết thêm hai nhiễu.

**file3** — câu kinh điển của bộ dữ liệu này:

```
Tạo máu nguyên thủy cung cấp các loại tế bào nào?
  A. Hồng cầu, bạch cầu hạt, tiểu cầu nguyên thủy
  B. Hồng cầu, bạch cầu lympho, tiểu cầu nguyên thủy
  C. Hồng cầu, bạch cầu hạt, đại thực bào
  D. Hồng cầu, đại thực bào, tiểu cầu nguyên thủy   <- đáp án đúng
```

Bốn phương án dùng chung một kho khái niệm. Gộp lại được 5 mục, đáp án mới chính là
ba mục nằm trong phương án D.

**file4** — đáp án đúng là `"Cả A và B đều đúng"`: A và B đúng, C là nhiễu có sẵn do
người ra đề viết, LLM viết thêm cho đủ 5 phương án.

### Giới hạn kích thước và bước cắt

FILE 3 nhận pool tới 8 mục, rồi **cắt ngẫu nhiên xuống 5 phương án**: giữ nguyên toàn
bộ đáp án đúng, chỉ bỏ bớt nhiễu (1.562 câu bị cắt), cắt sau khi lọc giữ được **3.048**.

---

## 3. Bộ dữ liệu

### `final_benchmark_9368.json`

| | |
|---|---|
| Số câu | **9.368** |
| Số phương án | 4 → 5.179 câu (55,3%) · 5 → 4.189 câu (44,7%). TB **4,45** |
| Số đáp án đúng | 2 → 1.901 · 3 → 7.102 · 4 → 365. TB **2,84** |
| Theo họ | file1 4.573 · file3 2.810 · file2 1.092 · file4 893 |
| Vị trí phương án SAI | A 3.332 · B 3.219 · C 3.359 · D 3.325 · E 1.858 |
| Câu mọi phương án đều đúng | **0** |

Trải trên cả 17 file nguồn, từ 117 câu (file nhỏ nhất) tới 1.153 câu.

Chủ đề chính: General Medicine 1.710 · Other 1.402 · Infectious Diseases 1.052 ·
Obstetrics and Gynecology 1.041 · Preventive Healthcare 936 · Public Health 868 ·
Eastern Medicine 699 · Pulmonology 569.

**Xáo trộn**: vị trí phương án trong từng câu trộn theo seed cố định.

### Thống kê số phương án và số đáp án đúng

**Số phương án, tách theo họ**

| Họ | n | 4 phương án | 5 phương án | TB |
|---|---:|---:|---:|---:|
| file1 phủ định | 4.573 | **4.573 (100%)** | 0 (0%) | 4,00 |
| file2 meta | 1.092 | 32 (3%) | **1.060 (97%)** | 4,97 |
| file3 pool | 2.810 | 501 (18%) | **2.309 (82%)** | 4,82 |
| file4 meta chữ cái | 893 | 73 (8%) | **820 (92%)** | 4,92 |
| **Tổng** | **9.368** | **5.179 (55%)** | **4.189 (45%)** | **4,45** |

**Số đáp án đúng, tách theo họ**

| Họ | n | 2 đúng | 3 đúng | 4 đúng | TB |
|---|---:|---:|---:|---:|---:|
| file1 phủ định | 4.573 | 0 | **4.573** | 0 | 3,00 |
| file2 meta | 1.092 | 0 | **1.092** | 0 | 3,00 |
| file3 pool | 2.810 | **1.329** | 1.116 | 365 | 2,66 |
| file4 meta chữ cái | 893 | **572** | 321 | 0 | 2,36 |
| **Tổng** | **9.368** | **1.901 (20,3%)** | **7.102 (75,8%)** | **365 (3,9%)** | **2,84** |

file1 và file2 **luôn đúng 3 đáp án**, cũng do cấu trúc: bỏ đúng một phương án (đáp án
gốc ở file1, phương án meta ở file2) khỏi bộ 4 phương án thì còn lại đúng 3. Toàn bộ
sự biến thiên nằm ở file3 và file4.

**Bảng chéo — số phương án × số đáp án đúng**

| | 2 đúng | 3 đúng | 4 đúng | Tổng |
|---|---:|---:|---:|---:|
| **4 phương án** | 488 | 4.691 | 0 | 5.179 |
| **5 phương án** | 1.413 | 2.411 | 365 | 4.189 |
| **Tổng** | 1.901 | 7.102 | 365 | 9.368 |

### `final_benchmark_9368_single.json`

Chính những câu đó, **nguyên văn từ file nguồn**, xếp theo đúng thứ tự bản nhiều đáp
án. Bản ghi thứ *i* của file này là bản gốc của bản ghi thứ *i* trong benchmark. Đã
kiểm tra: 9.368 cặp `(file nguồn, chỉ số)` đều duy nhất, ánh xạ 1:1 không hỏng.

Nhờ khớp 1:1 nên mọi chênh lệch điểm giữa hai bộ quy về **định dạng câu hỏi**, không
phải do bộ này khó hơn bộ kia.

### `final_benchmark_mixed.json` — bộ hỗn hợp 11.368 câu

**9.368 câu nhiều đáp án + 2.000 câu MỘT đáp án**, trộn lẫn vào nhau.
`final_benchmark_mixed_single.json` khớp 1:1 theo chỉ số: 9.368 dòng đầu là câu gốc
của bản nhiều đáp án, 2.000 dòng còn lại giống hệt bản kia.

Mục đích: model không biết trước câu nào có mấy đáp án nên phải **tự quyết định chọn
bao nhiêu ô** — thứ mà bộ thuần nhiều đáp án không đo được.

| | |
|---|---|
| Tổng | **11.368 câu** |
| Số phương án | 4 → 7.179 · 5 → 4.189 |
| Số đáp án đúng | **1 → 2.000** · 2 → 1.901 · 3 → 7.102 · 4 → 365 |
| Vị trí đáp án đúng của 2.000 câu | A 635 · B 507 · C 441 · D 417 |

**2.000 câu được chọn thế nào.** Lấy nguyên văn từ 122.017 câu đã khử trùng lặp, chống
trùng ba tầng: theo `uid`, theo cặp `(file nguồn, chỉ số)`, và theo gần trùng thân câu
(`SequenceMatcher > 0,90`, so với cả bản nhiều đáp án lẫn bản gốc của chúng, và giữa
2.000 câu mới với nhau).

| Loại khỏi kho ứng viên | Số câu |
|---|---:|
| gần trùng câu đã có trong benchmark | 20.000 |
| có phương án rác | 17.723 |
| đã dùng cho bản nhiều đáp án | 9.368 |
| phương án trùng nhau | 3.560 |
| thân câu hỏng / quá ngắn | 3.257 |
| đáp án đúng là meta (`"Tất cả đều đúng"`) | 764 |
| **còn lại đủ điều kiện** | **67.345** |

Loại câu có đáp án đúng là meta là có chủ đích — nó thực chất là câu nhiều đáp án trá
hình. Chọn rải đều 117–118 câu mỗi file trên cả 17 file, thay vì bốc ngẫu nhiên toàn kho.

**Không kế thừa lỗi lệch D.** "Luôn chọn D" chỉ ăn 20,9% trên 2.000 câu này, so với
41,5% ở `final_benchmark_9368_single.json` — vì lệch D vốn do hai họ `file2` và `file4`
gây ra, mà cả hai đều bị loại khỏi kho ứng viên. Vẫn còn lệch nhẹ về A: "luôn chọn A"
ăn 31,8%. Muốn triệt tiêu thì thêm `--shuffle-options`, khi đó cả hai file cùng được
trộn nên vẫn khớp nhau, chỉ là 2.000 câu không còn nguyên văn nữa.

**Mốc mù**

| Chiến lược | Toàn bộ 11.368 | Riêng 2.000 câu 1 đáp án | Riêng 9.368 câu nhiều đáp án |
|---|---:|---:|---:|
| chọn hết mọi phương án | 0,0% | 0,0% | 0,0% |
| chọn 3 phương án đầu | **12,6%** | **0,0%** | 15,3% |
| chọn ngẫu nhiên, mỗi ô 50% | 5,9% | 9,3% | 4,9% |

Trộn thêm câu một đáp án hạ mốc đoán mù từ 15,3% xuống **12,6%**.

**Chấm điểm.** Phải dùng `--mixed`; prompt của bộ thuần nhiều đáp án nói mọi câu đều có
từ 2 đáp án trở lên, sai với 2.000/11.368 câu. Trường `answerType` trong provenance
(`single` / `multi`) cho phép tách điểm hai nhóm.

```powershell
python eval_qwen3vl.py --data processed_data_v2/final_benchmark_mixed.json `
                       --provenance processed_data_v2/final_benchmark_mixed_provenance.json `
                       --mixed --baselines-only
```

### Hai file provenance

Ghi cho từng câu: file nguồn, chỉ số, mã định danh, họ, đáp án gốc, cờ chất lượng.

| Cờ | Số câu | Nghĩa |
|---|---:|---|
| `llm-verified` | 4.468 | file1, phần dẫn do LLM viết lại |
| `llm-screened` | 2.810 | file3, pool đã qua LLM sàng lọc |
| `llm-distractors` | 1.985 | file2 + file4, có phương án nhiễu do LLM sinh |
| `rule-only` | 105 | file1, dùng bản viết lại bằng luật |

---

## 4. Tái tạo

```powershell
python v2/run.py ingest route jobs        # -> llm_jobs/r1_*.jsonl
```
```bash
# trên máy H100
python3 -m venv ~/venv && ~/venv/bin/pip install vllm ninja
export PATH=$HOME/venv/bin:$PATH
python gpu/vllm_batch.py llm_jobs/r1_negation.jsonl llm_jobs/r1_distract.jsonl \
    llm_jobs/r1_pool.jsonl llm_jobs/r1_distract_letters.jsonl \
    --model Qwen/Qwen3-32B-FP8 --chunk 2048
```
```powershell
python v2/run.py apply
python v2/run.py build --skip-audit --out-name final_benchmark_9368
python v2/run.py mix                      # -> final_benchmark_mixed.json (11.368 câu)
```

### Chấm điểm bằng Qwen3-0.6B và Qwen3-4B

```bash
# trên máy có GPU — 2 model x 2 bộ, mỗi lượt một tiến trình riêng
bash lambda/eval_v2.sh mixed          # bộ hỗn hợp + bản một đáp án của nó
bash lambda/eval_v2.sh 9368           # bộ 9.368 + bản một đáp án
LIMIT=300 bash lambda/eval_v2.sh      # chạy thử 300 câu đầu mỗi bộ
```
```powershell
# so sánh hai định dạng trên cùng bộ câu hỏi, sau khi kéo eval_*.json về
python compare_benchmarks.py --multi eval_mixed_0.6b.json --single eval_mixedsingle_0.6b.json `
                             --multi eval_mixed_4b.json   --single eval_mixedsingle_4b.json `
                             --data processed_data_v2/final_benchmark_mixed.json `
                             --single-data processed_data_v2/final_benchmark_mixed_single.json `
                             --prov processed_data_v2/final_benchmark_mixed_provenance.json

python eval_qwen3vl.py --data processed_data_v2/final_benchmark_9368.json `
                       --provenance processed_data_v2/final_benchmark_9368_provenance.json `
                       --baselines-only
```
