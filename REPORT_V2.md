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

Bản trước ([REPORT.md](REPORT.md), [REPORT_COMPARE.md](REPORT_COMPARE.md)) làm trên
một file 10.242 câu và cho ra 150–300 câu.

---

## 1. Nguyên tắc nền

**Đáp án đúng luôn suy ra từ trường `correctAnswer` của đề gốc.** LLM chỉ được làm ba
việc: phán xét một câu có dùng được không, viết văn bản phương án nhiễu, và viết lại
phần dẫn. Nó không bao giờ được tự quyết định đâu là đáp án đúng.

Đây không phải chi tiết vụn vặt mà là điều kiện để benchmark có nghĩa. Nếu để model
tự chọn đáp án, ta chỉ đo được mức độ giống nhau giữa model sinh dữ liệu và model bị
chấm, chứ không đo được kiến thức. Ranh giới này giữ ở mọi tầng: ở FILE 3, LLM chỉ có
quyền **xoá** một mục khỏi danh sách nhiễu, không có quyền thêm mục vào tập đáp án.

---

## 2. Tầng 1 — nạp và khử trùng lặp

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

### Bóc tiền tố chữ cái

5.889 câu có phương án mang tiền tố lặp lại chính chữ cái của nó:

```
A. "A. Bệnh phổi tắc nghẽn mãn tính"
B. "B. Hen"
```

Nếu để nguyên thì ở FILE 2, ba phương án đúng lấy từ đề gốc sẽ có tiền tố còn phương
án nhiễu do LLM viết thì không — model bị chấm chỉ cần nhìn dấu hiệu đó là biết đáp
án mà không cần đọc nội dung. Phát hiện khi soi tay 20 câu chạy thử.

Chỉ bóc khi có **từ hai phương án trở lên** mang dấu đúng vị trí của chính nó, để
không cắt nhầm chuỗi kiểu `"D, L-alanine"`. Bóc trước khi tính mã định danh, nhờ vậy
hai bản export của cùng một câu nhận ra được nhau: số câu trùng phát hiện được tăng
từ 29.797 lên 30.913.

---

## 3. Tầng 2 — phân bốn họ và lọc cơ học

Mỗi câu chỉ vào đúng một họ, ưu tiên meta → meta chữ cái → phủ định → pool.

| Họ | Dấu hiệu | Cách biến đổi | Ứng viên |
|---|---|---|---:|
| **file1** phủ định | `"... NGOẠI TRỪ:"`, `"câu nào SAI"` | đảo tập đáp án: 3 phương án còn lại đều đúng | **4.729** |
| **file2** meta | đáp án đúng là `"Tất cả đều đúng"` | xoá phương án meta, LLM viết thêm 2 nhiễu | **1.102** |
| **file3** pool | mọi phương án là danh sách ngăn bởi dấu phẩy | gộp các mục thành phương án độc lập | **3.048** |
| **file4** meta chữ cái | đáp án đúng là `"Cả A và B đều đúng"` | đáp án suy từ chữ cái, LLM viết thêm nhiễu | **900** |
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
người ra đề viết, LLM viết thêm cho đủ 5 phương án. 373 câu không còn nhiễu gốc nào
(vì đề có hai phương án meta), với những câu đó cả hai nhiễu đều do LLM viết.

### Các bộ lọc cơ học

Chạy trước khi tốn GPU:

- **dấu phẩy thập phân** (`0,5 g/l`) — bảo vệ bằng ký tự canh trước khi tách
- **pool toàn số** — trên 60% số mục là số hoặc đơn vị đo
- **overlap < 0,2**, với `overlap = 1 − (số mục khác nhau / tổng số mục)`
- **dãy có thứ tự** — mục lặp trong cùng phương án, hoặc thân câu chứa
  "thứ tự / lần lượt / tương ứng / theo trình tự"
