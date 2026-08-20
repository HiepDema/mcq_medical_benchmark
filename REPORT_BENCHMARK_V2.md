# Hai bộ benchmark MCQ y khoa v2 và kết quả chấm Qwen3

Tài liệu này mô tả **hai bộ benchmark** sinh từ 17 bộ đề trắc nghiệm y khoa một đáp án,
và **kết quả chấm hai model** trên chúng. Quá trình dựng dữ liệu chi tiết nằm ở
[REPORT_V2.md](REPORT_V2.md).

| | Bộ A — nhiều đáp án | Bộ B — hỗn hợp |
|---|---|---|
| File | `final_benchmark_9368.json` | `final_benchmark_mixed.json` |
| Số câu | **9.368** | **11.368** |
| Thành phần | 100% câu nhiều đáp án | 9.368 nhiều đáp án + 2.000 một đáp án |
| Bản đối chứng | `final_benchmark_9368_single.json` | `final_benchmark_mixed_single.json` |
| Đo được điều gì | model có tìm đúng tập đáp án không | thêm: model có tự biết **chọn mấy ô** không |

Mỗi bộ đi kèm một bản đối chứng **một đáp án khớp 1:1 theo chỉ số**: bản ghi thứ *i* của
bản đối chứng là câu gốc nguyên văn của bản ghi thứ *i* trong benchmark. Nhờ vậy mọi
chênh lệch điểm giữa hai bên quy về **định dạng câu hỏi**, không phải do bộ này khó hơn
bộ kia.

---

## 1. Nguồn gốc

```
17 file, 160.194 câu  ->  122.017 sau khử trùng lặp toàn cục
                      ->    9.779 ứng viên qua lọc cơ học
                      ->    9.368 dựng được sau khi LLM phán xét
```

Gần một phần tư số câu nguồn là trùng lặp (30.913 câu) — các bộ đề là những bản export
chồng lấn của cùng một ngân hàng câu hỏi.

Bốn cách biến đổi, mỗi câu chỉ vào đúng một họ:

| Họ | Từ dạng câu gốc | Thành | n |
|---|---|---|---:|
| `file1_ngoai_tru` | `"... NGOẠI TRỪ:"`, `"câu nào SAI"` | đảo nhãn: 3 phương án còn lại đều đúng | 4.573 |
| `file3_tach_dau_phay` | mọi phương án là danh sách ngăn bởi dấu phẩy | gộp các mục thành phương án độc lập | 2.810 |
| `file2_them_nhieu` | đáp án đúng là `"Tất cả đều đúng"` | xoá meta, LLM viết thêm 2 nhiễu | 1.092 |
| `file4_ca_ab` | đáp án đúng là `"Cả A và B đều đúng"` | đáp án suy từ chữ cái, LLM thêm nhiễu | 893 |

**Đáp án đúng luôn suy ra từ trường `correctAnswer` của đề gốc.** LLM chỉ được phán xét
ứng viên, viết lại phần dẫn, và viết văn bản phương án nhiễu — không bao giờ được tự
quyết định đâu là đáp án đúng. Nếu để model tự chọn đáp án thì benchmark chỉ đo được độ
giống nhau giữa model sinh dữ liệu và model bị chấm.

2.000 câu một đáp án của Bộ B lấy nguyên văn từ kho nguồn, chống trùng ba tầng — theo mã
định danh, theo cặp `(file nguồn, chỉ số)`, và theo gần trùng thân câu
(`SequenceMatcher > 0,90`) — rải đều 117–118 câu mỗi file trên cả 17 file.

---

## 2. Thành phần hai bộ

| | Bộ A (9.368) | Bộ B (11.368) |
|---|---|---|
| Số phương án | 4 → 5.179 · 5 → 4.189 | 4 → 7.179 · 5 → 4.189 |
| TB số phương án | 4,45 | 4,37 |
| Số đáp án đúng | 2 → 1.901 · 3 → 7.102 · 4 → 365 | **1 → 2.000** · 2 → 1.901 · 3 → 7.102 · 4 → 365 |
| TB số đáp án đúng | 2,84 | 2,51 |
| Vị trí phương án SAI | A 3.332 · B 3.219 · C 3.359 · D 3.325 | — |
| Câu mọi phương án đều đúng | 0 | 0 |
| Trải trên 17 file nguồn | 117–1.153 câu/file | 235–1.271 câu/file |

Chủ đề chính của Bộ B: General Medicine 2.068 · Other 1.881 · Infectious Diseases 1.245
· Obstetrics and Gynecology 1.193 · Preventive Healthcare 1.093.

**Xáo trộn hai lần**: vị trí phương án trong từng câu trộn theo seed lấy từ mã định danh
câu hỏi, và thứ tự câu hỏi trong file trộn theo seed cố định. Chạy lại luôn ra cùng kết
quả. Nhờ đó vị trí phương án sai phân bố đều A/B/C/D — không có rò rỉ vị trí.

