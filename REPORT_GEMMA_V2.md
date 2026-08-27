# Chấm Gemma 3 trên benchmark v2 — và so với Qwen3

Bổ sung [REPORT_BENCHMARK_V2.md](REPORT_BENCHMARK_V2.md): chấm thêm **Gemma 3 1B và 4B**
trên đúng hai bộ benchmark đó, kèm thống kê theo **độ khó** cho cả bốn model.

| | |
|---|---|
| Model mới | `unsloth/gemma-3-1b-it` · `unsloth/gemma-3-4b-it` |
| Model đối chiếu | `Qwen/Qwen3-0.6B` · `Qwen/Qwen3-4B` |
| Hạ tầng | 1×A10 24 GB, vLLM 0.28.0, structured outputs |
| Thời gian | 8 lượt, 22 phút (1B ~170 câu/s · 4B ~35 câu/s) |
| Kết quả thô | [results_v2/](results_v2/) · `eval_*_gemma*.json` |
| Lệnh | `MODELS="1b\|unsloth/gemma-3-1b-it 4b\|unsloth/gemma-3-4b-it" PREFIX=gemma bash lambda/eval_v2.sh all` |

> **Về nguồn trọng số.** `google/gemma-3-*-it` bị gate trên HuggingFace (HTTP 401 khi
> tải không token), nên đã dùng bản re-upload `unsloth/gemma-3-*-it`. Đây là bên thứ ba;
> trọng số gần như chắc chắn giống bản gốc của Google nhưng không có gì bảo đảm chính
> thức. Muốn chắc thì chạy lại với token HuggingFace và model `google/gemma-3-*-it`.

---

## 1. Bảng điểm bốn model (exact match)

| Bộ | n | Qwen3-0.6B | Qwen3-4B | Gemma3-1B | Gemma3-4B |
|---|---:|---:|---:|---:|---:|
| **Bộ A** — nhiều đáp án | 9.368 | 3,6% | **24,7%** | 2,1% | 20,5% |
| **Bộ B** — hỗn hợp | 11.368 | 3,3% | **21,2%** | 1,8% | 16,3% |
| Đối chứng của A | 9.368 | 40,6% | **55,7%** | 37,5% | 50,2% |
| Đối chứng của B | 11.368 | 39,5% | **55,5%** | 37,0% | 49,3% |

**Qwen3 thắng Gemma 3 ở mọi bộ, mọi cỡ.** Khoảng cách rộng nhất đúng ở định dạng nhiều
đáp án: 24,7% so với 20,5% ở cỡ 4B, và 3,6% so với 2,1% ở cỡ nhỏ nhất. Ở định dạng một
đáp án khoảng cách hẹp hơn (55,7% so với 50,2%).

Xếp hạng giữ nguyên trên cả bốn bộ — không có bộ nào đảo thứ tự, nên kết luận không phụ
thuộc vào việc chọn bộ nào để báo cáo.

Hai model cỡ nhỏ (0.6B và 1B) đều **thất bại hoàn toàn** ở định dạng nhiều đáp án: 3,6%
và 2,1%.

---

## 2. Theo độ khó

Trường `difficultLevel` của đề gốc có **15 cách viết khác nhau** (`'2'`, `'Level 2'`,
`'Level 2 (Moderate)'`, `'Medium'`, `'Moderate'`…) nên phải quy về một thang chung trước
khi đếm:

| Bậc | Giá trị thô gộp vào |
|---|---|
| 1 — Dễ | `'1'`×1.567 · `'Level 1'`×462 · `'Easy'`×220 · `'Level 1 (Easy)'`×156 |
| 2 — Trung bình | `'2'`×6.437 · `'Level 2'`×852 · `'Level 2 (Moderate)'`×132 · `'Medium'`×45 · `'Moderate'`×30 |
| 3 — Khó | `'3'`×1.291 · `'Level 3'`×120 · `'Level 3 (Challenging)'`×17 |
| 4 — Rất khó | `'4'`×27 · `'Hard'`×9 · `'Level 4 (Hard)'`×3 |

### Số câu đúng / sai theo độ khó — Bộ B (11.368 câu)

| Độ khó | n | Qwen3-0.6B<br>đúng / sai | Qwen3-4B<br>đúng / sai | Gemma3-1B<br>đúng / sai | Gemma3-4B<br>đúng / sai |
|---|---:|---:|---:|---:|---:|
| 1 — Dễ | 2.405 | 101 / 2.304 | 630 / 1.775 | 47 / 2.358 | 420 / 1.985 |
| 2 — Trung bình | 7.496 | 235 / 7.261 | 1.573 / 5.923 | 130 / 7.366 | 1.240 / 6.256 |
| 3 — Khó | 1.428 | 41 / 1.387 | 205 / 1.223 | 27 / 1.401 | 186 / 1.242 |
| 4 — Rất khó | 39 | 1 / 38 | 5 / 34 | 1 / 38 | 3 / 36 |

Cùng số liệu, tính theo tỉ lệ:

