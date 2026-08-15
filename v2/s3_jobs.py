"""Tầng 3 — đóng gói việc cho LLM (vòng 1).

Sinh ra 3 lô việc trong llm_jobs/, mỗi lô là một file .jsonl + một file schema
JSON đi kèm. Chạy chúng bằng gpu/vllm_batch.py trên máy H100, kết quả ghi vào
<tên lô>.out.jsonl rồi copy về đây cho tầng 4.

Nguyên tắc: LLM chỉ được PHÁN XÉT và VIẾT VĂN BẢN NHIỄU.
Đáp án đúng luôn suy ra từ trường correctAnswer của đề gốc, không bao giờ do
model tự đặt — nếu để model tự chọn đáp án thì benchmark chỉ còn đo được độ
giống nhau giữa hai model chứ không đo được kiến thức.
"""
from __future__ import annotations

import lib2 as L

# ============================================================ T1 — file 3
POOL_PROMPT = """Bạn là chuyên gia biên soạn đề trắc nghiệm y khoa.

Câu hỏi trắc nghiệm 1 đáp án dưới đây có cả bốn phương án đều là DANH SÁCH các mục \
ngăn cách bởi dấu phẩy. Ta muốn gộp tất cả các mục lại thành một danh sách phương án \
độc lập, rồi hỏi "chọn tất cả các phương án đúng"; khi đó đáp án đúng chính là các mục \
nằm trong phương án đúng gốc.

CÂU HỎI: {question}

PHƯƠNG ÁN GỐC:
{options}
Đáp án đúng gốc: {correct_letter}

DANH SÁCH MỤC SAU KHI GỘP (đánh số từ 0):
{pool}
Các mục thuộc đáp án đúng gốc: {correct_idx}

Hãy trả lời 3 việc:

1. "tach_duoc": các mục trên có phải là những khái niệm ĐỘC LẬP, đứng riêng vẫn có \
nghĩa, và câu hỏi vẫn hợp lý khi hỏi "chọn tất cả các mục đúng" hay không?
   Trả false nếu: các mục chỉ có nghĩa khi đi liền nhau; đây là câu hỏi về thứ tự, \
trình tự hay ghép cặp tương ứng; hoặc tách ra thì câu hỏi mất nghĩa.

2. "muc_sai_thuc_ra_dung": trong các mục KHÔNG thuộc đáp án đúng gốc, hãy liệt kê chỉ \
số của những mục mà xét về chuyên môn thực ra CŨNG ĐÚNG với câu hỏi này (nếu để lại làm \
phương án nhiễu thì đáp án chuẩn sẽ sai). Chỉ liệt kê khi bạn chắc chắn; không chắc thì \
để mảng rỗng.

3. "do_tin_cay": mức tin cậy của bạn cho hai câu trả lời trên.

Chỉ trả về JSON, không giải thích."""

POOL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tach_duoc", "muc_sai_thuc_ra_dung", "do_tin_cay"],
    "properties": {
        "tach_duoc": {"type": "boolean"},
        "muc_sai_thuc_ra_dung": {"type": "array", "items": {"type": "integer", "minimum": 0}},
        "do_tin_cay": {"type": "string", "enum": ["cao", "trung binh", "thap"]},
    },
}

# ============================================================ T2 — file 2
DISTRACT_PROMPT = """Bạn là chuyên gia biên soạn đề trắc nghiệm y khoa.

CÂU HỎI: {question}

Ba phương án sau đây ĐỀU ĐÚNG với câu hỏi trên:
{options}

Hãy viết thêm ĐÚNG 2 phương án SAI (phương án nhiễu) cho câu hỏi này.

Yêu cầu bắt buộc:
- Phải SAI RÕ RÀNG về chuyên môn. Không được đúng một phần, không được là cách diễn \
đạt khác của ba phương án trên, không được là khái niệm bao hàm chúng.
- Cùng chủ đề, cùng văn phong, độ dài tương đương ba phương án trên, để đọc qua vẫn \
thấy hợp lý.
- Tiếng Việt, mỗi phương án là một cụm hoặc một câu ngắn. KHÔNG đánh số, KHÔNG thêm \
chữ cái đầu dòng, KHÔNG giải thích.
- Cấm dùng các cụm kiểu "tất cả đều đúng", "không câu nào đúng", "cả A và B".

Đặt "chac_chan_sai" = true CHỈ KHI bạn chắc chắn cả 2 phương án vừa viết đều sai.

Chỉ trả về JSON."""

DISTRACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["nhieu", "chac_chan_sai"],
    "properties": {
        "nhieu": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
        "chac_chan_sai": {"type": "boolean"},
    },
}

# ============================================================ T3 — file 1
NEG_PROMPT = """Bạn là chuyên gia biên soạn đề trắc nghiệm y khoa.

Câu hỏi dưới đây được cho là dạng PHỦ ĐỊNH: nó yêu cầu chọn phương án SAI, hoặc có \
chữ "ngoại trừ", "không đúng", "không phải". Nếu đúng như vậy thì mọi phương án TRỪ \
đáp án gốc đều là phát biểu ĐÚNG.

CÂU HỎI GỐC: {question}

ĐÁP ÁN GỐC (tức là phương án SAI / bị loại trừ): {wrong}

BA PHƯƠNG ÁN CÒN LẠI:
{options}

Hãy trả lời 3 việc:

1. "la_phu_dinh": câu hỏi trên có thực sự là dạng phủ định như mô tả không?

2. "cau_hoi_moi": viết lại phần dẫn thành dạng KHẲNG ĐỊNH để có thể hỏi "chọn tất cả \
các phương án đúng". Giữ nguyên toàn bộ nội dung chuyên môn, chỉ bỏ phần phủ định. \
KHÔNG thêm câu "Chọn tất cả các đáp án đúng". KHÔNG kèm phương án.
   Ví dụ: "Các triệu chứng sau gặp trong bệnh X, NGOẠI TRỪ:" -> "Các triệu chứng sau \
gặp trong bệnh X:"
   Ví dụ: "Điều nào sau đây KHÔNG ĐÚNG về thuốc Y?" -> "Điều nào sau đây đúng về thuốc Y?"

3. "ba_phuong_an_deu_dung": với câu hỏi mới đó, ba phương án còn lại có thực sự đều \
đúng cả không?

Chỉ trả về JSON."""

