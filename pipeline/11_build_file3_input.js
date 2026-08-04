'use strict';
// FILE 3 (bước 1/3) — lọc câu có >= 1 dấu phẩy ở MỌI phương án và đóng gói
// đầu vào cho LLM. Chỉ đưa 3 trường: question, options, correctAnswer.
const L = require('./lib');

const clean = L.readJson('01_clean.json');
const hit = clean.filter(r => r.options.every(o => o.includes(',')));

const items = hit.map(r => ({
  uid: r.uid,
  sourceIndex: r.sourceIndex,
  payload: {                                  // đúng 3 trường sẽ nhét vào prompt
    question: r.question,
    options: Object.fromEntries(r.optionLetters.map((le, i) => [le, r.options[i]])),
    correctAnswer: 'option' + r.correctLetter,
  },
}));

L.writeJson('11_file3_llm_input.json', items);

const chars = items.reduce((a, x) => a + JSON.stringify(x.payload).length, 0);
console.log(`FILE 3 bước 1 — lọc dấu phẩy: ${items.length} câu`);
console.log(`  payload trung bình : ${Math.round(chars / items.length)} ký tự/câu`);
console.log(`  tổng               : ~${Math.round(chars / 2.7 / 1000)}k token (chưa tính prompt khung)`);
console.log('\n  --- payload mẫu ---');
console.log('  ' + JSON.stringify(items[0].payload, null, 1).replace(/\n/g, '\n  ').slice(0, 420));