| Độ khó | n | % bộ | Qwen3-0.6B | Qwen3-4B | Gemma3-1B | Gemma3-4B |
|---|---:|---:|---:|---:|---:|---:|
| 1 — Dễ | 2.405 | 21,2% | 4,2% | **26,2%** | 2,0% | **17,5%** |
| 2 — Trung bình | 7.496 | 65,9% | 3,1% | 21,0% | 1,7% | 16,5% |
| 3 — Khó | 1.428 | 12,6% | 2,9% | 14,4% | 1,9% | 13,0% |
| 4 — Rất khó | 39 | 0,3% | 2,6% | 12,8% | 2,6% | 7,7% |

**Nhãn độ khó của đề gốc là thật.** Cả hai model 4B đều giảm đơn điệu khi độ khó tăng —
Qwen3-4B 26,2% → 21,0% → 14,4% → 12,8%, Gemma3-4B 17,5% → 16,5% → 13,0% → 7,7%. Đây là
một phép kiểm tra tính hợp lệ độc lập: nhãn do người ra đề gán, benchmark không hề dùng
tới nó khi dựng, vậy mà nó vẫn dự báo được điểm model.

Hai model nhỏ thì **không** cho tín hiệu đó — Qwen3-0.6B 4,2% → 3,1% → 2,9% → 2,6% gần
như phẳng, Gemma3-1B thậm chí đi ngang. Chúng thất bại vì lý do khác chứ không phải vì
câu khó: chúng hỏng ở định dạng, nên độ khó nội dung không còn ảnh hưởng gì.

Lưu ý: bậc **4 — Rất khó chỉ có 39 câu (0,3%)** nên mọi con số ở dòng đó có sai số rất
lớn, chênh một câu là đổi 2,6 điểm phần trăm. Không nên đọc dòng đó như một xu hướng.

### Độ khó × họ câu hỏi — Gemma3-4B

| Họ | 1 — Dễ | 2 — Trung bình | 3 — Khó | 4 — Rất khó |
|---|---:|---:|---:|---:|
| file1_ngoai_tru | 26,7% (475) | 20,7% (3.454) | 17,1% (637) | 0,0% (7) |
| file2_them_nhieu | 30,1% (389) | 29,1% (605) | 16,7% (96) | 50,0% (2) |
| file3_tach_dau_phay | 10,7% (671) | 9,2% (1.739) | 8,7% (381) | 5,3% (19) |
| file4_ca_ab | 28,3% (230) | 25,1% (578) | 20,2% (84) | 100,0% (1) |
| single_1_dap_an | 6,1% (640) | 3,8% (1.120) | 4,8% (230) | 0,0% (10) |

---

## 3. Theo họ câu hỏi — Bộ B

| Họ | n | Qwen3-0.6B | Qwen3-4B | Gemma3-1B | Gemma3-4B |
|---|---:|---:|---:|---:|---:|
| file1_ngoai_tru | 4.573 | 1,3% | 20,2% | 0,2% | **20,8%** |
| file2_them_nhieu | 1.092 | 2,3% | **38,7%** | 0,0% | 28,4% |
| file3_tach_dau_phay | 2.810 | 5,8% | **16,9%** | 5,1% | 9,5% |
| file4_ca_ab | 893 | 11,9% | **38,2%** | 6,0% | 25,5% |
| single_1_dap_an | 2.000 | 1,2% | **12,5%** | 0,1% | 4,7% |

Hai chi tiết đáng chú ý:

- **Gemma3-4B nhỉnh hơn Qwen3-4B đúng một nhóm**: `file1_ngoai_tru` (20,8% so với 20,2%)
  — nhóm đông nhất. Nhưng nó thua rõ ở `file3_tach_dau_phay` (9,5% so với 16,9%), nhóm
  đòi hỏi chọn từ danh sách mục tách ra, tức là nơi cần hiệu chỉnh số lượng nhiều nhất.
- **Gemma3-1B ăn 0 câu** trên toàn bộ 1.092 câu `file2_them_nhieu`.

---

## 4. Hiệu chỉnh số lượng ô — hai họ model hỏng theo hai kiểu khác nhau

Trên **cùng 2.000 câu một đáp án**, chỉ khác ở chỗ model có được báo trước số đáp án hay không:

| Model | Được báo "đúng 1 đáp án" | Không được báo | Chỉ chọn 1 ô | Đáp án đúng ⊆ tập chọn |
|---|---:|---:|---:|---:|
| Qwen3-0.6B | 33,1% | 1,2% | 1,9% | 56,9% |
| Qwen3-4B | **54,1%** | **12,5%** | 16,6% | 71,7% |
| Gemma3-1B | 34,8% | **0,1%** | 0,1% | 54,0% |
| Gemma3-4B | 45,0% | 4,7% | 7,4% | 71,6% |

Gemma3-1B chỉ trả lời đúng **2 câu trên 2.000** khi không được báo trước, dù khi được báo
thì nó đạt 34,8% — nhỉnh hơn cả Qwen3-0.6B.

