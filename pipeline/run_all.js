'use strict';
// Chạy toàn bộ pipeline theo thứ tự. Idempotent: chạy lại cho kết quả y hệt.
const { execFileSync } = require('child_process');
const path = require('path');

const stages = [
  '01_clean.js', '02_classify.js', '03_convert_meta.js',
  '04_convert_combination.js', '05_prepare_pool.js', '06_merge_validate.js',
];

for (const s of stages) {
  console.log(`\n${'='.repeat(64)}\n${s}\n${'='.repeat(64)}`);
  execFileSync(process.execPath, [path.join(__dirname, s)], { stdio: 'inherit' });
}
console.log('\nHoàn tất. raw_data.json không bị ghi đè ở bất kỳ tầng nào.');
