# Chấm Qwen3-0.6B và Qwen3-4B trên benchmark v2

| | |
|---|---|
| Model | `Qwen/Qwen3-0.6B` · `Qwen/Qwen3-4B` (text-only) |
| Bộ dữ liệu | 4 bộ: hỗn hợp 11.368 · nhiều đáp án 9.368, mỗi bộ kèm bản một đáp án |
| Hạ tầng | 1×A10 24 GB, vLLM 0.27.1, structured outputs, `enable_thinking=False` |
| Thời gian | 8 lượt, 20 phút (0,6B ~241 câu/s; 4B ~40 câu/s) |
| Kết quả thô | `results_v2/eval_*.json` |
| Lệnh | `bash lambda/eval_v2.sh all` |

---

## 1. Bảng điểm (exact match)

| Bộ | n | Mốc mù tốt nhất | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|---:|---:|
| **Hỗn hợp** (1 + nhiều đáp án) | 11.368 | 12,6% | 3,3% | **21,2%** |
| **Nhiều đáp án** | 9.368 | 15,3% | 3,6% | **24,7%** |
| Một đáp án (bản hỗn hợp) | 11.368 | 37,8%¹ | 39,5% | **55,5%** |
| Một đáp án (bản 9.368) | 9.368 | 41,5%¹ | 40,6% | **55,7%** |

¹ Mốc "luôn chọn D" — cả hai bộ một đáp án đều lệch về D (37,8% và 41,5%). Trên hai
bộ đó **0.6B gần như không vượt được mốc mù**: 39,5% so với 37,8%, và 40,6% so với
41,5% — tức là thua. Điểm 40% của nó ở định dạng một đáp án gần như hoàn toàn đến từ
thiên hướng chọn D, không phải từ kiến thức.

0.6B thua mốc mù ở cả hai bộ nhiều đáp án — nó thất bại hoàn toàn ở định dạng này,
đúng như đã thấy ở v1 (2,0%).

---

## 2. Phát hiện chính: model không biết phải chọn mấy ô

Bộ hỗn hợp được dựng để đo đúng điều này — model không được báo trước câu nào có
mấy đáp án. Trên **cùng 2.000 câu một đáp án**, chỉ khác ở chỗ có được báo hay không:

| | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|
| Được báo "đúng 1 đáp án" | 33,1% | **54,1%** |
| Không được báo (bộ hỗn hợp) | **1,2%** | **12,5%** |
| Chỉ chọn đúng 1 ô | 1,9% | 16,6% |
| Đáp án đúng **nằm trong** tập đã chọn | 56,9% | 71,7% |

4B rơi từ **54,1% xuống 12,5%** trên đúng những câu đó. Kiến thức vẫn còn — đáp án
đúng nằm trong tập nó chọn ở 71,7% số câu — nhưng nó không dừng lại được ở một ô.

Phân bố số ô model chọn trên 2.000 câu một đáp án:

```
0.6B :  1 ô →   39   2 ô → 1.940   3 ô → 11   4 ô → 10
4B   :  1 ô →  331   2 ô → 1.472   3 ô → 107  4 ô → 90
```

**0.6B chọn đúng 2 ô ở 97% số câu**, bất kể đáp án chuẩn có mấy ô.

---

## 3. Số ô chọn so với đáp án chuẩn, theo từng nhóm

Bộ hỗn hợp, cột "khớp số" = tỉ lệ câu model chọn đúng **số lượng** ô (chưa xét đúng ô nào).

| Nhóm | n | Chuẩn | 0.6B chọn | khớp số | 4B chọn | khớp số |
|---|---:|---:|---:|---:|---:|---:|
| file1 phủ định | 4.573 | 3,00 | 2,06 | 3,5% | 2,59 | 29,6% |
| file2 meta | 1.092 | 3,00 | 2,11 | 6,0% | 2,61 | 44,7% |
| file3 pool | 2.810 | 2,66 | 2,05 | 47,5% | 2,42 | 49,8% |
| file4 meta chữ cái | 893 | 2,36 | 2,06 | 62,8% | 2,33 | 62,3% |
| single 1 đáp án | 2.000 | 1,00 | 2,00 | 1,9% | 1,98 | 16,6% |

0.6B chọn 2,05–2,11 ô ở **mọi** nhóm, dù đáp án chuẩn dao động từ 1,00 đến 3,00 — nó
gần như mù hoàn toàn về số lượng. 4B có phản ứng theo nhóm (2,33–2,61) nhưng vẫn neo
quanh 2,5 và không xuống được 1 khi cần.

---

## 4. Độ phân biệt giữa hai model (bộ 9.368)

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai |
|---|---:|---:|---:|---:|
| Nhiều đáp án | 218 (2,3%) | **2.097 (22,4%)** | **119 (1,3%)** | 6.934 (74,0%) |
| Một đáp án | 2.501 (26,7%) | 2.721 (29,0%) | 1.300 (13,9%) | 2.846 (30,4%) |

Tín hiệu ròng: bộ nhiều đáp án **+89,3%** trên số câu mang thông tin, bộ một đáp án
chỉ **+35,3%**. Tỉ lệ câu nghịch đảo — dấu hiệu nhiễu — là **1,3%** so với 13,9%.

Bộ nhiều đáp án sạch hơn hẳn về mặt nhiễu, vì đoán mò không ăn được: xác suất trúng
khít một tập 3 ô trong 5 thấp hơn nhiều so với trúng 1 trong 4.

Điểm yếu còn lại: **74,0% số câu cả hai model đều sai**. Phần lớn bộ đề chưa phân loại
được gì ở dải năng lực này, cần model mạnh hơn mới biết trần nằm ở đâu.

---

## 5. Kết luận

**Về hai model.** 4B hơn 0.6B ở mọi bộ và mọi nhóm. Khoảng cách trên bộ nhiều đáp án
(24,7% so với 3,6%) rộng hơn hẳn trên bộ một đáp án (55,7% so với 40,6%).

**Về ba định dạng.**

| | Một đáp án | Nhiều đáp án | Hỗn hợp |
|---|---|---|---|
| Model vượt mốc mù? | ✓ chỉ 4B | ✓ chỉ 4B | ✓ chỉ 4B |
| Nhiễu khi phân biệt | 13,9% | **1,3%** | — |
| Đo được hiệu chỉnh số lượng | không | một phần | **có** |

Bộ hỗn hợp đo được thứ hai bộ kia không đo được: **khả năng tự quyết định chọn bao
nhiêu ô**. Đó là năng lực cả hai model đều thiếu nghiêm trọng — 4B mất 42 điểm phần
trăm trên cùng một tập câu hỏi chỉ vì không được báo trước số đáp án.

---

## Phụ lục — tái tạo

```bash
bash lambda/eval_v2.sh all
```
```powershell
python compare_benchmarks.py --multi results_v2/eval_multi_0.6b.json --single results_v2/eval_single_0.6b.json `
                             --multi results_v2/eval_multi_4b.json   --single results_v2/eval_single_4b.json `
                             --data processed_data_v2/final_benchmark_9368.json `
                             --single-data processed_data_v2/final_benchmark_9368_single.json `
                             --prov processed_data_v2/final_benchmark_9368_provenance.json
```
