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
| Thời gian GPU | ~9 phút, gồm cả nạp model |
| Mã nguồn | [v2/](v2/), [gpu/vllm_batch.py](gpu/vllm_batch.py) |

---

## 1. Nạp và khử trùng lặp

```
tổng đọc vào : 160.194
giữ lại      : 122.017  (76,2%)
trùng lặp    :  30.913  (24.519 y hệt + 6.394 chỉ đảo thứ tự phương án)
loại         :   7.264  (7.221 câu dưới 4 phương án, 43 câu hỏng khác)
```

**Khử trùng lặp phải làm trên toàn bộ 17 file gộp lại.** Các bộ đề này là những bản
export chồng lấn của cùng một ngân hàng câu hỏi — gần một phần tư số câu là trùng.
Khử trong từng file rồi mới gộp thì cùng một câu sẽ vào benchmark nhiều lần.

Hai mức khử: trùng tuyệt đối theo `sha1(câu hỏi + các phương án)`, và trùng sau khi
chuẩn hoá thứ tự phương án.

---

## 2. phân bốn họ và lọc cơ học

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

## 3. Prompt gửi cho Qwen

Bốn lô việc, mỗi lô một prompt riêng và một JSON Schema **ép** đầu ra.

### Cấu hình chạy

| | |
|---|---|
| Model | `Qwen/Qwen3-32B-FP8` |
| `temperature` | `0.0` |
| `max_tokens` | 256 |
| Ép định dạng | `StructuredOutputsParams(json=<schema>)` |
| Chế độ nghĩ | `chat_template_kwargs={"enable_thinking": False}` |
| `max_model_len` | 4096 |
| `gpu_memory_utilization` | 0.90 |
| Khối ghi đĩa | 2048 việc |

---

### 3.1 — `r1_negation` (FILE 1, 4.729 việc)

````
Bạn là chuyên gia biên soạn đề trắc nghiệm y khoa.

Câu hỏi dưới đây được cho là dạng PHỦ ĐỊNH: nó yêu cầu chọn phương án SAI, hoặc có
chữ "ngoại trừ", "không đúng", "không phải". Nếu đúng như vậy thì mọi phương án TRỪ
đáp án gốc đều là phát biểu ĐÚNG.

CÂU HỎI GỐC: {question}

ĐÁP ÁN GỐC (tức là phương án SAI / bị loại trừ): {wrong}

BA PHƯƠNG ÁN CÒN LẠI:
{options}

Hãy trả lời 3 việc:

1. "la_phu_dinh": câu hỏi trên có thực sự là dạng phủ định như mô tả không?

2. "cau_hoi_moi": viết lại phần dẫn thành dạng KHẲNG ĐỊNH để có thể hỏi "chọn tất cả
các phương án đúng". Giữ nguyên toàn bộ nội dung chuyên môn, chỉ bỏ phần phủ định.
KHÔNG thêm câu "Chọn tất cả các đáp án đúng". KHÔNG kèm phương án.
   Ví dụ: "Các triệu chứng sau gặp trong bệnh X, NGOẠI TRỪ:" -> "Các triệu chứng sau
gặp trong bệnh X:"
   Ví dụ: "Điều nào sau đây KHÔNG ĐÚNG về thuốc Y?" -> "Điều nào sau đây đúng về thuốc Y?"

3. "ba_phuong_an_deu_dung": với câu hỏi mới đó, ba phương án còn lại có thực sự đều
đúng cả không?

Chỉ trả về JSON.
````

```json
{"type": "object", "additionalProperties": false,
 "required": ["la_phu_dinh", "cau_hoi_moi", "ba_phuong_an_deu_dung"],
 "properties": {"la_phu_dinh": {"type": "boolean"},
                "cau_hoi_moi": {"type": "string"},
                "ba_phuong_an_deu_dung": {"type": "boolean"}}}
```

Model **không** sinh phương án ở lô này — nó chỉ viết lại phần dẫn và trả lời hai câu
hỏi kiểm chứng. Bốn phương án gốc giữ nguyên, chỉ đảo nhãn.

---

### 3.2 — `r1_distract` (FILE 2, 1.102 việc)

````
Bạn là chuyên gia biên soạn đề trắc nghiệm y khoa.

CÂU HỎI: {question}

Ba phương án sau đây ĐỀU ĐÚNG với câu hỏi trên:
{options}

Hãy viết thêm ĐÚNG 2 phương án SAI (phương án nhiễu) cho câu hỏi này.

Yêu cầu bắt buộc:
- Phải SAI RÕ RÀNG về chuyên môn. Không được đúng một phần, không được là cách diễn
đạt khác của ba phương án trên, không được là khái niệm bao hàm chúng.
- Cùng chủ đề, cùng văn phong, độ dài tương đương ba phương án trên, để đọc qua vẫn
thấy hợp lý.
- Tiếng Việt, mỗi phương án là một cụm hoặc một câu ngắn. KHÔNG đánh số, KHÔNG thêm
chữ cái đầu dòng, KHÔNG giải thích.
- Cấm dùng các cụm kiểu "tất cả đều đúng", "không câu nào đúng", "cả A và B".

Đặt "chac_chan_sai" = true CHỈ KHI bạn chắc chắn cả 2 phương án vừa viết đều sai.

Chỉ trả về JSON.
````

```json
{"type": "object", "additionalProperties": false,
 "required": ["nhieu", "chac_chan_sai"],
 "properties": {"nhieu": {"type": "array", "minItems": 2, "maxItems": 2,
                          "items": {"type": "string"}},
                "chac_chan_sai": {"type": "boolean"}}}
```

