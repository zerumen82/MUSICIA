# Project knowledge

Proyecto Musicia: creación musical con IA en local (FastAPI + React/Vite + Electron).

## Quickstart
- Setup backend: `pip install -r backend/requirements.txt` (requiere ffmpeg en PATH para pydub)
- Setup frontend: `cd frontend && npm install`
- Setup motor de música: `cd vendor/ACE-Step-1.5 && uv sync` (Python 3.11+, torch cu128, ~10 GB de pesos en la 1ª ejecución)
- App de escritorio (Electron): `powershell -ExecutionPolicy Bypass -File scripts/open_musicia.ps1` (motor + API + ventana)
- Arranque de servicios solo: `powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1`
- Parar: `powershell -ExecutionPolicy Bypass -File scripts/stop_local.ps1`
- Prueba de humo real: `powershell -ExecutionPolicy Bypass -File scripts/verify_e2e.ps1 -Seconds 30` (genera música y verifica el MP3 con ffprobe)
- Dev backend: `backend/venv/Scripts/python.exe backend/main.py`
- Dev frontend (HMR en navegador solo para desarrollar): `cd frontend && npm run dev`
- La UI en producción la sirve la propia API en `/` (mount de `frontend/dist`); hay que hacer `npm run build` tras cambiar el frontend
- Test: `backend/test_remix_logic.py` (unittest stdlib, sin GPU) + la verificación oficial es la ejecución real (ver reglas)

## Architecture
- `backend/` — FastAPI: generación ACE-Step 1.5, voz cantada por el mismo motor (la locución edge-tts se quitó el 2026-10-05), mezcla ffmpeg (atempo/loudnorm), separación demucs, DSP y análisis con pydub
- `frontend/` — React 19 + Vite + Tailwind + Tone.js; app de escritorio via Electron (`frontend/main.cjs`, CommonJS porque el package.json es `"type": "module"`; contextIsolation + sandbox)
  - En producción Electron carga `http://127.0.0.1:8000` (la API sirve la UI); en dev sin build, carga `http://localhost:5173`
- `.agents/` — definiciones de agentes (music-orchestrator, music-composer, audio-engineer)
- `spec/` — especificación SDD: principios (00), arquitectura (01), requisitos (02), pendientes (03), ejército de agentes (04)
- Agentes SDD GLOBALES en `~/.agents/`: `sd-coordinator` (pregunta antes de decidir), `sd-editor` (implementa), `sd-tester` (verifica con evidencia), `sd-reviewer` (APPROVE/CHANGES_REQUESTED), `sd-scout` (skills), `sd-researcher` (internet). Invócalos por nombre; ver spec/04-EJERCITO.md
- **PROTOCOLO DE EJECUCIÓN OBLIGATORIO** (el usuario lo dejó claro: los agentes
  SE USAN en cada trabajo, no son decorativos):
  1. Toda petición se trata según el flujo SDD: si es historia nueva → spec en
     `spec/02-REQUISITOS.md` + plan aprobado por el usuario ANTES de codificar.
  2. El coordinador pregunta (ask_user) ante cualquier decisión no trivial.
  3. Nada está HECHO sin: **PASS del tester** (evidencia real ejecutada: build,
     lint, e2e con salida pegada) **+ APPROVE del reviewer** (revisión completa
     de los archivos tocados, no solo del diff mental).
  4. El papel del tester/reviewer se ejercita SIEMPRE como paso explícito y
     separado, con veredicto explícito en memory.md, aunque el agente principal
     ejecute la implementación en la misma sesión.
  5. Tras un refactor de renombrado: re-leer el archivo completo (lección del
     bug "win is not defined").
- `memory.md` — bitácora del proyecto: decisiones, pruebas y resultados con fecha
- `scripts/` — arranque/parada del stack local y prueba de humo end-to-end
- `vendor/ACE-Step-1.5/` — motor de música (repo externo, venv propio Python 3.12)
- Data flow (producto): petición → music-orchestrator → music-composer (spec) → audio-engineer (generación real) → verificación → bitácora en memory.md
- Data flow (metodología): usuario (orchestrator supremo) → sd-coordinator [pregunta antes de decidir] → sd-scout + sd-researcher → sd-editor → sd-reviewer (APPROVE) → sd-tester (PASS) → memory.md → HECHO
  - Motor: `POST /music/generate` → ACE-Step `/release_task` → sondeo `/query_result` → descarga `/v1/audio` → verificación con pydub → `GET /music/audio/{name}`

## Conventions
- VRAM: el DiT 2B turbo cabe en 8 GB (pico medido 6.9 GB); el XL 4B (9 GB de pesos) NO cabe. Perfil del motor: tier3/tier4 con offload a CPU
- Si una generación falla: el error real viaja en `job["error"]` y en `logs/acestep-api.err.log`; nunca se maquilla
- REGLAS INNEGOCIABLES (todos los agentes):
  - NO HARDCODE: valores en config/parámetros, nunca mágicos en código
  - NO STUB: todo código se ejecuta de verdad; cero placeholders ni éxitos falsos
  - NO FAKE: verificación con ejecución real (archivo existe, duración > 0, código de salida 0)
  - LOCAL-FIRST: generación en la máquina del usuario; dependencias de red se declaran en memory.md
  - BITÁCORA: cada decisión/prueba se anota en memory.md con fecha
- Formato/linting: ESLint 9 flat config (`frontend/eslint.config.js`); Tailwind utility-first con tokens en `frontend/src/index.css`
- Patterns to follow: especificaciones de canción como datos (JSON), servicios de backend como clases estáticas con loguru
- Things to avoid: endpoints mock, datos inventados, constantes mágicas, servicios en la nube sin declarar en la bitácora