- **câu xếp hạng** — hai phương án có cùng tập mục, chỉ khác thứ tự
- **phương án rác** — `None`, `Không có`, `...`, chỉ toàn số, trùng nhau, chứa meta
- **thân câu có chỗ trống** `......` hoặc `___`
- **gần trùng** — khử theo khối (8 ký tự đầu + dải độ dài), `SequenceMatcher > 0,90`.
  So từng đôi trên 122.017 câu là bất khả thi; chia khối rồi chỉ so trong khối vẫn bắt
  được các bản export chỉ khác nhau dấu câu. Loại thêm 2.209 câu

### Giới hạn kích thước và bước cắt

FILE 3 nhận pool tới 8 mục, rồi **cắt ngẫu nhiên xuống 5 phương án**: giữ nguyên toàn
bộ đáp án đúng, chỉ bỏ bớt nhiễu (1.562 câu bị cắt). Chặn cứng ở 5 ngay tầng lọc thì
chỉ còn 1.280 ứng viên; cắt sau khi lọc giữ được **3.048**.

Bước cắt đặt ở tầng dựng chứ không phải tầng lọc: LLM vẫn nhìn thấy trọn pool khi
phán xét nên chỉ số nó trả về vẫn khớp, và cắt phải chạy **sau** khi LLM gỡ các mục
nhiễu thực ra đúng.

---

## 4. Prompt gửi cho Qwen

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

Ba ràng buộc bắt buộc trong [gpu/vllm_batch.py](gpu/vllm_batch.py), rút ra từ một lượt
chạy hỏng ở phiên bản trước:

1. **Không có structured outputs thì dừng hẳn**, không âm thầm chuyển sang sinh tự do.
   Ở v1, `GuidedDecodingParams` bị gỡ khỏi vLLM 0.12 → import lỗi → rơi về sinh tự do
   → hỏng trọn một lượt benchmark mà nhìn log không thấy gì bất thường.
2. **Tắt thinking của Qwen3.** Để nguyên thì `<think>` ăn hết ngân sách token. Vẫn cắt
   `<think>` khi parse để chắc chắn.
3. **Ghi ra đĩa theo từng khối, bỏ qua id đã có** → đứt giữa chừng chạy lại được.

JSON Schema tránh `uniqueItems`, `minLength`, `maxLength` — xgrammar không hỗ trợ
(`uniqueItems` từng gây `Grammar error: Unimplemented keys`). Các ràng buộc đó kiểm ở
phía Python trong `s4_apply.py`.

---

### 4.1 — `r1_negation` (FILE 1, 4.729 việc)

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

### 4.2 — `r1_distract` (FILE 2, 1.102 việc)

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

### 4.3 — `r1_distract_letters` (FILE 4, 900 việc)

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

### 4.4 — `r1_pool` (FILE 3, 3.048 việc)

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

Một prompt thật sau khi điền:

```
CÂU HỎI: Viêm não virus, sao bào tăng sinh trong giai đoạn nào?

PHƯƠNG ÁN GỐC:
A. Viêm cấp tính, giai đoạn phá hủy và hàn gắn mô
B. Viêm cấp tính, giai đoạn hàn gắn mô
C. Viêm cấp tính, giai đoạn phản ứng mô
D. Viêm mạn tính mất chất nhiều, giai đoạn phản ứng mô
Đáp án đúng gốc: D

DANH SÁCH MỤC SAU KHI GỘP (đánh số từ 0):
0. Viêm cấp tính
1. Giai đoạn phá hủy
2. Hàn gắn mô
3. Giai đoạn hàn gắn mô
4. Giai đoạn phản ứng mô
5. Viêm mạn tính mất chất nhiều
Các mục thuộc đáp án đúng gốc: [4, 5]
```

Ở lô này model **chỉ có quyền xoá**. Nó chỉ ra mục nào đang làm nhiễu nhưng thực ra
cũng đúng, mục đó bị gỡ khỏi danh sách — 233 mục bị gỡ trên toàn bộ. Số phương án chỉ
có giảm, không bao giờ tăng.

---

### 4.5 — Kết quả vòng gọi

