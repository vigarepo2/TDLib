/* Exercise the compiled browser module without signing into Telegram. */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const directory = path.resolve(process.argv[2]);
const createModule = require(path.join(directory, 'td_wasm.js'));
const deadline = setTimeout(() => { console.error('TDLib WebAssembly startup timed out'); process.exit(1); }, 60000);
(async () => {
  // Passing bytes avoids Node/browser fetch differences; browsers use the same wasm.
  const td = await createModule({wasmBinary: fs.readFileSync(path.join(directory, 'td_wasm.wasm'))});
  const execute = td.cwrap('td_emscripten_execute', 'string', ['string']);
  const result = JSON.parse(execute(JSON.stringify({'@type': 'getTextEntities', text: 'https://telegram.org'})));
  assert.strictEqual(result['@type'], 'textEntities');
  assert.ok(result.entities.length > 0);
  clearTimeout(deadline);
  console.log('TDLib WebAssembly JSON API smoke test passed');
  process.exit(0);
})().catch(error => { console.error(error); process.exit(1); });
