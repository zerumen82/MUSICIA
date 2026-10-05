# Musicia — estudio musical local

Aplicación de escritorio para crear, mezclar y remixar música en el PC del usuario.
FastAPI + React/Vite + Electron. El motor de música es **ACE-Step 1.5** (Apache 2.0).
MusicGen no forma parte del producto: sus pesos son CC-BY-NC.

Este archivo es el mapa corto. El detalle vivo está en `spec/` y la evidencia en `memory.md`.
Si este archivo y el código discrepan, manda el código y se corrige aquí.

## Qué hace hoy

- **CREAR** — `POST /music/generate` lanza un job real contra ACE-Step (`:8001`):
  `/release_task` → `/query_result` → `/v1/audio`. Instrumental o con voz cantada
  (letra con marcas `[Verse]`/`[Chorus]`, `vocal_language` elegido en la UI).
  BPM, tono, semilla y nombre salen de la pantalla.
- **Letra** — `POST /music/write_lyrics` pide un borrador al LM local (`/format_input`).
  Si el LM solo devuelve estructura instrumental, la API avisa. No inventa la letra.
  El cliente de ese endpoint espera hasta 300 s.
- **SUBIR** — análisis DSP. Re-crear manda el audio como `cover` (sin duración: la pone el origen). «Crear base» sigue siendo una cama nueva, instrumental. Alargar un tramo es `repaint` sobre el audio.
- **MEZCLA** — `MixLab`: ffmpeg (`atempo`, `adelay`, `loudnorm` a -14 LUFS).
  BASE y VOZ listan biblioteca y subidas. Si el tempo no es fiable, no se cuadra y se dice.
- **REMIXER** — el menú elige y HACER lanza. Versión y tramo piden prompt, letra, BPM, tono, semilla y nombre, igual que CREAR, y al terminar pasan por el master de −14 LUFS. Ajustar es DSP. También: voz real + base nueva, quitar voces, loop, medio tiempo (`half`) y doble tiempo (`double`), forzar BPM. La fase del trabajo (generar, remix IA o separar) sale en la barra de arriba.
- **Modelo** — en 8 GB permanece `acestep-v15-turbo`. Otro nombre se rechaza. Generar, separar y el remix con IA no corren a la vez. El lateral muestra el modelo que el motor tiene cargado.
- **Locución** — la pestaña se quitó el 2026-10-02 y los endpoints el 2026-10-05: edge-tts habla, no canta, y era red (anti LOCAL-FIRST). El canto sigue en CREAR. `POST /tts/generate` y `GET /voices` ya no existen; `tts_service.py` y `edge-tts` en requirements, borrados.
- **BIBLIOTECA** — MP3 en `backend/outputs/`. Al terminar una generación se escribe `nombre.ficha.json` al lado (prompt, BPM, tarea). La ficha viaja al renombrar, se borra con el MP3 y se copia en mezcla, tempo, loop, fundido, separación, remix DSP y remix IA. «Otra versión» manda `cover` con el audio. Renombrado con `PATCH /music/audio/{name}`.
- **Ventana** — Electron carga `http://127.0.0.1:8000`. La X minimiza a la bandeja.
  Salir es el botón SALIR. Si el bundle servido cambia, la ventana se recarga sola.

## Procesos

| Proceso | Dónde | Puerto |
|---------|--------|--------|
| Ventana Electron | `frontend/main.cjs` | — |
| API Musicia | `backend/` (venv Python 3.10) | 8000 |
| Motor ACE-Step 1.5 | `vendor/ACE-Step-1.5` (venv Python 3.12) | 8001 |
| demucs | `backend/demucs-venv` | lo invoca la API |

Arranque: `scripts/open_musicia.ps1`. Parada: `scripts/stop_local.ps1`.
Humo: `scripts/verify_e2e.ps1`.

## Módulos backend

| Archivo | Responsabilidad |
|---------|-----------------|
| `main.py` | Rutas HTTP, jobs, ficheros, UI estática |
| `config.py` | Defaults, `config.json`, variables `MUSICIA_*` |
| `music_service.py` | Habla con ACE-Step y comprueba el audio (pydub) |
| `prompt_enhancer.py` | Añade el BPM una sola vez (el mood se quitó: nadie lo usaba) |
| `mixer_service.py` | Mezcla y bootlegs con ffmpeg |
| `separator_service.py` | Voces y base con demucs |
| `audio_analysis.py` | BPM, fase, picos |
| `audio_service.py` | Ganancia, fade, recorte (pydub) |

`Mixer.jsx` no está montado. La mezcla en pantalla es `MixLab.jsx`.
El secuenciador no está en la navegación.

## Agentes

Globales, en `~/.agents/`: sd-coordinator, sd-editor, sd-reviewer, sd-tester, sd-scout, sd-researcher.
De este proyecto, en `.agents/`: music-orchestrator, music-composer, audio-engineer.
Mapa y flujo: `spec/04-EJERCITO.md`.

## Verificación

No hay tests unitarios. Una generación cuenta cuando el MP3 existe, pesa más de 0
y dura más de 0 (ffprobe o pydub), con lint y build en verde, y la prueba anotada en `memory.md`.