| Lô | Việc | Parse được | Tốc độ |
|---|---:|---:|---:|
| `r1_negation` | 4.729 | 4.728 | 29,4 việc/s |
| `r1_distract` | 1.102 | 1.102 | 33,1 việc/s |
| `r1_pool` | 3.048 | 3.048 | 24,7 việc/s |
| `r1_distract_letters` | 900 | 900 | 33,4 việc/s |
| **Tổng** | **9.779** | **9.778** | ~6 phút |

Cộng ~3 phút nạp model và capture CUDA graph.

---

## 5. Tầng 4 — áp kết quả và dựng câu hỏi

```
FILE 1: 4.573/4.729   (LLM viết lại phần dẫn ở 4.468 câu; 105 câu dùng bản viết lại cơ học)
FILE 2: 1.092/1.102
FILE 3: 2.810/3.048   (LLM gỡ 233 mục; cắt bớt nhiễu ở 1.562 câu)
FILE 4:   893/900
tổng  : 9.368         (loại 401)
```

Lý do loại: `llm_tu_choi` 155 · `llm_noi_khong_tach_duoc` 108 · `pool_sai_kich_thuoc`
88 · `tap_dap_an_khong_hop_le` 39 · `khong_du_phuong_an` 7 · `stem_too_short` 3 ·
`thieu_phan_quyet` 1.

### Không nhận thẳng đầu ra của model

**Phần dẫn viết lại** chỉ được dùng nếu còn sạch: không còn dấu phủ định, dài từ 0,4
đến 1,8 lần câu gốc, không bắt đầu bằng nhãn phương án. Không đạt thì rơi về bản viết
lại bằng luật — xảy ra ở 105 câu.

**Phương án nhiễu** phải dài 2–200 ký tự, không phải meta, không phải rác, và không
giống quá 85% bất kỳ phương án đúng nào hay nhiễu còn lại. Trong 1.985 câu có nhiễu
LLM, 1.932 câu giữ được cả 2 nhiễu, 53 câu chỉ giữ được 1.

**Cờ `chac_chan_sai` không dùng để lọc.** Ở lô chạy thử 20 câu, cả 20 đều trả `true`,
kể cả câu có nhiễu `"thiếu máu cục bộ"` thực ra là nguyên nhân có thật của viêm tụy
cấp. Model tự chấm mình trong cùng một lượt gọi thì gần như vô giá trị. Cờ đó chỉ được
ghi vào provenance.

### Cổng bất biến

Mọi bản ghi qua `lib2.validate()` trước khi ghi ra: ít nhất 4 phương án, số đáp án
đúng từ 2 trở lên và nhỏ hơn tổng số phương án, không phương án trùng nhau, không
phương án rác, `correctAnswer` trỏ đúng chỗ. Câu hỏng vào `data_v2/04_rejected.json`
kèm lý do — không im lặng bỏ qua.

---

## 6. Bộ dữ liệu

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

**Xáo trộn hai lần**: vị trí phương án trong từng câu trộn theo seed lấy từ mã định
danh câu hỏi (một lần ở tầng dựng, một lần ở tầng xuất), và thứ tự câu hỏi trong file
trộn theo seed cố định `20260815`. Chạy lại luôn ra cùng kết quả.

### Thống kê số phương án và số đáp án đúng

**Số phương án, tách theo họ**

| Họ | n | 4 phương án | 5 phương án | TB |
|---|---:|---:|---:|---:|
| file1 phủ định | 4.573 | **4.573 (100%)** | 0 (0%) | 4,00 |
| file2 meta | 1.092 | 32 (3%) | **1.060 (97%)** | 4,97 |
| file3 pool | 2.810 | 501 (18%) | **2.309 (82%)** | 4,82 |
| file4 meta chữ cái | 893 | 73 (8%) | **820 (92%)** | 4,92 |
| **Tổng** | **9.368** | **5.179 (55%)** | **4.189 (45%)** | **4,45** |

Hình dạng bị chi phối bởi cách biến đổi từng họ:

