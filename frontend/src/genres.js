/**
 * 29 estilos oficiales de Musicia alineados al 100% con el catálogo del modelo
 * (backend/style_catalog.json) y el vocabulario de géneros (genres_vocab.txt).
 *
 * Cada estilo tiene:
 * - id: clave identificadora única (coincide con name de style_catalog.json).
 * - label: nombre en español para la UI.
 * - bpm: tempo típico oficial del estilo.
 * - genre: término canónico que el modelo reconoce directamente en el prompt.
 */

export const CATALOG_GENRES = [
  { id: 'techno', label: 'Techno', bpm: 135, genre: 'techno' },
  { id: 'house', label: 'House', bpm: 124, genre: 'house' },
  { id: 'electronica', label: 'Electrónica', bpm: 128, genre: 'electronica' },
  { id: 'electro', label: 'Electro', bpm: 128, genre: 'electro' },
  { id: 'synthwave', label: 'Synthwave', bpm: 100, genre: 'synthwave' },
  { id: 'drum and bass', label: 'Drum and Bass', bpm: 174, genre: 'drum and bass' },
  { id: 'dubstep', label: 'Dubstep', bpm: 140, genre: 'dubstep' },
  { id: 'trance', label: 'Trance', bpm: 138, genre: 'trance' },
  { id: 'hard techno', label: 'Hard techno', bpm: 145, genre: 'hard techno' },
  { id: 'hardstyle', label: 'Hardstyle', bpm: 150, genre: 'hardstyle' },
  { id: 'hardcore holandes', label: 'Hardcore holandés', bpm: 180, genre: 'hardcore holandes' },
  { id: 'frenchcore', label: 'Frenchcore', bpm: 170, genre: 'frenchcore' },
  { id: 'uptempo hard dance', label: 'Uptempo hard dance', bpm: 160, genre: 'uptempo' },
  { id: 'hard bounce', label: 'Hard bounce', bpm: 140, genre: 'hard bounce' },
  { id: 'lo-fi', label: 'Lo-fi', bpm: 85, genre: 'lo-fi' },
  { id: 'hip hop', label: 'Hip hop', bpm: 90, genre: 'hip hop' },
  { id: 'trap', label: 'Trap', bpm: 140, genre: 'trap' },
  { id: 'reggaeton', label: 'Reggaeton', bpm: 95, genre: 'reggaeton' },
  { id: 'rock', label: 'Rock', bpm: 120, genre: 'rock' },
  { id: 'metal', label: 'Metal', bpm: 145, genre: 'metal' },
  { id: 'pop', label: 'Pop', bpm: 110, genre: 'pop' },
  { id: 'jazz', label: 'Jazz', bpm: 110, genre: 'jazz' },
  { id: 'funk', label: 'Funk / Disco', bpm: 115, genre: 'funk' },
  { id: 'folk acustico', label: 'Folk / Acústico', bpm: 95, genre: 'acustico' },
  { id: 'flamenco', label: 'Flamenco', bpm: 100, genre: 'flamenco' },
  { id: 'salsa', label: 'Salsa', bpm: 100, genre: 'salsa' },
  { id: 'reggae', label: 'Reggae', bpm: 90, genre: 'reggae' },
  { id: 'ambient', label: 'Ambient', bpm: 70, genre: 'ambient' },
  { id: 'orquestal', label: 'Orquestal / Épica', bpm: 100, genre: 'orquestal' },
];

/**
 * Busca un género por su id o por coincidencia con su nombre/etiqueta.
 */
export function findGenre(idOrName) {
  if (!idOrName) return null;
  const needle = String(idOrName).toLowerCase().trim();
  return CATALOG_GENRES.find(
    (g) => g.id.toLowerCase() === needle || g.label.toLowerCase() === needle || g.genre.toLowerCase() === needle
  ) ?? null;
}
