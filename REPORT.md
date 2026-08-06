# Báo cáo xây dựng bộ benchmark MCQ nhiều đáp án

Chuyển ngân hàng câu hỏi trắc nghiệm y khoa một-đáp-án thành bộ đánh giá
**nhiều-đáp-án**, phục vụ đo năng lực chọn-tất-cả-đáp-án-đúng của mô hình ngôn ngữ.

| | |
|---|---|
| Nguồn | `raw_data.json` — 10.242 câu, 1 đáp án đúng |
| Kết quả | `processed_data/benchmark_multi.json` — **326 câu**, 2–5 đáp án đúng |
| Ngày | 05/08/2026 |
| Mã nguồn | `pyline/` (Python 3.13, không phụ thuộc thư viện ngoài) |

---

## 1. Nguyên tắc xuyên suốt

**Ground truth phải được *suy ra*, không được *bịa ra*.** Với mỗi câu chuyển đổi,
tập đáp án đúng mới đều dẫn xuất bằng quy tắc xác định từ trường `correctAnswer`
của đề gốc. Sai ở đâu thì kiểm tra ngược lại được ở đó.

Ngoại lệ duy nhất là 30 câu có phương án nhiễu do LLM sinh (mục 5.2) — chúng
được đánh dấu riêng và tách khỏi phần dữ liệu suy ra.

**Không sửa dữ liệu gốc.** `raw_data.json` chỉ được đọc. Mọi bản ghi bị loại ở
bất kỳ tầng nào đều nằm trong một file `*_rejected` / `*_skipped` kèm lý do.

---

## 2. Dữ liệu nguồn

10.242 bản ghi, mỗi bản ghi gồm `question`, `answer_optionA..D`, `correctAnswer`,
`medicalTopic`, `difficultLevel`, `questionID`.

Vấn đề phát hiện khi khảo sát:

| Vấn đề | Số lượng | Xử lý |
|---|---|---|
| Bản ghi trùng lặp hoàn toàn | 720 | Tách ra `01_duplicates.json` |
| Thiếu đáp án (< 2 phương án) | 2 | Tách ra `01_dropped.json` |
| Câu chỉ có 2–3 phương án | 515 | Giữ lại nhưng không dùng để chuyển đổi |
| `questionID` **không duy nhất** | 2.096 giá trị / 10.242 câu | Sinh `uid` băm từ nội dung |

`questionID` trùng lặp là lý do mọi khâu truy vết đều dùng `sourceIndex`
(vị trí trong `raw_data.json`) và `uid` thay vì `questionID`.

Sau làm sạch: **9.520 câu**.

---

## 3. Phân loại tự động

Mỗi câu được gán vào một nhóm theo quy tắc thuần cấu trúc, không dùng kiến thức y khoa.

| Nhóm | Số câu | Dấu hiệu nhận biết |
|---|---|---|
| `meta` | 271 | Đáp án đúng là "Tất cả đều đúng" / "Cả a, b đúng" |
| `pool` | 622 | Cả 4 phương án là danh sách rút từ **một vốn từ chung** |
| `combination` | 33 | Phương án là tham chiếu số `(1),(2),(3)` tới mệnh đề trong thân câu |
| `none` | 8.594 | Không thuộc dạng nào ở trên |

### Chỉ số `overlap` — hạt nhân của nhóm `pool`

```
overlap = 1 − (số mục duy nhất) / (tổng số mục của cả 4 phương án)
```

Câu số 2 (*"Tạo máu nguyên thủy cung cấp các loại tế bào nào?"*) có 4 phương án ×
3 mục = 12 mục nhưng chỉ 5 mục duy nhất → `overlap = 0,58`.

Ý nghĩa: overlap cao nghĩa là bốn phương án là **hoán vị của một tập khái niệm
đóng** — người ra đề đã tự tuyên bố pool đó là toàn bộ vũ trụ khái niệm được xét.
Khi đó suy luận *"mục nằm ngoài phương án đúng thì sai"* là đúng theo cấu trúc,
không cần kiến thức chuyên ngành. Overlap thấp nghĩa là pool mở, và mục trong
phương án nhiễu hoàn toàn có thể đúng nhưng đơn giản là không được liệt kê.

