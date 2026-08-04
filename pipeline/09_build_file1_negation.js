'use strict';
// FILE 1 — câu dạng phủ định ("ngoại trừ", "chọn câu sai", "không đúng", "không phải").
// Cơ chế: đáp án gốc là mệnh đề SAI => tất cả phương án CÒN LẠI đều đúng.
// Xử lý: viết lại thân câu sang khẳng định + đảo tập đáp án. Giữ nguyên phương án gốc.
// Output theo đúng format raw_data.json.
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const raw = L.readRawData();
const clean = L.readJson('01_clean.json');

// Luật viết lại thân câu, thử theo thứ tự, dừng ở luật đầu tiên khớp.
const REWRITES = [
  ['A. ngoại trừ', /\s*[,;.]?\s*(ngoại|loại)\s*trừ\s*[:.]?\s*$/i, ':'],
  ['A. trừ',       /\s*[,;.]?\s*trừ\s*[:.]?\s*$/i, ':'],
  ['B. chọn sai',  /chọn\s+(câu|ý|phương án|đáp án)?\s*sai/i, 'Chọn các câu đúng'],
  ['B. nào sai',   /\bsai\b(?=\s*[:.?]?\s*$)/i, 'đúng'],
  ['B. nào sau đây sai', /(nào\s+(sau\s+đây\s+)?(là\s+)?)sai/i, '$1đúng'],
  ['C. không đúng', /không\s+(đúng|chính xác|phù hợp)/i, '$1'],
  ['D. không phải', /không\s+phải\s+(là\s+)?/i, '$1'],
];

const NEG_DETECT = /ngoại\s*trừ|loại\s*trừ|,\s*trừ\s*:?\s*$|chọn\s+(câu|ý|phương án|đáp án)?\s*sai|(câu|ý|phương án|đáp án|nhận định|khẳng định|điều)\s+nào\s+(sau\s+đây\s+)?(là\s+)?sai|nào\s+sau\s+đây\s+sai|không\s+(đúng|chính xác|phù hợp)|không\s+phải/i;

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
const out = [], prov = [], skipped = [];

for (const r of clean) {
  if (r.optionCount < 4) continue;
  if (!NEG_DETECT.test(r.question)) continue;

  let rewritten = null, family = null;
  for (const [name, re, rep] of REWRITES) {
    if (re.test(r.question)) {
      rewritten = L.collapse(r.question.replace(re, rep)).replace(/\s+([:.?])/g, '$1').replace(/[:\s]*:$/, ':');
      family = name;
      break;
    }
  }
  if (!rewritten || rewritten.length < 8) {
    skipped.push({ uid: r.uid, question: r.question, reason: 'no_clean_rewrite' });
    continue;
  }

  // Đảo tập đáp án: mọi phương án TRỪ đáp án gốc.
  const correct = r.options.map((_, i) => i).filter(i => i !== r.correctIndex);

  const src = raw[r.sourceIndex];
  const rec = {
    question: L.stripPrefix(rewritten),
    correctAnswer: correct.map(i => 'option' + LETTERS[i]).join(', '),
    medicalTopic: src.medicalTopic,
    difficultLevel: src.difficultLevel,
    regularFormat: src.regularFormat,
    questionID: src.questionID,
  };
  r.options.forEach((o, i) => { rec['answer_option' + LETTERS[i]] = o; });
  out.push(rec);

  prov.push({
    questionID: src.questionID, uid: r.uid, sourceIndex: r.sourceIndex,
    negationFamily: family, originalQuestion: r.question,
    originalCorrect: 'option' + r.correctLetter, newCorrect: rec.correctAnswer,
  });
}

L.writeJson('final_01_ngoai_tru.json', out);
L.writeJson('final_01_ngoai_tru_provenance.json', prov);
L.writeJson('final_01_ngoai_tru_skipped.json', skipped);

const byFam = {};
for (const p of prov) byFam[p.negationFamily] = (byFam[p.negationFamily] || 0) + 1;
console.log(`FILE 1 — câu phủ định: ${out.length} câu`);
console.log('  theo luật viết lại :', byFam);
console.log('  bỏ qua (không viết lại sạch được):', skipped.length);

console.log('\n  --- 3 ví dụ ---');
for (let i = 0; i < Math.min(3, out.length); i++) {
  const rec = out[i], p = prov[i];
  console.log(`\n  GỐC : ${p.originalQuestion.slice(0, 100)}   [đáp án ${p.originalCorrect}]`);
  console.log(`  MỚI : ${rec.question.slice(0, 100)}   [đáp án ${rec.correctAnswer}]`);
  LETTERS.slice(0, 4).forEach(le => {
    if (rec['answer_option' + le]) {
      console.log(`     ${rec.correctAnswer.includes('option' + le) ? '[x]' : '[ ]'} ${rec['answer_option' + le].slice(0, 80)}`);
    }
  });
}
