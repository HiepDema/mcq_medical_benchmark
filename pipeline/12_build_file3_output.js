'use strict';
// FILE 3 (bước 3/3) — đọc phán quyết CÓ/KHÔNG của LLM, xử lý những câu "CÓ"
// thành dạng nhiều đáp án, ghi ra theo đúng format raw_data.json.
//
//   node pipeline/12_build_file3_output.js                # dùng kết quả LLM thật
//   node pipeline/12_build_file3_output.js --assume-yes   # coi mọi câu là "CÓ" (thử logic)
const fs = require('fs');
const path = require('path');
const L = require('./lib');

const ASSUME_YES = process.argv.includes('--assume-yes');
const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

const raw = L.readRawData();
const clean = new Map(L.readJson('01_clean.json').map(r => [r.uid, r]));
const input = L.readJson('11_file3_llm_input.json');

let verdicts;
if (ASSUME_YES) {
  verdicts = input.map(x => ({ uid: x.uid, verdict: 'CÓ' }));
  console.log('CHẾ ĐỘ THỬ: coi mọi câu là "CÓ" — chỉ để kiểm tra logic biến đổi.\n');
} else {
  const p = path.join(L.DATA_DIR, '12_file3_llm_verdicts.json');
  if (!fs.existsSync(p)) {
    console.error('Chưa có data/12_file3_llm_verdicts.json.');
    console.error('Chạy `python lambda/run_remote.py` để lấy kết quả từ Qwen3-VL,');
    console.error('hoặc chạy lại với --assume-yes để thử logic biến đổi.');
    process.exit(1);
  }
  verdicts = L.readJson('12_file3_llm_verdicts.json');
}

const said = new Map(verdicts.map(v => [v.uid, v.verdict]));
const out = [], prov = [], rejected = [];

for (const item of input) {
  const verdict = said.get(item.uid);
  if (verdict !== 'CÓ') continue;

  const r = clean.get(item.uid);
  const reject = reason => rejected.push({ uid: item.uid, reason, question: r.question, options: r.options });

  // Tách mục, gom pool giữ dạng hiển thị gặp đầu tiên.
  const parts = r.options.map(L.splitItems);
  const surface = new Map();
  for (const it of parts.flat()) if (!surface.has(L.normItem(it))) surface.set(L.normItem(it), it);
  const pool = [...surface.values()];

  const correctIdx = [...new Set(parts[r.correctIndex].map(it => pool.findIndex(p => L.normItem(p) === L.normItem(it))))]
    .filter(i => i >= 0).sort((a, b) => a - b);

  if (pool.length < 3) { reject('pool_too_small'); continue; }
  if (pool.length > LETTERS.length) { reject('pool_too_large'); continue; }
  if (correctIdx.length < 2) { reject('fewer_than_two_correct'); continue; }
  if (correctIdx.length >= pool.length) { reject('all_options_correct'); continue; }

  const src = raw[r.sourceIndex];
  const rec = {
    question: r.questionClean,
    correctAnswer: correctIdx.map(i => 'option' + LETTERS[i]).join(', '),
    medicalTopic: src.medicalTopic,
    difficultLevel: src.difficultLevel,
    regularFormat: src.regularFormat,
    questionID: src.questionID,
  };
  pool.forEach((p, i) => { rec['answer_option' + LETTERS[i]] = p; });
  out.push(rec);

  prov.push({
    questionID: src.questionID, uid: r.uid, sourceIndex: r.sourceIndex,
    originalOptions: r.options, originalCorrect: 'option' + r.correctLetter,
    newOptionCount: pool.length, newCorrect: rec.correctAnswer,
  });
}

L.writeJson('final_03_tach_dau_phay.json', out);
L.writeJson('final_03_tach_dau_phay_provenance.json', prov);
L.writeJson('final_03_tach_dau_phay_rejected.json', rejected);

const yes = verdicts.filter(v => v.verdict === 'CÓ').length;
const byReason = {}, dist = {};
for (const x of rejected) byReason[x.reason] = (byReason[x.reason] || 0) + 1;
for (const p of prov) dist[p.newCorrect.split(',').length] = (dist[p.newCorrect.split(',').length] || 0) + 1;

console.log(`FILE 3 — tách từ câu có dấu phẩy`);
console.log(`  LLM trả "CÓ"        : ${yes}/${verdicts.length}`);
console.log(`  biến đổi thành công : ${out.length}`);
console.log(`  loại khi biến đổi   : ${rejected.length}`, byReason);
console.log(`  số đáp án đúng/câu  :`, dist);

console.log('\n  --- 2 ví dụ ---');
for (let i = 0; i < Math.min(2, out.length); i++) {
  const rec = out[i], p = prov[i];
  console.log(`\n  ${rec.question.slice(0, 110)}`);
  console.log(`  GỐC: ${p.originalOptions.map((o, k) => `${LETTERS[k]}. ${o}`).join('  |  ').slice(0, 170)}`);
  console.log(`  MỚI (đáp án đúng: ${rec.correctAnswer}):`);
  LETTERS.slice(0, p.newOptionCount).forEach(le =>
    console.log(`     ${rec.correctAnswer.includes('option' + le) ? '[x]' : '[ ]'} ${le}. ${rec['answer_option' + le]}`));
}
