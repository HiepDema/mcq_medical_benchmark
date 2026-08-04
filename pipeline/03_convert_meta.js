'use strict';
// Tầng 3 — chuyển đổi nhóm A (đáp án meta). Thuần rule, không dùng LLM.
// Bỏ option meta khỏi danh sách, tập đúng suy ra từ chính nội dung meta.
const L = require('./lib');

const rows = L.readJson('02_classified.json').filter(r => r.group === 'meta');
console.log(`Tầng 3 — chuyển đổi meta-option: ${rows.length} ứng viên`);

const usable = [], degenerate = [], rejected = [];

for (const r of rows) {
  const reject = reason => rejected.push({ uid: r.uid, reason, question: r.question, options: r.options });

  const keep = r.options.map((text, i) => ({ text, i, letter: r.optionLetters[i] }))
    .filter(o => !r.metaIndices.includes(o.i));
  if (keep.length < 2) { reject('too_few_non_meta_options'); continue; }

  let correct;
  if (r.reason === 'ALL_CORRECT') {
    correct = keep.map((_, k) => k);
  } else {                                        // LETTERS
    const wanted = (r.metaLetters || []).map(c => c.toUpperCase());
    const idx = wanted.map(le => keep.findIndex(o => o.letter === le));
    if (idx.some(k => k === -1)) { reject('letter_points_to_missing_or_meta_option'); continue; }
    correct = [...new Set(idx)].sort((a, b) => a - b);
    if (correct.length < 2) { reject('fewer_than_two_letters'); continue; }
  }

  const item = {
    uid: r.uid,
    sourceQuestionID: r.sourceQuestionID,
    sourceIndex: r.sourceIndex,
    question: r.questionClean,
    options: keep.map(o => o.text),
    correctAnswers: correct,
    answerCount: correct.length,
    derivedFrom: 'meta-option',
    metaKind: r.reason,
    originalCorrect: 'option' + r.correctLetter,
    originalOptions: r.options,
    confidence: 'high',
    medicalTopic: r.medicalTopic,
    difficultLevel: r.difficultLevel,
  };

  if (correct.length >= keep.length) {
    item.qualityFlag = 'all-options-correct';
    item.confidence = 'review';
    degenerate.push(item);
  } else {
    usable.push(item);
  }
}

L.writeJson('03_multi_meta.json', usable);
L.writeJson('03_meta_all_correct.json', degenerate);
L.writeJson('03_meta_rejected.json', rejected);

const byReason = {};
for (const x of rejected) byReason[x.reason] = (byReason[x.reason] || 0) + 1;
console.log(`\n  dùng được ngay          : ${usable.length}`);
console.log(`  toàn bộ đáp án đều đúng : ${degenerate.length}  (câu benchmark yếu — cần review)`);
console.log(`  loại                    : ${rejected.length}`, byReason);

console.log('\n  --- 3 ví dụ dùng được ---');
for (const it of usable.slice(0, 3)) {
  console.log(`\n  ${it.question}`);
  it.options.forEach((o, i) => console.log(`    ${it.correctAnswers.includes(i) ? '[x]' : '[ ]'} ${o}`));
}
