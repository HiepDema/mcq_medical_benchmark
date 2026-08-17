# Dựng benchmark MCQ nhiều đáp án từ 17 bộ đề gốc

Báo cáo quá trình tạo `final_benchmark.json` — **5.554 câu hỏi nhiều đáp án**, sinh
tự động từ 17 bộ đề trắc nghiệm y khoa một đáp án, kèm bộ đối chứng là chính các
câu gốc đó.

Bản trước ([REPORT.md](REPORT.md), [REPORT_COMPARE.md](REPORT_COMPARE.md)) làm trên
một file 10.242 câu và cho ra 150–300 câu. Bản này khác về quy mô lẫn phương pháp.

| | |
|---|---|
| Nguồn | 17 file trong `source_data/`, 160.194 câu |
| Kết quả | `processed_data_v2/final_benchmark.json` — 5.554 câu |
| Đối chứng | `processed_data_v2/final_benchmark_single.json` — 5.554 câu gốc, khớp 1:1 |
| Model | `Qwen/Qwen3-32B-FP8`, vLLM 0.27.1, 1×H100 SXM5 80 GB |
| Lượt gọi LLM | 19.147 (9.779 vòng 1 + 9.368 vòng 2) |
| Thời gian GPU | ~17 phút, gồm cả nạp model |
| Mã nguồn | [v2/](v2/), [gpu/vllm_batch.py](gpu/vllm_batch.py) |

---

## 1. Nguyên tắc nền

**Đáp án đúng luôn suy ra từ trường `correctAnswer` của đề gốc.** LLM chỉ được làm
ba việc: phán xét một câu có dùng được không, viết văn bản phương án nhiễu, và
thẩm định lại kết quả. Nó không bao giờ được tự quyết định đâu là đáp án đúng.

Đây không phải chi tiết kỹ thuật vụn vặt mà là điều kiện để benchmark có nghĩa.
Nếu để model tự chọn đáp án, ta chỉ đo được mức độ giống nhau giữa model sinh dữ
liệu và model bị chấm, chứ không đo được kiến thức. Ranh giới này được giữ ở mọi
tầng: ở FILE 3, LLM chỉ có quyền **xoá** một mục khỏi danh sách nhiễu, không có
quyền thêm mục vào tập đáp án.

---

## 2. Tầng 1 — nạp và khử trùng lặp

17 file, mỗi bản ghi có `question`, `answer_optionA..E`, `correctAnswer`,
`medicalTopic`, `difficultLevel`, `questionID`.

```
tổng đọc vào : 160.194
giữ lại      : 122.017  (76,2%)
trùng lặp    :  30.913  (24.519 y hệt + 6.394 chỉ đảo thứ tự phương án)
loại         :   7.264  (7.221 câu dưới 4 phương án, 43 câu hỏng khác)
```

**Khử trùng lặp phải làm trên toàn bộ 17 file gộp lại.** Các bộ đề này là những bản
export chồng lấn của cùng một ngân hàng câu hỏi — gần một phần tư số câu là trùng.
Nếu khử trong từng file rồi mới gộp, cùng một câu hỏi sẽ vào benchmark nhiều lần và
bị chấm nhiều lần.

Hai mức khử: trùng tuyệt đối theo `sha1(câu hỏi + các phương án)`, và trùng sau khi
chuẩn hoá thứ tự phương án — cùng thân câu, cùng tập phương án nhưng khác thứ tự
vẫn là một câu.

### Bóc tiền tố chữ cái

5.889 câu có phương án mang tiền tố lặp lại chính chữ cái của nó:

```
A. "A. Bệnh phổi tắc nghẽn mãn tính"
B. "B. Hen"
```

Phát hiện khi soi tay 20 câu chạy thử. Nếu để nguyên thì ở FILE 2, ba phương án
đúng lấy từ đề gốc sẽ có tiền tố còn phương án nhiễu do LLM viết thì không — model
bị chấm chỉ cần nhìn dấu hiệu đó là biết đáp án mà không cần đọc nội dung.

