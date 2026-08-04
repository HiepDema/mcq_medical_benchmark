'use strict';
// Tầng 8 — lọc theo đúng luật "mọi phương án đều chứa >= 1 dấu phẩy".
// Không biến đổi nội dung; chỉ gom lại và chấm điểm từng câu qua các lớp lọc
// tiếp theo để thấy luật dấu phẩy giữ lại được gì và lọt những gì.
const L = require('./lib');

const rows = L.readJson('01_clean.json');
const hit = rows.filter(r => r.options.every(o => o.includes(',')));
console.log(`Tầng 8 — luật dấu phẩy: ${hit.length}/${rows.length} câu có >=1 dấu phẩy ở MỌI phương án`);

const ORDER_STEM = /thứ tự|lần lượt|tương ứng|theo trình tự/i;

const out = hit.map(r => {
  const items = r.options.map(L.splitItems);                 // đã bảo vệ dấu thập phân
  const flat = items.flat();
  const surface = new Map();
  for (const it of flat) if (!surface.has(L.normItem(it))) surface.set(L.normItem(it), it);
  const pool = [...surface.values()];

  const overlap = +(1 - pool.length / flat.length).toFixed(3);
  const numericFrac = +(pool.filter(L.isNumericish).length / pool.length).toFixed(2);
  const allRoman = pool.every(L.isRoman);
  const dupInOption = items.some(p => new Set(p.map(L.normItem)).size !== p.length);

  // Chuỗi kiểm tra, dừng ở lỗi đầu tiên.
  let verdict = 'keep', dropReason = null;
  if (!items.every(p => p.length >= 2)) { verdict = 'drop'; dropReason = 'B2_dấu_phẩy_là_thập_phân'; }
  else if (numericFrac > 0.6 && !allRoman) { verdict = 'drop'; dropReason = 'B3_pool_toàn_số'; }
  else if (overlap < 0.2) { verdict = 'drop'; dropReason = 'B4_overlap_thấp'; }
  else if (dupInOption || ORDER_STEM.test(r.question)) { verdict = 'drop'; dropReason = 'B5_dãy_có_thứ_tự'; }

  return {
    uid: r.uid,
    sourceIndex: r.sourceIndex,
    sourceQuestionID: r.sourceQuestionID,
    question: r.question,
    options: Object.fromEntries(r.optionLetters.map((le, i) => [le, r.options[i]])),
    correctAnswer: r.correctLetter,
    correctText: r.options[r.correctIndex],
    optionCount: r.optionCount,
    verdict,
    dropReason,
    itemsPerOption: Object.fromEntries(r.optionLetters.map((le, i) => [le, items[i]])),
    itemsInCorrectAnswer: items[r.correctIndex],
    pool,
    overlap,
    numericFrac,
    hasDuplicateItemInOption: dupInOption,
    orderWordsInStem: ORDER_STEM.test(r.question),
    medicalTopic: r.medicalTopic,
    difficultLevel: r.difficultLevel,
  };
});

const rank = { keep: 0, drop: 1 };
out.sort((a, b) => rank[a.verdict] - rank[b.verdict]
  || String(a.dropReason).localeCompare(String(b.dropReason))
  || b.overlap - a.overlap);

L.writeJson('08_comma_rule.json', out);

const keep = out.filter(x => x.verdict === 'keep');
const byReason = {}, byCount = {};
for (const x of out) {
  byCount[x.optionCount] = (byCount[x.optionCount] || 0) + 1;
  if (x.dropReason) byReason[x.dropReason] = (byReason[x.dropReason] || 0) + 1;
}
console.log(`\n  theo số phương án :`, byCount);
console.log(`  giữ lại           : ${keep.length}  (${(100 * keep.length / out.length).toFixed(0)}% độ chính xác của luật dấu phẩy)`);
console.log(`  bị loại           : ${out.length - keep.length}`, byReason);

console.log('\n  --- 2 câu GIỮ LẠI (overlap cao nhất) ---');
for (const x of keep.slice(0, 2)) {
  console.log(`\n  [overlap ${x.overlap}] ${x.question.slice(0, 110)}`);
  for (const [k, v] of Object.entries(x.options)) console.log(`     ${k}. ${v.slice(0, 78)}${k === x.correctAnswer ? '   <== ĐÁP ÁN' : ''}`);
  console.log(`     pool: ${x.pool.join(' | ').slice(0, 120)}`);
}
console.log('\n  --- 1 câu BỊ LOẠI ở mỗi lý do ---');
for (const reason of Object.keys(byReason).sort()) {
  const x = out.find(y => y.dropReason === reason);
  console.log(`\n  [${reason}] ${x.question.slice(0, 100)}`);
  for (const [k, v] of Object.entries(x.options)) console.log(`     ${k}. ${v.slice(0, 70)}`);
}
