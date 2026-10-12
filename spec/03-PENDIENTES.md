# 03 · Pendientes y deudas técnicas (backlog vivo)

> Lo que aquí aparece **declarado** no es un stub oculto: es deuda reconocida
> con plan. Lo peligroso es lo que NO está aquí y debería estar.
>
> Actualizado el 2026-10-13 tras contrastar código, auditoría del plan y `memory.md` CI/CII. Correcciones R9/R10 autorizadas y en curso; no cerrarlas sin nuevos veredictos completos.

## Deudas técnicas (abiertas)

| ID | Deuda | Impacto | Plan |
|----|-------|---------|------|
| T2 | `Sequencer.jsx` sigue en el repo y no está en la navegación. Si vuelve, sus samples salen de tonejs.github.io | R4: sin internet no sonaría | [C2] empaquetar samples locales antes de remontarlo |
| T3 | El build del frontend no parte el bundle (`manualChunks`); la medición de 354.96 kB pertenece al 2026-10-06, no al bundle actual | primera carga de la ventana | reevaluar con la medición vigente; cualquier refactor requiere su plan aprobado |
| T4 | `backend/venv` con pip antiguo (Python 3.10) | avisos e instalaciones lentas | `python -m pip install -U pip` dentro de ese venv, con acuerdo |
| T5 | pip global del usuario con índice NVIDIA roto (DNS) | ralentiza instalaciones pip del sistema | quitar `extra-index-url` de la config global de pip, con acuerdo |

## Cerradas (siguen en la bitácora, ya no son deuda)

| ID | Qué era | Cierre |
|----|---------|--------|
| T6 | Sin tests automatizados | Cerrada 2026-10-08. La auditoría CI del 2026-10-13 ejecutó **164 tests backend y 8 frontend**; hay suites unittest/Node para contratos, análisis, cuadre, fichas, biblioteca y prompts. Estas suites no sustituyen los recorridos GPU/UI ni la escucha |
| T1 | Mezclador decorativo en pantalla | La pestaña MEZCLA es `MixLab` (ffmpeg). `Mixer.jsx` no se monta. Historia [C1] cerrada por [F1] |
| T7 | Fail-fast: si el motor no responde, no colgar la petición | Existe en `POST /music/generate` y `/audio/remix/ai` (503 con mensaje). Citada en código pero nunca anotada aquí: se registra el 2026-10-05 |
| A3 | «Falta la UI de la canción con voz» | Hecha y verificada: selector, letra, `vocal_language`. El usuario confirmó el 2026-10-02 que funciona |
| B1 | Borrado con MP3 ocupado y recursos del reproductor abiertos | Cerrada 2026-10-12: conflicto/lote Windows real y UI Electron real PASS; reviewer APPROVE. Evidencia XCIV |
| B2 | Historial perdido al retornar el modo voz | Cerrada 2026-10-12: remix real de dos variantes persistido y recuperado tras reinicio API; reviewer APPROVE. Evidencia XCIV |
| B3 | Colisión de nombres largos al recortar el ordinal | Cerrada 2026-10-12: regresión antes/después y remix largo de dos variantes PASS; límites en config. Evidencia XCIV |
| Q1 | Historial perdido al reiniciar la API | Implementada y verificada mediante save/load en disco, `memory.md` LXI y XCIV. Al recuperar trabajos interrumpidos se declara el fallo; no se promete reanudar la inferencia |

## Bugs conocidos no resueltos