Chỉ bóc khi có **từ hai phương án trở lên** mang dấu đúng vị trí của chính nó, để
không cắt nhầm các chuỗi kiểu `"D, L-alanine"` đứng một mình ở phương án D. Bóc
trước khi tính mã định danh, nhờ vậy hai bản export của cùng một câu — một bản có
tiền tố, một bản không — nhận ra được nhau: số câu trùng phát hiện được tăng từ
29.797 lên 30.913.

---

## 3. Tầng 2 — phân bốn họ và lọc cơ học

Mỗi câu chỉ vào đúng một họ, theo thứ tự ưu tiên meta → meta chữ cái → phủ định → pool.

| Họ | Dấu hiệu | Cách biến đổi | Ứng viên |
|---|---|---|---:|
| **file1** phủ định | `"... NGOẠI TRỪ:"`, `"câu nào SAI"` | đảo tập đáp án: 3 phương án còn lại đều đúng | **4.729** |
| **file2** meta | đáp án đúng là `"Tất cả đều đúng"` | xoá phương án meta, LLM viết thêm 2 nhiễu | **1.102** |
| **file3** pool | mọi phương án là danh sách ngăn bởi dấu phẩy | gộp các mục thành phương án độc lập | **3.048** |
| **file4** meta chữ cái | đáp án đúng là `"Cả A và B đều đúng"` | đáp án suy từ chữ cái, LLM viết thêm nhiễu | **900** |
| | | | **9.779** |

9.779 ứng viên trên 122.017 câu nguồn — **8,0%**.

### Ví dụ mỗi họ

**file1** — `"Đâu KHÔNG PHẢI là tổn thương do rối loạn sinh sản tế bào:"` với đáp án
gốc `"Loạn sản"`. Viết lại thân câu thành khẳng định, giữ nguyên cả 4 phương án,
đánh dấu 3 phương án không phải đáp án gốc là đúng.

**file2** — `"Các yếu tố thuận lợi của thủng ổ loét dạ dày tá tràng:"` với A/B/C
đúng và D là `"Tất cả đều đúng"`. Xoá D, LLM viết thêm hai nhiễu.

**file3** — câu kinh điển của bộ dữ liệu này:

```
Tạo máu nguyên thủy cung cấp các loại tế bào nào?
  A. Hồng cầu, bạch cầu hạt, tiểu cầu nguyên thủy
  B. Hồng cầu, bạch cầu lympho, tiểu cầu nguyên thủy
  C. Hồng cầu, bạch cầu hạt, đại thực bào
  D. Hồng cầu, đại thực bào, tiểu cầu nguyên thủy   <- đáp án đúng
```

Bốn phương án dùng chung một kho khái niệm. Gộp lại được 5 mục — hồng cầu, bạch cầu
hạt, bạch cầu lympho, tiểu cầu nguyên thủy, đại thực bào — và đáp án mới chính là ba
mục nằm trong phương án D.

**file4** — đáp án đúng là `"Cả A và B đều đúng"`: A và B đúng, C là nhiễu có sẵn do
người ra đề viết, LLM viết thêm cho đủ 5 phương án.

### Các bộ lọc cơ học

Chạy trước khi tốn GPU, để lô việc gửi lên nhỏ và sạch:

- **dấu phẩy thập phân** (`0,5 g/l`) — bảo vệ bằng ký tự canh trước khi tách, nếu
  không `"0,5 g/l"` bị cắt thành `"0"` và `"5 g/l"`
- **pool toàn số** — trên 60% số mục là số hoặc đơn vị đo
- **overlap < 0,2**, với `overlap = 1 − (số mục khác nhau / tổng số mục)`. Các phương
  án không dùng chung kho khái niệm thì không phải dạng tách được
- **dãy có thứ tự** — một mục lặp lại trong cùng phương án, hoặc thân câu chứa
  "thứ tự / lần lượt / tương ứng / theo trình tự"
