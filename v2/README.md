# Pipeline v2 — dựng benchmark MCQ nhiều đáp án từ nhiều bộ đề 1 đáp án

Cùng logic biến đổi với pipeline v1 (`pyline/`), khác ở ba chỗ:

| | v1 | v2 |
|---|---|---|
| Nguồn | 1 file (`raw_data.json`) | N file trong `source_data/` |
| Khử trùng lặp | trong 1 file | **toàn bộ N file gộp lại** |
| Vai trò LLM | lọc ứng viên file 3 | lọc + **sinh nhiễu** + **thẩm định lại toàn bộ** |
| Chạy GPU | tự bật/tắt Lambda | thủ công, qua file `.jsonl` |

Nguyên tắc không đổi: **đáp án đúng luôn suy ra từ trường `correctAnswer` của đề
gốc**. LLM chỉ được phán xét ứng viên và viết văn bản nhiễu, không bao giờ được
tự đặt đâu là đáp án đúng — nếu để nó làm việc đó thì benchmark chỉ còn đo được
độ giống nhau giữa hai model.

---

## 0. Chuẩn bị nguồn

Bỏ file MCQ 1 đáp án vào `source_data/`:

```powershell
copy D:\bo_de_moi\*.json source_data\
```

Khi `source_data/` có file thì đó là **nguồn duy nhất** — mọi file JSON ở gốc repo
bị bỏ qua. Thư mục trống thì mới quay về lấy `raw_data.json` + `PIPELINE_*.json`
ở gốc. Tên file phải duy nhất (là khoá truy ngược bản ghi gốc). Không tầng nào
ghi đè file nguồn.

Thêm file mới thì chạy lại:

```powershell
python v2/run.py ingest route jobs
```

Kết quả GPU cũ **không mất**: id của mỗi việc là `uid` của câu hỏi, nên
`gpu/vllm_batch.py` bỏ qua các câu đã có trong `*.out.jsonl` và chỉ chạy phần
mới. Cứ để nguyên các file `.out.jsonl` ở `llm_jobs/`.

Định dạng mỗi file: mảng JSON các bản ghi
`{question, answer_optionA..E, correctAnswer: "optionX", questionID, medicalTopic, difficultLevel, regularFormat}`.

---

## 1. Các bước không cần GPU

```powershell
python v2/run.py ingest      # nạp + làm sạch + khử trùng lặp toàn cục
python v2/run.py route       # phân 3 họ + lọc cơ học + khử gần-trùng
python v2/run.py jobs        # -> llm_jobs/r1_*.jsonl  (+ --limit N để giới hạn)
```

Bốn họ câu hỏi:

- **file1 — phủ định**: `"... NGOẠI TRỪ:"`, `"câu nào SAI"` → 3 phương án còn lại đều đúng.
- **file2 — meta**: đáp án đúng là `"Tất cả đều đúng"` → 3 phương án còn lại đều
  đúng, **cần LLM sinh thêm phương án nhiễu** thì mới thành câu hỏi có nghĩa.
- **file3 — pool**: mọi phương án đều là danh sách ngăn bởi dấu phẩy → gộp các
  mục thành danh sách phương án độc lập.
- **file4 — meta chữ cái**: đáp án đúng là `"Cả A và B đều đúng"` → tập đáp án
  suy thẳng từ chữ cái, các phương án còn lại là nhiễu **có sẵn trong đề gốc**;
  LLM viết thêm cho đủ số phương án.

---

## 2. Chạy LLM vòng 1 (trên H100)

```bash
python3 -m venv ~/venv && ~/venv/bin/pip install -U pip vllm
export PATH=$HOME/venv/bin:$PATH               # xem mục lỗi môi trường bên dưới
python gpu/vllm_batch.py llm_jobs/r1_negation.jsonl llm_jobs/r1_distract.jsonl \
    llm_jobs/r1_pool.jsonl llm_jobs/r1_distract_letters.jsonl \
    --model Qwen/Qwen3-32B-FP8 --chunk 2048
```

Copy 4 file `*.out.jsonl` về `llm_jobs/`.

Xem thử prompt trước khi tốn GPU: `python gpu/vllm_batch.py llm_jobs/r1_pool.jsonl --dry-run`.
Script chạy lại được sau khi đứt — id nào đã có trong `.out.jsonl` thì bỏ qua.

---

## 3. Dựng 3 file + chạy LLM vòng 2

```powershell
python v2/run.py apply       # -> processed_data_v2/final_0{1,2,3,4}_*.json
                             # -> llm_jobs/r2_audit.jsonl
```

Vòng 2 là bước thẩm định **đồng nhất cho cả bốn họ**: đưa lại câu hỏi đã dựng
xong kèm nhãn đúng/sai hiện tại, hỏi model có phương án nào bị gán nhãn ngược
hay không. Đây là bộ lọc duy nhất bắt được lỗi **ngữ nghĩa** — lọc cơ học không
bao giờ biết "xì dầu" thực ra là thực phẩm nhiều muối, hay "bại liệt" thực ra
lây qua đường phân–miệng.

