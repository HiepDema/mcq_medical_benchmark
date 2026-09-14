# Thử nghiệm bộ đề ĐIỀN TỪ, gồm nhánh multi-hop

Câu hỏi cần trả lời: **có thể chuyển kho MCQ một đáp án thành bộ đề điền từ — kể cả dạng
điền nhiều ô nối chuỗi — mà vẫn giữ được bảo đảm "đáp án derive chứ không generate"?**

Kết luận ngắn: **dựng được, nhưng hai trong ba nhánh KHÔNG HỢP LỆ.** Không phải vì model
kém, mà vì bỏ bốn phương án đi thì thân câu không còn xác định được một đáp án duy nhất.
Riêng nhánh đáp án số liệu thì hợp lệ và dùng được.

---

## 1. Thiết kế, và vì sao nó đáng thử

Nhánh một ô lấy từ một câu MCQ; nhánh multi-hop lấy từ một cặp câu A → B trong đó đáp án
của A xuất hiện ở thân câu B:

```
(1) Nhánh bờ trái của động mạch vành xuất phát từ ___(1)___.
(2) ___(1)___ cánh tay trước và mũ cánh tay sau xuất phát từ động mạch là ___(2)___.

    (1) = Động mạch mũ        (2) = Động mạch nách
```

**Điểm đáng thử:** bản MCQ multi-hop trước đó chết vì phải thay thực thể cầu nối bằng một
cụm mô tả, và 52,8% cụm mô tả đó không định danh duy nhất (xem
[REPORT_MULTIHOP.md](REPORT_MULTIHOP.md)). Ở dạng điền từ thì **không phải thay gì cả** —
khoét trống cả hai thực thể, và ô (1) được nhắc lại tường minh ở câu thứ hai. Nguồn mơ hồ
lớn nhất của bản trước biến mất.

Ground truth vẫn **derive 100%**: đáp án mỗi ô chính là phương án đúng của câu gốc.
[v2/cloze_build.py](v2/cloze_build.py) thuần luật, không LLM nào tham gia.

---

## 2. Dựng đề

Từ 122.017 câu sạch, 79,9% thân câu chuyển được sang dạng khẳng định bằng luật (bóc đuôi
hỏi `là gì?` / `nào sau đây?` / `:` rồi nối chỗ trống vào).

| | Số câu |
|---|---:|
| Nhánh một ô, dùng được | 50.028 |
| **Phát hành (lấy mẫu)** | **8.000** |
| **Nhánh multi-hop** | **583** |
| **Nhánh số liệu** (lọc từ nhánh một ô) | **428** |

Hai nhánh không dùng chung câu gốc nào.

### Bộ lọc, mỗi cái sinh ra sau khi đọc output thật

- **Câu "chọn câu SAI"** — đáp án đúng của chúng là một mệnh đề **sai**; khoét trống ra sẽ
  tạo câu khẳng định điều sai. Đây là lỗi về tính đúng đắn, không phải văn phong. Loại hẳn.
- **Bệnh án lâm sàng** — dùng được cho nhánh một ô, nhưng nối chuỗi thì thành ghép bừa hai
  ca bệnh không liên quan. Loại khỏi nhánh 2.
- **Đáp án rác** còn sót ký hiệu phương án (`"B. S"`), câu Đúng/Sai, nhãn
  `Other(No Category)`.
- **Ngữ pháp** — không chèn thêm "là" khi thân câu đã kết thúc bằng giới từ
  (`"gặp ở là ___"`, `"là bao nhiêu là ___"`).

### Một phát hiện về dữ liệu

**0,6% kho đề lưu chữ có dấu ở dạng tổ hợp (NFD)** thay vì dựng sẵn (NFC). Hai chuỗi hiển
thị y hệt nhau nhưng khác byte — cùng một câu cho `len` 60 và 46. Mọi regex tiếng Việt đều
trượt trên chúng, và nhìn bằng mắt không phát hiện được.