- **câu xếp hạng** — hai phương án có cùng tập mục, chỉ khác thứ tự
- **phương án rác** — `None`, `Không có`, `...`, chỉ toàn số, trùng nhau, chứa meta
- **thân câu có chỗ trống** `......` hoặc `___`
- **gần trùng** — khử theo khối (8 ký tự đầu + dải độ dài), `SequenceMatcher > 0,90`.
  So từng đôi trên 122.017 câu là bất khả thi; chia khối rồi chỉ so trong khối vẫn
  bắt được các bản export chỉ khác nhau dấu câu. Loại thêm 2.209 câu

### Giới hạn kích thước và bước cắt

FILE 3 nhận pool tới 8 mục, rồi **cắt ngẫu nhiên xuống 5 phương án**: giữ nguyên
toàn bộ đáp án đúng, chỉ bỏ bớt nhiễu. Chặn cứng ở 5 ngay tầng lọc thì chỉ còn
1.280 ứng viên; cắt sau khi lọc giữ được **3.048** mà mọi câu vẫn chỉ 4–5 phương án.

Bước cắt đặt ở tầng dựng chứ không phải tầng lọc, vì hai lý do: LLM vẫn nhìn thấy
trọn pool khi phán xét nên chỉ số nó trả về vẫn khớp; và cắt phải chạy **sau** khi
LLM gỡ các mục nhiễu thực ra đúng.

Kèm điều kiện tối đa 4 đáp án đúng — cắt xuống 5 phương án mà có 5 đáp án đúng thì
không còn chỗ cho phương án sai nào.

---

## 4. Tầng 3–4 — LLM vòng 1

Bốn lô việc, mỗi lô một file `.jsonl` kèm JSON Schema ép đầu ra.

| Lô | Việc | Model phải trả lời | Tốc độ |
|---|---:|---|---:|
| `r1_negation` | 4.729 | có thật là câu phủ định không; viết lại thân câu thành khẳng định; ba phương án còn lại có đúng cả không | 29,4 việc/s |
| `r1_distract` | 1.102 | viết 2 phương án sai | 33,1 việc/s |
| `r1_pool` | 3.048 | các mục có tách độc lập được không; mục nào đang làm nhiễu nhưng **thực ra cũng đúng** | 24,7 việc/s |
| `r1_distract_letters` | 900 | viết 2 phương án sai, không trùng ý nhiễu có sẵn | 33,4 việc/s |

**9.778/9.779 phán quyết parse được** (một câu lỗi). Toàn bộ vòng 1 mất khoảng 6 phút.

### Kết quả dựng

```
FILE 1: 4.573/4.729   (LLM viết lại thân câu ở 4.468 câu; 105 câu dùng bản viết lại cơ học)
FILE 2: 1.092/1.102   (1.060 câu đủ 2 nhiễu hợp lệ)
FILE 3: 2.810/3.048   (LLM gỡ 233 mục nhiễu thực ra đúng; cắt bớt nhiễu ở 1.562 câu)
FILE 4:   893/900
tổng  : 9.368         (loại 401)
```

Lý do loại: `llm_tu_choi` 155 · `llm_noi_khong_tach_duoc` 108 · `pool_sai_kich_thuoc`
88 · `tap_dap_an_khong_hop_le` 39 · `khong_du_phuong_an` 7 · `stem_too_short` 3 ·
`thieu_phan_quyet` 1.

### Kiểm soát chất lượng văn bản LLM viết ra

Không nhận thẳng đầu ra của model. Thân câu viết lại chỉ được dùng nếu còn sạch:
không còn dấu phủ định, dài từ 0,4 đến 1,8 lần câu gốc, không bắt đầu bằng nhãn
phương án. Không đạt thì rơi về bản viết lại cơ học (105 câu). Phương án nhiễu phải
dài 2–200 ký tự, không phải meta, không phải rác, và không giống quá 85% bất kỳ
phương án đúng nào hay nhiễu còn lại.

### Cổng bất biến

