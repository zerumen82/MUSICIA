import { useEffect, useState } from 'react';
import { api, isTransportBlip, PROMPT_PREVIEW_DEBOUNCE_MS, TRANSPORT_ERROR_CLEAR_MS } from './api';
import { emptyStyleSelection, stylePromptKey, stylePromptRequest, stylePromptStatus } from './style_prompt';

/** Requests are keyed by their complete input, so stale responses cannot be sent. */
export function usePreparedStylePrompts(inputs) {
  const [answers, setAnswers] = useState({});
  const encoded = JSON.stringify(inputs);
  useEffect(() => {
    let active = true;
    const retryTimers = new Map();
    const waitToRetry = () => new Promise((resolve) => {
      const timer = setTimeout(() => { retryTimers.delete(timer); resolve(); }, TRANSPORT_ERROR_CLEAR_MS);
      retryTimers.set(timer, resolve);
    });
    const prepare = async (id, request) => {
      const key = stylePromptKey(request);
      while (active) {
        try {
          const result = await api.enhancePrompt(request);
          if (typeof result?.enhanced !== 'string') throw new Error('El preparador no devolvió un prompt válido.');
          if (active) setAnswers((previous) => ({ ...previous, [id]: { key, result } }));
          return;
        } catch (error) {
          if (!active) return;
          const retrying = isTransportBlip(error.message);
          setAnswers((previous) => ({ ...previous, [id]: { key, error: error.message || 'No se pudo preparar el prompt.', retrying } }));
          if (!retrying) return;
          await waitToRetry();
        }
      }
    };
    const timer = setTimeout(() => {
      for (const [id, request] of Object.entries(JSON.parse(encoded))) {
        if (!(request.prompt || request.main_style || request.influence_styles.length)
          || (request.influence_styles.length && !request.main_style)) continue;
        void prepare(id, request);
      }
    }, PROMPT_PREVIEW_DEBOUNCE_MS);
    return () => {
      active = false;
      clearTimeout(timer);
      for (const [retryTimer, resolve] of retryTimers) { clearTimeout(retryTimer); resolve(); }
      retryTimers.clear();
    };
  }, [encoded]);
  return Object.fromEntries(Object.entries(inputs).map(([id, request]) => [id, stylePromptStatus(request, answers[id])]));
}

export default function useStylePrompt(prompt, exclusionSource = null) {
  const [selection, setSelection] = useState(emptyStyleSelection);
  const state = usePreparedStylePrompts({ prompt: stylePromptRequest(prompt, selection, exclusionSource) }).prompt;
  return { ...state, selection, setSelection };
}
