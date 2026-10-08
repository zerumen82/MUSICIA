import React, { useEffect, useRef, useState } from 'react';
import { AudioWaveform, Library as LibraryIcon, FileUp, SlidersHorizontal, LogOut } from 'lucide-react';
import Composer from './components/Composer';
import Library from './components/Library';
import Uploads from './components/Uploads';
import MixLab from './components/MixLab';
import { api, JOB_POLL_INTERVAL_MS } from './api';

// Nota: el Mixer decorativo original se sustituye por MixLab (mezcla real
// vía POST /audio/mix). Sequencer sigue retirado (deuda T2 de spec/03).
const TABS = [
  { id: 'composer', icon: AudioWaveform, label: 'CREAR', hint: 'canciones IA' },
  { id: 'uploads', icon: FileUp, label: 'SUBIR', hint: 'tu audio + remix' },
  { id: 'mix', icon: SlidersHorizontal, label: 'MEZCLA', hint: 'base + voz cantada' },
  { id: 'library', icon: LibraryIcon, label: 'BIBLIOTECA', hint: 'tus MP3' },
];

const POLL_HEALTH_MS = 10000;

function App() {
  const [tab, setTab] = useState('composer');
  const [engine, setEngine] = useState({ checked: false, ok: false });
  const [models, setModels] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const activeJobRef = useRef(null);
  // La cola la sondea App UNA vez cada 3 s y la reparte: la barra, el
  // auto-refresh de BIBLIOTECA/MEZCLA y JobsPanel beben del mismo tick.
  const [jobsFeed, setJobsFeed] = useState([]);
  // Cada vez que cambia lo que hay en outputs/, BIBLIOTECA se recarga sola
  // (huella del servidor, spec/02 [R1]: cubre trabajos encadenados, mezclas
  // DSP síncronas y borrados, que no pasan por la cola de jobs).
  const [libraryTick, setLibraryTick] = useState(0);
  const libraryVersionRef = useRef(null);

  useEffect(() => {
    activeJobRef.current = activeJob;
  }, [activeJob]);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      const health = await api.engineHealth();
      if (!alive) return;
      if (health?.engine?.reachable) {
        setEngine({ checked: true, ok: true });
        return;
      }
      // Sin respuesta, motor ocupado o canción en curso: no se pinta apagado.
      if (health?.engine?.unknown || health?.engine?.busy || activeJobRef.current) return;
      setEngine({ checked: true, ok: false });
    };
    // Modelo y VRAM se refrescan con el mismo ritmo que la salud: un VRAM
    // congelado en el arranque mentiría durante una generación.
    const loadModels = () => {
      api.musicModels().then((info) => {
        if (!alive || !info) return;
        setModels(info);
      }).catch(() => {});
    };
    check();
    loadModels();
    const t = setInterval(() => {
      check();
      loadModels();
    }, POLL_HEALTH_MS);
    return () => { alive = false; clearInterval(t); };
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const data = await api.musicJobs();
        const feed = data.items ?? [];
        const active = feed.find((job) => job.status === 'queued' || job.status === 'running');
        if (!alive) return;
        // Un MP3 nuevo o borrado cambia la huella: avisar a BIBLIOTECA.
        const version = data.library_version ?? null;
        const prevVersion = libraryVersionRef.current;
        libraryVersionRef.current = version;
        setJobsFeed(feed);
        setActiveJob(active ?? null);
        if (prevVersion !== null && version !== prevVersion) setLibraryTick((t) => t + 1);
      } catch {
        // Un fallo de red no borra la fase que ya se estaba viendo.
      }
    };
    void tick();
    const timer = setInterval(tick, JOB_POLL_INTERVAL_MS);
    return () => { alive = false; clearInterval(timer); };
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

        {/* SALIR apaga motor y API y cierra el proceso. No hay diálogo. */}
        <button
          onClick={() => {
            // Única salida: apaga UI + API + motor. La X de la ventana no hace nada.
            if (window.musica?.exit) window.musica.exit('stop-all');
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
                !engine.checked
                  ? 'bg-[var(--faint)]'
                  : engine.ok
                    ? 'bg-[var(--acc)] shadow-[0_0_8px_var(--acc)]'
                    : 'bg-[var(--err)]'
              }`}
            />
            <span className="mono text-[9.5px] tracking-[0.1em] uppercase text-[var(--muted)] leading-tight">
              <span className="block">
                {!engine.checked ? 'MOTOR' : engine.ok ? 'MOTOR ACTIVO' : 'MOTOR APAGADO'}
              </span>
              {models ? (
                <span className="block normal-case tracking-normal text-[var(--faint)]">
                  {[models.loaded || models.configured, models.loaded_lm]
                    .filter(Boolean)
                    .join(' · ')}
                  {Number.isFinite(models.vram_free_mb) && models.vram_free_mb > 0
                    ? ` · VRAM ${models.vram_free_mb} MB`
                    : ''}
                  {models.remix_model && models.remix_model !== models.loaded
                    ? <span className="block">remix: {models.remix_model}</span>
                    : null}
                </span>
              ) : null}
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
            {activeJob && (
              <span className="mono text-[10.5px] text-[var(--acc)] truncate max-w-[420px]">
                {(activeJob.output_name || (activeJob.prompt ?? '').slice(0, 40) || 'Trabajando…')}
                {Number(activeJob.progress_ratio) > 0 ? ` · ${Math.round(Number(activeJob.progress_ratio) * 100)}%` : ''}
                {activeJob.phase ? ` · ${activeJob.phase}` : ''}
              </span>
            )}
          </div>
          <div className="flex items-center gap-5">
            <span className="mono text-[10.5px] text-[var(--faint)] tracking-[0.12em]">100% LOCAL · SIN NUBE</span>
            {engine.checked && (
              <span className={`mono text-[10.5px] tracking-[0.12em] px-2.5 py-1 border ${
                engine.ok
                  ? 'text-[var(--acc)] border-[var(--acc-line)]'
                  : 'text-[var(--err)] border-[rgba(255,92,92,0.45)]'
              }`}>
                {engine.ok ? 'ACTIVO' : 'APAGADO'}
              </span>
            )}
          </div>
        </header>

        <main className="flex-1 min-h-0 overflow-hidden">
          {/* Montadas siempre: cambiar de pestaña no borra la letra ni el sondeo. */}
          <div className={tab === 'composer' ? 'h-full overflow-y-auto' : 'hidden'}><Composer engine={engine} jobs={jobsFeed} /></div>
          <div className={tab === 'uploads' ? 'h-full overflow-y-auto' : 'hidden'}><Uploads /></div>
          <div className={tab === 'mix' ? 'h-full overflow-y-auto' : 'hidden'}><MixLab externalRefresh={libraryTick} /></div>
          <div className={tab === 'library' ? 'h-full overflow-y-auto' : 'hidden'}><Library externalRefresh={libraryTick} /></div>
        </main>
      </div>
    </div>
  );
}

export default App;