Mọi bản ghi đều qua `lib2.validate()` trước khi được ghi ra: ít nhất 4 phương án,
số đáp án đúng từ 2 trở lên và nhỏ hơn tổng số phương án, không phương án trùng
nhau, không phương án rác, `correctAnswer` trỏ đúng chỗ. Câu hỏng vào
`data_v2/04_rejected.json` kèm lý do — không im lặng bỏ qua.

---

## 5. Tầng 5 — LLM vòng 2, thẩm định

Vòng 2 là bước **đồng nhất cho cả bốn họ**: đưa lại câu đã dựng xong kèm nhãn
đúng/sai hiện tại, hỏi hai chiều — ô nào đang gán nhãn ĐÚNG nhưng thực ra sai, ô nào
đang gán nhãn SAI nhưng thực ra đúng.

Đây là bộ lọc duy nhất bắt được lỗi **ngữ nghĩa**. Lọc cơ học không bao giờ biết
"xì dầu" là thực phẩm nhiều muối, hay "thiếu máu cục bộ" là một nguyên nhân có thật
của viêm tụy cấp.

9.368 việc, 9.368 parse được, 33,6 việc/s, khoảng 5 phút.

### Hai lỗi phát hiện khi soi kết quả vòng 2

Phiên bản đầu của cổng thẩm định giữ lại 4.325 câu — loại 54%. Con số đó đủ bất
thường để phải kiểm tra thay vì nhận luôn.

**Lỗi 1 — model lẫn hai mảng chỉ số.** Mảng "ô đang đánh dấu ĐÚNG nhưng thực ra SAI"
bắt buộc phải trỏ vào ô đang đánh dấu ĐÚNG. Đo trên toàn bộ 9.368 phán quyết:

| Mảng | Trỏ đúng hướng | Trỏ ngược hướng |
|---|---:|---:|
| `danh_dau_dung_thuc_ra_sai` | 4.657 (73,5%) | **1.680 (26,5%)** |
| `danh_dau_sai_thuc_ra_dung` | 793 (57,1%) | **594 (42,9%)** |

Một phán quyết tự mâu thuẫn thì không dùng làm bằng chứng được. Chỉ tính các chỉ số
trỏ đúng hướng: giữ **5.554** câu thay vì 4.325 — trước đó loại oan **1.229 câu**.

**Lỗi 2 — cổng thẩm định làm lệch vị trí.** Tỉ lệ phương án SAI nằm ở D:

```
trước thẩm định : A 22,1%  B 21,8%  C 21,7%  D 21,6%   <- đều
sau  thẩm định : A 20,2%  B 22,0%  C 20,5%  D 24,0%   <- lệch về D
```

Lệch khoảng 5 độ lệch chuẩn, không phải nhiễu ngẫu nhiên. Nguyên nhân: model dễ chấp
nhận hơn khi bố cục nhãn là `ĐÚNG ĐÚNG ĐÚNG SAI` — đúng khuôn đề thi quen thuộc — nên
những câu có phương án sai ở cuối sống sót nhiều hơn. Chính bộ lọc tạo ra rò rỉ vị trí.

Khắc phục: **trộn lại vị trí phương án sau cổng thẩm định**. An toàn, vì các câu còn
lại đều đã được thẩm định là không có ô nào gán nhãn ngược, nên đổi vị trí không làm
hỏng kết quả thẩm định. Sau khi sửa: A 1.945 · B 1.839 · C 1.877 · D 1.899 — đều trở lại.

### Tỉ lệ sống sót

| Họ | Ứng viên | Sau vòng 1 | Sau vòng 2 | Giữ lại |
|---|---:|---:|---:|---:|
| file1 phủ định | 4.729 | 4.573 | **3.025** | 64,0% |
| file2 meta | 1.102 | 1.092 | **717** | 65,1% |
| file3 pool | 3.048 | 2.810 | **1.228** | 40,3% |
| file4 meta chữ cái | 900 | 893 | **584** | 64,9% |
| **Tổng** | **9.779** | **9.368** | **5.554** | **56,8%** |

