# Musicia — estudio musical local

Aplicación de escritorio para crear, mezclar y remixar música en el PC del usuario: FastAPI + React/Vite + Electron y ACE-Step 1.5. Este archivo es el mapa corto; los contratos y criterios están en `spec/`, la evidencia fechada en `memory.md`.

## Estado vigente (2026-10-13)

- **CREAR**: `/music/generate` → ACE-Step `/release_task` → `/query_result` → `/v1/audio`. Instrumental o canto con letra e idioma. BPM, tono, compás, semilla, nombre y variantes se parametrizan desde configuración/controles.
- **Prompts**: el texto se conserva; MEJORAR es un borrador optativo. La validación de conflictos y el preview efectivo forman parte de las correcciones R10 autorizadas. No confundir conservación textual con obediencia musical universal.
- **Modelo**: decisión del usuario del 2026-10-09, SFT en toda la app; perfil aprobado de 50 pasos/guidance 9/batch 2, LM 0.6B, `thinking` y `use_format` apagados. Turbo permanece instalado y permitido en configuración; no es el modelo vigente por defecto. No base, XL ni SFT-stems, ni Lego/Extract/Complete con los checkpoints actuales.
- **REMIX**: `RemixWorkspace` comparte acceso en SUBIR/BIBLIOTECA; cover de canción completa, repaint regional y cuatro grupos reales de Demucs (voz/batería/bajo/other). `other` es acompañamiento agrupado. Mantener voz separada y generar base nueva es otro recorrido existente de `/audio/remix/ai`; la auditoría detectó pérdida de su acceso UI y autorizó restaurarlo.
- **Análisis de fuente**: `source_understanding.py` usa el análisis nativo local `full_analysis_only`; clasificación revisable, incertidumbre declarada. Hay evidencia de ejecución en XCIX. No convierte géneros inferidos en instrucciones del prompt.
- **Audio**: intermedios de remix sin pérdida y exportación final; `MixLab` mezcla biblioteca/subidas mediante ffmpeg, con cuadre cuando la medida es fiable. Las fichas acompañan generación y operaciones derivadas.
- **Cola y PARAR**: historial en disco y cancelación implementados; los trabajos interrumpidos no se reanudan como si siguieran ejecutándose. Cancelar generación puede reiniciar el motor. La prueba del ciclo real cancelar/liberar/recuperar seguía pendiente en la auditoría CI.
- **Retirado**: locución edge-tts, endpoints TTS y pestaña VOZ; el canto sigue en CREAR. `Mixer.jsx` no se monta; `Sequencer.jsx` permanece fuera de la navegación.
- **R9/R10**: parcialmente cumplidos en la auditoría CI, con CHANGES_REQUESTED del cierre. Correcciones autorizadas por «HAZLO» en CII y en curso. No basta declarar «solo falta oído»: se exige completar comparación alineada, conflictos/preview, accesos y herramientas de prompts, sincronización regional y recorridos reales de UI/cancelación.

## Procesos y módulos

| Proceso | Entorno | Puerto |
|---|---|---|
| Electron | `frontend/main.cjs` | — |
| API/UI | `backend/venv` (Python 3.10 del equipo) | 8000 |
| ACE-Step | `vendor/ACE-Step-1.5/.venv` (Python 3.12 del equipo) | 8001 |
| Demucs | `backend/demucs-venv` | invocado por API |

Arranque con ventana: `scripts/open_musicia.ps1`. Solo servicios: `scripts/start_local.ps1`. Parada: `scripts/stop_local.ps1`. Humo real: `scripts/verify_e2e.ps1`.

`main.py` registra API/jobs/fichas/UI; `config.py` carga defaults/JSON/variables `MUSICIA_*`; `music_service.py` construye el payload y comprueba audio; `remix_project.py` coordina fuente/referencia/región/grupos/intermedios; `source_understanding.py` analiza la fuente; `prompt_enhancer.py` propone mejoras optativas; `separator_service.py` separa con Demucs; `mixer_service.py`, `audio_analysis.py` y `audio_service.py` mezclan, miden y procesan. Contratos completos: `spec/01-ARQUITECTURA.md`.

## Agentes y verificación

Globales en `~/.agents/`: sd-coordinator, sd-editor, sd-reviewer, sd-tester, sd-scout y sd-researcher. Musicales en `.agents/`: music-orchestrator, music-composer y audio-engineer. Flujo obligatorio: `spec/04-EJERCITO.md`.

Hay tests automatizados backend unittest y frontend Node. CI registró 164/164 backend y 8/8 frontend, lint/build verdes y 15 audios válidos; ese PASS parcial no cerró R9/R10. HECHO exige ejecución real de los recorridos afectados, audio existente con tamaño/duración positivos, lint/build verdes, **PASS del tester + APPROVE del reviewer**, y evidencia en `memory.md`. La aceptación artística depende de escucha del usuario. Paquetes/modelos/skills se instalan únicamente con aprobación explícita; descargas y red se declaran en la bitácora.