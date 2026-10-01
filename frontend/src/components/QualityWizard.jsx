import React, { useState } from 'react';
import { X, ArrowRight, ArrowLeft, Wand2 } from 'lucide-react';

/**
 * Asistente de obra de calidad: 5 preguntas con opciones sugeridas.
 * No genera nada por sí mismo: devuelve una especificación que prellena
 * el Composer (género, mood, bpm, tono, duración, texto libre).
 */
const STEPS = ['PROPÓSITO', 'GÉNERO Y CARÁCTER', 'TEMPO Y TONO', 'DURACIÓN', 'INSTRUMENTACIÓN'];

const PURPOSES = [
  { id: 'escuchar', tag: 'Para escuchar', extra: 'estructura de canción con evolución' },
  { id: 'fondo', tag: 'Música de fondo', extra: 'textura continua sin cambios bruscos' },
  { id: 'video', tag: 'Para vídeo', extra: 'con entrada clara y final resuelto' },
  { id: 'dormir', tag: 'Relajarse/dormir', extra: 'muy suave, sin percusión agresiva' },
];

const MOODS = [
  { id: 'alegre', tag: 'Alegre', words: 'luminoso y optimista' },
  { id: 'epico', tag: 'Épico', words: 'épico y grandioso' },
  { id: 'melancolico', tag: 'Melancólico', words: 'melancólico y nostálgico' },
  { id: 'oscuro', tag: 'Oscuro', words: 'oscuro y tenso' },
  { id: 'chill', tag: 'Chill', words: 'relajado y cálido' },
  { id: 'energico', tag: 'Enérgico', words: 'enérgico y potente' },
];

const GENRES = [
  { id: 'lofi', tag: 'Lo-fi', style: 'lo-fi hip hop con piano suave y vinilo' },
  { id: 'techno', tag: 'Techno', style: 'techno con bombo seco y sintes' },
  { id: 'orquestal', tag: 'Orquestal', style: 'orquestal con cuerdas y percusión' },
  { id: 'ambient', tag: 'Ambient', style: 'ambient con pads largos y aire' },
  { id: 'acustico', tag: 'Acústico', style: 'acústico con guitarras y folk' },
  { id: 'electro', tag: 'Electrónica', style: 'electrónica moderna con bajos profundos' },
];

const TEMPOS = [
  { id: 'slow', tag: 'Lento', bpm: 70 },
  { id: 'mid', tag: 'Medio', bpm: 100 },
  { id: 'fast', tag: 'Rápido', bpm: 128 },
  { id: 'auto', tag: 'Como el género', bpm: null },
];

const KEYS = [
  { id: '', tag: 'Cualquiera' },
  { id: 'C major', tag: 'Do M (luminoso)' },
  { id: 'A minor', tag: 'La m (nostálgico)' },
  { id: 'D minor', tag: 'Re m (melancólico)' },
  { id: 'E minor', tag: 'Mi m (tenso)' },
];

const DURATIONS = [
  { id: '30', tag: '30 s · idea', value: 30 },
  { id: '60', tag: '1 min · corto', value: 60 },
  { id: '120', tag: '2 min · estándar', value: 120 },
  { id: '180', tag: '3 min · canción', value: 180 },
];

const TEXTURES = [
  { id: 'solo', tag: 'Un instrumento protagonista', extra: 'un solo instrumento protagonista íntimo' },
  { id: 'grupo', tag: 'Grupo completo', extra: 'arreglos completos de banda' },
  { id: 'electronico', tag: 'Producción electrónica', extra: 'producción electrónica con capas de sintes' },
  { id: 'hibrido', tag: 'Híbrido acústico+digital', extra: 'híbrido de instrumentos acústicos y electrónicos' },
];