### Vị trí đáp án trong hai bản đối chứng

Hai bản đối chứng một đáp án **lệch nặng về D**: 41,5% số câu của bản A và 37,8% của
bản B có đáp án nằm ở phương án D. Nguyên nhân cấu trúc: `"Tất cả đều đúng"` và
`"Cả A và B đều đúng"` gần như luôn là phương án cuối trong đề gốc, mà hai họ
`file2`/`file4` chọn đúng những câu có đáp án là phương án meta. Không tránh được nếu
vẫn giữ câu gốc nguyên văn.

Hệ quả: điểm tổng trên hai bản đối chứng bị thổi phồng, so sánh theo từng cặp câu mới
hợp lệ. Bản thân hai benchmark **không** dính lỗi này — phương án đã được trộn hai lần.

---

## 3. Kết quả chấm

| | |
|---|---|
| Model | `Qwen/Qwen3-0.6B` · `Qwen/Qwen3-4B` (text-only) |
| Hạ tầng | 1×A10 24 GB, vLLM 0.27.1, structured outputs, `enable_thinking=False` |
| Thời gian | 8 lượt, 20 phút (0.6B ~241 câu/s · 4B ~40 câu/s) |
| Kết quả thô | [results_v2/](results_v2/) · lệnh `bash lambda/eval_v2.sh all` |

### 3.1 Bảng điểm (exact match)

| Bộ | n | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|---:|
| **Bộ A** — nhiều đáp án | 9.368 | 3,6% | **24,7%** |
| **Bộ B** — hỗn hợp | 11.368 | 3,3% | **21,2%** |
| Đối chứng của A | 9.368 | 40,6% | **55,7%** |
| Đối chứng của B | 11.368 | 39,5% | **55,5%** |

Hai điều đọc ra ngay:

- **0.6B thất bại hoàn toàn ở định dạng nhiều đáp án** — 3,6% và 3,3%, tức là hầu như
  không câu nào nó trả lời khít tập đáp án.
- **Điểm ~40% của 0.6B ở định dạng một đáp án không phản ánh kiến thức**: nó thấp hơn
  tỉ lệ câu có đáp án nằm ở D của chính bản đối chứng đó (41,5%), tức là chọn D cho mọi
  câu còn ra kết quả cao hơn.

### 3.2 Điểm theo từng họ câu hỏi

| Nhóm | n | 0.6B (Bộ A) | 4B (Bộ A) | 0.6B (Bộ B) | 4B (Bộ B) |
|---|---:|---:|---:|---:|---:|
| file1_ngoai_tru | 4.573 | 1,0% | 22,7% | 1,3% | 20,2% |
| file2_them_nhieu | 1.092 | 3,2% | **41,9%** | 2,3% | 38,7% |
| file3_tach_dau_phay | 2.810 | 5,9% | 17,0% | 5,8% | 16,9% |
| file4_ca_ab | 893 | 10,1% | 38,5% | 11,9% | 38,2% |
| single_1_dap_an | 2.000 | — | — | 1,2% | 12,5% |

Điểm của bốn họ gần như không đổi giữa hai bộ — trộn thêm câu một đáp án không làm nhiễu
phần còn lại. Nhóm khó nhất với 4B là `file3` (17%), dễ nhất là `file2` (42%).

### 3.3 Phát hiện chính: model không biết phải chọn mấy ô

Bộ B được dựng để đo đúng điều này. Trên **cùng 2.000 câu một đáp án**, chỉ khác ở chỗ
model có được báo trước số đáp án hay không:

| | Qwen3-0.6B | Qwen3-4B |
|---|---:|---:|
| Được báo "đúng 1 đáp án" | 33,1% | **54,1%** |
| Không được báo (Bộ B) | **1,2%** | **12,5%** |
| Chỉ chọn đúng 1 ô | 1,9% | 16,6% |
| Đáp án đúng **nằm trong** tập đã chọn | 56,9% | 71,7% |

4B rơi **42 điểm phần trăm** trên đúng những câu đó. Kiến thức vẫn còn — đáp án đúng nằm
trong tập nó chọn ở 71,7% số câu — nhưng nó không dừng lại được ở một ô.

Phân bố số ô model chọn trên 2.000 câu một đáp án:

```
0.6B :  1 ô →   39   2 ô → 1.940   3 ô → 11   4 ô → 10
4B   :  1 ô →  331   2 ô → 1.472   3 ô → 107  4 ô → 90
```

Số ô model chọn so với đáp án chuẩn, theo từng nhóm. Cột "khớp số" là tỉ lệ câu model
chọn đúng **số lượng** ô, chưa xét đúng ô nào:

| Nhóm | Chuẩn | 0.6B chọn | khớp số | 4B chọn | khớp số |
|---|---:|---:|---:|---:|---:|
| file1_ngoai_tru | 3,00 | 2,06 | 3,5% | 2,59 | 29,6% |
| file2_them_nhieu | 3,00 | 2,11 | 6,0% | 2,61 | 44,7% |
| file3_tach_dau_phay | 2,66 | 2,05 | 47,5% | 2,42 | 49,8% |
| file4_ca_ab | 2,36 | 2,06 | 62,8% | 2,33 | 62,3% |
| single_1_dap_an | 1,00 | 2,00 | 1,9% | 1,98 | 16,6% |

**0.6B chọn 2,05–2,11 ô ở mọi nhóm**, dù đáp án chuẩn dao động từ 1,00 đến 3,00 — nó gần
như mù hoàn toàn về số lượng. 4B có phản ứng theo nhóm (2,33–2,61) nhưng vẫn neo quanh
2,5 và không xuống được 1 khi cần.

### 3.4 Độ phân biệt giữa hai model

Phân loại từng câu theo việc model mạnh/yếu làm được hay không:

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai |
|---|---:|---:|---:|---:|
| Bộ A nhiều đáp án | 218 (2,3%) | **2.097 (22,4%)** | **119 (1,3%)** | 6.934 (74,0%) |
| Bản đối chứng 1 đáp án | 2.501 (26,7%) | 2.721 (29,0%) | 1.300 (13,9%) | 2.846 (30,4%) |

Tỉ lệ câu nghịch đảo — model yếu đúng trong khi model mạnh sai, tức dấu hiệu nhiễu —
là **1,3%** ở bộ nhiều đáp án so với **13,9%** ở bộ một đáp án.

Bộ nhiều đáp án sạch hơn hẳn vì đoán mò không ăn được: trúng khít một tập 3 ô trong 5
khó hơn nhiều so với trúng 1 trong 4.

**Bộ B** cho bức tranh gần như y hệt — thêm 2.000 câu một đáp án không làm bẩn tín hiệu:

| | Cả hai đúng | **Mạnh ✓ / Yếu ✗** | Yếu ✓ / Mạnh ✗ | Cả hai sai |
|---|---:|---:|---:|---:|
| **Tổng Bộ B** | 237 (2,1%) | **2.176 (19,1%)** | **141 (1,2%)** | 8.814 (77,5%) |
| ├─ 9.368 câu nhiều đáp án | 224 (2,4%) | 1.939 (20,7%) | 130 (1,4%) | 7.075 (75,5%) |
| └─ 2.000 câu một đáp án | 13 (0,7%) | 237 (11,8%) | **11 (0,6%)** | 1.739 (87,0%) |
| *(bản đối chứng 1 đáp án)* | 2.969 (26,1%) | 3.341 (29,4%) | 1.520 (13,4%) | 3.538 (31,1%) |

Điều đáng chú ý ở dòng cuối cùng của phần benchmark: **2.000 câu một đáp án có tỉ lệ
nghịch đảo thấp nhất — chỉ 11 câu trên 2.000 (0,6%)**. Đúng những câu đó, khi được báo
trước là chỉ có một đáp án (bản đối chứng), lại rơi vào vùng nhiễu 13,4%.

Cùng một câu hỏi, cùng hai model: hỏi theo kiểu "chọn một trong bốn" thì 13,4% khác biệt
giữa hai model là ăn may; hỏi mà không nói trước số đáp án thì chỉ còn 0,6%. Đoán mò
không còn ăn được, nên mọi khác biệt quan sát được đều là năng lực thật.

Đổi lại, **87,0% số câu một đáp án cả hai model đều sai** — nhóm này gần như chưa phân
loại được gì ở dải năng lực 0.6B–4B.

---

## 4. Kết luận

**Về hai model.** 4B hơn 0.6B ở mọi bộ và mọi nhóm. Khoảng cách trên định dạng nhiều đáp
án (24,7% so với 3,6%) rộng hơn hẳn trên định dạng một đáp án (55,7% so với 40,6%), mà
phần lớn điểm của 0.6B ở định dạng sau lại là ăn may theo vị trí D.

Bộ B đo được thứ Bộ A không đo được: **khả năng tự quyết định chọn bao nhiêu ô**. Đó là
năng lực cả hai model đều thiếu nghiêm trọng, và là chỗ khác biệt lớn nhất giữa 0.6B và
4B khi tính theo mức độ hụt.

**Giới hạn còn lại.** 74,0% số câu cả hai model đều sai — phần lớn bộ đề chưa phân loại
được gì ở dải năng lực này. Cần chấm thêm model mạnh hơn mới biết trần nằm ở đâu, và mới
biết bao nhiêu phần trong 74% đó là do câu quá khó, bao nhiêu là do đáp án chuẩn của đề
nguồn sai.