---

## 4. So sánh: luật đếm dấu phẩy đơn thuần

Một cách tiếp cận đơn giản là "mọi phương án đều chứa ít nhất một dấu phẩy".
Đo trên 9.005 câu bốn phương án:

| Bước lọc | Còn lại | Loại thêm |
|---|---|---|
| B1 — mọi phương án có ≥1 dấu phẩy | 701 | — |
| B2 — bảo vệ dấu phẩy thập phân (`0,5`) | 593 | −108 |
| B3 — loại pool toàn số / đơn vị đo | 566 | −27 |
| B4 — `overlap ≥ 0,2` | 425 | −141 |
| B5 — loại dãy có thứ tự | 417 | −8 |

**Luật đếm dấu phẩy đơn thuần chỉ đúng 59%** và đồng thời **bỏ sót 31%** (192/622
câu dùng `;` hoặc chữ "và" làm dấu phân tách). Bước lọc quan trọng nhất là B4:
loại 141 câu, ví dụ điển hình là câu *"Một số mầm bệnh truyền nhiễm lây đường
tiêu hoá"* — nếu tách ra thì **bại liệt** bị gán nhãn nhiễu, trong khi bại liệt
cũng lây qua đường phân–miệng.

---

## 5. Ba tập dữ liệu thành phần

### 5.1 FILE 1 — câu phủ định (265 câu)

Câu dạng *"ngoại trừ"*, *"chọn câu sai"*, *"không đúng"*, *"không phải"* có tính
chất: đáp án đúng theo đề chính là mệnh đề **sai**, nên **ba phương án còn lại
đều đúng**.

Bộ lọc bắt được **297 câu** (đưa vào `filter_data/final_01_ngoai_tru.json` ở dạng
nguyên văn gốc), trong đó 265 câu viết lại được sạch sẽ và trở thành FILE 1.

Xử lý: viết lại thân câu sang khẳng định + đảo tập đáp án. Phương án gốc giữ nguyên.

**Ví dụ 1 — dạng "ngoại trừ"** (`sourceIndex` 49, `questionID` 25):

```
GỐC   Các chất gây ngưng tập tiểu cầu chính, ngoại trừ:     → đáp án optionB
      A. Thromboxan A2   B. Adenosin   C. Adenosin diphodphat   D. Thrombin

MỚI   Các chất gây ngưng tập tiểu cầu chính:      → optionA, optionB, optionD
      [x] A. Thrombin
      [x] B. Adenosin diphodphat
      [ ] C. Adenosin                  ← đáp án gốc, nay thành phương án nhiễu
      [x] D. Thromboxan A2
```

Chữ *"ngoại trừ"* bị cắt khỏi thân câu, ba phương án còn lại trở thành đáp án đúng,
và **Adenosin** — đáp án đúng theo đề gốc — trở thành phương án nhiễu duy nhất.
Vị trí đã được trộn nên nhiễu không còn nằm cố định ở chỗ cũ (xem mục 7).

**Ví dụ 2 — dạng "chọn câu sai"**:

```
GỐC   Chọn câu sai: Các tế bào gốc tạo máu cư trú ở người trưởng thành:  → optionD
MỚI   Chọn các câu đúng: Các tế bào gốc tạo máu cư trú ở người trưởng thành:
      [x] A. Tủy xương   [x] B. Lách   [x] C. Máu ngoại vi   [ ] D. Gan
```

Ưu điểm lớn nhất của cả nhóm: **phương án nhiễu do chính người ra đề viết**,
không phải máy sinh.

| Luật viết lại | Số câu |
|---|---|
| `không phải` → `là` | 99 |
| `chọn câu sai` → `chọn các câu đúng` | 79 |
| cắt đuôi `, ngoại trừ:` / `, trừ:` | 71 |
| `không đúng` → `đúng` | 16 |

