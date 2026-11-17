import React from 'react';
import InfoHint from './InfoHint';
import { PROMPT_GUIDE } from '../prompt_guide';

/** ⓘ único con la guía del prompt en toda la app. El contenido vive en
 *  `prompt_guide.js` como dato: ningún sitio escribe su propia versión. */
export default function PromptGuide({ label = 'Cómo montar el prompt para el modelo' }) {
  return <InfoHint label={label}>
    {PROMPT_GUIDE.map((line) => <span key={line} className="block">{line}</span>)}
  </InfoHint>;
}
