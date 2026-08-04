'use strict';
// Tầng 5 — đóng gói nhóm C thành đầu vào cho LLM.
// Việc tách chuỗi đã xong bằng code; LLM chỉ còn phải (1) chuẩn hoá/gộp mục
// trùng khái niệm, (2) xác nhận đáp án gốc có liệt kê đầy đủ không, (3) từ chối.
const L = require('./lib');

const rows = L.readJson('02_classified.json').filter(r => r.group === 'pool');
console.log(`Tầng 5 — đóng gói nhóm pool: ${rows.length} ứng viên`);

const candidates = [], rejected = [];

for (const r of rows) {
  const reject = reason => rejected.push({ uid: r.uid, reason, question: r.question, options: r.options, pool: r.pool });

  const proposed = [...new Set(r.optionItems[r.correctIndex])].sort((a, b) => a - b);

  if (r.pool.length < 3) { reject('pool_too_small'); continue; }
  if (proposed.length < 2) { reject('correct_option_has_one_item'); continue; }
  if (proposed.length >= r.pool.length) { reject('correct_option_covers_whole_pool'); continue; }

  const warnings = [];
  const maxLen = Math.max(...r.pool.map(p => p.length));
  if (maxLen > 120) warnings.push('long_pool_item');            // có thể tách hụt
  if (new Set(r.options.map(L.normItem)).size < r.options.length) warnings.push('duplicate_source_options');
  if (r.numericFrac > 0.3) warnings.push('mixed_numeric_items');

  candidates.push({
    uid: r.uid,
    sourceQuestionID: r.sourceQuestionID,
    sourceIndex: r.sourceIndex,
    question: r.questionClean,
    pool: r.pool,
    proposedCorrect: proposed,
    optionItems: r.optionItems,
    originalOptions: r.options,
    originalCorrect: 'option' + r.correctLetter,
    poolType: r.poolType,
    tier: r.reason === 'overlap_high' ? 'high' : 'medium',
    overlap: r.overlap,
    warnings,
    medicalTopic: r.medicalTopic,
    difficultLevel: r.difficultLevel,
  });
}

// Schema cho guided decoding (vLLM guided_json / xgrammar).
const schema = {
  type: 'object',
  additionalProperties: false,
  required: ['uid', 'decision', 'pool', 'correctAnswers', 'confidence'],
  properties: {
    uid: { type: 'string' },
    decision: {
      type: 'string',
      enum: ['accept', 'reject'],
      description: 'reject khi câu không tách được thành nhiều đáp án độc lập',
    },
    rejectReason: { type: 'string' },
    pool: {
      type: 'array', minItems: 3, maxItems: 24,
      items: { type: 'string' },
      description: 'Danh sách mục đã chuẩn hoá, gộp các mục trùng khái niệm. Giữ nguyên thuật ngữ y khoa gốc.',
    },
    correctAnswers: {
      type: 'array', minItems: 1, items: { type: 'integer', minimum: 0 },
      description: 'Chỉ số trong pool của các mục đúng',
    },
    exhaustive: {
      type: 'boolean',
      description: 'true nếu đáp án đúng gốc là liệt kê đầy đủ, nên các mục còn lại chắc chắn là nhiễu',
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
};

L.writeJson('05_pool_candidates.json', candidates);
L.writeJson('05_pool_rejected.json', rejected);
L.writeJson('05_llm_schema.json', schema);

const byReason = {};
for (const x of rejected) byReason[x.reason] = (byReason[x.reason] || 0) + 1;
const byTier = {}, byWarn = {};
for (const c of candidates) {
  byTier[`${c.tier}/${c.poolType}`] = (byTier[`${c.tier}/${c.poolType}`] || 0) + 1;
  for (const w of c.warnings) byWarn[w] = (byWarn[w] || 0) + 1;
}
console.log(`\n  sẵn sàng cho LLM : ${candidates.length}`, byTier);
console.log(`  loại trước LLM   : ${rejected.length}`, byReason);
console.log(`  cảnh báo         :`, byWarn);

const chars = candidates.reduce((a, c) =>
  a + c.question.length + c.originalOptions.join('').length + c.pool.join('').length, 0);
console.log(`  payload ước tính : ~${Math.round(chars / 2.7 / 1000)}k token input cho cả lô`);