32 câu không viết lại sạch được → `final_01_ngoai_tru_skipped.json`.

### 5.2 FILE 2 — câu "Tất cả đều đúng" (50 câu)

271 câu có đáp án đúng là phương án meta. Sau khi bỏ phương án meta thì **mọi
phương án còn lại đều đúng** — câu benchmark rất yếu, vì chiến lược "chọn hết"
tự động đạt điểm tuyệt đối.

Từ 180 ứng viên sạch (đã loại câu điền khuyết, câu còn sót meta, câu có phương án
trùng nhau), chọn 50 câu chia hai lô:

- **Lô A — 20 câu**: chỉ xoá phương án meta. Cả 3 phương án còn lại đều đúng.
  Giữ lại như một *nhóm đối chứng* để đo mức độ ăn may của chiến lược "chọn hết".
- **Lô B — 30 câu**: xoá phương án meta, rồi **dùng LLM sinh thêm 2 phương án
  nhiễu** cho mỗi câu → 5 phương án, 3 đáp án đúng.

**Ví dụ lô A** — chỉ xoá meta, không thêm gì:

```
GỐC   Virus cúm ở Việt Nam gồm những loại nào?          → optionD
      A. A/H3N2   B. A/H1N1   C. Cúm B   D. Tất cả đều đúng

MỚI   Virus cúm ở Việt Nam gồm những loại nào?     → optionA, optionB, optionC
      [x] A. A/H1N1   [x] B. Cúm B   [x] C. A/H3N2
```

Thấy rõ điểm yếu: không còn phương án nhiễu nào, "chọn hết" là đúng.

**Ví dụ lô B** — thêm 2 phương án nhiễu do LLM sinh:

```
GỐC   Theo Hồ Chí Minh, ở đời và làm người thì phải:    → optionD
      A. Thương dân.  B. Yêu nước.  C. Thương nhân loại bị áp bức.
      D. Cả ba phương án kia đều đúng.

MỚI   Theo Hồ Chí Minh, ở đời và làm người thì phải:  → optionC, optionD, optionE
      [ ] A. Trung với vua.                      ← LLM sinh
      [ ] B. Đặt lợi ích cá nhân lên trên hết.   ← LLM sinh
      [x] C. Yêu nước.
      [x] D. Thương dân.
      [x] E. Thương nhân loại bị áp bức.
```

⚠️ Phương án nhiễu lô B **chưa được chuyên gia y khoa thẩm định**. Mọi bản ghi lô
B mang `qualityFlag: "synthetic-distractors-unverified"` và liệt kê chính xác các
chuỗi do LLM sinh trong trường `syntheticDistractors`.

### 5.3 FILE 3 — tách theo dấu phẩy (11 câu)

Đây là dạng chuyển đổi thú vị nhất: mỗi phương án gốc là một **danh sách**, gom
tất cả mục lại thành pool, mục nào nằm trong phương án đúng gốc thì là đáp án đúng.

**Ví dụ mẫu** (`sourceIndex` 1, `questionID` 2):

```
GỐC   Tạo máu nguyên thủy cung cấp các loại tế bào nào?          → optionD
      A. Hồng cầu, bạch cầu hạt, tiểu cầu nguyên thủy
      B. Hồng cầu, bạch cầu lympho, tiểu cầu nguyên thủy
      C. Hồng cầu, bạch cầu hạt, đại thực bào
      D. Hồng cầu, đại thực bào, tiểu cầu nguyên thủy

      → 4 phương án × 3 mục = 12 mục, chỉ 5 mục duy nhất → overlap = 0,58

MỚI   Tạo máu nguyên thủy cung cấp các loại tế bào nào?  → optionA, optionC, optionD
      [x] A. tiểu cầu nguyên thủy
      [ ] B. bạch cầu lympho
      [x] C. đại thực bào
      [x] D. Hồng cầu
      [ ] E. bạch cầu hạt
```

