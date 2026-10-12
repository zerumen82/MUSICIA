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

## Cerradas (siguen en la bitácora, ya no son deuda)

| ID | Qué era | Cierre |
|----|---------|--------|
| T6 | Sin tests automatizados | **Cerrada 2026-10-08**: 113 tests backend (`test_remix_logic` + `test_prompt_style` + `test_genre_glossary` + `test_realism` + `test_verify_align`) + 9 de glosa (`node --test`), todos sin GPU. Cubren cuadre (`plan_alignment`, `first_beat_seconds`, `bars_duration_seconds`), `verify_audio` y la ficha [M3] |
| T1 | Mezclador decorativo en pantalla | La pestaña MEZCLA es `MixLab` (ffmpeg). `Mixer.jsx` no se monta. Historia [C1] cerrada por [F1] |
| T7 | Fail-fast: si el motor no responde, no colgar la petición | Existe en `POST /music/generate` y `/audio/remix/ai` (503 con mensaje). Citada en código pero nunca anotada aquí: se registra el 2026-10-05 |
| A3 | «Falta la UI de la canción con voz» | Hecha y verificada: selector, letra, `vocal_language`. El usuario confirmó el 2026-10-02 que funciona |
| B1 | Borrado con MP3 ocupado y recursos del reproductor abiertos | Cerrada 2026-10-12: conflicto/lote Windows real y UI Electron real PASS; reviewer APPROVE. Evidencia XCIV |
| B2 | Historial perdido al retornar el modo voz | Cerrada 2026-10-12: remix real de dos variantes persistido y recuperado tras reinicio API; reviewer APPROVE. Evidencia XCIV |
| B3 | Colisión de nombres largos al recortar el ordinal | Cerrada 2026-10-12: regresión antes/después y remix largo de dos variantes PASS; límites en config. Evidencia XCIV |

## Bugs conocidos no resueltos

| ID | Bug | Estado |
|----|-----|--------|
| R9 | Comprensión/fidelidad general del prompt y REMIX integral más versátil | Abierto: usuario aclara que voz/guitarra son ejemplos. Diseñar operaciones reales sobre audio original y calidad; las correcciones de envío de XCIV tienen PASS técnico, sin veredicto de oído ni nueva arquitectura implementada |
| R10 | Adiciones no pedidas y vista previa incompleta en CREAR y REMIX | Abierto y reproducido 2026-10-12: presets añaden instrumentos/caracteres; modificadores confunden alcance (bajo potente→voz potente en entrada directa sin glosa, batería al fondo→protagonista también desde UI). Ver logs/prompt-audit-tester-20261012.json y spec/02. No considerar resuelta la fidelidad general por el PASS técnico de XCIV |

## Puntos de vigilancia

| ID | Riesgo | Vigilancia |
|----|--------|-----------|
| W1 | VRAM: pico medido 6.9 GB de 8 GB con turbo; remix sft con guidance 9.0 y 50 pasos: pico 6 607 MB (mínimo 1 418 MB libres, `logs/vram-sft-remix.log` 2026-10-05) y una medición anterior de 7 914 MB (`logs/vram-sft2.log`) | medir con nvidia-smi antes de alargar pistas o subir el batch |
| W2 | Motor y API son procesos aparte | Con la ventana abierta, `scripts/ensure_local.ps1` arranca el proceso que falte. No mata uno que ya responde. SALIR escribe `logs/stop.flag` y los para. La siguiente apertura borra esa marca y los arranca. Un `/health` que no contesta no pinta APAGADO |
| W3 | La primera ejecución de ACE-Step descarga ~10 GB. demucs, ~80 MB la primera separación | declarado en el lanzador y en esta bitácora |
| W4 | Umbrales de cuadre (`-14 LUFS`, confianza 0.12, ratio 0.8–1.25) viven en `mixer_service.py`, no en `config.py` | no duplicarlos; cambiarlos solo si el usuario lo pide |
| W5 | **Otros programas en la GPU**: ComfyUI de AUTOAUTO (PID 18536, `--normalvram`) subió la línea base de VRAM de **710 MB (09:30) a ~3 300 MB**, dejó al motor con `Effective free VRAM: 0.03 GB` al empezar el VAE y forzó decode en CPU → job `5fc1bbb7` agotó `job_timeout=1800` (2026-10-08, entrada LXXXIV) | antes de una generación larga o del e2e, `nvidia-smi --query-gpu=memory.used`; si la base está por encima de ~1 GB, cerrar el otro programa. El motor sigue contestando `200` aunque su hilo siga decodificando tras el timeout |

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
