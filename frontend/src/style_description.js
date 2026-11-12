/** Read exact server-backed descriptions; never infer a recipe from a subgenre. */
export function descriptionFor(descriptions, label) {
  if (!descriptions || !Object.hasOwn(descriptions, label)) return null;
  const description = descriptions[label];
  return typeof description?.text === 'string' && description.text.trim() ? description : null;
}

/** Sources are explicit links only; a catalog entry cannot create executable URLs. */
export function descriptionSourceUrl(value) {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