Ba mục trong phương án D gốc trở thành đáp án đúng; hai mục còn lại của pool
(**bạch cầu hạt**, **bạch cầu lympho**) trở thành phương án nhiễu. Không cần
kiến thức y khoa nào — toàn bộ suy ra từ `correctAnswer` gốc.

714 câu có dấu phẩy ở mọi phương án được lọc vào `filter_data/final_03_dau_phay.json`.
Bộ lọc tự động (overlap cao, không phải dãy có thứ tự, không phải câu xếp hạng,
thân câu không phủ định, pool không toàn số) rút xuống **301 ứng viên**.

**LLM rà soát các ứng viên hàng đầu và chọn ra 11 câu tách được an toàn.** Bước
này cần thiết vì bộ lọc cấu trúc không phát hiện được lỗi ngữ nghĩa — LLM đã loại
thêm những câu như:

| Câu | Vấn đề |
|---|---|
| "Thực phẩm giàu muối" | nhiễu là **"xì dầu"**, thực tế cũng giàu muối |
| "Tổ chức phụ thuộc vào cơ vân" | nhiễu là **"Gân"**, thực tế cũng thuộc nhóm |
| "Yếu tố ảnh hưởng quá trình dịch" | nhiễu **"mầm bệnh"** đồng nghĩa với đáp án đúng |

11 câu được giữ đều có nhiễu chắc chắn sai, ghi rõ lý do trong `selectedBecause`.
Toàn bộ nội dung do người ra đề viết, ground truth suy ra từ `correctAnswer` gốc
→ cờ `derived-from-source-truth`.

---

## 6. Bộ benchmark gộp

`processed_data/benchmark_multi.json` — 326 câu, trộn với seed cố định `20260805`.

| Nguồn | Số câu | Độ tin cậy |
|---|---|---|
| File 1 — phủ định | 265 | cao (suy ra từ nguồn) |
| File 2 lô B — thêm nhiễu | 30 | trung bình (nhiễu do LLM sinh) |
| File 2 lô A — xoá meta | 20 | thấp (mọi phương án đều đúng) |
| File 3 — tách dấu phẩy | 11 | cao (suy ra từ nguồn) |

| Thống kê | Giá trị |
|---|---|
| Tổng phương án | 1.327 |
| Tổng đáp án đúng | 982 |
| Số phương án mỗi câu | 3 (20 câu) · 4 (270) · 5 (31) · 6 (3) · 7 (2) |
| Số đáp án đúng mỗi câu | 2 (2 câu) · 3 (319) · 4 (4) · 5 (1) |

Chuyên khoa nhiều nhất: Pathology 70, General Medicine 58, Preventive Healthcare 40,
Oncology 36, Public Health 32.

---

## 7. Lỗi chất lượng phát hiện và đã sửa

Phần này ghi lại các lỗi **không lộ ra nếu chỉ nhìn số lượng đầu ra**.

**Dấu phẩy thập phân tiếng Việt.** `0,5 - 1%` bị cắt thành `0` và `5 - 1%`. Sửa
bằng cách thay `\d,\d` bằng ký tự canh giữ trước khi tách. Ảnh hưởng 108 câu.

**Đáp án là dãy có thứ tự, không phải tập hợp.** `sp2, sp, sp2, sp3` (trạng thái
lai hoá theo thứ tự) có overlap 0,81 — cao nhất bảng — nhưng tách ra là vô nghĩa.
Dấu hiệu nhận biết: một phương án chứa mục lặp lại. Ảnh hưởng 24 câu, trong đó
15 câu nằm ở nhóm overlap cao.

**Câu xếp hạng.** Bốn phương án chứa **đúng cùng một tập mục**, chỉ khác trật tự.
Bộ lọc dãy-có-thứ-tự không bắt được vì không có mục lặp.

**Thân câu phủ định trong nhóm pool.** 42 câu vừa có pool vừa có thân phủ định →
tập đáp án bị **đảo ngược**. Đã loại khỏi ứng viên File 3.