| ID | Bug | Estado |
|----|-----|--------|
| R9 | REMIX integral: criterios técnicos incompletos tras el cierre anterior | Reabierta por CI; correcciones autorizadas en CII. Completar comparación A/B alineada, acceso voz original + base nueva, herramientas de prompts en acompañamiento, selección regional compartida, procedencia de clasificación, trazabilidad por variante y recorridos reales de UI. Cover/repaint/grupos tienen implementación y evidencia parcial en XCIX; no bastan para cierre integral |
| R10 | Conflictos texto/controles y preview efectivo incompleto en rutas con prompt | Reabierta por CI; correcciones autorizadas en CII. El prompt literal y MEJORAR optativo ya tienen evidencia parcial. Falta cerrar validación de conflictos y mostrar payload/parámetros realmente usados, con igualdad preview/envío y comprobación del recorrido React/HTTP real |
| Q2 | Cancelación implementada sin evidencia completa del ciclo real | PARAR y cancelación del motor/separador existen (`memory.md` LXI; estado auditado en CI). Verificar cancelar/liberar recursos/recuperar y nueva operación real; conservar errores y evidencia. No confundir cancelar el trabajo con SALIR ni las pruebas de lógica con cancelación GPU |

## Puntos de vigilancia

| ID | Riesgo | Vigilancia |
|----|--------|-----------|
| W1 | VRAM: pico medido 6.9 GB de 8 GB con turbo; remix sft con guidance 9.0 y 50 pasos: pico 6 607 MB (mínimo 1 418 MB libres, `logs/vram-sft-remix.log` 2026-10-05) y una medición anterior de 7 914 MB (`logs/vram-sft2.log`) | medir con nvidia-smi antes de alargar pistas o subir el batch |
| W2 | Motor y API son procesos aparte | Con la ventana abierta, `scripts/ensure_local.ps1` arranca el proceso que falte. No mata uno que ya responde. SALIR escribe `logs/stop.flag` y los para. La siguiente apertura borra esa marca y los arranca. Un `/health` que no contesta no pinta APAGADO |
| W3 | La primera ejecución de ACE-Step descarga ~10 GB. demucs, ~80 MB la primera separación | declarado en el lanzador y en esta bitácora |
| W4 | Umbrales de cuadre (`-14 LUFS`, confianza 0.12, ratio 0.8–1.25) viven en `mixer_service.py`, no en `config.py` | no duplicarlos; cambiarlos solo si el usuario lo pide |
| W5 | **Otros programas en la GPU**: el 2026-10-08 hubo VRAM ocupada por otro programa y timeout (`memory.md` LXXXIV); ese PID/consumo histórico no describe el estado actual | medir con `nvidia-smi` antes de una prueba larga y comunicar restricciones; no cerrar aplicaciones ajenas sin autorización. Un health 200 no acredita que la inferencia haya acabado |

## Propuesta de mejoras

El detalle histórico está en `spec/05-MEJORAS.md`; no representa el estado actual ni autoriza decisiones descartadas. El 2026-10-02 el usuario pidió quitar
la locución y aplicar las mejoras sustanciales. Eso está en código (entrada XVI
de `memory.md`): cover/repaint, mesa con HACER, separación en segundo plano,
las dos listas en mezcla, ficha y pestañas que no se desmontan.
No se ha instalado ni medido `acestep-v15-base`; no forma parte de la fase autorizada. Cola en disco y PARAR están implementados, con el e2e completo de cancelación todavía abierto en CI. La antigua propuesta de ondas de 28 px no es requisito de este cierre. Repaint ya probado en GPU
(`prueba-auditoria-tramo.mp3`, 2026-10-05) y remixes/ covers reales generados
(jobs `93ef9310`, `7d4c5de7`, A/B/C/D/E/F de estilo); el oído del usuario
decide la obediencia fina (guidance sft actual: 9.0).

## Próximas historias candidatas

1. [R9]/[R10]/[Q2] Completar las correcciones autorizadas del cierre y verificar todos los criterios con tester/reviewer; estado en CII y entradas posteriores
2. [F3]/[R9] Veredicto de oído de cover/repaint y variantes: el usuario escucha y sentencia obediencia/cuadre; separado del PASS técnico
3. [D3] Instalador — candidato, requiere decisión del usuario
4. [C2]/[T2] Secuenciador — candidato solo si el usuario vuelve a quererlo, con samples locales

Hechas el 2026-10-05: [A4] compás en CREAR (selector COMPÁS 4/4·3/4·6/8, viaja al motor y a la ficha).
