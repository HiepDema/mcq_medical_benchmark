'use strict';
// Tầng 7 — CHỈ GOM, KHÔNG BIẾN ĐỔI.
// Xuất 3 file để kiểm tra bằng mắt: câu phủ định / câu có đáp án meta / câu dùng chung pool.
// Giữ nguyên văn câu hỏi và đáp án gốc, chỉ thêm trường ghi chú lý do lọt vào file.
const L = require('./lib');

const rows = L.readJson('02_classified.json');
console.log(`Tầng 7 — gom nhóm để kiểm tra: ${rows.length} bản ghi`);

const NEGATION = [
  ['A. ngoại trừ / trừ',  'strong', /ngoại\s*trừ|,\s*trừ\s*:?\s*$|\btrừ\s*:/i],
  ['B. chọn câu sai',     'strong', /(câu|ý|đáp án|phương án|điều|nhận định|khẳng định)\s+nào\s+(sau đây\s+)?(là\s+)?sai|nào\s+sau\s+đây\s+sai|chọn\s+(câu\s+)?sai|\bsai\s*(là|\?|:)?\s*$/i],
  ['C. không đúng',       'strong', /không\s+(đúng|chính xác|phù hợp)/i],
  ['D. không phải',       'strong', /không\s+phải\s+(là\s+)?/i],
  ['E. "không" khác',     'weak',   /\bkhông\b/i],
];

// Khung bản ghi chung — nguyên văn, chưa xử lý gì.
const base = r => ({
  uid: r.uid,
  sourceIndex: r.sourceIndex,
  sourceQuestionID: r.sourceQuestionID,
  question: r.question,
  options: Object.fromEntries(r.optionLetters.map((le, i) => [le, r.options[i]])),
  correctAnswer: r.correctLetter,
  correctText: r.options[r.correctIndex],
  optionCount: r.optionCount,
  pipelineGroup: `${r.group}:${r.reason}`,
  medicalTopic: r.medicalTopic,
  difficultLevel: r.difficultLevel,
});

// ---------- FILE 1: câu phủ định ----------
const negation = [];
for (const r of rows) {
  if (r.optionCount < 4) continue;
  for (const [family, strength, re] of NEGATION) {
    const m = r.question.match(re);
    if (m) { negation.push({ ...base(r), negationFamily: family, negationStrength: strength, matchedText: m[0].trim() }); break; }
  }
}
negation.sort((a, b) => a.negationFamily.localeCompare(b.negationFamily) || a.sourceIndex - b.sourceIndex);

// ---------- FILE 2: câu có đáp án meta ----------
const meta = [];
for (const r of rows) {
  if (r.optionCount < 4) continue;
  const hits = r.options.map((o, i) => ({ i, letter: r.optionLetters[i], text: o, meta: L.metaKind(o) })).filter(x => x.meta);
  if (!hits.length) continue;
  const onCorrect = hits.find(x => x.i === r.correctIndex);
  meta.push({
    ...base(r),
    metaOptions: hits.map(x => ({ letter: x.letter, text: x.text, kind: x.meta.kind, letters: x.meta.letters || null })),
    metaIsCorrectAnswer: Boolean(onCorrect),
    metaKindOnCorrect: onCorrect ? onCorrect.meta.kind : null,
  });
}
meta.sort((a, b) => (b.metaIsCorrectAnswer - a.metaIsCorrectAnswer) || a.sourceIndex - b.sourceIndex);

// ---------- FILE 3: câu dùng chung pool (dạng câu số 2) ----------
const ORDER_STEM = /thứ tự|lần lượt|tương ứng|theo trình tự/i;
const pool = rows.filter(r => r.group === 'pool').map(r => {
  const itemsPerOption = r.optionLetters.map((le, i) => [le, r.optionItems[i].map(k => r.pool[k])]);
  // Đáp án là DÃY CÓ THỨ TỰ chứ không phải tập hợp -> tách thành multi-answer là sai.
  // Dấu hiệu chắc chắn: một đáp án chứa mục lặp lại (vd "sp2, sp, sp2, sp3").
  const signals = [];
  if (itemsPerOption.some(([, items]) => new Set(items.map(L.normItem)).size !== items.length))
    signals.push('duplicate_item_within_option');
  if (ORDER_STEM.test(r.question)) signals.push('order_words_in_stem');

  return {
    ...base(r),
    pool: r.pool,
    itemsPerOption: Object.fromEntries(itemsPerOption),
    itemsInCorrectAnswer: r.optionItems[r.correctIndex].map(k => r.pool[k]),
    overlap: r.overlap,
    tier: r.reason === 'overlap_high' ? 'high' : 'medium',
    poolType: r.poolType,
    suspectOrderedSequence: signals.length > 0,
    orderSignals: signals,
  };
});
pool.sort((a, b) => b.overlap - a.overlap || a.sourceIndex - b.sourceIndex);

L.writeJson('07_inspect_negation.json', negation);
L.writeJson('07_inspect_meta.json', meta);
L.writeJson('07_inspect_pool.json', pool);

// ---------- thống kê + kiểm chéo ----------
const count = (arr, key) => arr.reduce((a, x) => (a[x[key]] = (a[x[key]] || 0) + 1, a), {});
console.log('\n1) 07_inspect_negation.json —', negation.length, 'câu');
console.log('   theo họ  :', count(negation, 'negationFamily'));
console.log('   độ chắc  :', count(negation, 'negationStrength'));

console.log('\n2) 07_inspect_meta.json —', meta.length, 'câu');
console.log('   meta CHÍNH LÀ đáp án đúng :', meta.filter(x => x.metaIsCorrectAnswer).length);
console.log('   meta chỉ là nhiễu         :', meta.filter(x => !x.metaIsCorrectAnswer).length);
console.log('   loại meta trên đáp án đúng:', count(meta.filter(x => x.metaIsCorrectAnswer), 'metaKindOnCorrect'));

console.log('\n3) 07_inspect_pool.json —', pool.length, 'câu');
console.log('   tier :', count(pool, 'tier'), ' loại pool:', count(pool, 'poolType'));
const susp = pool.filter(p => p.suspectOrderedSequence);
console.log('   nghi là DÃY CÓ THỨ TỰ (không tách được):', susp.length,
  `(tier high: ${susp.filter(p => p.tier === 'high').length})`);

// Cảnh báo chồng lấn: thân câu phủ định làm đảo ngược ý nghĩa của tập đúng.
const negUids = new Set(negation.map(x => x.uid));
const negStrong = new Set(negation.filter(x => x.negationStrength === 'strong').map(x => x.uid));
const overlapPool = pool.filter(p => negUids.has(p.uid));
const overlapMeta = meta.filter(m => m.metaIsCorrectAnswer && negUids.has(m.uid));
console.log('\n⚠  KIỂM CHÉO chồng lấn (thân câu phủ định làm đảo ngược tập đúng):');
console.log('   pool ∩ phủ định :', overlapPool.length, `(chắc chắn: ${overlapPool.filter(p => negStrong.has(p.uid)).length})`);
console.log('   meta ∩ phủ định :', overlapMeta.length, `(chắc chắn: ${overlapMeta.filter(m => negStrong.has(m.uid)).length})`);
if (overlapPool.length) {
  console.log('\n   Ví dụ pool có thân phủ định:');
  for (const p of overlapPool.filter(x => negStrong.has(x.uid)).slice(0, 3)) {
    console.log(`     [${p.tier}] ${p.question.slice(0, 120)}`);
    console.log(`        đáp án gốc ${p.correctAnswer}: ${p.correctText.slice(0, 90)}`);
  }
}