export default function QualityWizard({ onClose, onApply }) {
  const [step, setStep] = useState(0);
  const [purpose, setPurpose] = useState(null);
  const [genre, setGenre] = useState(null);
  const [mood, setMood] = useState(null);
  const [tempo, setTempo] = useState(null);
  const [key, setKey] = useState('');
  const [duration, setDuration] = useState(null);
  const [texture, setTexture] = useState(null);

  const canNext =
    (step === 0 && purpose) ||
    (step === 1 && genre && mood) ||
    (step === 2 && tempo) ||
    (step === 3 && duration) ||
    (step === 4 && texture);

  const buildResult = () => {
    const g = GENRES.find((x) => x.id === genre);
    const m = MOODS.find((x) => x.id === mood);
    const t = TEMPOS.find((x) => x.id === tempo);
    const p = PURPOSES.find((x) => x.id === purpose);
    const tx = TEXTURES.find((x) => x.id === texture);
    const parts = [
      g?.style,
      m?.words,
      p?.extra,
      tx?.extra,
    ].filter(Boolean);
    return {
      prompt: parts.join(', '),
      genre: g?.tag ?? null,
      mood: m?.tag ?? null,
      bpm: t?.bpm ?? null,
      key_scale: key || null,
      duration: duration ? Number(duration) : null,
      summary: [p?.tag, g?.tag, m?.tag, t?.tag, tx?.tag].filter(Boolean).join(' · '),
    };
  };

  const optionsRow = (options, value, setter, renderLabel) => (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button key={opt.id} onClick={() => setter(opt.id)}
          className={`btn-chip ${value === opt.id ? 'active' : ''}`}>
          {renderLabel ? renderLabel(opt) : opt.tag}
        </button>
      ))}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-8">
      <div className="w-full max-w-[640px] bg-[var(--surface)] border border-[var(--line-strong)] flex flex-col max-h-[86vh]">
        {/* Cabecera */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-[var(--line)] bg-[var(--surface-2)]">
          <Wand2 size={15} className="text-[var(--acc)]" />
          <span className="mono text-[11px] tracking-[0.14em] text-[var(--acc)]">ASISTENTE DE CALIDAD</span>
          <span className="mono text-[9.5px] text-[var(--faint)] ml-auto">PASO {step + 1}/5 · {STEPS[step]}</span>
          <button onClick={onClose} className="text-[var(--faint)] hover:text-red-300 ml-2"><X size={15} /></button>
        </div>

        {/* Pasos como puntos */}
        <div className="flex gap-1.5 px-6 pt-4">
          {STEPS.map((s, i) => (
            <span key={s} className={`h-1 flex-1 ${i <= step ? 'bg-[var(--acc)]' : 'bg-[var(--surface-3)]'}`} />
          ))}
        </div>

        <div className="p-6 flex flex-col gap-5 overflow-y-auto">
          {step === 0 && (
            <>
              <Question title="¿Para qué es esta pieza?" />
              {optionsRow(PURPOSES, purpose, setPurpose)}
            </>
          )}
          {step === 1 && (
            <>
              <Question title="¿Qué género encaja?" />
              {optionsRow(GENRES, genre, setGenre)}
              <Question title="¿Y el carácter de la pieza?" />
              {optionsRow(MOODS, mood, setMood)}
            </>
          )}
          {step === 2 && (
            <>
              <Question title="¿Qué tempo tiene que tener?" />
              {optionsRow(TEMPOS, tempo, setTempo, (o) => `${o.tag}${o.bpm ? ` · ${o.bpm}` : ''}`)}
              <Question title="¿Tonalidad?" />
              {optionsRow(KEYS, key, setKey)}
            </>
          )}
          {step === 3 && (
            <>
              <Question title="¿Cuánto debe durar?" />
              {optionsRow(DURATIONS, duration, setDuration, (o) => o.tag)}
            </>
          )}
          {step === 4 && (
            <>
              <Question title="¿Qué tipo de instrumentación?" />
              {optionsRow(TEXTURES, texture, setTexture)}
            </>
          )}
        </div>

        {/* Navegación */}
        <div className="flex items-center gap-3 px-6 py-4 border-t border-[var(--line)]">
          {step > 0 && (
            <button onClick={() => setStep(step - 1)} className="btn btn-ghost h-9 px-4">
              <ArrowLeft size={13} /> ATRÁS
            </button>
          )}
          <span className="mono text-[9.5px] text-[var(--faint)] ml-auto">
            TODO SE PUEDE EDITAR DESPUÉS EN CREAR
          </span>
          {step < 4 ? (
            <button onClick={() => setStep(step + 1)} disabled={!canNext} className="btn btn-signal h-9 px-5">
              SIGUIENTE <ArrowRight size={13} />
            </button>
          ) : (
            <button onClick={() => onApply(buildResult())} disabled={!canNext} className="btn btn-signal h-9 px-5">
              <Wand2 size={13} /> APLICAR EN CREAR
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Question({ title }) {
  return <p className="text-[14.5px] font-semibold text-zinc-200">{title}</p>;
}
