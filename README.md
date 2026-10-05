# 🎵 Musicia

Estudio de música con IA **100% local** para Windows. Genera canciones, canta con texto-a-voz, sube tus propios audios y mézclalos — todo sin salir de tu PC y sin enviar nada a la nube.

## ✨ Qué puede hacer

- **CREAR** — Genera música instrumental o canciones con voz a partir de un prompt. Asistente de calidad en 5 pasos, mejora de prompt con un clic, variaciones A/B comparables.
- **SUBIR** — Arrastra tus MP3/WAV, análisis DSP automático (BPM, loudness, dinámica) y re-creación con IA a partir de un prompt editable.
- **MEZCLA** — Mezcla varias pistas con volúmenes, fundidos de entrada/salida y normalización.
- **BIBLIOTECA** — Todas tus creaciones, con remezcla y ajustes por pista.

## 🏗️ Arquitectura

| Componente | Tecnología | Puerto |
|---|---|---|
| Frontend (ventana Electron) | React + Vite + Tailwind | — |
| API local | FastAPI (Python, venv propio) | 8000 |
| Motor de música | ACE-Step 1.5 turbo (2B, venv propio en `vendor/`) | 8001 |

- Backend en Python con dependencias mínimas (FastAPI, httpx, pydub, loguru); análisis DSP en Python puro (sin numpy).
- Procesamiento de audio con ffmpeg (instalado aparte).
- Progreso en vivo con fases y porcentaje real durante la generación.
- Bandeja de sistema: cerrar la ventana la minimiza; el botón SALIR detiene API y motor.

## 🚀 Puesta en marcha

```powershell
# 1. Frontend
cd frontend
npm install
npm run build

# 2. Lanzar todo (API + motor + ventana Electron)
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
# o directamente: Musicia.exe
```

Requisitos: Windows, Python 3.11+, Node 18+, GPU NVIDIA con ≥8 GB VRAM recomendado (RTX 3060 Ti verificado).

## 📁 Estructura

```
backend/     API FastAPI + servicios (música, mezcla, análisis DSP)
frontend/    UI React/Vite + main.cjs de Electron
scripts/     lanzadores, launcher C# (Musicia.exe)
spec/        especificaciones SDD
vendor/      ACE-Step 1.5 (no incluido en el repo)
```

## 🔒 Privacidad

Todo el procesamiento — generación, análisis y mezcla — ocurre en tu máquina. No hay telemetría ni llamadas externas.
