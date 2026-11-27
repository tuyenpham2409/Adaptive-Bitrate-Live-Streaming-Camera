// node tests/test_abr_port.js  - the JS HybridCore must give the same decisions as the Python Hybrid.
const fs = require('fs'), path = require('path');
const { HybridCore } = require('../web/hybrid_abr.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'abr_vectors.json')));
let n = 0, bad = 0;
for (const c of cases) {
  const core = new HybridCore(c.bw);
  for (const e of c.events) {
    const out = core.onSegment(e.level, e.kbit, e.dur, e.buf, e.now); n++;
    if (out !== e.out) { bad++; if (bad < 5) console.log('MISMATCH', e, 'js=', out); }
  }
}
console.log(`${n} decisions checked, ${bad} mismatches`);
process.exit(bad ? 1 : 0);
