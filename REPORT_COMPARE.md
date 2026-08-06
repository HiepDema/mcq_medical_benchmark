# So sánh 2 model × 2 benchmark

Báo cáo bổ sung cho [REPORT.md](REPORT.md). Đo `Qwen/Qwen3-0.6B` và `Qwen/Qwen3-4B`
trên **cả hai** bộ dữ liệu để trả lời hai câu hỏi tách biệt: model mạnh đến đâu, và
**bản thân benchmark có đo được gì không**.

| | |
|---|---|
| Model | `Qwen/Qwen3-0.6B` · `Qwen/Qwen3-4B` (text-only) |
| Bộ nhiều đáp án | `processed_data/benchmark_multi.json` — 326 câu, 2–5 đáp án đúng |
| Bộ một đáp án | `processed_data/benchmark_single.json` — 326 câu gốc, 1 đáp án đúng |
| Hạ tầng | vLLM trên Lambda A10, structured outputs, `enable_thinking=False` |
| Kết quả thô | `eval_{multi,single}_{0.6b,4b}.json` |

**Thiết kế cặp.** Hai bộ chứa **đúng cùng 326 câu hỏi**, khớp 1:1 theo chỉ số — bộ
một đáp án là bản gốc nguyên văn của bộ nhiều đáp án. Mọi khác biệt quan sát được
đều quy về định dạng, không phải do câu khó dễ khác nhau.

> ⚠️ **Số liệu ở mục 11 của REPORT.md đã lỗi thời.** Lần chạy đó dính hai lỗi cộng
> dồn: vLLM gỡ `GuidedDecodingParams` ở v0.12.0 nên ràng buộc đầu ra âm thầm mất
> tác dụng, và Qwen3 mặc định bật chế độ suy nghĩ nên toàn bộ token bị khối
> `<think>` chiếm chỗ — đáp án bị vớt nhầm từ chính đoạn suy nghĩ. Các con số
> trong file này mới là bản đúng.

---

## 1. Bảng kết quả (exact match)

| | Mốc mù tốt nhất | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|---:|
| **Bộ MỘT đáp án** | 28,2% *(đoán ngẫu nhiên 1/4)* | 42,0% | **54,6%** |
| **Bộ NHIỀU đáp án** | 25,5% *(chọn 3 ô đầu)* | **0,0%** | 21,2% |

---

## 2. Không model nào vượt được mốc mù ở bộ nhiều đáp án

Đây là kết quả quan trọng nhất. Trên bộ nhiều đáp án, 4B đạt **21,2%** trong khi
chiến lược mù "chọn 3 ô đầu" đạt **25,5%** — model **thấp hơn** heuristic không đọc
câu hỏi. 0.6B đạt 0,0%.

Tách theo nhóm cho thấy rõ hơn:

| Nhóm | n | Mốc "chọn 3 ô đầu" | Qwen3-4B |
|---|---:|---:|---:|
| file1_ngoai_tru | 265 | 23,0% | **17,4%** ⟵ thua mốc |
| file2_them_nhieu | 30 | 6,7% | 46,7% |
| file2_xoa_meta | 20 | 100,0% | 30,0% ⟵ thua mốc |
| file3_tach_dau_phay | 11 | 0,0% | 27,3% |

4B chỉ vượt mốc ở hai nhóm nhỏ. Trên nhóm chiếm 81% bộ dữ liệu (`file1_ngoai_tru`)
nó thua mốc mù. Ở dải năng lực này, **bộ nhiều đáp án chưa đo được năng lực** — nó
mới chỉ cho thấy định dạng quá khó.

Ngược lại, bộ một đáp án hoạt động đúng như benchmark cần: cả hai model đều vượt
mốc mù (42,0% và 54,6% so với 28,2%), và xếp hạng đúng theo kích thước.

---

## 3. Chi phí của định dạng nhiều đáp án

Bảng chéo trên thiết kế cặp. S = bộ một đáp án, M = bộ nhiều đáp án.

| Model | S✓M✓ | **S✓M✗** | **S✗M✓** | S✗M✗ | McNemar p |
|---|---:|---:|---:|---:|---:|
| Qwen3-0.6B | 0 | **137** | **0** | 189 | < 0,0001 |
| Qwen3-4B | 59 | **119** | **10** | 138 | < 0,0001 |

Với 4B, **119 câu** thuộc dạng biết kiến thức nhưng hỏng khi phải chọn nhiều ô, so
với chỉ **10 câu** theo chiều ngược. Chênh lệch có ý nghĩa thống kê rõ rệt.

Ô `S✗M✓` nhỏ (0 và 10) là tín hiệu tốt về chất lượng: **bản nhiều đáp án không rò
rỉ đáp án**, không dễ hơn bản gốc một cách bất thường. Đây là rủi ro đã được lường
trước khi thiết kế, và số liệu cho thấy nó không xảy ra.

---

## 4. Năng lực bị thiếu là hiệu chỉnh SỐ LƯỢNG đáp án

Đáp án chuẩn có 3 ô ở 319/326 câu. Số ô model thực sự chọn:

| Model | TB số ô | Phân bố | Precision | Recall |
|---|---:|---|---:|---:|
| Qwen3-0.6B | 2,05 | 2 ô ở **312/326 câu** | 74,0% | 50,4% |
| Qwen3-4B | 2,49 | 2 ô: 185 · 3 ô: 92 · 4 ô: 36 | 83,0% | 68,6% |

