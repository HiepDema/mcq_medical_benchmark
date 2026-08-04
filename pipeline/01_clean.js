'use strict';
// Tầng 1 — làm sạch. Đọc raw_data.json (chỉ đọc), sinh uid ổn định,
// tách bản trùng và bản hỏng ra file riêng. Không bản ghi nào bị mất.
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const raw = JSON.parse(fs.readFileSync(path.join(L.ROOT, 'raw_data.json'), 'utf8'));
console.log(`Tầng 1 — làm sạch: đọc ${raw.length} bản ghi từ raw_data.json`);

const LETTERS = ['A', 'B', 'C', 'D', 'E'];
const clean = [], dropped = [], duplicates = [];
const seen = new Map();

raw.forEach((q, i) => {
  const drop = reason => dropped.push({ sourceIndex: i, reason, record: q });

  const question = L.collapse(q.question || '');
  if (!question) return drop('empty_question');

  // Giữ nguyên vị trí gốc của đáp án để ánh xạ correctAnswer cho đúng.
  const slots = LETTERS.map(le => ({ letter: le, text: L.collapse(q['answer_option' + le] || '') }))
    .filter(s => s.text);
  if (slots.length < 2) return drop('too_few_options');

  const m = String(q.correctAnswer || '').match(/option([A-E])/i);
  if (!m) return drop('unparseable_correctAnswer');
  const correctLetter = m[1].toUpperCase();
  const correctIndex = slots.findIndex(s => s.letter === correctLetter);
  if (correctIndex === -1) return drop('correct_option_is_empty');

  const options = slots.map(s => s.text);
  const uid = L.uidOf(question, options);

  if (seen.has(uid)) {
    duplicates.push({ uid, sourceIndex: i, keptSourceIndex: seen.get(uid), record: q });
    return;
  }
  seen.set(uid, i);

  clean.push({
    uid,
    sourceIndex: i,
    sourceQuestionID: q.questionID,
    question,
    questionClean: L.stripPrefix(question),
    options,
    optionLetters: slots.map(s => s.letter),
    optionCount: options.length,
    correctIndex,
    correctLetter,
    medicalTopic: q.medicalTopic || [],
    difficultLevel: q.difficultLevel,
  });
});

L.writeJson('01_clean.json', clean);
L.writeJson('01_duplicates.json', duplicates);
L.writeJson('01_dropped.json', dropped);

const byCount = {};
for (const r of clean) byCount[r.optionCount] = (byCount[r.optionCount] || 0) + 1;
const byReason = {};
for (const d of dropped) byReason[d.reason] = (byReason[d.reason] || 0) + 1;

console.log(`\n  giữ lại      : ${clean.length}`);
console.log(`  trùng lặp    : ${duplicates.length}`);
console.log(`  loại bỏ      : ${dropped.length}`, byReason);
console.log(`  số đáp án    :`, byCount);
console.log(`  uid duy nhất : ${new Set(clean.map(r => r.uid)).size} / ${clean.length}`);
