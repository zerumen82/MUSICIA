/** Selection provenance stays separate from editable details and derived prose. */
export const emptyStyleSelection = () => ({ main_style: null, influence_styles: [], include_descriptions: true });

const same = (left, right) => String(left ?? '').trim().toLowerCase() === String(right ?? '').trim().toLowerCase();

const sameList = (left, right) => left.length === right.length
  && left.every((item, index) => same(item, right[index]));

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

export function stylePromptRequest(prompt, selection = emptyStyleSelection(),
                                   exclusion_source = null) {
  return { prompt: String(prompt ?? '').trim(), ...selection, bpm: null,
           ...(exclusion_source ? { exclusion_source } : {}) };
}

export function stylePromptKey(request) { return JSON.stringify(request); }

/**
 * Papeles del estilo: principal, matices y ficha de descripción.
 *
 * En «Por pistas» la pista hereda del prompt general papel por papel: lo que
 * el usuario no toca en la pista sigue viniendo del general; lo que toca
 * manda en la pista. Un papel tocado queda en la pista: si lo quitas, no
 * vuelve a insertarse solo.
 */
export const emptyTouchedRoles = () => ({ main: false, influence: false, descriptions: false });

/** Papeles que cambian entre dos selecciones efectivas. */
export function touchedRoles(before, after) {
  const left = before ?? emptyStyleSelection();
  const right = after ?? emptyStyleSelection();
  return {
    main: !same(left.main_style, right.main_style),
    influence: !sameList(left.influence_styles ?? [], right.influence_styles ?? []),
    descriptions: Boolean(left.include_descriptions) !== Boolean(right.include_descriptions),
  };
}

/**
 * El estilo que ve y puede tocar el usuario en una pista.
 *
 * La herencia va PAPEL POR PAPEL: principal, matices y ficha. Lo que el
 * usuario no toca en la pista sigue viniendo del prompt general; lo que toca
 * pasa a ser de la pista y manda ahí. Un papel tocado no vuelve a heredarse.
 *
 * El principal propio define el estilo completo de la pista: sus matices son
 * los suyos, no los del general. Sin principal propio, los matices heredados
 * se mantienen salvo que la pista toque ese papel.
 */
export function effectiveTrackSelection(own, touched, global) {
  const roles = (touched && typeof touched === 'object') ? touched : emptyTouchedRoles();
  const mine = own ?? emptyStyleSelection();
  const base = global ?? emptyStyleSelection();
  const ownInfluence = [...(mine.influence_styles ?? [])];
  return {
    main_style: roles.main ? (mine.main_style ?? null) : (base.main_style ?? null),
    influence_styles: (roles.influence || roles.main) ? ownInfluence : [...(base.influence_styles ?? [])],
    include_descriptions: roles.descriptions
      ? Boolean(mine.include_descriptions)
      : (base.include_descriptions ?? true),
  };
}

/**
 * Aplica una acción de estilo a una pista y devuelve su estado nuevo.
 *
 * La acción parte de la selección EFECTIVA (lo que el usuario ve) y la
 * modifica. Los papeles que cambian pasan a ser de la pista; los demás
 * siguen heredados del prompt general. Lo que se quita no se reinserta.
 */
export function applyTrackAction(own, touched, global, action) {
  const before = effectiveTrackSelection(own, touched, global);
  const after = typeof action === 'function' ? action(before) : action;
  const previousRoles = touched && typeof touched === 'object' ? touched : emptyTouchedRoles();
  if (!after) {
    return { own: own ?? emptyStyleSelection(), touched: previousRoles, effective: before };
  }
  const changed = touchedRoles(before, after);
  const roles = {
    main: previousRoles.main || changed.main,
    influence: previousRoles.influence || changed.influence,
    descriptions: previousRoles.descriptions || changed.descriptions,
  };
  const next = {
    main_style: roles.main ? (after.main_style ?? null) : (own?.main_style ?? null),
    influence_styles: roles.influence
      ? [...(after.influence_styles ?? [])]
      : [...(own?.influence_styles ?? [])],
    include_descriptions: roles.descriptions
      ? Boolean(after.include_descriptions)
      : (own?.include_descriptions ?? true),
  };
  return { own: next, touched: roles, effective: effectiveTrackSelection(next, roles, global) };
}

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
