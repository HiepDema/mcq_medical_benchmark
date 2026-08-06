# So sánh 2 model × 2 benchmark

Báo cáo bổ sung cho [REPORT.md](REPORT.md). Đo `Qwen/Qwen3-0.6B` và `Qwen/Qwen3-4B`
trên **cả hai** bộ dữ liệu để trả lời hai câu hỏi tách biệt: model mạnh đến đâu, và
**bản thân benchmark có đo được gì không**.

| | |
|---|---|
| Model | `Qwen/Qwen3-0.6B` · `Qwen/Qwen3-4B` (text-only) |
| Bộ nhiều đáp án | `processed_data/benchmark_multi.json` |
| Bộ một đáp án | `processed_data/benchmark_single.json` — bản gốc nguyên văn |
| Phạm vi chấm | **150 câu**, 3 nhóm × 50 |
| Hạ tầng | vLLM trên Lambda A10, structured outputs, `enable_thinking=False` |
| Kết quả thô | `eval_{multi,single}_{0.6b,4b}.json` |

**Thiết kế cặp.** Hai bộ chứa **đúng cùng các câu hỏi**, khớp 1:1 theo chỉ số — bộ
một đáp án là bản gốc của bộ nhiều đáp án. Mọi khác biệt quan sát được đều quy về
định dạng, không phải do câu khó dễ khác nhau.

**Vì sao 150 chứ không phải 200.** File dữ liệu phát hành có 200 câu (4 nhóm × 50),
nhưng báo cáo này bỏ nhóm `file2_xoa_meta` khỏi phần chấm. Đó là 50 câu mà **mọi
phương án đều đúng**, nên chiến lược mù "chọn hết" tự động đạt 100% ở nhóm đó và
kéo mốc mù toàn bộ từ 0% lên 25%. Giữ nhóm này trong điểm chính sẽ thổi phồng mọi
con số. Nhóm vẫn nằm trong file để dùng làm phép thử độ lệch chọn-thiếu (mục 7).

> ⚠️ **Số liệu ở mục 11 của REPORT.md đã lỗi thời** — đo trên bộ 326 câu cũ và dính
> lỗi guided decoding (vLLM gỡ `GuidedDecodingParams` ở v0.12.0 khiến ràng buộc đầu
> ra âm thầm mất tác dụng, đáp án bị vớt nhầm từ khối `<think>`). Các con số trong
> file này mới là bản đúng.

---

## 1. Bảng kết quả (exact match)

| | Mốc mù tốt nhất | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|---:|
| **Bộ MỘT đáp án** | 22,0% *(đoán ngẫu nhiên 1/4)* | 48,7% | **57,3%** |
| **Bộ NHIỀU đáp án** | 10,7% *(chọn 3 ô đầu)* | 2,0% | **28,7%** |

Đầy đủ các mốc mù (không dùng model), tính trên đúng 150 câu này:

| Bộ | Chiến lược mù | exact |
|---|---|---:|
| Nhiều đáp án | chọn 3 ô đầu | **10,7%** |
| Nhiều đáp án | chọn ngẫu nhiên (mỗi ô 50%) | 3,3% |
| Nhiều đáp án | chọn hết mọi phương án | **0,0%** |
| Một đáp án | đoán ngẫu nhiên 1 trong 4 | **22,0%** |
| Một đáp án | luôn chọn A | 15,3% |

Mốc "chọn hết" bằng đúng **0,0%** — sau khi bỏ `file2_xoa_meta`, không câu nào có
toàn bộ phương án đều đúng, nên đường đi tắt đó biến mất hoàn toàn.

---

## 2. Bộ nhiều đáp án đo được năng lực, nhưng chỉ với model đủ lớn

Qwen3-4B đạt **28,7%** so với mốc mù **10,7%** — vượt **18 điểm**. Đây là lần đầu
bộ nhiều đáp án cho tín hiệu năng lực thật (trên bộ 326 câu chưa cân bằng trước
đây, 4B đạt 21,2% trong khi mốc mù là 25,5%, tức *thua* mốc).

Qwen3-0.6B đạt **2,0%**, thấp hơn cả mốc mù — nó thất bại hoàn toàn ở định dạng này.

