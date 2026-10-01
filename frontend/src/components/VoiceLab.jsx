import React, { useEffect, useState } from 'react';
import { Mic2, Loader2, AlertTriangle, Download, Volume2 } from 'lucide-react';
import axios from 'axios';
import { API_BASE_URL } from '../api';

const UI = {
  maxChars: 2000,
  defaultVoiceFallback: 'es-ES-AlvaroNeural',
};

export default function VoiceLab() {
  const [text, setText] = useState('');
  const [voices, setVoices] = useState([]);
  const [voice, setVoice] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [audioName, setAudioName] = useState('');

  useEffect(() => {
    let active = true;
    axios
      .get(`${API_BASE_URL}/voices`, { timeout: 15000 })
      .then(({ data }) => {
        if (!active || !Array.isArray(data)) return;
        const es = data
          .filter((v) => typeof v === 'object' && v.ShortName?.startsWith('es-'))
          .slice(0, 8);
        setVoices(es);
        setVoice(es[0]?.ShortName ?? UI.defaultVoiceFallback);
      })
      .catch(() => {
        if (active) setVoice(UI.defaultVoiceFallback);
      });
    return () => { active = false; };
  }, []);

  const generate = async () => {
    setError(null);
    setAudioUrl(null);
    setGenerating(true);
    const name = `voz-${Date.now()}.mp3`;
    try {
      await axios.post(
        `${API_BASE_URL}/tts/generate`,
        { text: text.trim(), voice, output_name: name },
        { timeout: 120000 },
      );
      setAudioUrl(`${API_BASE_URL}/music/audio/${encodeURIComponent(name)}`);
      setAudioName(name);
    } catch (e) {
      setError(e?.response?.data?.detail ?? e.message);
    } finally {
      setGenerating(false);
    }
  };

  const canGenerate = text.trim().length > 0 && !generating && voice;

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto w-full px-16 py-12 flex flex-col gap-6 fade-up">
        {/* Editor de texto */}
        <div className="rack corner relative">
          <div className="rack-head">
            <span className="dot" />
            VOZ · TEXTO A LOCUCIÓN
            <span className="ml-auto mono text-[9px] text-[var(--faint)]">{text.length} / {UI.maxChars}</span>
          </div>
          <div className="rack-body flex flex-col gap-5">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, UI.maxChars))}
              placeholder="Escribe aquí el texto que quieres escuchar…"
              className="bg-transparent! outline-none resize-none text-[17px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[180px] font-medium"
            />
            <div className="flex items-center justify-between pt-3 border-t border-[var(--line)] gap-4">
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="max-w-[260px] text-[11.5px] font-bold"
              >
                {voices.length === 0 && <option value={UI.defaultVoiceFallback}>Voz por defecto (es-ES)</option>}
                {voices.map((v) => (
                  <option key={v.ShortName} value={v.ShortName} className="bg-[#12121a]">
                    {v.DisplayName ?? v.ShortName} — {v.Gender === 'Female' ? '♀' : '♂'}
                  </option>
                ))}
              </select>
              <button onClick={generate} disabled={!canGenerate} className="btn btn-signal px-6 h-10">
                {generating ? <Loader2 size={15} className="animate-spin" /> : <Volume2 size={15} />}
                {generating ? 'GENERANDO…' : 'ESCUCHAR'}
              </button>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="rack fade-up" style={{ borderColor: 'rgba(255,92,92,0.4)' }}>
            <div className="rack-body flex items-center gap-3 text-sm text-red-300">
              <AlertTriangle size={16} /> <span className="mono text-[11px]">{error}</span>
            </div>
          </div>
        )}

        {/* Resultado */}
        {audioUrl && (
          <div className="rack fade-up">
            <div className="rack-head">
              <span className="dot" />
              RESULTADO · LOCUCIÓN
              <a href={audioUrl} download={audioName} className="ml-auto btn-chip flex items-center gap-1.5">
                <Download size={11} /> MP3
              </a>
            </div>
            <div className="rack-body flex items-center gap-5">
              <div className="w-11 h-11 rounded-[4px] bg-[var(--acc-dim)] border border-[var(--acc-line)] flex items-center justify-center shrink-0">
                <Mic2 size={18} className="text-[var(--acc)]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="mono text-[10px] tracking-[0.12em] text-[var(--acc)] mb-2">LOCUCIÓN LISTA</p>
                <audio key={audioUrl} controls autoPlay src={audioUrl} className="player" />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
