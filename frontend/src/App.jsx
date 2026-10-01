import React, { useEffect, useState } from 'react';
import { AudioWaveform, Mic2, Library as LibraryIcon, FileUp, SlidersHorizontal, LogOut } from 'lucide-react';
import Composer from './components/Composer';
import VoiceLab from './components/VoiceLab';
import Library from './components/Library';
import Uploads from './components/Uploads';
import MixLab from './components/MixLab';
import { api } from './api';

// Nota: el Mixer decorativo original se sustituye por MixLab (mezcla real
// vía POST /audio/mix). Sequencer sigue retirado (deuda T2 de spec/03).
const TABS = [
  { id: 'composer', icon: AudioWaveform, label: 'CREAR', hint: 'canciones IA' },
  { id: 'uploads', icon: FileUp, label: 'SUBIR', hint: 'tu audio + remix' },
  { id: 'mix', icon: SlidersHorizontal, label: 'MEZCLA', hint: 'base + voz' },
  { id: 'voice', icon: Mic2, label: 'VOZ', hint: 'texto a voz' },
  { id: 'library', icon: LibraryIcon, label: 'BIBLIOTECA', hint: 'tus MP3' },
];

const POLL_HEALTH_MS = 10000;

function App() {
  const [tab, setTab] = useState('composer');
  const [engine, setEngine] = useState({ checked: false, ok: false });

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const health = await api.engineHealth();
        if (alive) setEngine({ checked: true, ok: Boolean(health?.engine?.reachable) });
      } catch {
        if (alive) setEngine({ checked: true, ok: false });
      }
    };
    check();
    const t = setInterval(check, POLL_HEALTH_MS);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="app-container">
      {/* ===== NAV LATERAL ===== */}
      <aside className="relative z-10 w-[230px] shrink-0 h-full flex flex-col px-4 py-5 border-r border-[var(--line)] bg-[var(--surface)]">
        {/* Marca */}
        <div className="flex items-center gap-2.5 px-2 mb-7">
          <div className="w-8 h-8 rounded-[4px] bg-[var(--acc)] flex items-center justify-center shadow-[0_0_16px_rgba(184,255,41,0.35)]">
            <AudioWaveform className="text-[#0c0f04]" size={16} strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="text-[13.5px] font-extrabold tracking-tight leading-none">MUSICIA</h1>
            <span className="label text-[8px] mt-0.5 block">estudio local v1</span>
          </div>
        </div>

        {/* Canales */}
        <nav className="space-y-1">
          {TABS.map(({ id, icon: Icon, label, hint }) => (
            <button key={id} onClick={() => setTab(id)} className={`nav-item ${tab === id ? 'active' : ''}`}>
              <Icon size={14} strokeWidth={2.2} />
              <span className="flex flex-col leading-tight flex-1">
                <span>{label}</span>
                <span className="text-[9px] text-[var(--faint)] font-sans tracking-normal">{hint}</span>
              </span>
              {tab === id && <span className="w-1.5 h-1.5 rounded-full bg-[var(--acc)] shadow-[0_0_6px_var(--acc)]" />}
            </button>
          ))}
        </nav>

        {/* Salida: dispara el diálogo de cierre seguro (apagar motor / dejar activo) */}
        <button
          onClick={() => {
            // Cierra TODO sin preguntar: UI + API + motor (libera VRAM)
            if (window.musica?.exit) window.musica.exit('stop-all');
            else window.close();
          }}
          className="nav-item mt-4 hover:!text-red-300 hover:!border-[rgba(255,92,92,0.4)]"
          title="Salir de Musicia"
        >
          <LogOut size={14} strokeWidth={2.2} />
          <span>SALIR</span>
        </button>

        {/* Estado del motor (real, con polling) */}
        <div className="mt-3 px-1">
          <div className="panel-2 px-3 py-2.5 flex items-center gap-2.5">
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                engine.checked
                  ? engine.ok
                    ? 'bg-[var(--acc)] shadow-[0_0_8px_var(--acc)]'
                    : 'bg-[var(--err)]'
                  : 'bg-[var(--warn)] animate-pulse'
              }`}
            />
            <span className="mono text-[9.5px] tracking-[0.1em] uppercase text-[var(--muted)] leading-tight">
              {engine.checked
                ? engine.ok ? 'MOTOR ACTIVO' : 'MOTOR APAGADO'
                : 'CONECTANDO…'}
            </span>
          </div>
        </div>
      </aside>

      {/* ===== ZONA DE TRABAJO ===== */}
      <div className="relative z-10 flex-1 min-w-0 h-full flex flex-col">
        {/* Barra superior tipo transport */}
        <header className="h-12 shrink-0 flex items-center justify-between px-7 border-b border-[var(--line)] bg-[var(--surface)]">
          <div className="flex items-center gap-3">
            <span className="label">{TABS.find((t) => t.id === tab)?.label}</span>
            <span className="text-[var(--faint)] mono text-[11px]">/</span>
            <span className="mono text-[11px] text-[var(--muted)]">{TABS.find((t) => t.id === tab)?.hint}</span>
          </div>
          <div className="flex items-center gap-5">
            <span className="mono text-[10.5px] text-[var(--faint)] tracking-[0.12em]">100% LOCAL · SIN NUBE</span>
            <span className={`mono text-[10.5px] tracking-[0.12em] px-2.5 py-1 border ${
              engine.checked && engine.ok
                ? 'text-[var(--acc)] border-[var(--acc-line)]'
                : 'text-[var(--muted)] border-[var(--line-strong)]'
            }`}>
              MOTOR IA LOCAL
            </span>
          </div>
        </header>

        <main className="flex-1 min-h-0 overflow-y-auto">
          {tab === 'composer' && <Composer />}
          {tab === 'uploads' && <Uploads />}
          {tab === 'mix' && <MixLab />}
          {tab === 'voice' && <VoiceLab />}
          {tab === 'library' && <Library />}
        </main>
      </div>
    </div>
  );
}

export default App;