| Nhóm | n | Mốc "chọn 3 ô đầu" | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|---:|---:|
| file1_ngoai_tru | 50 | 18,0% | 0,0% | 20,0% |
| file2_them_nhieu | 50 | 10,0% | 2,0% | **46,0%** |
| file3_tach_dau_phay | 50 | 4,0% | 4,0% | 20,0% |
| **Tổng** | 150 | 10,7% | 2,0% | **28,7%** |

4B vượt mốc ở cả ba nhóm. Nhóm `file2_them_nhieu` cao nhất (46,0%) nhưng cần đọc
kèm cảnh báo ở mục 6.

---

## 3. Chi phí của định dạng nhiều đáp án

Bảng chéo trên thiết kế cặp. S = bộ một đáp án, M = bộ nhiều đáp án.

| Model | S✓M✓ | **S✓M✗** | **S✗M✓** | S✗M✗ | McNemar p |
|---|---:|---:|---:|---:|---:|
| Qwen3-0.6B | 1 | **72** | **2** | 75 | < 0,0001 |
| Qwen3-4B | 31 | **55** | **12** | 52 | < 0,0001 |

Với 4B, **55 câu** thuộc dạng biết kiến thức nhưng hỏng khi phải chọn nhiều ô, so
với **12 câu** theo chiều ngược. Chênh lệch có ý nghĩa thống kê ở cả ba nhóm con
(p = 0,0005 · 0,0056 · 0,0247).

Ô `S✗M✓` nhỏ là tín hiệu tốt về chất lượng: **bản nhiều đáp án không rò rỉ đáp án**,
không dễ hơn bản gốc một cách bất thường.

---

## 4. Năng lực bị thiếu là hiệu chỉnh SỐ LƯỢNG đáp án

Đáp án chuẩn trung bình 2,99 ô mỗi câu. Số ô model thực sự chọn:

| Model | TB số ô | Phân bố | Precision | Recall |
|---|---:|---|---:|---:|
| Qwen3-0.6B | 2,19 | 2 ô ở **131/150 câu** | 64,1% | 47,1% |
| Qwen3-4B | 2,85 | 2 ô: 66 · 3 ô: 53 · 4 ô: 20 | 79,4% | 75,7% |

0.6B gần như luôn chọn 2 ô nên hiếm khi trùng khít với đáp án 3 ô — giải thích con
số 2,0%. Đây không phải thiếu kiến thức: cùng model đó đạt 48,7% ở bản một đáp án.
Cái nó thiếu là khả năng quyết định *"nên chọn bao nhiêu ô"*.

4B hiệu chỉnh tốt hơn hẳn: trung bình 2,85 ô so với chuẩn 2,99, và precision gần
bằng recall (79,4% / 75,7%) — tức không còn lệch mạnh về phía chọn thiếu như 0.6B
(64,1% / 47,1%).

---

## 5. Độ phân biệt giữa hai model

Phân loại từng câu theo việc model mạnh/yếu làm được hay không:

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai | Tín hiệu ròng |
|---|---:|---:|---:|---:|---:|
| Bộ nhiều đáp án | 1 | **42** | **2** | 105 | **+90,9%** |
| Bộ một đáp án | 54 | 32 | 19 | 45 | +25,5% |

Bộ nhiều đáp án phân biệt gần như sạch hoàn toàn: 42 câu tách được hai model, chỉ
2 câu theo chiều nghịch đảo. Bộ một đáp án có 19 câu nghịch đảo — nhiễu từ việc
đoán trúng 1 trong 4.

Điểm yếu còn lại của bộ nhiều đáp án: **70,0% số câu cả hai model đều sai**. Phần
lớn bộ đề vẫn chưa phân loại được gì ở dải năng lực này, cần model mạnh hơn mới
biết trần nằm ở đâu.

---

## 6. Bộ MỘT đáp án vẫn nhiễm thiên lệch vị trí

Vị trí đáp án đúng trong 150 câu: A 23 · B 27 · C 17 · **D 83** — D chiếm **55%**.
Lỗi này thuộc về ngân hàng đề gốc; bộ một đáp án được giữ nguyên văn có chủ ý.

Hệ quả thấy rõ ở nhóm `file2_them_nhieu`, nơi đáp án gốc là "Tất cả đều đúng" nằm
ở D tới 47/50 câu:

