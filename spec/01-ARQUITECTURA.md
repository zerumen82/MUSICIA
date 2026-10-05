# 01 · Arquitectura

## Vista de procesos

```
┌────────────────────────────── PC DEL USUARIO (Windows) ─────────────────────────────┐
│                                                                                      │
│  ┌───────────────┐   carga http://127.0.0.1:8000    ┌──────────────────────────────┐ │
│  │ Electron      │ ────────────────────────────────► │  Musicia API (FastAPI :8000) │ │
│  │ (main.cjs)    │ ◄─── UI servida desde dist/ ────── │  backend/venv (Python 3.10)  │ │
│  └───────────────┘                                   └──────────┬───────────────────┘ │
│         ventana                                                    │ httpx              │
│                                                          ┌─────────▼─────────────────┐  │
│                                                          │ Motor ACE-Step 1.5 (:8001)│  │
│                                                          │ vendor/ACE-Step-1.5       │  │
│                                                          │ .venv Python 3.12 + torch │  │
│                                                          │ RTX 3060 Ti 8GB, tier 3/4 │  │
│                                                          └───────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Contratos

### Motor ACE-Step (externo, no lo modificamos)
- `POST /release_task` → `{task_id, status}` (respuesta envuelta `{data, code, error}`)
- `POST /query_result` `{task_id_list:[id]}` → estado `0=curso, 1=ok, 2=fallo`,
  `result` = JSON-texto con lista de pistas (`file`, `prompt`, `metas`)
- `GET /v1/audio?path=…` → bytes del audio (¡la pista viene YA como URL!)
- `GET /health` → `{status, models_initialized}`

### Musicia API (nuestro backend — contrato estable)
| Método | Ruta | Función |
|--------|------|---------|
| GET | `/api/info` | metadatos del servicio |
| GET | `/health` | estado real del motor |
| GET | `/music/config` | defaults y límites (el frontend NO los invente) |
| GET | `/music/models` | modelo cargado y los permitidos en 8 GB; no cambia el modelo |
| POST | `/music/generate` | crea job → `{job_id, status_url}` |
| GET | `/music/status/{job_id}` | estado + `audio_url` cuando succeed |
| GET | `/music/audio/{name}` | MP3 generado |
| POST | `/audio/mix` | mezcla: cuadre opcional + loudnorm -14 LUFS |
| POST | `/audio/mix/plan` | plan de cuadre (o null si no es seguro) |
| POST | `/audio/separate` | arranca voces y base; responde `{job_id}` |
| GET | `/audio/separate/{job_id}` | estado de esa separación |
| GET | `/audio/separate/status` | si el venv de demucs está instalado |
| POST | `/audio/remix/ai` | bootleg: separar → generar → cuadrar → mezclar |
| POST | `/music/write_lyrics` | letra vía `/format_input` del motor |
| PATCH | `/music/audio/{name}` | renombrar en outputs/ o uploads/ |
| `/` | mount estático | UI de `frontend/dist` |

### Frontend ↔ Backend
- Única fuente de URLs: `frontend/src/api.js` (`VITE_API_BASE_URL` opcional).
- Límites y defaults SIEMPRE de `/music/config` — prohibido hardcodearlos (R1).
- Estado de job: `queued | running | succeeded | failed` (del backend, nunca
  inventado en el cliente).

## Módulos backend (responsabilidad única)

| Módulo | Responsabilidad | NO hace |
|--------|----------------|---------|
| `config.py` | cargar/validar configuración (defaults → JSON → env) | lógica de negocio |
| `music_service.py` | hablar con el motor + verificar audio | servir HTTP |
| `mixer_service.py` | ffmpeg: atempo, adelay, loudnorm, loop, tempo, crossfade | generación musical |
| `separator_service.py` | demucs en `backend/demucs-venv` | mezclar |
| `audio_analysis.py` | BPM, fase, picos (pydub) | escribir archivos de mezcla |
| `prompt_enhancer.py` | enriquece el prompt; el BPM entra una sola vez | llamar al motor |
| `main.py` | rutas HTTP, jobs, estáticos | lógica de generación |

## Módulos frontend

| Módulo | Responsabilidad |
|--------|----------------|
| `src/api.js` | cliente HTTP único |
| `src/App.jsx` | shell + navegación |
| `src/components/Composer.jsx` | crear música + historial (localStorage) |
| `src/components/VoiceLab.jsx` | retirada el 2026-10-02 (locución, no canto) |
| `src/components/Sequencer.jsx` | retirado de la navegación (T2: si vuelve, samples locales) |
| `src/components/MixLab.jsx` | mezcla real (pestaña MEZCLA) |
| `src/components/RemixActions.jsx` | remixer de bootlegs, una línea |
| `src/vocal.js` | etiquetas de voz cantada y estructura de la letra |
| `Mixer.jsx` | código viejo, no montado. La pestaña usa MixLab |

## Decisiones de arquitectura registradas

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-10-01 | Motor como proceso separado, no librería | exige Python 3.12 + torch; backend en 3.10 sin torch |
| 2026-10-01 | ACE-Step 1.5 (Apache 2.0) en vez de MusicGen | MusicGen: pesos CC-BY-NC (no comerciales) |
| 2026-10-01 | La API sirve la UI (`/` → dist) | una sola puerta; sin CORS en producción |
| 2026-10-01 | Historial en localStorage | sin cuentas ni servidor de estado |