Lý do loại ở vòng 2: `cau_dan_khong_ro` 1.794 · `dap_an_dung_thuc_ra_sai` 1.570 ·
`nhieu_thuc_ra_dung` 450.

FILE 3 sống sót thấp nhất (40,3%) là đúng như dự đoán: nó là họ duy nhất mà thân câu
bị viết lại nhiều nhất so với đề gốc, nên dễ trở nên cụt nghĩa.

---

## 6. Bộ dữ liệu cuối

### `final_benchmark.json` — 5.554 câu

| | |
|---|---|
| Số phương án | 4 → 3.325 câu (59,9%) · 5 → 2.229 câu (40,1%). TB **4,40** |
| Số đáp án đúng | 2 → 932 · 3 → 4.471 · 4 → 151. TB **2,86** |
| Theo họ | file1 3.025 · file3 1.228 · file2 717 · file4 584 |
| Vị trí phương án SAI | A 1.945 · B 1.839 · C 1.877 · D 1.899 · E 1.004 |
| Câu mọi phương án đều đúng | **0** |

Trải đều trên cả 17 file nguồn, từ 67 câu (file nhỏ nhất) tới 716 câu.

Chủ đề chính: General Medicine 1.004 · Other 734 · Obstetrics and Gynecology 690 ·
Infectious Diseases 618 · Preventive Healthcare 574 · Public Health 505 ·
Eastern Medicine 342 · Pulmonology 337.

**Xáo trộn hai lần**: vị trí phương án trong từng câu trộn theo seed lấy từ mã định
danh câu hỏi (lần một ở tầng dựng, lần hai sau cổng thẩm định), và thứ tự câu hỏi
trong file trộn theo seed cố định `20260815`. Chạy lại luôn ra cùng kết quả.

### `final_benchmark_single.json` — 5.554 câu gốc

Chính những câu đó, **nguyên văn từ file nguồn**, xếp theo đúng thứ tự của bản nhiều
đáp án. Bản ghi thứ *i* của file này là bản gốc của bản ghi thứ *i* trong
`final_benchmark.json`. Đã kiểm tra: 5.554 cặp `(file nguồn, chỉ số)` đều duy nhất,
ánh xạ 1:1 không hỏng.

Nhờ khớp 1:1 nên mọi chênh lệch điểm giữa hai bộ quy về **định dạng câu hỏi**, không
phải do bộ này khó hơn bộ kia.

### Bản chưa qua thẩm định — 9.368 câu

Kèm theo là bộ đầy đủ **trước** cổng thẩm định vòng 2, để so sánh xem bước đó thực
sự mang lại gì:

| File | Nội dung |
|---|---|
| `final_benchmark_9368.json` | 9.368 câu, chỉ qua vòng 1 |
| `final_benchmark_9368_single.json` | các câu gốc tương ứng, khớp 1:1 |
| + 2 file provenance | như trên, `auditStatus` là `khong_tham_dinh` |

```powershell
python v2/run.py build --skip-audit --out-name final_benchmark_9368
```

| | 9.368 câu | 5.554 câu |
|---|---|---|
| Theo họ | file1 4.573 · file3 2.810 · file2 1.092 · file4 893 | file1 3.025 · file3 1.228 · file2 717 · file4 584 |
| Số phương án | 4 → 5.179 · 5 → 4.189 | 4 → 3.325 · 5 → 2.229 |
| Số đáp án đúng | 2 → 1.901 · 3 → 7.102 · 4 → 365 | 2 → 932 · 3 → 4.471 · 4 → 151 |
| Vị trí phương án SAI | A 3.332 · B 3.219 · C 3.359 · D 3.325 | A 1.945 · B 1.839 · C 1.877 · D 1.899 |
| Mốc "chọn 3 ô đầu" | 15,3% | 16,7% |
| Mốc "chọn hết" | 0,0% | 0,0% |
| %D bộ một đáp án | 41,5% | 44,5% |

