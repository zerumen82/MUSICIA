/** Guía ÚNICA del prompt para toda la app: cómo entiende el texto el modelo
 *  local (ACE-Step SFT). Vive aquí como dato; ningún sitio escribe su propia
 *  versión. Sirve también sin glosario: con estas reglas el usuario puede
 *  montar prompts que el modelo interprete bien. */
export const PROMPT_GUIDE = [
  'El modelo (ACE-Step SFT) recibe UN texto y lo sigue literal. Móntalo con: género/estilo, instrumentos concretos, tempo (BPM), energía (subidón/bajón), textura (distorsión, reverb) y estructura (intro, build, drop, breakdown, outro).',
  'Puedes escribirlo en español: Musicia lo traduce al inglés y te muestra la frase exacta que recibirá el modelo (Se envía / LEÍDO) antes de lanzar nada.',
  'Palabras útiles: build-up, drop, breakdown, riser, sweep, sub-bass, distorted kick, reverb tail, sidechain, 4x4, offbeat hi-hat.',
  'Ejemplo montado: «italo-disco instrumental, four-on-the-floor drum machine, punchy sequenced synth bass, bright brassy synth stabs, energetic build into a drop, 120 bpm».',
  'No entiende instrucciones de mezcla (volumen, pan, EQ): eso se hace con los controles de pistas y mezcla de Musicia.',
];