- **file1 luôn đúng 4 phương án** vì nó giữ nguyên bộ phương án gốc, chỉ đảo nhãn —
  không thêm không bớt. Đây cũng là họ đông nhất nên kéo tỉ lệ 4-phương-án lên 55%.
- **file2 gần như luôn 5** (3 phương án đúng + 2 nhiễu LLM). 32 câu chỉ đạt 4 vì một
  trong hai nhiễu bị bộ lọc loại (trùng ý phương án đúng, hoặc là meta).
- **file3 và file4 chủ yếu 5**, phần 4 phương án đến từ pool nhỏ (file3) hoặc từ câu
  chỉ giữ được 1 nhiễu (file4).

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

**Số phương án SAI mỗi câu** — chính là thứ quyết định mốc đoán mù:

| Số phương án sai | Số câu | Tỉ lệ |
|---|---:|---:|
| 1 | 5.056 | **54,0%** |
| 2 | 2.899 | 30,9% |
| 3 | 1.413 | 15,1% |

Hơn một nửa số câu chỉ có **một** phương án sai. Với câu 4 phương án 3 đáp án đúng
(4.691 câu, ô lớn nhất bảng chéo), chiến lược mù "chọn bừa 3 trong 4" ăn đúng 25%.
Đó là nguồn gốc của mốc "chọn 3 phương án đầu" = 15,3% ở mục 7 — không phải rò rỉ dữ
liệu mà là hệ quả toán học của hình dạng câu hỏi.

Muốn hạ mốc đó thì phải tăng số phương án sai mỗi câu, nghĩa là cho LLM sinh thêm
nhiễu cho cả file1 — hiện file1 không được sinh nhiễu, nó chỉ đảo nhãn bộ phương án
gốc.

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

Kèm theo: danh sách mục nhiễu LLM đã gỡ, danh sách nhiễu bị cắt khi thu về 5 phương
án, và cờ `llmChacChanSai` của model.

---

## 7. Mốc so sánh mù

Không dùng model, tính trên đúng 9.368 câu này. Mọi kết quả chấm model đều phải báo
cáo kèm những con số này — không vượt được chúng thì điểm cao vô nghĩa.

| Bộ | Chiến lược | exact | jaccard |
|---|---|---:|---:|
| Nhiều đáp án | chọn hết mọi phương án | **0,0%** | 64,8% |
| Nhiều đáp án | chọn 3 phương án đầu | **15,3%** | 52,9% |
| Nhiều đáp án | chọn ngẫu nhiên, mỗi phương án 50% | 5,1% | 41,1% |
| Một đáp án | chọn ngẫu nhiên 1 trong 4 | 26,1% | |
| Một đáp án | luôn chọn A | 22,5% | |
| Một đáp án | **luôn chọn D** | **41,5%** ⚠ | |

### Cảnh báo: bộ đối chứng một đáp án lệch nặng về D

Vị trí đáp án đúng trong bộ gốc: A 2.106 · B 1.520 · C 1.857 · **D 3.885 (41,5%)**.

| Họ | n | %D |
|---|---:|---:|
| file2 meta | 1.092 | **88,5%** |
| file4 meta chữ cái | 893 | **84,3%** |
| file1 phủ định | 4.573 | 35,6% |
| file3 pool | 2.810 | 19,1% |

Nguyên nhân cấu trúc: `"Tất cả đều đúng"` và `"Cả A và B đều đúng"` gần như luôn là
phương án cuối trong đề gốc, mà hai họ đó chọn đúng những câu có đáp án là phương án
meta. Không tránh được nếu vẫn giữ câu gốc nguyên văn.

Hệ quả khi dùng:

- **Điểm tổng trên bộ một đáp án bị thổi phồng.** Model có thiên hướng chọn D sẽ ăn
  điểm mà không cần biết gì. Ở v1 đã đo được: Qwen3-0.6B đúng 76,8% khi đáp án ở D và
  chỉ 10,5% ở các vị trí khác.
- **So sánh theo từng cặp câu vẫn hợp lệ** — đó là mục đích của thiết kế 1:1.
- **Bộ nhiều đáp án không bị lỗi này**, vì mọi phương án đã được trộn hai lần.

