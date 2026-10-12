/** Libera las lecturas de audio antes de borrar el archivo en Windows.
 * Pausar conserva el recurso abierto; quitar src y cargar lo descarga.
 * Se recorren también los reproductores de pestañas montadas pero ocultas.
 */
export function releaseAudioSources(urls, root = globalThis.document) {
  if (!root) return;
  const sources = new Set(urls.map((url) => new URL(url, root.baseURI).href));
  for (const audio of root.querySelectorAll('audio')) {
    if (!sources.has(audio.src) && !sources.has(audio.currentSrc)) continue;
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
  }
}