| Nhóm (bộ một đáp án) | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|
| file2_them_nhieu | **78,0%** | 74,0% |
| file1_ngoai_tru | 36,0% | 54,0% |
| file3_tach_dau_phay | 32,0% | 44,0% |

Model 0.6B **thắng cả 4B** ở nhóm đó — không phải vì hiểu bài mà vì nó thiên lệch
chọn D. Đây là lý do không nên đọc điểm bộ một đáp án tách rời khỏi phân bố vị trí.

Bộ nhiều đáp án **không mắc lỗi này**: vị trí phương án sai phân bố đều
(A 62 · B 50 · C 56 · D 50 · E 34 · F 8 · G 4) nhờ bước trộn có seed ở cả ba nhóm.

---

## 7. Nhóm `file2_xoa_meta` — dùng làm phép thử, không tính điểm

50 câu bị loại khỏi phần chấm vẫn hữu ích. Vì mọi phương án đều đúng, chúng đo
trực tiếp xu hướng chọn-thiếu: model nào không dám chọn hết sẽ lộ ra ngay.

| Model | exact trên nhóm này |
|---|---:|
| Mốc "chọn hết" | 100,0% |
| Qwen3-4B | 56,0% |
| Qwen3-0.6B | 6,0% |

Kết quả khớp với mục 4: 4B hiệu chỉnh số lượng khá hơn nhưng vẫn bỏ sót gần một
nửa, còn 0.6B gần như không bao giờ chọn đủ.

---

## 8. Kết luận

**Về hai model.** Qwen3-4B vượt 0.6B trên cả hai bộ và ở mọi nhóm con, trừ đúng
một ngoại lệ do artifact vị trí (mục 6). Khoảng cách trên bộ nhiều đáp án rất rõ
(28,7% so với 2,0%), cho thấy định dạng này phân tách năng lực tốt hơn.

**Về hai benchmark.**

| | Bộ một đáp án | Bộ nhiều đáp án |
|---|---|---|
| Model vượt mốc mù? | ✓ cả hai | ✓ chỉ 4B |
| Nhiễu khi phân biệt | 19 câu nghịch đảo | **2 câu** |
| Thiên lệch vị trí | ✗ D chiếm 55% | ✓ phân bố đều |
| Câu cả hai model đều sai | 30,0% | 70,0% |
| Đường đi tắt "chọn hết" | không áp dụng | **0,0%** |

Bộ nhiều đáp án sạch hơn về mặt artifact và phân biệt gần như không nhiễu, nhưng
còn quá khó. Bộ một đáp án dễ tiếp cận hơn nhưng bị thiên lệch vị trí làm méo.

**Ba việc nên làm tiếp:**

1. **Đo thêm một model mạnh hơn hẳn** (14B trở lên, hoặc model qua API). 70% số câu
   cả hai model hiện tại đều sai — chưa biết đó là do khó thật hay do ground truth
   sai. Model mạnh sẽ phân định được.
2. **Cân bằng vị trí đáp án cho bộ một đáp án**, hoặc ít nhất báo cáo kèm phân bố
   vị trí mỗi lần công bố điểm.
3. **Mở rộng `file3_tach_dau_phay`** — nhóm này có nhiễu do người ra đề viết nên
   đáng tin nhất, hiện mới dùng 50/121 ứng viên đạt lọc tự động.

---

## Phụ lục — cách tái tạo

```bash
# trên máy có GPU
git clone https://github.com/HiepDema/mcq_medical_benchmark.git
cd mcq_medical_benchmark
python3 -m venv ~/venv && ~/venv/bin/pip install -U pip && ~/venv/bin/pip install vllm
bash lambda/eval_models.sh
```

```powershell
# trên máy local, sau khi kéo 4 file eval_*.json về
python compare_benchmarks.py `
    --multi eval_multi_0.6b.json --single eval_single_0.6b.json `
    --multi eval_multi_4b.json   --single eval_single_4b.json `
    --exclude file2_xoa_meta
```

Bỏ cờ `--exclude` để xem kết quả trên đủ 200 câu. Mốc so sánh tính được không cần GPU:

```powershell
python eval_qwen3vl.py --baselines-only
python eval_qwen3vl.py --data processed_data/benchmark_single.json `
                       --provenance processed_data/benchmark_single_provenance.json `
                       --single --baselines-only
```