**Rò rỉ vị trí trong File 1.** Ban đầu giữ nguyên thứ tự phương án gốc, nên phương
án sai duy nhất rơi vào vị trí D tới **105/265 lần** (ngân hàng đề chuộng đáp án D).
Mốc "luôn chọn A, B, C" đạt 39,1% exact match mà không đọc câu hỏi. Sau khi thêm
bước trộn vị trí có seed, phân bố về đều (A:65 D:61 B:63 C:76) và mốc tụt xuống 25,5%.

**Ba lỗi biểu thức chính quy** phát hiện khi soi đầu ra thủ công: mẫu meta
`"Cả A và B đều không đúng"` không khớp; marker mệnh đề `( 2)` có khoảng trắng
trong ngoặc bị bỏ qua; bộ lọc độ dài tối thiểu cắt mất mệnh đề hợp lệ nhưng ngắn
như `(5) HIV`, làm lệch ánh xạ số → chỉ số.

---

## 8. Truy vết

Mỗi file dữ liệu có một file `*_provenance.json` đi kèm, ghép cặp theo cùng chỉ số.
Lý do tách riêng: file thành phẩm phải giữ đúng format `raw_data.json`, không có
chỗ chứa metadata.

Trường dùng chung: `sourceIndex` (vị trí trong `raw_data.json`), `uid` (băm nội dung),
`questionID` (giữ nguyên từ gốc, **không duy nhất**).

Trường riêng đáng chú ý: `negationFamily` + `originalQuestion` (File 1),
`syntheticDistractors` + `batch` (File 2), `selectedBecause` + `originalOptions` (File 3),
`subset` + `index` (bộ gộp).

Nhờ vậy có thể lọc ra phần dữ liệu do người ra đề viết và phần do LLM sinh chỉ
bằng một dòng code.

---

## 9. Giới hạn đã biết

**30 câu có nhiễu do LLM sinh chưa được thẩm định chuyên môn.** Nếu một phương án
nhiễu thực ra đúng về mặt y khoa, câu hỏi hỏng âm thầm và không có nguồn nào để
đối chiếu. Nên loại nhóm này khi cần độ chính xác cao.

**20 câu lô A có mọi phương án đều đúng.** Giữ lại làm nhóm đối chứng chứ không
phải để đo năng lực.

**Phân bố số đáp án đúng lệch nặng: 319/326 câu có đúng 3 đáp án.** Model có thể
khai thác tiên nghiệm này. Mốc "chọn 3 phương án đầu" đạt 25,5% exact match.

**File 3 mới xử lý 11/714 câu.** Pipeline chạy Qwen3-VL-30B trên Lambda A10 đã
viết xong (`lambda/run_remote.py`, `lambda/gpu_infer.py`) nhưng chưa chạy ở quy mô
đầy đủ. Còn 290 ứng viên trong danh sách rút gọn.

**Chưa có ai review tay toàn bộ.** Khuyến nghị bốc ngẫu nhiên 40–50 câu để ước
lượng tỷ lệ lỗi trước khi dùng làm chuẩn đối sánh chính thức.

---

## 10. Phương pháp đánh giá

Script: `eval_qwen3vl.py`.

| Chỉ số | Định nghĩa |
|---|---|
| **exact match** | Tập đáp án chọn trùng khít tập chuẩn — chỉ số chính |
| **Jaccard** | \|giao\| / \|hợp\| — điểm từng phần |
| **micro F1** | Coi mỗi phương án là một quyết định nhị phân chọn/không chọn |

Đầu ra của model bị ép về JSON hợp lệ bằng guided decoding với `enum` đúng các
chữ cái của từng câu, nên không có lỗi phân tích cú pháp.

### Mốc so sánh (không dùng model)

| Chiến lược | exact | Jaccard | micro F1 |
|---|---|---|---|
| Chọn hết mọi phương án | 6,1% | 74,8% | **85,1%** |
| Chọn 3 phương án đầu | 25,5% | 61,8% | 74,0% |
| Chọn ngẫu nhiên (mỗi phương án 50%) | 6,7% | 45,4% | 60,9% |

