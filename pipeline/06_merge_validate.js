'use strict';
// Tầng 6 — gộp các nhóm đã chuyển đổi bằng rule và kiểm tra bất biến.
// Bản ghi vi phạm bị tách ra file riêng chứ không bị bỏ im lặng.
const L = require('./lib');

const parts = [
  ['03_multi_meta.json', 'meta-option'],
  ['04_multi_combination.json', 'combination'],
];

const ok = [], bad = [];
const seen = new Set();

for (const [file] of parts) {
  for (const it of L.readJson(file)) {
    const errs = [];
    const n = it.options.length;
    const c = it.correctAnswers;

    if (!Array.isArray(c) || c.length < 2) errs.push('fewer_than_two_correct');
    if (c.length >= n) errs.push('all_options_correct');
    if (c.some(i => !Number.isInteger(i) || i < 0 || i >= n)) errs.push('index_out_of_range');
    if (new Set(c).size !== c.length) errs.push('duplicate_correct_index');
    if (it.options.some(o => !String(o).trim())) errs.push('empty_option');
    if (new Set(it.options.map(L.normItem)).size !== n) errs.push('duplicate_options');
    if (it.answerCount !== c.length) errs.push('answerCount_mismatch');
    if (seen.has(it.uid)) errs.push('duplicate_uid');
    seen.add(it.uid);

    if (errs.length) bad.push({ ...it, violations: errs });
    else ok.push(it);
  }
}

ok.sort((a, b) => a.sourceIndex - b.sourceIndex);
L.writeJson('06_multi_ready.json', ok);
L.writeJson('06_validation_failures.json', bad);

const dist = {}, src = {};
for (const it of ok) {
  dist[it.answerCount] = (dist[it.answerCount] || 0) + 1;
  src[it.derivedFrom] = (src[it.derivedFrom] || 0) + 1;
}
const byViolation = {};
for (const b of bad) for (const v of b.violations) byViolation[v] = (byViolation[v] || 0) + 1;

console.log(`Tầng 6 — gộp & kiểm tra`);
console.log(`\n  đạt bất biến : ${ok.length}`, src);
console.log(`  vi phạm      : ${bad.length}`, byViolation);
console.log(`  số đáp án đúng mỗi câu:`, dist);

// --- bảng tổng kết toàn pipeline ---
const summary = {
  generatedAt: new Date().toISOString(),
  source: { file: 'raw_data.json', records: 10242 },
  stages: {
    clean: { kept: L.readJson('01_clean.json').length,
             duplicates: L.readJson('01_duplicates.json').length,
             dropped: L.readJson('01_dropped.json').length },
    ruleConverted: { ready: ok.length, failedValidation: bad.length,
                     allOptionsCorrect: L.readJson('03_meta_all_correct.json').length },
    awaitingLLM: { poolCandidates: L.readJson('05_pool_candidates.json').length },
  },
};
L.writeJson('06_summary.json', summary);

console.log('\n  --- 2 ví dụ trong 06_multi_ready.json ---');
for (const it of ok.slice(0, 2)) {
  console.log(`\n  [${it.derivedFrom}] ${it.question.slice(0, 120)}`);
  it.options.forEach((o, i) => console.log(`    ${it.correctAnswers.includes(i) ? '[x]' : '[ ]'} ${o.slice(0, 100)}`));
}