Bộ 9.368 câu **không** được đảm bảo về mặt ngữ nghĩa: nó còn chứa những câu tham
chiếu sơ đồ không tồn tại, và những câu có phương án bị gán nhãn ngược do phép đảo
tập đáp án ở FILE 1 (xem mục 5). Bù lại nó nhiều hơn 69%, và cả hai bộ đều không có
rò rỉ vị trí.

Dùng bộ nào tuỳ mục đích: chấm model thì dùng bản 5.554, còn muốn đo xem bước thẩm
định đáng giá bao nhiêu thì chấm cả hai rồi so.

### Hai file provenance

`final_benchmark_provenance.json` và `final_benchmark_single_provenance.json` ghi cho
từng câu: file nguồn, chỉ số trong file đó, mã định danh, họ, đáp án gốc, và cờ chất
lượng.

| Cờ | Số câu | Nghĩa |
|---|---:|---|
| `llm-verified` | 2.964 | file1, thân câu do LLM viết lại |
| `llm-distractors` | 1.301 | file2 + file4, có phương án nhiễu do LLM sinh |
| `llm-screened` | 1.228 | file3, pool đã qua LLM sàng lọc |
| `rule-only` | 61 | file1, dùng bản viết lại cơ học |

Cùng với đó: `auditStatus` (4.164 `dat`, 1.390 `dat_co_canh_bao`), danh sách mục nhiễu
LLM đã gỡ (97 mục), danh sách nhiễu bị cắt khi thu về 5 phương án (659 câu).

---

## 7. Mốc so sánh mù

Không dùng model, tính trên đúng 5.554 câu này. Mọi kết quả chấm model đều phải
báo cáo kèm những con số này — không vượt được chúng thì điểm cao vô nghĩa.

| Bộ | Chiến lược | exact |
|---|---|---:|
| Nhiều đáp án | chọn hết mọi phương án | **0,0%** |
| Nhiều đáp án | chọn 3 phương án đầu | **16,7%** |
| Nhiều đáp án | chọn ngẫu nhiên, mỗi phương án 50% | 4,4% |
| Một đáp án | chọn ngẫu nhiên 1 trong 4 | 24,7% |
| Một đáp án | luôn chọn A | 19,9% |
| Một đáp án | **luôn chọn D** | **44,5%** ⚠ |

### Cảnh báo: bộ đối chứng một đáp án lệch nặng về D

Vị trí đáp án đúng trong bộ gốc: A 1.104 · B 885 · C 1.091 · **D 2.474 (44,5%)**.

Tách theo họ thì thấy ngay nguồn gốc:

| Họ | n | %D |
|---|---:|---:|
| file2 meta | 717 | **89,7%** |
| file4 meta chữ cái | 584 | **84,2%** |
| file1 phủ định | 3.025 | 36,0% |
| file3 pool | 1.228 | 20,4% |

Nguyên nhân cấu trúc: `"Tất cả đều đúng"` và `"Cả A và B đều đúng"` gần như luôn là
phương án cuối trong đề gốc, mà hai họ đó chọn đúng những câu có đáp án là phương án
meta. Không thể tránh được nếu vẫn giữ câu gốc nguyên văn.

Hệ quả cần nhớ khi dùng:

- **Điểm tổng trên bộ một đáp án bị thổi phồng.** Một model có thiên hướng chọn D sẽ
  ăn điểm mà không cần biết gì. Ở bản v1 đã đo được hiện tượng này: Qwen3-0.6B đúng
  76,8% khi đáp án nằm ở D và chỉ 10,5% ở các vị trí khác.
- **So sánh theo từng cặp câu vẫn hợp lệ** — đó mới là mục đích của thiết kế 1:1.
- **Bộ nhiều đáp án không bị lỗi này**, vì mọi phương án đã được trộn hai lần.

Nếu cần một bộ đối chứng công bằng về tổng điểm, phải trộn lại vị trí phương án của
bản một đáp án — nhưng khi đó nó không còn là "câu gốc nguyên văn" nữa. File hiện tại
giữ nguyên văn theo đúng yêu cầu.

