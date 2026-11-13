import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const esbuild = require('esbuild');
require.extensions['.jsx'] = (module, filename) => module._compile(esbuild.transformSync(fs.readFileSync(filename, 'utf8'), {
  loader: 'jsx', format: 'cjs', jsx: 'automatic', sourcefile: filename,
}).code, filename);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const RemixSequence = require(path.join(import.meta.dirname, 'components/RemixSequence.jsx')).default;
const capabilities = { sequence: { focuses: ['todo'], max_steps: 16, default_steps: 8,
  pattern: { steps: 16, instruments: ['kick', 'snare', 'hihat', 'cymbal'] } } };
const base = { steps: [{ index: 0, enabled: true, focus: 'todo', prompt: 'techno', patternEnabled: false }],
  onSteps: () => { throw new Error('Static rendering must not edit a step'); }, capabilities,
  prepared: { 0: { ready: true } }, sent: { 0: 'without a voice' }, busy: false };
const render = (props) => renderToStaticMarkup(React.createElement(RemixSequence, { ...base, ...props }));

test('el editor opcional de batería comienza oculto', () => {
  const html = render({});
  assert.ok(!html.includes('data-pattern-cell='));
  assert.ok(!html.includes('data-sequence-pattern-editor='));
});

test('un patrón activo se declara aunque su editor esté cerrado', () => {
  const html = render({ steps: [{ ...base.steps[0], patternEnabled: true, pattern: { kick: [true] } }] });
  assert.match(html, /PATRÓN ACTIVO/);
  assert.match(html, /Desactivar patrón del paso 1/);
  assert.ok(!html.includes('data-pattern-cell='));
});

test('el caption de un preview anterior no se muestra como enviado', () => {
  const html = render({ previewReady: false,
    preview: { sequence: { steps: [{ index: 0, start: 0, end: 8, effective_prompt: 'PREVIEW ANTERIOR' }] } } });
  assert.ok(!html.includes('PREVIEW ANTERIOR'));
  assert.match(html, /PREPARANDO VISTA/);
});

test('el caption actual muestra literalmente la respuesta del servidor', () => {
  const html = render({ previewReady: true,
    preview: { sequence: { steps: [{ index: 0, start: 0, end: 8, effective_prompt: 'CAPTION EXACTO DEL SERVIDOR' }] } } });
  assert.match(html, /CAPTION EXACTO DEL SERVIDOR/);
  assert.ok(!html.includes('without a voice'));
});

test('los tramos vienen del reparto aunque el caption no sea el actual', () => {
  const html = render({ previewReady: false,
    preview: { sequence: { steps: [{ index: 0, start: 0, end: 8, effective_prompt: 'PREVIEW ANTERIOR' }] } } });
  assert.match(html, /0:00–0:08/);
  assert.ok(!html.includes('PREVIEW ANTERIOR'));
});