Với bộ điền từ thì nghiêm trọng hơn nhiều: **đáp án đúng sẽ bị chấm là sai**. Đã chuẩn hoá
NFC lúc nạp (2.179 trường).

Bộ B của benchmark MCQ hiện tại có **89 câu (0,8%)** dính NFD. Không ảnh hưởng điểm MCQ vì
model chỉ xuất chữ cái, nhưng có thể đã làm sót một ít trùng lặp lúc dedup.

---

## 3. Chấm điểm

Chấm văn bản tự do tiếng Việt là chỗ khó nhất. **Không dùng LLM làm giám khảo** — làm vậy
là biến điểm số thành mức đồng thuận với model chấm, đúng vòng lặp mà cả dự án này tránh.
Thay vào đó ba thang minh bạch, báo cáo cả ba:

| | |
|---|---|
| **EM** | khớp tuyệt đối sau chuẩn hoá NFC, bỏ dấu câu, thường hoá |
| **F1** | độ phủ token kiểu SQuAD — điểm từng phần |
| **EM~** | như EM nhưng bỏ dấu tiếng Việt — đo riêng phần model mất dấu |

Và một chỉ số chẩn đoán, hoá ra là thứ quan trọng nhất của cả thử nghiệm:

> **TRÚNG NHIỄU** — câu trả lời khớp đúng một phương án **sai** của câu gốc. Đây là bằng
> chứng model sai *thật*, không phải lỗi chấm do đồng nghĩa. Khoảng cách giữa `1 − EM` và
> tỉ lệ trúng nhiễu cho biết thang EM đang khắt khe quá mức bao nhiêu.

Đã kiểm thang đo trước khi chạy: điền đáp án chuẩn → EM 100%; điền một phương án nhiễu →
EM 0,1% và bắt trúng nhiễu 100%, F1 có mức nền 27,4%.

---

## 4. Kết quả

Qwen3-8B, vLLM 0.29.0, A100-SXM4-40GB, greedy, thinking tắt.

| Nhánh | n | Trả lời được | EM | F1 | **Trúng nhiễu** | Kết luận |
|---|---:|---:|---:|---:|---:|---|
| Một ô | 300 | 94,7% | 3,9% | 17,7% | 1,8% | **không hợp lệ** |
| Multi-hop | 200 | 99,5% | 3,3% | 18,9% | 2,8% | **không hợp lệ** |
| Số liệu | 428 | 87,1% | 9,9% | 17,4% | **12,6%** | **hợp lệ** |

Nhánh multi-hop có 0,0% số câu đúng cả hai ô.

### Đọc bảng này theo cột "trúng nhiễu"

Ở **hai nhánh đầu**, trúng nhiễu (1,8% và 2,8%) **thấp hơn rất nhiều** so với phần EM báo
sai (96,1% và 96,7%). Model **không chọn phương án sai** — nó đưa đáp án **khác mà vẫn
đúng**. Bằng chứng trực tiếp từ output:

| Model trả lời | Đáp án chuẩn | |
|---|---|---|
| `phân tích nhiễm sắc thể` | `Nhiễm sắc đồ` | cùng một thứ |
| `vi khuẩn liên cầu tan huyết nhóm A` | `Streptocoque tan huyết beta nhóm A` | cùng một thứ |
| `chẹn kênh canxi` | `Ức chế giao cảm` | đều là nhóm thuốc hạ áp hợp lệ |
| `tiểu não` | `Đại não` | thân câu không đủ ràng buộc |

Ở **nhánh số liệu thì ngược lại**: trúng nhiễu (12,6%) **vượt** EM (9,9%), tức thang đo bắt
được lỗi thật. Kiểm tay các câu không khớp cũng cho thấy phần lớn là sai thật —
`8506` so với `13979`, `10%` so với `8%`, `40-60%` so với `80%`. **9,9% là điểm thật.**

### Phụ thuộc hai bước không đo được

| | |
|---|---|
| ô(1) đúng → ô(2) đúng | 0/9 |
| ô(1) sai → ô(2) đúng | 4/190 = 2,1% |