---

## 8. Giới hạn đã biết

**Chất lượng benchmark bị chặn trên bởi chất lượng đề nguồn.** Pipeline suy đáp án từ
`correctAnswer` chứ không tự phán, nên đề gốc sai thì benchmark sai theo. Một ví dụ
thật gặp khi kiểm tra:

```
Insulin tác dụng ngắn (Regular insulin = Actrapid, Humulin R) có đặc điểm:
  [x] Bắt đầu tác dụng 0,5 – 1 giờ
  [x] Đạt đỉnh 2 – 5 giờ
  [x] Kéo dài 24 giờ          <- sai về chuyên môn, thực tế 6–8 giờ
```

Vòng thẩm định sinh ra để bắt loại lỗi này, và nó bắt được 1.570 câu, nhưng không thể
bắt hết.

**Model tự chấm mình quá dễ dãi.** Ở lô chạy thử 20 câu, cả 20 đều trả
`chac_chan_sai = true`, kể cả câu có nhiễu "thiếu máu cục bộ" thực ra đúng. Vì vậy cờ
đó chỉ được ghi vào provenance, **không** dùng làm điều kiện lọc. Bài học: model tự
kiểm tra mình trong cùng một lượt gọi thì gần như vô giá trị; phải là một lượt thẩm
định riêng, nhìn câu hỏi đã dựng xong.

**Vòng 2 vẫn do chính model đó chạy.** Cách cải thiện rõ ràng nhất là chạy vòng thẩm
định bằng một model khác họ — hai model độc lập cùng soi bắt được nhiều lỗi hơn hẳn
một model soi lại chính nó.

**Phương án nhiễu chưa được chuyên gia y khoa thẩm định.** 1.301 câu có nhiễu do LLM
viết. Chất lượng nhìn chung tốt — ví dụ với câu về Menthol, model viết
`"Là một sesquiterpene do có 15 carbon"` và `"Có sườn cơ bản là camphene"`, sai đúng ở
một chi tiết chuyên môn — nhưng có câu nhiễu quá lộ hoặc lệch trục. Mọi câu như vậy
đều mang cờ `llm-distractors`, lọc lại được.

**Độ khó do tổ hợp đã bị cắt bỏ.** Giới hạn 5 phương án loại hết các câu pool 8–12
phương án, vốn là phần khó nhất. Đổi lại là hình thức đồng đều giữa bốn họ.

---

## 9. Tái tạo

```powershell
python v2/run.py ingest route jobs        # -> llm_jobs/r1_*.jsonl
```
```bash
# trên máy H100
python3 -m venv ~/venv && ~/venv/bin/pip install vllm ninja
export PATH=$HOME/venv/bin:$PATH
python gpu/vllm_batch.py llm_jobs/r1_*.jsonl --model Qwen/Qwen3-32B-FP8 --chunk 2048
```
```powershell
python v2/run.py apply                    # -> llm_jobs/r2_audit.jsonl
```
```bash
python gpu/vllm_batch.py llm_jobs/r2_audit.jsonl --model Qwen/Qwen3-32B-FP8 --max-tokens 128
```
```powershell
python v2/run.py build                    # -> final_benchmark.json
python eval_qwen3vl.py --data processed_data_v2/final_benchmark.json `
                       --provenance processed_data_v2/final_benchmark_provenance.json `
                       --baselines-only
```

Mọi bước đều xác định trước: seed trộn cố định, mã định danh câu hỏi làm seed cho
việc trộn phương án. Cùng đầu vào cho ra cùng đầu ra từng byte, trừ phần phán quyết
LLM.

Hai lỗi môi trường phải sửa trên instance Lambda mới — cả hai đều báo
`Engine core initialization failed` trong khi nguyên nhân thật nằm cách đó mấy chục
dòng phía trên — được ghi trong [v2/README.md](v2/README.md) mục "Hai lỗi phải sửa
trên instance Lambda mới".
