'use strict';
// Tầng 2 — phân loại bằng rule. Không biến đổi gì, chỉ gán nhãn nhóm
// cho từng câu để các tầng sau xử lý theo đúng cách.
const L = require('./lib');

const clean = L.readJson('01_clean.json');
console.log(`Tầng 2 — phân loại: ${clean.length} bản ghi`);

const classified = clean.map(r => {
  const tag = (group, reason, extra) => ({ ...r, group, reason, ...extra });

  if (r.optionCount < 4) return tag('none', 'insufficient_options');

  // --- nhóm A: đáp án meta ("Cả a,b đúng" / "Tất cả đều đúng") -----------
  const metas = r.options.map((o, i) => ({ i, meta: L.metaKind(o) })).filter(x => x.meta);
  if (metas.length) {
    const hit = metas.find(x => x.i === r.correctIndex);
    if (!hit) return tag('none', 'meta_is_distractor');           // đáp án đúng không phải meta -> suy luận không an toàn
    if (hit.meta.kind === 'ALL_WRONG') return tag('none', 'meta_all_wrong');
    return tag('meta', hit.meta.kind, {
      metaIndices: metas.map(x => x.i),
      metaLetters: hit.meta.letters || null,
    });
  }

  // --- nhóm B: câu tổ hợp "(1),(2),(3)" ----------------------------------
  if (r.options.every(L.isRefOnlyOption)) {
    const stmts = L.extractNumberedStatements(r.question);
    if (stmts && stmts.length >= 2) return tag('combination', 'numbered_stem', { statements: stmts });
    return tag('none', 'refs_without_stem');
  }

  // --- nhóm C: 4 đáp án dùng chung một pool từ vựng -----------------------
  const parts = r.options.map(L.splitItems);
  if (!parts.every(p => p.length >= 2)) return tag('none', 'not_all_lists');

  const flat = parts.flat();
  const surface = new Map();                       // normalized -> dạng hiển thị đầu tiên gặp
  for (const it of flat) if (!surface.has(L.normItem(it))) surface.set(L.normItem(it), it);
  const union = [...surface.keys()];

  const overlap = +(1 - union.length / flat.length).toFixed(3);
  const numericFrac = +(union.filter(L.isNumericish).length / union.length).toFixed(2);
  const allRoman = union.every(L.isRoman);

  if (numericFrac > 0.6 && !allRoman) return tag('none', 'numeric_pool', { overlap, numericFrac });
  if (overlap < 0.2) return tag('none', 'low_overlap', { overlap, numericFrac });

  return tag('pool', overlap >= 0.4 ? 'overlap_high' : 'overlap_medium', {
    poolType: allRoman ? 'roman' : 'lexical',
    overlap,
    numericFrac,
    pool: union.map(k => surface.get(k)),
    optionItems: parts.map(p => p.map(it => union.indexOf(L.normItem(it)))),
  });
});

L.writeJson('02_classified.json', classified);

const summary = {};
for (const r of classified) {
  const k = `${r.group}:${r.reason}`;
  summary[k] = (summary[k] || 0) + 1;
}
console.log('\n  Phân bố nhóm:');
for (const [k, v] of Object.entries(summary).sort((a, b) => b[1] - a[1])) {
  console.log(`    ${String(v).padStart(5)}  ${k}`);
}
const conv = classified.filter(r => r.group !== 'none').length;
console.log(`\n  Tổng ứng viên chuyển đổi được: ${conv} (${(100 * conv / classified.length).toFixed(1)}%)`);
