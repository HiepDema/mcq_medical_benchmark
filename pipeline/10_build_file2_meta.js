'use strict';
// FILE 2 — câu có đáp án đúng là "Tất cả đều đúng" / "Cả a, b đều đúng".
// Theo yêu cầu: GIỮ NGUYÊN Y HỆT bản ghi gốc, không xử lý gì.
const L = require('./lib');

const raw = L.readRawData();
const clean = L.readJson('01_clean.json');

const out = [], prov = [];

for (const r of clean) {
  if (r.optionCount < 4) continue;
  const meta = L.metaKind(r.options[r.correctIndex]);
  if (!meta || meta.kind === 'ALL_WRONG') continue;      // "tất cả đều sai" không thuộc dạng này

  out.push(raw[r.sourceIndex]);                          // nguyên văn, không đụng vào
  prov.push({
    questionID: r.sourceQuestionID, uid: r.uid, sourceIndex: r.sourceIndex,
    metaKind: meta.kind, metaLetters: meta.letters || null,
    correctAnswer: 'option' + r.correctLetter, metaText: r.options[r.correctIndex],
  });
}

L.writeJson('final_02_tat_ca_deu_dung.json', out);
L.writeJson('final_02_tat_ca_deu_dung_provenance.json', prov);

const byKind = {};
for (const p of prov) byKind[p.metaKind] = (byKind[p.metaKind] || 0) + 1;
console.log(`FILE 2 — giữ nguyên bản gốc: ${out.length} câu`, byKind);
console.log('  (ALL_CORRECT = "Tất cả đều đúng" · LETTERS = "Cả a, b đúng")');

const sample = out[0];
console.log('\n  --- 1 bản ghi mẫu (nguyên văn raw_data.json) ---');
console.log('  ' + JSON.stringify(sample).slice(0, 320));
