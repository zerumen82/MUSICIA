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
| GET | `/music/config` | defaults y límites (el frontend NO los inventa) |
| POST | `/music/generate` | crea job → `{job_id, status_url}` |
| GET | `/music/status/{job_id}` | estado + `audio_url` cuando succeed |
| GET | `/music/audio/{name}` | MP3 generado |
| POST | `/tts/generate` | texto → voz |
| GET | `/voices` | voces disponibles |
| POST | `/audio/mix` | mezcla de dos pistas |
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
| `tts_service.py` | edge-tts | - |
| `mixer_service.py` | pydub/ffmpeg | - |
| `main.py` | rutas HTTP, jobs, estáticos | lógica de generación |

## Módulos frontend

| Módulo | Responsabilidad |
|--------|----------------|
| `src/api.js` | cliente HTTP único |
| `src/App.jsx` | shell + navegación |
| `src/components/Composer.jsx` | crear música + historial (localStorage) |
| `src/components/VoiceLab.jsx` | texto a voz |
| `src/components/Sequencer.jsx` | batería (Tone.js; samples remotos — R4: declarado) |
| `src/components/Mixer.jsx` | mezclador visual (aún sin conexión al backend — ver 03) |

## Decisiones de arquitectura registradas

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-10-01 | Motor como proceso separado, no librería | exige Python 3.12 + torch; backend en 3.10 sin torch |
| 2026-10-01 | ACE-Step 1.5 (Apache 2.0) en vez de MusicGen | MusicGen: pesos CC-BY-NC (no comerciales) |
| 2026-10-01 | La API sirve la UI (`/` → dist) | una sola puerta; sin CORS en producción |
| 2026-10-01 | Historial en localStorage | sin cuentas ni servidor de estado |