```bash
~/venv/bin/python gpu/vllm_batch.py llm_jobs/r2_audit.jsonl --model Qwen/Qwen3-32B-FP8
```

---

## 4. Xuất benchmark

```powershell
python v2/run.py build                    # lấy hết cả 4 họ, không cân bằng
python v2/run.py build --per-subset 500   # hoặc giới hạn mỗi họ 500 câu
```

Ra 4 file trong `processed_data_v2/`:

| File | Nội dung |
|---|---|
| `final_benchmark.json` | **bộ nhiều đáp án, gộp cả 4 họ**, đã trộn |
| `final_benchmark_single.json` | **đúng các câu gốc đó**, nguyên văn, khớp 1:1 theo chỉ số |
| `final_benchmark_*_provenance.json` | nguồn gốc từng câu: file nguồn, chỉ số, nhóm, cờ chất lượng |

Khớp 1:1 để mọi chênh lệch điểm giữa hai bộ quy về **định dạng**, không phải do
bộ này khó hơn bộ kia.

Chấm điểm dùng lại script cũ:

```powershell
python eval_qwen3vl.py --data processed_data_v2/final_benchmark.json `
                       --provenance processed_data_v2/final_benchmark_provenance.json `
                       --baselines-only
```

---

## 5. Chạy thử khi chưa có GPU

```powershell
python v2/run.py ingest route jobs
python v2/run.py apply --no-llm
python v2/run.py build --skip-audit
```

Vẫn ra benchmark, nhưng **chỉ có file1 và file3**: file2 và file4 bắt buộc cần
phương án nhiễu do LLM viết mới thành câu hỏi hợp lệ (file2 rơi hết vào nhóm
`file2_xoa_meta` để riêng, file4 bị loại vì không đủ 4 phương án). file3 cũng
không được thẩm định chuyên môn — các bản ghi mang cờ `qualityFlag: "rule-only"`
đúng với thực tế đó.

---

## 6. Chọn model cho 1×H100 80GB

Việc cần làm: đọc hiểu tiếng Việt chuyên ngành y, phán đoán nhị phân, sinh 2 câu
nhiễu ngắn. Không cần cửa sổ ngữ cảnh dài (prompt < 1000 token), rất cần
**thông lượng** vì có vài nghìn lượt gọi.

| Model | VRAM | Chọn khi |
|---|---|---|
| **`Qwen/Qwen3-32B-FP8`** | ~35 GB | **Mặc định.** Tiếng Việt tốt nhất trong tầm giá, còn thừa ~45 GB cho KV cache nên batch rất lớn. |
| `Qwen/Qwen3-30B-A3B-Instruct-2507` | ~60 GB | Cần thông lượng tối đa. MoE chỉ kích hoạt 3B tham số → nhanh hơn hẳn 32B dense, chất lượng xấp xỉ. |
| `Qwen/Qwen3-32B` (bf16) | ~64 GB | Muốn tránh mọi rủi ro lượng tử hoá. Phải hạ `--max-model-len 2048` và `--gpu-mem 0.95`. |
| `Qwen/Qwen2.5-72B-Instruct-AWQ` | ~40 GB | Cần model to nhất nhét vừa. Chậm hơn, đời cũ hơn. |
| `meta-llama/Llama-3.3-70B-Instruct` FP8 | ~70 GB | Chỉ khi bắt buộc dùng Llama. Tiếng Việt y khoa yếu hơn Qwen rõ rệt. |
| `google/medgemma-27b-text-it` | ~54 GB | Chỉ để đối chiếu ở bước thẩm định: mạnh kiến thức y khoa nhưng tiếng Việt yếu. |

Không dùng cho việc này:

- `Qwen3-235B-A22B` — ~235 GB, không vừa một H100.
- Bản `-VL` — prompt của ta thuần văn bản, vision tower chỉ tốn VRAM.
- Model < 8B — ở v1, Qwen3-0.6B chọn 2 phương án ở 131/150 câu; nó không đủ sức
  quyết định "nên chọn bao nhiêu ô", nói gì đến thẩm định đáp án.

Ước lượng: ~3.700 lượt vòng 1 + ~3.200 lượt vòng 2, prompt ~600 token, đầu ra
≤ 256 token. Với Qwen3-32B-FP8 trên 1×H100, cả hai vòng chạy trong khoảng
**20–40 phút**.

Cờ hay dùng: `--tp 2` (2 GPU), `--max-tokens 128` (vòng pool/audit, không sinh
văn bản dài), `--chunk 2048`, `--limit N` (chạy thử N câu trước khi chạy hết).

### Hai lỗi phải sửa trên instance Lambda mới

Đã gặp thật trên Lambda H100 PCIe (Ubuntu 22.04, Python 3.10.12, vLLM 0.27.1,
flashinfer-python 0.6.16). Cả hai đều làm engine chết ngay lúc khởi động với
`RuntimeError: Engine core initialization failed`, nguyên nhân thật nằm cách đó
mấy chục dòng phía trên.