Cả hai đều gần 0 nên **không kết luận được** chuỗi có thực sự phụ thuộc nhau hay không.
Phép kiểm tính hợp lệ quan trọng nhất của nhánh multi-hop vì thế bỏ ngỏ — và sẽ còn bỏ ngỏ
chừng nào EM còn ở mức 3%.

---

## 5. Một lỗi kỹ thuật phải sửa giữa chừng

Ép JSON schema qua xgrammar sinh ra một bệnh lý: khi model "bí", ngữ pháp vẫn cho phép
khoảng trắng vô hạn nên nó xuất một dấu `{` rồi hàng trăm ký tự xuống dòng cho tới hết ngân
sách token, và JSON thu được không parse nổi.

**Hỏng 52% số câu ở nhánh một ô, 15% ở nhánh multi-hop.**

Đã thêm chế độ `--format text` (nay là mặc định): văn bản thuần, mỗi dòng một ô, trích bằng
regex. Ở đây đầu ra là văn bản tự do nên vốn không cần ngữ pháp.

**Tỉ lệ parse 48% → 95%.** Nếu không phát hiện chỗ này thì mọi con số ở trên đều sai lệch
nặng, nên ghi lại để lần sau không vấp lại.

---

## 6. Kết luận

**Nút thắt không nằm ở kỹ thuật dựng đề** — pipeline chạy tốt, ground truth vẫn derive
100%, và ý tưởng "điền từ né được điểm chết của MCQ multi-hop" là đúng về mặt thiết kế.

**Nút thắt nằm ở chỗ khác, và nó sâu hơn:** câu hỏi MCQ dựa vào bốn phương án để thu hẹp
nghĩa. *"Điều trị tăng huyết áp người ta sử dụng thuốc ___"* là mơ hồ, nhưng có bốn lựa
chọn cụ thể thì nó xác định. **Bỏ phương án đi chính là bỏ mất cái làm cho câu hỏi có một
đáp án duy nhất.** Điều này đúng với gần như toàn bộ bộ đề, không phải một phần nhỏ.

Đây cũng chính là nguyên nhân gốc đã giết bản MCQ multi-hop, chỉ xuất hiện dưới dạng khác.

### Khuyến nghị

**Bỏ nhánh một ô và nhánh multi-hop ở dạng hiện tại.** Sửa bằng cách cho thêm "ngân hàng
từ" thì lại thành trắc nghiệm, mất đúng cái mới.

**Giữ và mở rộng nhánh số liệu.** 428 câu hiện lọc từ 8.000 câu mẫu; mở ra cả 50.028 câu
dùng được sẽ cho khoảng **2.700 câu**, và kho gốc có 4.818 câu đáp án thuần số nên còn dư
địa. Bộ này **chấm sạch** và đo đúng thứ model hay bịa nhất trên lâm sàng — liều thuốc,
ngưỡng xét nghiệm, tỉ lệ.

Trước khi mở rộng cần lọc thêm chất lượng thân câu: vẫn còn câu hỏng như *"Có bao nhiêu đơn
vị phổi chính là ___"* (thừa "là") và đáp án gốc lỗi *"Ngoàiổphúc mạc"* (mất dấu cách).

**Với paper ICLR:** bộ MCQ nhiều đáp án vẫn là thứ nên nộp. Thử nghiệm này là một kết quả
âm tính có ích — nó cho thấy vì sao định dạng trắc nghiệm, dù bị chê là "cho không đáp án",
lại là thứ khiến bộ đề chấm được một cách rõ ràng.

---

## Phụ lục — tái tạo

```bash
python v2/cloze_build.py --single 8000          # dựng đề, thuần luật

# trên máy GPU
bash lambda/eval_cloze.sh                       # nhiều model một phiên
python v2/cloze_vllm.py --model Qwen/Qwen3-8B --dataset numeric --format text
```

Bộ đề (`processed_data_v2/final_cloze_*.json`) nằm trong `.gitignore` — tái tạo được từ
code. Kết quả chấm lưu ở `results_v2/cloze_*_t8b.json`.
