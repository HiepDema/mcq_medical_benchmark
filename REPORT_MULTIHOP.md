# Thử nghiệm multi-hop: dựng câu hỏi hai bước từ kho đề MCQ

Câu hỏi cần trả lời: **có thể dựng một bộ đề multi-hop tiếng Việt y khoa từ chính kho đề
MCQ một đáp án hay không, mà vẫn giữ được bảo đảm "đáp án được derive chứ không generate"
như bộ đề đa đáp án hiện tại?**

Kết luận ngắn: **kỹ thuật chạy được, chất lượng chưa đủ.** Từ 122.017 câu nguồn lọc ra
4.167 ứng viên, nhưng chỉ khoảng **18% sống sót** tới mức dùng được. Nút thắt không nằm ở
chỗ mình dự đoán.

---

## 1. Ý tưởng

Hai câu hỏi độc lập nối được thành một câu multi-hop khi **đáp án của câu A xuất hiện làm
chủ đề trong thân câu B**:

```
A: "Biến chứng nguy hiểm nhất của đặt dụng cụ tử cung tránh thai là?"   -> Thủng tử cung
B: "Thủng tử cung hay gặp nhất trong trường hợp nào?"                    -> Chửa trứng xâm nhập

=> "Biến chứng nguy hiểm nhất của đặt dụng cụ tử cung tránh thai
    hay gặp nhất trong trường hợp nào?"                                  -> Chửa trứng xâm nhập
```

**Điểm mấu chốt về phương pháp:** câu ghép **giữ nguyên toàn bộ bốn phương án và đáp án
của câu B**. Chỉ thân câu đổi. Nên đáp án vẫn derive từ đáp án gốc của B, và LLM chỉ viết
lại cách diễn đạt — đúng vai trò nó đang đóng trong pipeline MCQ hiện tại (viết lại thân
câu phủ định, viết nhiễu), không bao giờ quyết định đáp án.

Đây là lý do hướng này đáng thử: nó **không phá vỡ luận điểm trung tâm** của bộ đề đang có.

---

## 2. Nối câu không phải chỗ khó

Nhận định ban đầu của tôi sai và cần ghi lại. Tôi cho rằng phải dùng LLM để rút thực thể,
dựa trên phép đo rút từ khoá theo tần suất — cách đó cho ra toàn `chất`, `dùng`, `quan`,
`những`, không có thực thể y khoa nào.

Đo đúng cách — tìm xem đáp án của A có xuất hiện trong thân câu nào khác không — thì nối
được bằng **luật thuần tuý**:

| | Số câu |
|---|---:|
| Câu có đáp án 2–4 từ, không phải meta | 35.799 |
| Trong đó đáp án xuất hiện ở thân câu khác | **18.524 (51,7%)** |

Vấn đề nằm ở **độ mơ hồ của liên kết**:

| Đáp án của A khớp bao nhiêu thân câu B | Số câu | |
|---|---:|---:|
| **đúng 1 câu** | 2.720 | 14,7% |
| 2–3 câu | 2.933 | 15,8% |
| 4–10 câu | 3.974 | 21,5% |
| 11–100 câu | 6.490 | 35,0% |
| trên 100 câu | 2.407 | 13,0% |

Nửa dưới là nhiễu: `'bệnh nhân'` khớp 5.271 thân câu, `'điều trị'` khớp 5.198. Đây là cụm
danh từ chung chứ không phải thực thể.

---

## 3. Pipeline bốn bước

| Bước | Script | Vai trò |
|---|---|---|
| 1 | [v2/multihop_mine.py](v2/multihop_mine.py) | Khai thác chuỗi bằng luật, không gọi LLM |
| 2 | [v2/multihop_rewrite.py](v2/multihop_rewrite.py) | LLM viết lại thân câu, được phép **từ chối** |
| 3 | [v2/multihop_check.py](v2/multihop_check.py) | Thẩm định nghiêm ngặt, chạy offline |
| 4 | [v2/multihop_judge.py](v2/multihop_judge.py) | Giám khảo LLM bắt lỗi ngữ nghĩa |

Mỗi bộ lọc ở bước 1 đều sinh ra **sau khi đọc output và thấy một lỗi cụ thể**, không phải
phòng xa:

- **Bỏ bệnh án lâm sàng** — thân câu A kiểu *"Bệnh nhân nam 45 tuổi, tiền căn tăng huyết
  áp…"* không rút thành cụm danh từ định danh được. Ghép ra câu vô nghĩa.
