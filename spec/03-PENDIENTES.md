# 03 · Pendientes y deudas técnicas (backlog vivo)

> Lo que aquí aparece **declarado** no es un stub oculto: es deuda reconocida
> con plan. Lo peligroso es lo que NO está aquí y debería estar.
>
> Actualizado el 2026-10-15. Correcciones R9/R10 autorizadas y en curso; no cerrarlas sin nuevos veredictos completos. R11 quedó cerrada a nivel técnico (memory CXXXI) y reabierta en el uso general como **B6**. **B7 (memory CXLI)**: ninguna opción de QUÉ HACER garantiza que el audio sea lo pedido. El arreglo de una sola pista en transformar no cubre el resto.

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
| B4 | VAE fallback CPU conservaba BF16 y el remix se quedaba al 80 % | Cerrada 2026-10-13: dtype CPU correcto y restauración garantizada, parche durable; réplica real con 0,15 GB libres y dos MP3 de 66,952 s. Tester PASS/reviewer APPROVE, memory CXVII |
| B5 | UI/progreso ambiguo y ajustes editables durante otra operación | Cerrada 2026-10-13: acción contextual y fuente exacta, controles/onda bloqueados y recuperados en DSP real, dos resoluciones, Decoding sin porcentaje y sin confundir carga VAE. CREAR real de dos variantes de 30 s; evidencia DOM/API y capturas, memory CXVII |
| R11 | BPM común en Por pistas y remix más largo por repetición de partes con transiciones | Cerrada técnicamente el 2026-10-14: PASS del tester + APPROVE del reviewer citados en `logs/remix-r11-tester-verdict-20261014.json` y comprobados en primera mano (cinco MP3 de 90,000 s y 2.161.196 bytes, fichas con `timeline` y `bpm_measured` separado del pedido, capabilities con límites de configuración). No acredita el BPM medido de las partes nuevas, la calidad de aislamiento ni la escucha artística; R9/R10 y Q2 siguen abiertos. **Reabierta el 2026-10-14 (memory CXXXII)** al reproducir el recorrido con los dos audios reales del usuario: el BPM común se rechaza cuando la medición automática falla de octava y en canción completa el BPM pedido no se cumple en el audio; ver **B6** |

## Bugs conocidos no resueltos

| ID | Bug | Estado |
|----|-----|--------|
| R9 | REMIX integral: criterios técnicos incompletos tras el cierre anterior | Reabierta por CI; correcciones autorizadas en CII. Completar comparación A/B alineada, acceso voz original + base nueva, herramientas de prompts en acompañamiento, selección regional compartida, procedencia de clasificación, trazabilidad por variante y recorridos reales de UI. Cover/repaint/grupos tienen implementación y evidencia parcial en XCIX; no bastan para cierre integral. R11 (CXXXI) añadió BPM común y ampliación por partes con PASS técnico propio, sin cerrar esto |
| R10 | Conflictos texto/controles y preview efectivo incompleto en rutas con prompt | Reabierta por CI; correcciones autorizadas en CII. El prompt literal y MEJORAR optativo ya tienen evidencia parcial. Falta cerrar validación de conflictos y mostrar payload/parámetros realmente usados, con igualdad preview/envío y comprobación del recorrido React/HTTP real |
| Q2 | Cancelación implementada sin evidencia completa del ciclo real | PARAR y cancelación del motor/separador existen (`memory.md` LXI; estado auditado en CI). Verificar cancelar/liberar recursos/recuperar y nueva operación real; conservar errores y evidencia. No confundir cancelar el trabajo con SALIR ni las pruebas de lógica con cancelación GPU |
| B6 | BPM original automático y BPM pedido en canción completa | Verificado el 2026-10-14 (memory CXXXII) con los dos audios reales del usuario: `f6fc62fe-Arroja la bomba.mp3` mide **363,64 BPM** (confianza 0,101) y el BPM común se rechaza con 422 «No hay un BPM original fiable»; un MP3 real a 199 BPM se mide como **99,2** (PEDÍA 199 · SALIÓ 99 en ficha y Biblioteca); en canción completa el BPM pedido 199 salió medido **104,7** y **250,5**. Además, el rechazo por duración no dice el mínimo. Corrección autorizada en curso (memory CXXXIII; spec02 B6): corregir octava, precargar medición revisable e informar mínimo; el usuario aprueba medir y ajustar por DSP cada variante full sin cambiar tono. Falta PASS/APPROVE final. Evidencia: `logs/fix-bpm-repro.json` y `logs/diag-groove-octave.py`. Al 2026-10-15 (memory CXXXVI) una variante de semilla 42 sí queda en 199,17 BPM a 90 s, y el lote no se publica si la otra variante no tiene pulso medible. CXXXVII genera de nuevo solo esa variante, con tope en configuración, y sigue sin publicar si la muestra nueva tampoco tiene pulso. |
| B7 | Ninguna opción de QUÉ HACER devuelve por sí sola lo pedido | Medido el 2026-10-15 (memory CXL y CXLI) en el remix por pistas de «Arroja la bomba»: batería en transformar, voz y acompañamiento en conservar, bajo quitado, frase «gabber, hardcore». El motor generó otro audio y el separador archivó el estilo fuera de la batería; la mezcla se quedó con un resto a unos 11 dB bajo la voz. El arreglo nuevo solo cubre **una** pista en transformar: esa pista monta la generación sin la voz nueva y sin los grupos quitados. No cubre canción completa, tramo, varias pistas a la vez, voz con base nueva ni el ajuste DSP. Una etiqueta corta no fija el estilo. La escucha de un remix rehecho con este arreglo sigue pendiente. |

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

1. [B6] Corrección en curso, autorizada por «continua» y la elección explícita de DSP posterior en canción completa (memory CXXXIII; criterios en spec02). Octava del BPM original, valor revisable a la vista, mínimo de duración y medición/ajuste individual de variantes. Falta PASS del tester y APPROVE final del reviewer; la reproducción y el diagnóstico están en CXXXII. Estado al 2026-10-15 en memory CXXXVI: la sonda de semilla 42 sigue en FAIL porque una de las dos variantes no tiene pulso. CXXXVII pide otra muestra de esa variante, sin bajar el corte ni inventar el BPM; la sonda nueva todavía no se ha ejecutado.
2. [R9]/[R10]/[Q2] Completar las correcciones autorizadas del cierre y verificar todos los criterios con tester/reviewer; estado en CII y entradas posteriores. [R11] quedó cerrada técnicamente en CXXXI, con su alcance rectificado en CXXXII, y no cierra estas historias
3. [F3]/[R9]/[B7] Veredicto de oído de cover, repaint, pistas y variantes. Ninguna opción de QUÉ HACER garantiza el estilo pedido (memory CXLI). El usuario escucha y sentencia; separado del PASS técnico
4. [D3] Instalador — candidato, requiere decisión del usuario
5. [C2]/[T2] Secuenciador — candidato solo si el usuario vuelve a quererlo, con samples locales

Hechas el 2026-10-05: [A4] compás en CREAR (selector COMPÁS 4/4·3/4·6/8, viaja al motor y a la ficha).