Kết quả thật:

```
CÂU HỎI: Tinh dầu bạc hà (Menthol)... Tính chất nào sau đây đúng về cấu tạo của Menthol?
  [x] Là một monoterpene do có 10 carbon
  [x] Có sườn cơ bản là p-menthane
  [x] Là một chất ít tan trong nước
  [ ] Là một sesquiterpene do có 15 carbon     <- LLM viết
  [ ] Có sườn cơ bản là camphene                <- LLM viết
```

---

### 3.3 — `r1_distract_letters` (FILE 4, 900 việc)

Khác 4.2 ở chỗ đề gốc **đã có sẵn** phương án nhiễu do người ra đề viết. Phải nói cho
model biết để nó không viết trùng ý, và để nó lấy đó làm mốc độ khó.

````
Bạn là chuyên gia biên soạn đề trắc nghiệm y khoa.

CÂU HỎI: {question}

Các phương án sau ĐỀU ĐÚNG với câu hỏi trên:
{correct}

Phương án sau đây SAI, lấy nguyên từ đề gốc:
{wrong}

Hãy viết thêm ĐÚNG 2 phương án SAI cho câu hỏi này.

Yêu cầu bắt buộc:
- Phải SAI RÕ RÀNG về chuyên môn. Không được đúng một phần, không được là cách
diễn đạt khác của các phương án đúng ở trên.
- Không được trùng ý với phương án sai đã có (nếu có liệt kê ở trên).
- Cùng chủ đề, cùng văn phong, độ dài tương đương các phương án trên.
- Tiếng Việt, mỗi phương án là một cụm hoặc một câu ngắn. KHÔNG đánh số, KHÔNG
thêm chữ cái đầu dòng, KHÔNG giải thích.
- Cấm dùng các cụm kiểu "tất cả đều đúng", "không câu nào đúng", "cả A và B".

Đặt "chac_chan_sai" = true CHỈ KHI bạn chắc chắn cả 2 phương án vừa viết đều sai.

Chỉ trả về JSON.
````

Dùng chung schema với 4.2. Khối `Phương án sau đây SAI...` bị bỏ hẳn khỏi prompt với
373 câu không còn nhiễu gốc.

---

### 3.4 — `r1_pool` (FILE 3, 3.048 việc)

````
Bạn là chuyên gia biên soạn đề trắc nghiệm y khoa.

Câu hỏi trắc nghiệm 1 đáp án dưới đây có cả bốn phương án đều là DANH SÁCH các mục
ngăn cách bởi dấu phẩy. Ta muốn gộp tất cả các mục lại thành một danh sách phương án
độc lập, rồi hỏi "chọn tất cả các phương án đúng"; khi đó đáp án đúng chính là các mục
nằm trong phương án đúng gốc.

CÂU HỎI: {question}

PHƯƠNG ÁN GỐC:
{options}
Đáp án đúng gốc: {correct_letter}

DANH SÁCH MỤC SAU KHI GỘP (đánh số từ 0):
{pool}
Các mục thuộc đáp án đúng gốc: {correct_idx}

Hãy trả lời 3 việc:

1. "tach_duoc": các mục trên có phải là những khái niệm ĐỘC LẬP, đứng riêng vẫn có
nghĩa, và câu hỏi vẫn hợp lý khi hỏi "chọn tất cả các mục đúng" hay không?
   Trả false nếu: các mục chỉ có nghĩa khi đi liền nhau; đây là câu hỏi về thứ tự,
trình tự hay ghép cặp tương ứng; hoặc tách ra thì câu hỏi mất nghĩa.

2. "muc_sai_thuc_ra_dung": trong các mục KHÔNG thuộc đáp án đúng gốc, hãy liệt kê chỉ
số của những mục mà xét về chuyên môn thực ra CŨNG ĐÚNG với câu hỏi này (nếu để lại làm
phương án nhiễu thì đáp án chuẩn sẽ sai). Chỉ liệt kê khi bạn chắc chắn; không chắc thì
để mảng rỗng.

3. "do_tin_cay": mức tin cậy của bạn cho hai câu trả lời trên.

Chỉ trả về JSON, không giải thích.
````

```json
{"type": "object", "additionalProperties": false,
 "required": ["tach_duoc", "muc_sai_thuc_ra_dung", "do_tin_cay"],
 "properties": {"tach_duoc": {"type": "boolean"},
                "muc_sai_thuc_ra_dung": {"type": "array",
                                         "items": {"type": "integer", "minimum": 0}},
                "do_tin_cay": {"type": "string",
                               "enum": ["cao", "trung binh", "thap"]}}}
```

---

## 4. Bộ dữ liệu

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

### Hai file provenance

Ghi cho từng câu: file nguồn, chỉ số, mã định danh, họ, đáp án gốc, cờ chất lượng.

| Cờ | Số câu | Nghĩa |
|---|---:|---|
| `llm-verified` | 4.468 | file1, phần dẫn do LLM viết lại |
| `llm-screened` | 2.810 | file3, pool đã qua LLM sàng lọc |
| `llm-distractors` | 1.985 | file2 + file4, có phương án nhiễu do LLM sinh |
| `rule-only` | 105 | file1, dùng bản viết lại bằng luật |

---

## 10. Tái tạo

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

python eval_qwen3vl.py --data processed_data_v2/final_benchmark_9368.json `
                       --provenance processed_data_v2/final_benchmark_9368_provenance.json `
                       --baselines-only
```