- **Bỏ câu Đúng/Sai** — đáp án `"Đúng"` không phải thực thể.
- **Bỏ nhãn `Other(No Category)`** — xem mục 6.
- **Giữ phủ định** — xem mục 5, đây là lỗi nguy hiểm nhất.

Hiệu ứng của bộ lọc: 7.119 → 5.261 → **4.167** ứng viên.

---

## 4. Phễu kết quả

| Bước | Còn lại | Tỉ lệ qua |
|---|---:|---:|
| Ứng viên khai thác bằng luật | 4.167 | — |
| LLM viết lại thân câu | 3.649 | 87,6% |
| Thẩm định nghiêm ngặt (offline) | 3.427 | 82,2% |
| **Giám khảo LLM** | — | **43,8%** |
| **Suy ra còn dùng được** | **~1.500** | **36,0%** |

Trong 4.167 ứng viên có **1.166 liên kết 1-1** và 2.438 câu B khác nhau.

Lý do bị loại ở bước 3 (thẩm định offline):

| Lý do | Số câu |
|---|---:|
| Không còn là câu hỏi | 361 |
| Đáp án lộ trong câu hỏi | 199 |
| Lộ cụm cầu nối (chuỗi sụp về 1 bước) | 115 |
| Mất phủ định của câu A | 74 |
| Không mang thông tin của A | 43 |
| Mất phủ định của câu B | 16 |
| LLM tự từ chối | 5 |
| Giống hệt câu B | 3 |

### Một cảnh báo về con số 43,8%

Vòng giám khảo gửi đi 2.500 chuỗi thì **661 chuỗi lỗi API do hết credit giữa chừng**. Con
số 43,8% tính trên **1.839 chuỗi thực sự có phán quyết**, không phải trên 2.500.

Nếu tính 661 chuỗi đó thành "bị loại" thì ra 32,2% — **sai**, vì chúng không được chấm chứ
không phải bị từ chối. Đây đúng cái bẫy đã gặp ở lượt chấm DeepSeek trước đây và ở lượt
Claude-Sonnet-5 (1.764 câu HTTP 403).

---

## 5. Giám khảo bắt được gì — và phát hiện chính

| Lý do loại | Tỉ lệ trên số có phán quyết |
|---|---:|
| **Mô tả không định danh duy nhất** | **52,8%** |
| Hop collapse | 17,7% |
| Không trôi chảy | 8,6% |

**Lỗi lớn nhất không phải hop collapse như tôi dự đoán, mà là mô tả ở bước 1 ứng với nhiều
thực thể.**

Đây là vấn đề gốc rễ, và nó giải thích tại sao hướng này khó: **thân câu MCQ không được
viết để làm mô tả định danh**. Câu hỏi gốc dựa vào bốn phương án để thu hẹp nghĩa — *"thuốc
điều trị tăng huyết áp"* là mơ hồ, nhưng khi có bốn lựa chọn cụ thể thì nó xác định. Bỏ
phương án đi để biến thân câu thành cụm mô tả là **bỏ mất chính cái chỗ dựa đó**.

Hai lỗi còn lại, cùng ví dụ thật từ output:

**Hop collapse** — câu ghép trả lời được mà không cần bước 1:

> *"Tiền thân của Bệnh viện Quân y 103 được thành lập tại đâu?"*
> Không đòi hỏi biết tiền thân đó là "Đội điều trị 3".

**Đảo phủ định** — lỗi nguy hiểm nhất vì nó làm câu hỏi **sai về y khoa** chứ không chỉ xấu
về văn phong:

> Bước 1: *"Biến chứng nào **KHÔNG** là biến chứng muộn của băng huyết sau đẻ?"* → Dính
> buồng tử cung — tức nó **không phải** biến chứng muộn.
> Câu ghép: *"**Biến chứng muộn nào** của băng huyết sau đẻ có thể đưa đến hậu quả nào?"*
> — khẳng định điều ngược lại.

Lỗi này giờ bị luật ở bước 3 chặn (74 + 16 = 90 chuỗi).

---

## 6. Phát hiện phụ: kho đề không thuần y khoa

Đọc mẫu phát hiện trong kho có cả **chứng khoán** (*"cổ phiếu quỹ"*), **luật hành chính**
(*"mặt khách quan của vi phạm pháp luật"*), **tin học** (*"phần mềm Dev C++"*), **hoá đại
cương** (*"liên kết ion trong NaCl"*), **tâm lý học**.