---

## 8. Bản lọc kỹ hơn — 5.554 câu

Kèm theo là một bản đã qua thêm **một vòng thẩm định bằng LLM**:
`final_benchmark.json` (5.554 câu) và `final_benchmark_single.json`.

Vòng này đưa lại câu đã dựng xong kèm nhãn đúng/sai hiện tại, hỏi hai chiều — ô nào
đang gán ĐÚNG mà thực ra sai, ô nào đang gán SAI mà thực ra đúng:

````
Bạn là chuyên gia thẩm định đề thi y khoa.

Câu hỏi trắc nghiệm NHIỀU ĐÁP ÁN dưới đây được sinh tự động từ một câu hỏi 1 đáp án.
Hãy kiểm định trước khi đưa vào đề thi.

CÂU HỎI: {question}

CÁC PHƯƠNG ÁN (đánh số từ 0, kèm nhãn hiện tại):
{options}

Hãy trả lời 4 việc:

1. "cau_hoi_ro_rang": phần dẫn có đủ nghĩa, đọc là hiểu, không cụt và không thiếu ngữ
cảnh hay không?

2. "danh_dau_sai_thuc_ra_dung": chỉ số các phương án đang bị đánh dấu SAI nhưng thực
ra ĐÚNG với câu hỏi.

3. "danh_dau_dung_thuc_ra_sai": chỉ số các phương án đang được đánh dấu ĐÚNG nhưng
thực ra SAI.

4. "dat": true nếu câu hỏi dùng được ngay làm đề thi mà không cần sửa gì.

Chỉ liệt kê khi chắc chắn; không chắc thì để mảng rỗng. Chỉ trả về JSON.
````

9.368 việc, 9.368 parse được, 33,6 việc/s. Loại 3.814 câu: `cau_dan_khong_ro` 1.794 ·
`dap_an_dung_thuc_ra_sai` 1.570 · `nhieu_thuc_ra_dung` 450.

Nó bắt được hai loại lỗi mà không luật cú pháp nào bắt được:

```
Cho chuỗi phản ứng như sau. Nhận định nào sau đây đúng?
  [x] Tách nước (B) thu được alkene có đồng phân hình học
  [ ] (A) là but-1-ene
```
`(A)`, `(B)` nằm trong sơ đồ **không có trong dữ liệu** — chỉ phần chữ được export.

```
Cho các nhận định về vận chuyển các chất qua màng tế bào:
  [ ] Xuất bào và nhập bào là kiểu vận chuyển thông qua sự biến dạng của màng
```
Phát biểu này đúng nhưng đang bị gán nhãn sai — hỏng do phép đảo tập đáp án ở FILE 1.

Hai chi tiết phải xử lý khi dùng phán quyết của vòng này:

- **Model lẫn hai mảng chỉ số.** 26,5% chỉ số ở mảng "đang ĐÚNG mà thực ra sai" lại
  trỏ vào ô vốn đã đánh dấu SAI; mảng kia lệch 42,9%. Phán quyết tự mâu thuẫn thì
  không dùng làm bằng chứng được. Bỏ chúng đi thì giữ 5.554 câu thay vì 4.325.
- **Cổng lọc làm lệch vị trí.** Tỉ lệ phương án SAI ở D là 21,6% trước thẩm định và
  24,0% sau (~5 độ lệch chuẩn) — model dễ chấp nhận hơn khi bố cục là
  `ĐÚNG ĐÚNG ĐÚNG SAI`, đúng khuôn đề thi quen thuộc. Khắc phục bằng cách trộn lại vị
  trí phương án sau cổng lọc.