Hai điều rút ra:

1. **micro F1 gây ảo giác.** Chiến lược "chọn hết" — hoàn toàn không hiểu gì —
   đã đạt F1 85,1%. Không dùng F1 làm chỉ số chính.
2. **Ngưỡng có nghĩa của exact match là 25,5%**, không phải 0%. Model đạt 30% chỉ
   hơn mốc mù 5 điểm.

Kiểm chứng bằng dự đoán ngẫu nhiên (chọn 3 phương án bất kỳ) cho thấy phân rã
theo nguồn hoạt động đúng như thiết kế:

| Nguồn | exact của dự đoán ngẫu nhiên |
|---|---|
| file2_xoa_meta (20 câu lô A) | **100,0%** |
| file1_ngoai_tru (265 câu) | 23,8% |
| file2_them_nhieu (30 câu) | 10,0% |
| file3_tach_dau_phay (11 câu) | 0,0% |

Nhóm lô A bị ăn trọn 100% đúng như dự đoán — bằng chứng số cho khuyến nghị ở mục 9.

---

## 11. Kết quả đánh giá — 2 model × 2 benchmark

Đánh giá `Qwen/Qwen3-0.6B` và `Qwen/Qwen3-4B` trên cả hai bộ, chạy bằng vLLM
trên Lambda A10. Cả 326 câu, ràng buộc đầu ra bằng structured outputs nên không
có lỗi phân tích cú pháp.

> **Số liệu đo lần trước đã bị loại bỏ.** Lần chạy đầu dính hai lỗi cộng dồn:
> vLLM đã gỡ `GuidedDecodingParams` (v0.12.0) nên ràng buộc đầu ra âm thầm mất
> tác dụng, và Qwen3 mặc định bật chế độ suy nghĩ nên toàn bộ token bị khối
> `<think>` chiếm chỗ. Đáp án khi đó bị vớt nhầm từ chính đoạn suy nghĩ
> ("options are A, B, C, D" → luôn ra A). Chi tiết ở mục 7.

### 11.1 Bảng kết quả (exact match)

| | Mốc mù tốt nhất | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|---:|
| **Bộ MỘT đáp án** | 28,2% *(đoán ngẫu nhiên 1/4)* | 42,0% | **54,6%** |
| **Bộ NHIỀU đáp án** | 25,5% *(chọn 3 ô đầu)* | **0,0%** | 21,2% |

### 11.2 Không model nào vượt được mốc mù ở bộ nhiều đáp án

Đây là kết quả quan trọng nhất. Trên bộ nhiều đáp án, 4B đạt **21,2%** trong khi
chiến lược mù "chọn 3 ô đầu" đạt **25,5%** — model **thấp hơn** heuristic không
đọc câu hỏi. 0.6B đạt 0,0%.

Tách theo nhóm cho thấy rõ hơn:

| Nhóm | n | Mốc "chọn 3 ô đầu" | Qwen3-4B |
|---|---:|---:|---:|
| file1_ngoai_tru | 265 | 23,0% | **17,4%** ⟵ thua mốc |
| file2_them_nhieu | 30 | 6,7% | 46,7% |
| file2_xoa_meta | 20 | 100,0% | 30,0% ⟵ thua mốc |
| file3_tach_dau_phay | 11 | 0,0% | 27,3% |

4B chỉ vượt mốc ở hai nhóm nhỏ. Trên nhóm chiếm 81% bộ dữ liệu (`file1_ngoai_tru`)
nó thua mốc mù. Ở dải năng lực này, **bộ nhiều đáp án chưa đo được năng lực** —
nó mới chỉ cho thấy định dạng quá khó.

Ngược lại, bộ một đáp án hoạt động đúng như benchmark cần: cả hai model đều vượt
mốc mù (42,0% và 54,6% so với 28,2%), và xếp hạng đúng theo kích thước.