6/8 câu phi y khoa tìm thấy đều mang nhãn `medicalTopic = "Other(No Category)"` (901 câu
trong tập ứng viên), nên lọc nhãn đó là đủ.

**Điều này ảnh hưởng cả bộ MCQ đa đáp án hiện tại** và đáng kiểm riêng — bộ đề đang được mô
tả là "y khoa" trong paper.

---

## 7. Đọc tay: 43,8% vẫn là con số lạc quan

Đọc 12 mẫu ngẫu nhiên trong nhóm **đã qua cả bốn bước**, khoảng **một nửa vẫn hỏng**:

- Câu hỏi đọc hình mà không có hình: *"Chi tiết nào trong hình là hệ tĩnh mạch chủ?"*
- Đáp án là ký tự lẻ: `"Đ"`
- Ghép hai bệnh lý không liên quan: *"phim chẩn đoán gãy Pouteau–Colles… tốt nhất trong gãy
  xương hàm dưới"*
- Không còn là câu hỏi, chỉ là một mệnh đề

**Ước tính thật: ~18% của 4.167, tức khoảng 750 chuỗi dùng được**, và mỗi chuỗi vẫn cần
người đọc duyệt.

---

## 8. Chi phí

| Việc | $ |
|---|---:|
| Thử 60 + 80 chuỗi (hai lượt hiệu chỉnh bộ lọc) | 0,05 |
| Viết lại 4.167 chuỗi | 1,59 |
| Giám khảo 2.500 chuỗi (1.839 có phán quyết) | 0,91 |
| **Tổng** | **2,55** |

Model: `google/gemini-2.5-flash`, reasoning tắt, đầu ra ép JSON schema. Vòng viết lại chạy
229 giây ở concurrency 32; vòng giám khảo 337 giây.

Ước tính chi phí của tôi sai: dự $0,00020/chuỗi cho vòng giám khảo, thực tế **gấp đôi** —
đó là lý do hết tiền giữa chừng. Bộ chặn ngân sách trong `multihop_judge.py` đã hoạt động
đúng ở lần gọi đầu (từ chối chạy 3.427 chuỗi vì không đủ), nhưng ngưỡng dựa trên ước tính
sai nên lần thứ hai vẫn tràn.

---

## 9. Kết luận

**Nút thắt không nằm ở kỹ thuật.** Việc nối câu — thứ tôi từng cho là khó nhất — chạy tốt
bằng luật thuần tuý. Việc giữ bảo đảm derive cũng làm được: đáp án luôn là đáp án gốc của
câu B.

**Nút thắt nằm ở nguồn dữ liệu.** Thân câu MCQ dựa vào bốn phương án để xác định nghĩa; khi
bị biến thành cụm mô tả độc lập thì hơn một nửa trở nên mơ hồ. Đây là hạn chế của định dạng
đề gốc, không phải của phương pháp.

### Điều kiện để hướng này sống

Phải đổi tiêu chí chọn câu A: chỉ lấy những câu mà **đáp án là định nghĩa đảo ngược được** —
tên hội chứng, tên thuốc cụ thể, tên cấu trúc giải phẫu — thay vì câu "chọn phương án tốt
nhất". Nhóm đó nhỏ hơn nhiều, có lẽ vài trăm chuỗi.

### Khuyến nghị

Multi-hop là **hướng nghiên cứu riêng, chưa đủ chín để thành bộ đề**. Bộ MCQ đa đáp án hiện
tại — 11.368 câu, 9 model, phát hiện về hiệu chỉnh số lượng đáp án — vẫn là thứ nên đưa vào
paper ICLR.

Nếu quay lại hướng này, thứ tự việc nên làm:

1. Lọc câu A theo tiêu chí "đáp án đảo ngược được" (rẻ, làm bằng luật, đo ngay được)
2. Thẩm định tay 100 chuỗi để có con số chuẩn thay cho ước lượng 18%
3. Chỉ khi tỉ lệ vượt 60% thì mới mở rộng quy mô

---

## Phụ lục — tái tạo

```bash
python v2/multihop_mine.py                       # luật, không tốn tiền
python v2/multihop_rewrite.py --limit 5000 --concurrency 32
python v2/multihop_check.py                      # offline, không tốn tiền
python v2/multihop_judge.py --concurrency 32 --limit 2500 --min-credit 0.15
```

File trung gian (`data_v2/multihop_*.json`) nằm trong `.gitignore` — tái tạo được từ code.
