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

---

## 2. Bộ nhiều đáp án đo được năng lực, nhưng chỉ với model đủ lớn

Qwen3-4B đạt **28,7%** so với mốc mù **10,7%** — vượt **18%**.

Qwen3-0.6B đạt **2,0%**, thấp hơn cả mốc mù — nó thất bại hoàn toàn ở định dạng này.

| Nhóm | n | Mốc "chọn 3 ô đầu" | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|---:|---:|
| file1_ngoai_tru | 50 | 18,0% | 0,0% | 20,0% |
| file2_them_nhieu | 50 | 10,0% | 2,0% | **46,0%** |
| file3_tach_dau_phay | 50 | 4,0% | 4,0% | 20,0% |
| **Tổng** | 150 | 10,7% | 2,0% | **28,7%** |

4B vượt mốc ở cả ba nhóm. Nhóm `file2_them_nhieu` cao nhất (46,0%).

---

## 3. Năng lực bị thiếu là hiệu chỉnh SỐ LƯỢNG đáp án

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

## 4. Độ phân biệt giữa hai model

Phân loại từng câu theo việc model mạnh/yếu làm được hay không:

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai |
|---|---:|---:|---:|---:|
| Bộ nhiều đáp án | 1 | **42** | **2** | 105 |
| Bộ một đáp án | 54 | 32 | 19 | 45 |

Bộ nhiều đáp án phân biệt gần như sạch hoàn toàn: 42 câu tách được hai model, chỉ
2 câu theo chiều nghịch đảo. Bộ một đáp án có 19 câu nghịch đảo — nhiễu từ việc
đoán trúng 1 trong 4.

Điểm yếu còn lại của bộ nhiều đáp án: **70,0% số câu cả hai model đều sai**. Phần
lớn bộ đề vẫn chưa phân loại được gì ở dải năng lực này, cần model mạnh hơn mới
biết trần nằm ở đâu.

---

## 5. Kết luận

**Về hai model.** Qwen3-4B vượt 0.6B trên cả hai bộ và ở mọi nhóm con. Khoảng cách trên bộ nhiều đáp án rất rõ
(28,7% so với 2,0%), cho thấy định dạng này phân tách năng lực tốt hơn.

**Về hai benchmark.**

| | Bộ một đáp án | Bộ nhiều đáp án |
|---|---|---|
| Model vượt mốc mù? | ✓ cả hai | ✓ chỉ 4B |
| Nhiễu khi phân biệt | 19 câu nghịch đảo | **2 câu** |
| Câu cả hai model đều sai | 30,0% | 70,0% |

Bộ nhiều đáp án sạch hơn về mặt artifact và phân biệt gần như không nhiễu, nhưng
còn quá khó.

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
