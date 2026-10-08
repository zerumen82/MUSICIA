# 03 · Pendientes y deudas técnicas (backlog vivo)

> Lo que aquí aparece **declarado** no es un stub oculto: es deuda reconocida
> con plan. Lo peligroso es lo que NO está aquí y debería estar.
>
> Actualizado el 2026-10-06 al cruzar este archivo con el código y con `memory.md`.

## Deudas técnicas (abiertas)

| ID | Deuda | Impacto | Plan |
|----|-------|---------|------|
| T2 | `Sequencer.jsx` sigue en el repo y no está en la navegación. Si vuelve, sus samples salen de tonejs.github.io | R4: sin internet no sonaría | [C2] empaquetar samples locales antes de remontarlo |
| T3 | El build del frontend no parte el bundle (`manualChunks`). Medido el 2026-10-06: `index-Don8Zd9O.js` 354.96 kB (gzip 109.75 kB). R1+R2+R4+R5+R6: +1.5 kB | primera carga de la ventana | partir react / tone si pasa de 400 kB |
| T4 | `backend/venv` con pip antiguo (Python 3.10) | avisos e instalaciones lentas | `python -m pip install -U pip` dentro de ese venv, con acuerdo |
| T5 | pip global del usuario con índice NVIDIA roto (DNS) | ralentiza instalaciones pip del sistema | quitar `extra-index-url` de la config global de pip, con acuerdo |
| T6 | Sin tests automatizados | las regresiones se ven solo al ejecutar | `backend/test_remix_logic.py` + `backend/test_prompt_style.py` (unittest, stdlib, sin GPU): 73 tests de `_find_audio` (con kind), `remix_cover_strength_for`, cancel/historial, `library_version`, cover nativo (`src_audio_path`, fuerza, rango, `use_format`), `model_for`/`build_payload`, `style_caption`/`analyze_prompt` (catálogo + idempotencia), `_remember` + `frontend/src/prompt_gloss.test.js` (8 tests de la glosa con `node --test`). Falta: cuadre y `verificar_audio` |

## Cerradas (siguen en la bitácora, ya no son deuda)

| ID | Qué era | Cierre |
|----|---------|--------|
| T1 | Mezclador decorativo en pantalla | La pestaña MEZCLA es `MixLab` (ffmpeg). `Mixer.jsx` no se monta. Historia [C1] cerrada por [F1] |
| T7 | Fail-fast: si el motor no responde, no colgar la petición | Existe en `POST /music/generate` y `/audio/remix/ai` (503 con mensaje). Citada en código pero nunca anotada aquí: se registra el 2026-10-05 |
| A3 | «Falta la UI de la canción con voz» | Hecha y verificada: selector, letra, `vocal_language`. El usuario confirmó el 2026-10-02 que funciona |

## Bugs conocidos no resueltos

| ID | Bug | Estado |
|----|-----|--------|
| — | Ninguno abierto. Los cerrados están en `memory.md` con su fix | ✅ |

## Puntos de vigilancia

| ID | Riesgo | Vigilancia |
|----|--------|-----------|
| W1 | VRAM: pico medido 6.9 GB de 8 GB con turbo; remix sft con guidance 9.0 y 50 pasos: pico 6 607 MB (mínimo 1 418 MB libres, `logs/vram-sft-remix.log` 2026-10-05) y una medición anterior de 7 914 MB (`logs/vram-sft2.log`) | medir con nvidia-smi antes de alargar pistas o subir el batch |
| W2 | Motor y API son procesos aparte | Con la ventana abierta, `scripts/ensure_local.ps1` arranca el proceso que falte. No mata uno que ya responde. SALIR escribe `logs/stop.flag` y los para. La siguiente apertura borra esa marca y los arranca. Un `/health` que no contesta no pinta APAGADO |
| W3 | La primera ejecución de ACE-Step descarga ~10 GB. demucs, ~80 MB la primera separación | declarado en el lanzador y en esta bitácora |
| W4 | Umbrales de cuadre (`-14 LUFS`, confianza 0.12, ratio 0.8–1.25) viven en `mixer_service.py`, no en `config.py` | no duplicarlos; cambiarlos solo si el usuario lo pide |

## Propuesta de mejoras

El detalle está en `spec/05-MEJORAS.md`. El 2026-10-02 el usuario pidió quitar
la locución y aplicar las mejoras sustanciales. Eso está en código (entrada XVI
de `memory.md`): cover/repaint, mesa con HACER, separación en segundo plano,
las dos listas en mezcla, ficha y pestañas que no se desmontan.
Sigue sin hacerse: medir `acestep-v15-base`, cola en disco, botón que pare la
GPU, y la capa visual (ondas de 28 px en biblioteca). Repaint ya probado en GPU
(`prueba-auditoria-tramo.mp3`, 2026-10-05) y remixes/ covers reales generados
(jobs `93ef9310`, `7d4c5de7`, A/B/C/D/E/F de estilo); el oído del usuario
decide la obediencia fina (guidance sft actual: 9.0).

## Próximas historias candidatas

1. [T6] Tests del servicio de música y del cuadre — protege lo que ya funciona
2. [F3] Veredicto de oído de cover/repaint (MP3 ya generados: repaint `prueba-auditoria-tramo.mp3`, remix sft `prueba-sft-obediencia.mp3`, serie A/B/C/D/E/F): el usuario escucha y sentencia obediencia/cuadre
3. [D3] Instalador — cuando el producto se quiera empaquetar
4. [C2] / [T2] Secuenciador, solo si se vuelve a querer en la UI, con samples locales

Hechas el 2026-10-05: [A4] compás en CREAR (selector COMPÁS 4/4·3/4·6/8, viaja al motor y a la ficha).