### 11.3 Chi phí của định dạng nhiều đáp án

Thiết kế cặp (cùng câu hỏi, hai định dạng, cùng model) cho phép đo trực tiếp.
Bảng chéo: S = bộ một đáp án, M = bộ nhiều đáp án.

| Model | S✓M✓ | **S✓M✗** | **S✗M✓** | S✗M✗ | McNemar p |
|---|---:|---:|---:|---:|---:|
| Qwen3-0.6B | 0 | **137** | **0** | 189 | < 0,0001 |
| Qwen3-4B | 59 | **119** | **10** | 138 | < 0,0001 |

Với 4B, **119 câu** thuộc dạng biết kiến thức nhưng hỏng khi phải chọn nhiều ô,
so với chỉ **10 câu** theo chiều ngược. Chênh lệch có ý nghĩa thống kê rõ rệt.

Ô `S✗M✓` nhỏ (0 và 10) là tín hiệu tốt về mặt chất lượng: **bản nhiều đáp án
không rò rỉ đáp án**, không dễ hơn bản gốc một cách bất thường.

### 11.4 Năng lực bị thiếu là hiệu chỉnh SỐ LƯỢNG đáp án

Đáp án chuẩn có 3 ô ở 319/326 câu. Số ô mà model thực sự chọn:

| Model | TB số ô chọn | Phân bố | Precision | Recall |
|---|---:|---|---:|---:|
| Qwen3-0.6B | 2,05 | 2 ô ở **312/326 câu** | 74,0% | 50,4% |
| Qwen3-4B | 2,49 | 2 ô: 185 · 3 ô: 92 · 4 ô: 36 | 83,0% | 68,6% |

0.6B gần như luôn chọn đúng 2 ô, nên **không bao giờ trùng khít** với đáp án 3 ô
— giải thích trọn vẹn con số 0,0%. Đây không phải thiếu kiến thức: cùng model đó
đạt 42,0% ở bản một đáp án. Cái nó thiếu là khả năng quyết định *"nên chọn bao
nhiêu ô"*.

Cả hai model đều có precision cao hơn recall nhiều — lỗi chủ đạo là **chọn thiếu**
chứ không phải chọn sai. Đây đúng là năng lực mà bộ nhiều đáp án sinh ra để đo,
và nó đo được.

### 11.5 Độ phân biệt giữa hai model

Phân loại từng câu theo việc model mạnh/yếu làm được hay không:

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai | Tín hiệu ròng |
|---|---:|---:|---:|---:|---:|
| Bộ nhiều đáp án | 0 | **69** | **0** | 257 | **+100%** |
| Bộ một đáp án | 93 | 85 | 44 | 104 | +31,8% |

Bộ nhiều đáp án phân biệt **sạch tuyệt đối**: 69 câu tách được hai model, 0 câu
theo chiều nghịch đảo. Bộ một đáp án có 44 câu nghịch đảo — nhiễu từ việc đoán
trúng 1 trong 4.

Nhưng bộ nhiều đáp án có **78,8% số câu cả hai model đều sai**, tức phần lớn bộ
đề chưa phân loại được gì ở dải năng lực này. Bộ một đáp án cân bằng hơn nhiều
(28,5% quá dễ, 31,9% quá khó, 39,6% mang thông tin).

### 11.6 Bộ MỘT đáp án có lỗi thiên lệch vị trí nghiêm trọng

Phân bố vị trí đáp án đúng trong dữ liệu gốc:

| Nhóm | Tỷ lệ đáp án nằm ở D |
|---|---:|
| file2_xoa_meta | **100%** (20/20) |
| file2_them_nhieu | 90% (27/30) |
| file1_ngoai_tru | 40% (105/265) |
| Toàn bộ | 47,5% (155/326) |

Điều này giải thích điểm số của 0.6B. Nó chọn D ở **236/326 câu**, và:

- đúng **76,8%** khi đáp án thật là D
- đúng **10,5%** khi đáp án không phải D