**1. `TypeError: 'type' object is not subscriptable`**

`flashinfer/comm/fd_exchange.py` có annotation `array.array[int]`, mà `array.array`
chỉ subscript được từ Python 3.12. vLLM có bọc `try/except ImportError` quanh chỗ
import flashinfer, nhưng lỗi ném ra là `TypeError` nên lọt qua.

```bash
F=~/venv/lib/python3.10/site-packages/flashinfer/comm/fd_exchange.py
cp -n "$F" "$F.bak"
sed -i '15i from __future__ import annotations' "$F"   # chèn trước import đầu tiên
~/venv/bin/python -c 'import flashinfer.comm; print("OK")'
```

`from __future__ import annotations` làm annotation không được đánh giá lúc import.
Cách khác: dựng venv bằng Python 3.12, hoặc chạy với `enforce_eager` (chậm hơn vì
mất torch.compile và CUDA graph).

**2. `FileNotFoundError: 'ninja'`**

torch.compile cần `ninja` khi capture CUDA graph. Cài vào venv là chưa đủ — gọi
`~/venv/bin/python` trực tiếp KHÔNG đưa `~/venv/bin` vào `PATH`, nên tiến trình
EngineCore con không tìm thấy.

```bash
~/venv/bin/pip install ninja
export PATH=$HOME/venv/bin:$PATH        # hoặc: source ~/venv/bin/activate
```

Thời gian khởi động sau khi sửa: nạp trọng số 21 s, capture CUDA graph 98 s,
tổng ~3 phút 15 s trước khi sinh token đầu tiên (lần đầu cộng thêm ~10 phút tải
model). Chi phí này trả một lần cho cả ba lô nếu chạy chung một lệnh.

### Ba điều `gpu/vllm_batch.py` bắt buộc làm

1. **Không có structured outputs thì dừng hẳn**, không âm thầm chuyển sang sinh
   tự do. Ở v1, `GuidedDecodingParams` bị gỡ khỏi vLLM 0.12 → import lỗi → rơi về
   sinh tự do → hỏng trọn một lượt benchmark mà nhìn log không thấy gì bất thường.
2. **Tắt thinking của Qwen3** (`enable_thinking=False`), nếu không `<think>` ăn
   hết ngân sách token. Vẫn cắt `<think>` khi parse để chắc chắn.
3. **Ghi ra đĩa theo từng khối, bỏ qua id đã có** → đứt giữa chừng chạy lại được.

Lưu ý về JSON Schema: xgrammar không hỗ trợ mọi từ khoá. Đã tránh `uniqueItems`
(từng gây `Grammar error: Unimplemented keys`), `minLength`/`maxLength` — các
ràng buộc đó kiểm ở phía Python trong `s4_apply.py` thay vì ép ở tầng grammar.

---

## 7. Các bộ lọc chất lượng

Cơ học (`s2_route.py`), loại trước khi tốn GPU:

- dấu phẩy là dấu **thập phân** (`0,5 g/l`) → bảo vệ bằng sentinel trước khi tách
- pool **toàn số** (> 60% mục là số/đơn vị)
- **overlap < 0,2** — các phương án không dùng chung kho khái niệm thì không phải
  dạng tách được. `overlap = 1 − (số mục khác nhau / tổng số mục)`
- **dãy có thứ tự**: mục lặp trong cùng một phương án, hoặc thân câu có
  "thứ tự / lần lượt / tương ứng"
- **câu xếp hạng**: hai phương án có cùng tập mục, chỉ khác thứ tự
- phương án rác: `None`, `Không có`, `...`, chỉ toàn số, trùng nhau, chứa meta
- thân câu có chỗ trống `......` / `___`
- **gần trùng**: khử theo khối (8 ký tự đầu + dải độ dài), `SequenceMatcher > 0,90`

Ngữ nghĩa (chỉ LLM làm được):

- file3 vòng 1 — mục nào đang làm nhiễu nhưng **thực ra cũng đúng** → gỡ khỏi pool
- file1 vòng 1 — câu có thật là dạng phủ định không, 3 phương án còn lại có đúng cả không
- file2 vòng 1 — phương án nhiễu sinh ra có **chắc chắn sai** không
- vòng 2 — thẩm định lại toàn bộ câu đã dựng, hai chiều (nhãn đúng hoá ra sai, và ngược lại)

Cổng bất biến `lib2.validate()` chạy trên **mọi** bản ghi trước khi ghi ra:
≥ 4 phương án, 2 ≤ số đáp án đúng < tổng số phương án, không phương án trùng,
không phương án rác, `correctAnswer` trỏ đúng chỗ. Câu hỏng vào
`data_v2/04_rejected.json` kèm lý do — không im lặng bỏ qua.

Chống rò rỉ vị trí: mọi phương án đều được **trộn theo seed lấy từ `uid`**. Ở v1,
để nguyên thứ tự gốc thì phương án sai rơi vào D ở 105/265 câu và chiến lược mù
"luôn chọn A, B, C" ăn 39,1%.