| | 9.368 câu | 5.554 câu |
|---|---|---|
| Theo họ | file1 4.573 · file3 2.810 · file2 1.092 · file4 893 | file1 3.025 · file3 1.228 · file2 717 · file4 584 |
| Số phương án | 4 → 5.179 (55%) · 5 → 4.189 (45%) | 4 → 3.325 (60%) · 5 → 2.229 (40%) |
| TB phương án | 4,45 | 4,40 |
| Số đáp án đúng | 2 → 1.901 · 3 → 7.102 · 4 → 365 | 2 → 932 · 3 → 4.471 · 4 → 151 |
| TB đáp án đúng | 2,84 | 2,86 |
| Câu chỉ có 1 phương án sai | 5.056 (54,0%) | 3.242 (58,4%) |
| Vị trí phương án SAI | A 3.332 · B 3.219 · C 3.359 · D 3.325 | A 1.945 · B 1.839 · C 1.877 · D 1.899 |
| Mốc "chọn 3 ô đầu" | 15,3% | 16,7% |
| %D bộ một đáp án | 41,5% | 44,5% |

Bản 5.554 có mốc đoán mù **cao hơn** (16,7% so với 15,3%) vì vòng thẩm định loại
file3 mạnh nhất (2.810 → 1.228), mà file3 lại là họ có nhiều phương án sai nhất. Tỉ lệ
câu chỉ có một phương án sai vì thế tăng từ 54,0% lên 58,4%.

Chấm cùng một model trên cả hai bộ thì đo được luôn 3.814 câu bị loại nhiễu đến mức nào.

---

## 9. Giới hạn đã biết

**Chất lượng benchmark bị chặn trên bởi chất lượng đề nguồn.** Pipeline suy đáp án từ
`correctAnswer` chứ không tự phán, nên đề gốc sai thì benchmark sai theo:

```
Insulin tác dụng ngắn (Regular insulin = Actrapid, Humulin R) có đặc điểm:
  [x] Bắt đầu tác dụng 0,5 – 1 giờ
  [x] Đạt đỉnh 2 – 5 giờ
  [x] Kéo dài 24 giờ          <- sai về chuyên môn, thực tế 6–8 giờ
```

**Giả định của ba trong bốn họ không phải lúc nào cũng đúng.** FILE 1 giả định hỏi
"câu nào SAI" thì ba phương án còn lại đều đúng; nhiều câu thực ra là "chọn câu **sai
nhất**", hai ba phương án cùng có vấn đề. FILE 2 và FILE 4 giả định phần còn lại sau
khi bỏ meta đều đúng. Bộ 9.368 câu **không** có bước kiểm tra giả định này — đó chính
là việc của bản 5.554.

**Phương án nhiễu chưa được chuyên gia y khoa thẩm định.** 1.985 câu có nhiễu do LLM
viết. Chất lượng nhìn chung tốt, nhưng có câu nhiễu quá lộ (`"Tiếp xúc với ánh sáng
mặt trời quá mức"`) hoặc lệch trục. Mọi câu như vậy đều mang cờ `llm-distractors`,
lọc lại được.

**Độ khó do tổ hợp đã bị cắt bỏ.** Giới hạn 5 phương án loại hết các câu pool 8–12
phương án, vốn là phần khó nhất. Đổi lại là hình thức đồng đều giữa bốn họ.

**Cùng một model chạy mọi vòng.** Cải thiện rõ nhất là chạy vòng thẩm định bằng một
model khác họ — hai model độc lập cùng soi bắt được nhiều lỗi hơn một model soi lại
chính nó.

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

Xem prompt trước khi tốn GPU: `python gpu/vllm_batch.py llm_jobs/r1_pool.jsonl --dry-run`.
Chạy thử một ít: thêm `--limit 50`. Đứt giữa chừng thì chạy lại đúng lệnh cũ, id đã
xong nằm trong `.out.jsonl` sẽ được bỏ qua.

Mọi bước đều xác định trước: seed trộn cố định, mã định danh câu hỏi làm seed cho việc
trộn phương án. Cùng đầu vào cho ra cùng đầu ra từng byte, trừ phần phán quyết LLM.

Hai lỗi môi trường phải sửa trên instance Lambda mới — cả hai đều báo
`Engine core initialization failed` trong khi nguyên nhân thật nằm cách đó mấy chục
dòng phía trên — được ghi trong [v2/README.md](v2/README.md).
