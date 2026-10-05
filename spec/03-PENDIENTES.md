# 03 · Pendientes y deudas técnicas (backlog vivo)

> Lo que aquí aparece **declarado** no es un stub oculto: es deuda reconocida
> con plan. Lo peligroso es lo que NO está aquí y debería estar.
>
> Actualizado el 2026-10-03 al cruzar este archivo con el código y con `memory.md`.

## Deudas técnicas (abiertas)

| ID | Deuda | Impacto | Plan |
|----|-------|---------|------|
| T2 | `Sequencer.jsx` sigue en el repo y no está en la navegación. Si vuelve, sus samples salen de tonejs.github.io | R4: sin internet no sonaría | [C2] empaquetar samples locales antes de remontarlo |
| T3 | El build del frontend no parte el bundle (`manualChunks`). Medido el 2026-10-04: `index-RaxfxUaQ.js` 333.65 kB (gzip 103.76 kB). La cifra vieja de 624 kB no describe el build actual | primera carga de la ventana | medir de nuevo si el bundle crece, y entonces partir react / tone |
| T4 | `backend/venv` con pip antiguo (Python 3.10) | avisos e instalaciones lentas | `python -m pip install -U pip` dentro de ese venv, con acuerdo |
| T5 | pip global del usuario con índice NVIDIA roto (DNS) | ralentiza instalaciones pip del sistema | quitar `extra-index-url` de la config global de pip, con acuerdo |
| T6 | Sin tests automatizados | las regresiones se ven solo al ejecutar | pytest de `verificar_audio`, `build_payload` y el cuadre que devuelve null |

## Cerradas (siguen en la bitácora, ya no son deuda)

| ID | Qué era | Cierre |
|----|---------|--------|
| T1 | Mezclador decorativo en pantalla | La pestaña MEZCLA es `MixLab` (ffmpeg). `Mixer.jsx` no se monta. Historia [C1] cerrada por [F1] |
| A3 | «Falta la UI de la canción con voz» | Hecha y verificada: selector, letra, `vocal_language`. El usuario confirmó el 2026-10-02 que funciona |

## Bugs conocidos no resueltos

| ID | Bug | Estado |
|----|-----|--------|
| — | Ninguno abierto. Los cerrados están en `memory.md` con su fix | ✅ |

## Puntos de vigilancia

| ID | Riesgo | Vigilancia |
|----|--------|-----------|
| W1 | VRAM: pico medido 6.9 GB de 8 GB | medir con nvidia-smi antes de alargar pistas o subir el batch |
| W2 | Motor y API son procesos aparte | Con la ventana abierta, `scripts/ensure_local.ps1` arranca el proceso que falte. No mata uno que ya responde. SALIR escribe `logs/stop.flag` y los para. La siguiente apertura borra esa marca y los arranca. Un `/health` que no contesta no pinta APAGADO |
| W3 | La primera ejecución de ACE-Step descarga ~10 GB. demucs, ~80 MB la primera separación | declarado en el lanzador y en esta bitácora |
| W4 | Umbrales de cuadre (`-14 LUFS`, confianza 0.12, ratio 0.8–1.25) viven en `mixer_service.py`, no en `config.py` | no duplicarlos; cambiarlos solo si el usuario lo pide |

## Propuesta de mejoras

El detalle está en `spec/05-MEJORAS.md`. El 2026-10-02 el usuario pidió quitar
la locución y aplicar las mejoras sustanciales. Eso está en código (entrada XVI
de `memory.md`): cover/repaint, mesa con HACER, separación en segundo plano,
las dos listas en mezcla, ficha y pestañas que no se desmontan.
Sigue sin hacerse: medir `acestep-v15-base`, cola en disco, botón que pare la
GPU, y la capa visual (chips de CREAR, ondas de 28 px). No hay audio real de
una cover ni de un repaint.

## Próximas historias candidatas

1. [T6] Tests del servicio de música y del cuadre — protege lo que ya funciona
2. [A4] Compás (time signature) en CREAR — BPM, tono y semilla ya están
3. [F3] Una cover y un repaint reales (MP3, duración > 0) cuando se pueda ocupar la GPU
4. [D3] Instalador — cuando el producto se quiera empaquetar
5. [C2] / [T2] Secuenciador, solo si se vuelve a querer en la UI, con samples locales
