/** Selection provenance stays separate from editable details and derived prose. */
export const emptyStyleSelection = () => ({ main_style: null, influence_styles: [], include_descriptions: true });

const same = (left, right) => String(left ?? '').trim().toLowerCase() === String(right ?? '').trim().toLowerCase();

export function chooseStyle(selection, term, role) {
  const value = String(term ?? '').trim();
  if (!value) return selection;
  if (role === 'main') return {
    ...selection,
    main_style: same(selection.main_style, value) ? null : value,
    influence_styles: selection.influence_styles.filter((item) => !same(item, value)),
  };
  return {
    ...selection,
    main_style: same(selection.main_style, value) ? null : selection.main_style,
    influence_styles: selection.influence_styles.some((item) => same(item, value))
      ? selection.influence_styles.filter((item) => !same(item, value))
      : [...selection.influence_styles, value],
  };
}

export function stylePromptRequest(prompt, selection = emptyStyleSelection()) {
  return { prompt: String(prompt ?? '').trim(), ...selection, bpm: null };
}

export function stylePromptKey(request) { return JSON.stringify(request); }

export function stylePromptStatus(request, answer) {
  const hasContent = Boolean(request.prompt || request.main_style || request.influence_styles.length);
  const missingMain = request.influence_styles.length > 0 && !request.main_style;
  const current = answer?.key === stylePromptKey(request) ? answer : null;
  return {
    ready: !hasContent || Boolean(!missingMain && current?.result),
    effectivePrompt: !missingMain && current?.result ? current.result.enhanced : '',
    result: current?.result ?? null,
    error: missingMain ? 'Elige un estilo principal para estos matices.' : current?.error ?? null,
    pending: hasContent && !missingMain && !current,
    retrying: Boolean(current?.retrying),
  };
}
