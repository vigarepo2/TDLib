// An offline query. Koffi is the adapter from JavaScript to TDLib's C JSON ABI.
import koffi from 'koffi';

const tdlib = koffi.load(process.env.TDLIB_LIBRARY_PATH || 'libtdjson.so');
const execute = tdlib.func('const char *td_execute(const char *request)');
const result = execute(JSON.stringify({ '@type': 'getOption', name: 'version' }));
if (result === null) throw new Error('TDLib did not return a synchronous response');
console.log(JSON.parse(result));
