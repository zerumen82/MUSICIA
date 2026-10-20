import test from 'node:test'
import assert from 'node:assert/strict'
import { currentProcessLogStreams } from './process_log_view.js'

test('console view keeps current logs but hides archived startup copies', () => {
  const streams = currentProcessLogStreams([{
    id: 'engine_stdout',
    present: true,
    text: 'current run',
    backup_present: true,
    backup_text: 'previous run',
  }])

  assert.deepEqual(streams, [{
    id: 'engine_stdout',
    present: true,
    text: 'current run',
  }])
})
