'use strict';
// Tầng 4 — chuyển đổi nhóm B (câu tổ hợp "(1),(2),(3)").
// Mệnh đề đánh số nằm trong thân câu hỏi; đáp án đúng chỉ ra tập số nào đúng.
const L = require('./lib');

const rows = L.readJson('02_classified.json').filter(r => r.group === 'combination');
console.log(`Tầng 4 — chuyển đổi câu tổ hợp: ${rows.length} ứng viên`);

// Cắt đuôi chỉ dẫn dính vào mệnh đề cuối ("Hãy chọn đáp án đúng nhất?")
const TAIL = /\s*(hãy\s+)?(chọn|tìm|cho biết)\s+(đáp án|câu|phương án|tổ hợp|ý)\b.*$/i;
const numsIn = s => [...String(s).matchAll(/\d{1,2}/g)].map(m => Number(m[0]));

const usable = [], rejected = [];

for (const r of rows) {
  const reject = reason => rejected.push({ uid: r.uid, reason, question: r.question, options: r.options });

  // Không lọc theo độ dài: bỏ một mệnh đề sẽ làm lệch ánh xạ số -> chỉ số.
  const stmts = r.statements
    .map(s => ({ n: s.n, text: L.collapse(s.text).replace(TAIL, '').replace(/[.\s]+$/, '') }));
  if (stmts.some(s => !s.text)) { reject('empty_statement_text'); continue; }
  if (stmts.length < 3) { reject('too_few_usable_statements'); continue; }

  const numbers = stmts.map(s => s.n);
  if (new Set(numbers).size !== numbers.length) { reject('duplicate_statement_numbers'); continue; }

  // Mọi số mà bất kỳ đáp án nào nhắc tới đều phải tồn tại trong thân câu hỏi.
  const referenced = r.options.flatMap(numsIn);
  if (!referenced.length || referenced.some(n => !numbers.includes(n))) {
    reject('option_references_unknown_statement'); continue;
  }

  const correctNums = [...new Set(numsIn(r.options[r.correctIndex]))];
  if (correctNums.length < 2) { reject('correct_option_selects_fewer_than_two'); continue; }
  if (correctNums.length >= stmts.length) { reject('correct_option_selects_everything'); continue; }

  const stem = L.collapse(r.question.slice(0, r.question.indexOf('(' + stmts[0].n + ')'))) || r.questionClean;

  usable.push({
    uid: r.uid,
    sourceQuestionID: r.sourceQuestionID,
    sourceIndex: r.sourceIndex,
    question: L.stripPrefix(stem),
    options: stmts.map(s => s.text),
    correctAnswers: correctNums.map(n => numbers.indexOf(n)).sort((a, b) => a - b),
    answerCount: correctNums.length,
    derivedFrom: 'combination',
    originalCorrect: 'option' + r.correctLetter,
    originalOptions: r.options,
    confidence: 'high',
    medicalTopic: r.medicalTopic,
    difficultLevel: r.difficultLevel,
  });
}

L.writeJson('04_multi_combination.json', usable);
L.writeJson('04_combination_rejected.json', rejected);

const byReason = {};
for (const x of rejected) byReason[x.reason] = (byReason[x.reason] || 0) + 1;
console.log(`\n  dùng được : ${usable.length}`);
console.log(`  loại      : ${rejected.length}`, byReason);

console.log('\n  --- 2 ví dụ dùng được ---');
for (const it of usable.slice(0, 2)) {
  console.log(`\n  ${it.question.slice(0, 160)}`);
  it.options.forEach((o, i) => console.log(`    ${it.correctAnswers.includes(i) ? '[x]' : '[ ]'} ${o.slice(0, 110)}`));
}
