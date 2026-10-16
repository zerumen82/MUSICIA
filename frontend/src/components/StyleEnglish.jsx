import React, { useEffect, useState } from 'react';
import { api, PROMPT_PREVIEW_DEBOUNCE_MS } from '../api';

/** Muestra el inglés que el servidor enviará. El cuadro sigue en el idioma escrito. */
export default function StyleEnglish({ text, empty = '' }) {
  const trimmed = (text || '').trim();
  const [state, setState] = useState(null);
  useEffect(() => {
    if (!trimmed) return undefined;
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const result = await api.styleEnglish(trimmed);
        if (active) setState({ key: trimmed, prompt: result.prompt });
      } catch (error) {
        if (active) setState({ key: trimmed, error: error.message });
      }
    }, PROMPT_PREVIEW_DEBOUNCE_MS);
    return () => { active = false; clearTimeout(timer); };
  }, [trimmed]);
  if (!trimmed) {
    return empty
      ? <p className="text-[13px] text-[var(--text)]" data-track-phrase aria-label="Frase que se envía">{empty}</p>
      : null;
  }
  const current = state?.key === trimmed ? state : null;
  const shown = !current ? 'Traduciendo el estilo al inglés…' : (current.error || current.prompt);
  return <p className="text-[13px] text-[var(--text)]" data-track-phrase aria-label="Frase que se envía" role={current?.error ? 'alert' : 'status'}>
    <span className="text-[var(--muted)]">Se envía: </span>{shown}
  </p>;
}