Phân bố số ô model chọn trên toàn Bộ B (đáp án chuẩn trung bình 2,51 ô):

| Model | TB số ô | 1 ô | 2 ô | 3 ô | 4 ô | 5 ô |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-0.6B | 2,05 | 93 | **10.788** | 317 | 150 | 20 |
| Gemma3-1B | 2,01 | 3 | **11.315** | 32 | 17 | 1 |
| Qwen3-4B | 2,42 | 662 | 6.673 | 2.734 | 1.176 | 123 |
| Gemma3-4B | **2,71** | 477 | 4.786 | 3.962 | 1.884 | 259 |

Hai kiểu hỏng khác nhau:

- **Hai model nhỏ chọn đúng 2 ô ở gần như mọi câu** — Gemma3-1B làm vậy ở 11.315/11.368
  câu (99,5%), còn cực đoan hơn Qwen3-0.6B (94,9%). Chúng bỏ qua hoàn toàn nội dung câu
  hỏi khi quyết định chọn mấy ô.
- **Gemma3-4B chọn thừa** (2,71 ô so với chuẩn 2,51) trong khi **Qwen3-4B chọn thiếu**
  (2,42). Cả hai lệch xấp xỉ như nhau về độ lớn, nhưng lệch ngược chiều. Tỉ lệ "đáp án
  đúng nằm trong tập chọn" của hai model gần bằng nhau (71,6% và 71,7%) — nghĩa là kiến
  thức tương đương, khác biệt điểm số đến từ chỗ cắt tập chọn ở đâu.

---

## 5. Độ phân biệt trong cùng một họ model

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai |
|---|---:|---:|---:|---:|
| Qwen3 trên Bộ B | 237 (2,1%) | 2.176 (19,1%) | **141 (1,2%)** | 8.814 (77,5%) |
| Gemma3 trên Bộ B | 82 (0,7%) | 1.767 (15,5%) | **123 (1,1%)** | 9.396 (82,7%) |
| Gemma3 trên Bộ A | 66 (0,7%) | 1.859 (19,8%) | **134 (1,4%)** | 7.309 (78,0%) |

Tỉ lệ câu nghịch đảo — model yếu đúng trong khi model mạnh sai, tức dấu hiệu nhiễu — ổn
định quanh **1,1–1,4%** cho cả hai họ model. Benchmark hành xử nhất quán, không phụ thuộc
vào việc chấm model nào.

Đổi lại, **82,7% số câu cả hai model Gemma đều sai** (so với 77,5% của Qwen3). Dải năng
lực này vẫn còn quá thấp so với bộ đề.

---

## 6. Kết luận

**Qwen3 mạnh hơn Gemma 3 ở mọi so sánh**, và cách biệt lớn nhất nằm đúng ở chỗ khó nhất
— định dạng nhiều đáp án, nơi phải tự quyết định chọn bao nhiêu ô. Ở cỡ 4B: 24,7% so với
20,5% trên Bộ A, 21,2% so với 16,3% trên Bộ B.

**Nhãn độ khó của đề gốc dự báo được điểm model** — nhưng chỉ với model đủ lớn. Hai model
4B giảm đơn điệu qua bốn bậc; hai model dưới 1,5B thì đường điểm phẳng, vì chúng hỏng ở
định dạng chứ không phải ở kiến thức.

**Cỡ model quyết định nhiều hơn họ model.** Chênh lệch 1B → 4B (2,1% → 20,5%, gấp gần 10
lần) lớn hơn hẳn chênh lệch Qwen3 → Gemma 3 ở cùng cỡ. Không model nào dưới 1,5B dùng
được cho định dạng nhiều đáp án.

**Giới hạn còn lại.** 78–83% số câu cả hai model trong mỗi họ đều sai. Cần chấm model
mạnh hơn hẳn (14B–32B trở lên) mới biết trần của bộ đề nằm ở đâu, và mới tách được phần
"câu quá khó" khỏi phần "đáp án chuẩn của đề nguồn sai".

---

## Phụ lục — tái tạo

```bash
MODELS="1b|unsloth/gemma-3-1b-it 4b|unsloth/gemma-3-4b-it" PREFIX=gemma \
  bash lambda/eval_v2.sh all
```
```powershell
python analyze_results.py `
    --data processed_data_v2/final_benchmark_mixed.json `
    --prov processed_data_v2/final_benchmark_mixed_provenance.json `
    --result "Gemma3-1B=results_v2/eval_mixed_gemma1b.json" `
    --result "Gemma3-4B=results_v2/eval_mixed_gemma4b.json"
```

[analyze_results.py](analyze_results.py) in ra toàn bộ thống kê trong tài liệu này: tổng
thể, theo họ, theo độ khó (kèm số câu đúng/sai), độ khó × họ, hiệu chỉnh số ô, và bảng
chéo độ phân biệt. Thêm `--json-out` để ghi số liệu ra JSON.