NEG_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["la_phu_dinh", "cau_hoi_moi", "ba_phuong_an_deu_dung"],
    "properties": {
        "la_phu_dinh": {"type": "boolean"},
        "cau_hoi_moi": {"type": "string"},
        "ba_phuong_an_deu_dung": {"type": "boolean"},
    },
}

# ============================================================ T4 — vòng 2
AUDIT_PROMPT = """Bạn là chuyên gia thẩm định đề thi y khoa.

Câu hỏi trắc nghiệm NHIỀU ĐÁP ÁN dưới đây được sinh tự động từ một câu hỏi 1 đáp án. \
Hãy kiểm định trước khi đưa vào đề thi.

CÂU HỎI: {question}

CÁC PHƯƠNG ÁN (đánh số từ 0, kèm nhãn hiện tại):
{options}

Hãy trả lời 4 việc:

1. "cau_hoi_ro_rang": phần dẫn có đủ nghĩa, đọc là hiểu, không cụt và không thiếu ngữ \
cảnh hay không?

2. "danh_dau_sai_thuc_ra_dung": chỉ số các phương án đang bị đánh dấu SAI nhưng thực \
ra ĐÚNG với câu hỏi.

3. "danh_dau_dung_thuc_ra_sai": chỉ số các phương án đang được đánh dấu ĐÚNG nhưng \
thực ra SAI.

4. "dat": true nếu câu hỏi dùng được ngay làm đề thi mà không cần sửa gì.

Chỉ liệt kê khi chắc chắn; không chắc thì để mảng rỗng. Chỉ trả về JSON."""

AUDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cau_hoi_ro_rang", "danh_dau_sai_thuc_ra_dung",
                 "danh_dau_dung_thuc_ra_sai", "dat"],
    "properties": {
        "cau_hoi_ro_rang": {"type": "boolean"},
        "danh_dau_sai_thuc_ra_dung": {"type": "array",
                                      "items": {"type": "integer", "minimum": 0}},
        "danh_dau_dung_thuc_ra_sai": {"type": "array",
                                      "items": {"type": "integer", "minimum": 0}},
        "dat": {"type": "boolean"},
    },
}


# ------------------------------------------------------------------ tiện ích
def _bullets(texts, start_letter=True):
    if start_letter:
        return "\n".join(f"{L.LETTERS[i]}. {t}" for i, t in enumerate(texts))
    return "\n".join(f"{i}. {t}" for i, t in enumerate(texts))


def _cap(rows, limit):
    """Cắt bớt lô việc cho vừa ngân sách GPU. Lấy đều theo bước nhảy, không lấy
    50 câu đầu — nếu không, lô việc sẽ toàn câu của một file nguồn."""
    if not limit or len(rows) <= limit:
        return rows
    step = len(rows) / limit
    return [rows[int(i * step)] for i in range(limit)]


# ------------------------------------------------------------------ tầng 3
def s3_jobs(limit: int = 0):
    f1 = _cap(L.read_work("02_route_file1.json"), limit)
    f2 = _cap(L.read_work("02_route_file2.json"), limit)
    f3 = _cap(L.read_work("02_route_file3.json"), limit)
    print(f"Tầng 3 — đóng gói việc cho LLM"
          f"{f' (giới hạn {limit} câu/họ)' if limit else ''}")

    L.write_jobs("r1_negation", [{
        "id": r["uid"],
        "prompt": NEG_PROMPT.format(
            question=r["question"], wrong=r["wrongOption"],
            options=_bullets(r["correctOptions"])),
    } for r in f1], NEG_SCHEMA)

    L.write_jobs("r1_distract", [{
        "id": r["uid"],
        "prompt": DISTRACT_PROMPT.format(
            question=r["questionClean"], options=_bullets(r["correctOptions"])),
    } for r in f2], DISTRACT_SCHEMA)

    L.write_jobs("r1_pool", [{
        "id": r["uid"],
        "prompt": POOL_PROMPT.format(
            question=r["questionClean"],
            options="\n".join(f"{le}. {r['options'][i]}"
                              for i, le in enumerate(r["optionLetters"])),
            correct_letter=r["correctLetter"],
            pool=_bullets(r["pool"], start_letter=False),
            correct_idx=r["poolCorrect"]),
    } for r in f3], POOL_SCHEMA)

    # Ghi lại đúng tập ứng viên đã gửi đi, để tầng 4 khớp 1:1 với kết quả trả về.
    for name, rows in (("file1", f1), ("file2", f2), ("file3", f3)):
        L.write_work(f"03_sent_{name}.json", rows)

    print(f"\n  Bước tiếp theo — chạy trên máy H100:")
    print(f"    python gpu/vllm_batch.py llm_jobs/r1_negation.jsonl "
          f"llm_jobs/r1_distract.jsonl llm_jobs/r1_pool.jsonl \\")
    print(f"        --model Qwen/Qwen3-32B-FP8")
    print(f"  Copy 3 file *.out.jsonl về {L.JOBS_DIR.name}/ rồi chạy: python v2/run.py apply")