Nghĩa là 42,0% của 0.6B gần như hoàn toàn là **trùng vị trí, không phải hiểu bài**.
Nó "thắng" 4B ở hai nhóm `file2` (85,0% so với 75,0%; 83,3% so với 76,7%) chỉ vì
"Tất cả đều đúng" hầu như luôn nằm ở phương án D.

4B cũng lệch nhưng nhẹ hơn nhiều (64,5% khi là D so với 45,6% khi không phải D),
tức nó thực sự đọc nội dung.

Lỗi này thuộc về **ngân hàng đề gốc**, không phải do xử lý — bộ một đáp án được
giữ nguyên văn có chủ ý. Bộ nhiều đáp án **không mắc lỗi này** vì đã trộn vị trí
có seed ở cả ba tập thành phần (mục 7).

### 11.7 Kết luận

**Về hai model.** Qwen3-4B vượt 0.6B trên cả hai bộ và ở mọi nhóm con có ý nghĩa.
Nhưng ở bộ nhiều đáp án, cả hai đều chưa vượt được mốc mù — cần model mạnh hơn
hẳn mới biết trần của bộ này ở đâu.

**Về hai benchmark.** Chúng đo hai thứ khác nhau và bổ sung cho nhau:

- Bộ **một đáp án** phân loại được model ở dải năng lực hiện tại, nhưng bị nhiễm
  thiên lệch vị trí D từ đề gốc nên điểm số của model nhỏ bị thổi phồng.
- Bộ **nhiều đáp án** sạch về thiên lệch vị trí và phân biệt không nhiễu, nhưng
  hiện quá khó: 78,8% số câu cả hai model đều sai, và mốc mù còn cao hơn model.

**Ba việc nên làm tiếp**, theo thứ tự ưu tiên:

1. **Cân bằng phân bố số đáp án đúng.** 319/326 câu có đúng 3 đáp án khiến mốc
   "chọn 3 ô" cao bất thường (25,5%). Mở rộng File 3 (còn 290 ứng viên) sẽ đa
   dạng hoá phân bố và kéo mốc mù xuống.
2. **Đo thêm một model mạnh hơn hẳn** để biết 21,2% là giới hạn của model 4B hay
   của chính bộ dữ liệu. Nếu model mạnh cũng quanh mốc mù thì vấn đề nằm ở
   ground truth chứ không phải độ khó.
3. **Loại 20 câu `file2_xoa_meta` khỏi phần chấm chính** ở cả hai bộ. Ở bản một
   đáp án chúng có đáp án D 100%; ở bản nhiều đáp án mốc mù đạt 100%. Không bản
   nào đo được năng lực.

## Phụ lục — cách tái tạo

```powershell
$py = "C:\Users\User\miniconda3\python.exe"

# làm sạch + phân loại + các file trung gian
$env:MCQ_DATA_DIR="data"; $env:MCQ_OUT_DIR="data"; & $py pyline\run.py all

# lọc (chưa xử lý) -> filter_data/
$env:MCQ_OUT_DIR="filter_data"; & $py pyline\run.py 17 10 14

# xử lý thành nhiều đáp án -> processed_data/
$env:MCQ_OUT_DIR="processed_data"; & $py pyline\run.py 09 15
$env:MCQ_DATA_DIR="filter_data";   & $py pyline\run.py 13

# gộp thành bộ benchmark
$env:MCQ_DATA_DIR="processed_data"; & $py pyline\run.py 16

# đánh giá
& $py eval_qwen3vl.py --baselines-only
& $py eval_qwen3vl.py
```

| Thư mục | Nội dung |
|---|---|
| `data/` | File trung gian (làm sạch, phân loại, kiểm tra) |
| `filter_data/` | Dữ liệu đã lọc, **chưa xử lý** |
| `processed_data/` | Dữ liệu đã chuyển thành nhiều đáp án + bộ gộp |
| `pyline/` | Pipeline Python (17 tầng) |
| `lambda/` | Điều khiển GPU Lambda cho bước LLM quy mô lớn |