0.6B gần như luôn chọn đúng 2 ô nên **không bao giờ trùng khít** với đáp án 3 ô —
giải thích trọn vẹn con số 0,0%. Đây không phải thiếu kiến thức: cùng model đó đạt
42,0% ở bản một đáp án. Cái nó thiếu là khả năng quyết định *"nên chọn bao nhiêu ô"*.

Cả hai model đều có precision cao hơn recall nhiều — lỗi chủ đạo là **chọn thiếu**
chứ không phải chọn sai. Đây đúng là năng lực mà bộ nhiều đáp án sinh ra để đo, và
nó đo được.

---

## 5. Độ phân biệt giữa hai model

Phân loại từng câu theo việc model mạnh/yếu làm được hay không:

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai | Tín hiệu ròng |
|---|---:|---:|---:|---:|---:|
| Bộ nhiều đáp án | 0 | **69** | **0** | 257 | **+100%** |
| Bộ một đáp án | 93 | 85 | 44 | 104 | +31,8% |

Bộ nhiều đáp án phân biệt **sạch tuyệt đối**: 69 câu tách được hai model, 0 câu theo
chiều nghịch đảo. Bộ một đáp án có 44 câu nghịch đảo — nhiễu từ việc đoán trúng 1
trong 4.

Nhưng bộ nhiều đáp án có **78,8% số câu cả hai model đều sai**, tức phần lớn bộ đề
chưa phân loại được gì ở dải năng lực này. Bộ một đáp án cân bằng hơn nhiều: 28,5%
quá dễ, 31,9% quá khó, 39,6% mang thông tin.

---

## 6. Bộ MỘT đáp án có lỗi thiên lệch vị trí nghiêm trọng

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
Nó thậm chí "thắng" 4B ở hai nhóm `file2` (85,0% so với 75,0%; 83,3% so với 76,7%)
chỉ vì "Tất cả đều đúng" hầu như luôn nằm ở phương án D.

4B cũng lệch nhưng nhẹ hơn nhiều (64,5% khi là D so với 45,6% khi không phải D),
tức nó thực sự đọc nội dung.

Lỗi này thuộc về **ngân hàng đề gốc**, không phải do xử lý — bộ một đáp án được giữ
nguyên văn có chủ ý. Bộ nhiều đáp án **không mắc lỗi này** vì đã trộn vị trí có seed
ở cả ba tập thành phần (REPORT mục 7).

---

## 7. Kết luận

**Về hai model.** Qwen3-4B vượt 0.6B trên cả hai bộ và ở mọi nhóm con có ý nghĩa.
Nhưng ở bộ nhiều đáp án, cả hai đều chưa vượt được mốc mù — cần model mạnh hơn hẳn
mới biết trần của bộ này ở đâu.

**Về hai benchmark.** Chúng đo hai thứ khác nhau và bổ sung cho nhau:

| | Bộ một đáp án | Bộ nhiều đáp án |
|---|---|---|
| Phân loại được model? | ✓ cả hai vượt mốc mù | ✗ cả hai dưới mốc mù |
| Nhiễu khi phân biệt | 44 câu nghịch đảo | **0 câu** |
| Thiên lệch vị trí | ✗ D chiếm 47,5% | ✓ đã trộn có seed |
| Câu cả hai model đều sai | 31,9% | 78,8% |

**Ba việc nên làm tiếp**, theo thứ tự ưu tiên:

1. **Cân bằng phân bố số đáp án đúng.** 319/326 câu có đúng 3 đáp án khiến mốc "chọn
   3 ô" cao bất thường (25,5%). Mở rộng File 3 (còn 290 ứng viên trong danh sách rút
   gọn) sẽ đa dạng hoá phân bố và kéo mốc mù xuống.
2. **Đo thêm một model mạnh hơn hẳn** để biết 21,2% là giới hạn của model 4B hay của
   chính bộ dữ liệu. Nếu model mạnh cũng quanh mốc mù thì vấn đề nằm ở ground truth
   chứ không phải độ khó.
3. **Loại 20 câu `file2_xoa_meta` khỏi phần chấm chính** ở cả hai bộ. Ở bản một đáp
   án chúng có đáp án D 100%; ở bản nhiều đáp án mốc mù đạt 100%. Không bản nào đo
   được năng lực.

---

## Phụ lục — cách tái tạo

```bash
# trên máy có GPU
git clone https://github.com/HiepDema/mcq_medical_benchmark.git
python3 -m venv ~/venv && ~/venv/bin/pip install -U pip && ~/venv/bin/pip install vllm
bash mcq_medical_benchmark/lambda/eval_models.sh
```

```powershell
# trên máy local, sau khi kéo 4 file eval_*.json về
python compare_benchmarks.py `
    --multi eval_multi_0.6b.json --single eval_single_0.6b.json `
    --multi eval_multi_4b.json   --single eval_single_4b.json
```

Mốc so sánh tính được không cần GPU:

```powershell
python eval_qwen3vl.py --baselines-only
python eval_qwen3vl.py --data processed_data/benchmark_single.json `
                       --provenance processed_data/benchmark_single_provenance.json `
                       --single --baselines-only
```
