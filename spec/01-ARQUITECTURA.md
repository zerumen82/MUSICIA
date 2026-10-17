# 01 · Arquitectura

Estado contrastado el 2026-10-13. R9/R10 tienen implementación y correcciones autorizadas en curso; los contratos descritos no equivalen al PASS integral del producto. Evidencia y veredictos en `memory.md` CI/CII y entradas posteriores. R11 quedó verificado técnicamente el 2026-10-14 (memory CXXXI) sin cerrar R9/R10.

## Procesos

```text
Electron (frontend/main.cjs)
    → http://127.0.0.1:8000
FastAPI (backend/venv, Python 3.10 del equipo)
    → sirve frontend/dist en /
    → HTTP local al motor ACE-Step 1.5 :8001
        vendor/ACE-Step-1.5/.venv (Python 3.12, torch)
    → proceso Demucs en backend/demucs-venv
    → ffmpeg/ffprobe y archivos locales
```

La GPU verificada es RTX 3060 Ti de 8 GB. El perfil aprobado usa SFT en toda la app, 50 pasos/guidance 9/batch 2, LM 0.6B, `thinking` y `use_format` apagados; configuración y valores explícitos de la petición determinan los parámetros efectivos. No hay instalaciones nuevas en R9/R10. Generación, separación y análisis se coordinan para evitar solapamientos de GPU.

El arranque local aplica `scripts/patches/acestep_vae_cpu_dtype.patch` mediante `scripts/apply_acestep_patches.py` antes de importar un motor ausente. El parche usa la política CPU del VAE para convertir modelo y latentes, y restaura dispositivo y dtype incluso tras error; no cambia el perfil de generación. El aplicador acepta bloques originales o ya corregidos, conserva saltos de línea, escribe de forma atómica y rechaza implementaciones desconocidas. Un motor presente no se modifica. Esto permite reproducir la corrección pese a que `vendor/` no se versiona. Réplica CPU y UI/CREAR verificadas con PASS/APPROVE en memory CXVII; no equivalen al cierre R9/R10 entero.

## Contratos

### Motor ACE-Step (vendor externo)

- `POST /release_task` → tarea aceptada; respuesta envuelta en `{data, code, error}`.
- `POST /query_result` con `task_id_list` → estado `0=curso, 1=ok, 2=fallo`; `result` es texto JSON de audios/metadatos.
- `GET /v1/audio?path=…` → audio; respetar la ruta/URL devuelta por el motor.
- `GET /health` → disponibilidad/modelos inicializados; `GET /v1/models` es inventario, no autorización de capacidades.
- SFT instalado: text2music/cover/repaint y referencia tímbrica. No Lego/Extract/Complete ni aislamiento universal por nombres de menú.
- Análisis nativo `full_analysis_only`: metadatos derivados del audio; no es un planificador musical universal.

### Musicia API

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/info`, `/health` | metadatos y estado real del motor |
| GET | `/music/config`, `/music/models` | configuración, límites y modelos permitidos/cargados; no cambia modelo |
| POST | `/music/preview` | validar petición de generación y mostrar parámetros efectivos/procedencia/advertencias antes de enviarla |
| POST | `/music/generate` | enviar tarea real → job y URL de estado |
| GET | `/music/status/{job_id}` | generación, errores y resultados con parámetros efectivos |
| GET | `/music/jobs` | historial común de generación/remix/separación |
| GET | `/music/process-logs` | final real de la salida del motor, de su error y del error de la API |
| POST | `/music/jobs/{job_id}/cancel` | cancelar trabajo; reiniciar motor si la operación lo requiere |
| GET | `/music/library`, `/music/audio/{name}` | biblioteca/fichas y audio generado |
| PATCH / DELETE | `/music/audio/{name}` | renombrar/borrar audio y ficha; conflicto real si el archivo está ocupado |
| POST | `/music/audio/delete_many` | borrado por lote con resultado por archivo |
| POST / GET | `/audio/upload`, `/audio/uploads` | subir/listar fuentes reales |
| GET | `/audio/uploads/file/{name}` | audio subido |
| GET | `/audio/peaks/{name}`, `/audio/groove/{name}` | onda, duración y medidas rítmicas |
| POST | `/audio/mix`, `/audio/mix/plan` | mezcla y plan de cuadre opcional |
| POST | `/audio/separate` | separar voz/base en segundo plano |
| GET | `/audio/separate/{job_id}`, `/audio/separate/status` | job y disponibilidad real de Demucs |
| GET | `/music/remix/capabilities` | ámbitos, grupos/acciones, límites/defaults y advertencias del checkpoint |
| POST | `/music/remix/analyze` | análisis local revisable de la fuente, con job |
| GET | `/music/remix/analyze/{job_id}` | progreso, metadatos, incertidumbre y resultado del análisis |
| POST | `/music/remix/separate` | producir los cuatro grupos reales y su identidad de origen |
| POST | `/music/remix/preview` | validar proyecto sobre original y mostrar operaciones/parámetros efectivos; declarar material aún pendiente |
| POST | `/music/remix/project` | ejecutar cover, repaint o conservar/transformar/quitar grupos |
| POST | `/audio/remix/ai/preview` | preview de remix compatible, incluida voz original + base nueva |
| POST | `/audio/remix/ai` | voz/base o cover: separar/generar/cuadrar/mezclar según operación |
| GET | `/audio/remix/ai/{job_id}` | estado y resultados de remix, incluido proyecto integral |
| POST | `/audio/remix`, `/audio/process` | DSP y procesamiento de audio |
| POST | `/audio/tempo`, `/audio/loop`, `/audio/crossfade` | herramientas de tempo/loop/transición |
| GET | `/music/style_options`, `/music/genre_glossary`, `/music/genre_glossary/combine` | opciones y glosario del catálogo real |
| POST | `/music/enhance_prompt`, `/audio/remix_prompt` | propuestas optativas; no sustituir intención sin decisión del usuario |
| POST | `/music/write_lyrics` | borrador de letra mediante LM local |
| GET | `/` | UI de `frontend/dist` |

Los tres previews incorporados en la corrección CII comparten preparación con la ejecución correspondiente. Devuelven `effective_parameters`, `provenance` y `warnings`, y operaciones/material pendiente cuando corresponda; conflictos se devuelven como HTTP 422 con `detail`. En voz/base o transformación de grupos, rutas de material que todavía debe generarse/separarse se declaran pendientes, sin fingir un payload concreto de audio ya disponible. Verificar la igualdad preview/envío y la trazabilidad es un criterio del cierre, no un éxito supuesto por tener endpoint.

### Proyecto y fuente

`RemixProjectRequest` identifica fuente y origen (upload/output), prompt literal, ámbito full/region/groups, referencia opcional, controles cover/repaint, BPM/semilla/letra/voz y acciones/ganancias por grupo. Región debe quedar dentro de la duración real; cada grupo tiene una acción. Clasificación y procedencia manual/análisis/unknown son datos revisables, no instrucciones implícitas.

R11 (autorizado el 2026-10-14 y verificado técnicamente con PASS del tester y APPROVE del reviewer, memory CXXXI) añade `duration_seconds`, `source_bpm`, `repeat_start`, `repeat_end` y `transition_seconds`. En grupos, el BPM común usa un único filtro `atempo` de ocho canales sobre los cuatro grupos estéreo antes de transformar/recombinar; el original medido se puede revisar manualmente. La duración natural se deriva de la relación BPM objetivo/original y el cover opera sobre el material preparado, sin un segundo estiramiento. En full, el BPM conserva su contrato de condicionamiento del motor y se mide el resultado por separado.

La ampliación full/groups ocurre después de cover o recombinación: repite el material o la parte elegida con fundidos hasta la duración objetivo, en PCM float; después exporta a MP3. Los tiempos de parte se expresan sobre el original y se mapean al tempo común. No se permite usar la ampliación como recorte ni dentro de repaint regional. Capacidades publica límites/defaults de timeline derivados de configuración. Preview, operaciones del job, variantes y ficha registran duración original/natural/final, relación y procedencia de tempo, sección y repeticiones. La duración cover nativa sigue siendo la de la fuente preparada.

**Corrección de entrega verificada, 2026-10-15 (memory CL; tester PASS/reviewer APPROVE)**: tras descargar un lote se conserva un recibo local con identidad de proyecto/tarea/fuente, parámetros y huellas de los WAV y sus metadatos, anclado por SHA256 en el historial. `scripts/complete_downloaded_remix.py` permite completar explícitamente el posprocesado de un remix Por pistas interrumpido, usando esos archivos verificados y el mismo runtime de mezcla/ampliación/exportación/publicación, sin otra inferencia. Inspecciona por defecto; `--execute` exige lote completo, servicios detenidos, copia de historial y preservación de trabajos ajenos. Para lotes anteriores al recibo se contrasta el resultado real de la caché local del motor y sus archivos con las descargas. No se reanudan tareas automáticamente; SALIR conserva su apagado y Q1 mantiene la marca de interrupción. El lote se publica tras verificar todas sus variantes. La ejecución real recuperó dos MP3 de 240 s y sus fichas, verificados en biblioteca/API/Electron; no cierra los defectos de BPM o estilo.

**Rectificación 2026-10-14 (memory CXXXII)**: comprobado con los audios reales del usuario, el BPM original automático falla de octava (363,64 BPM en `f6fc62fe-Arroja la bomba.mp3`; 99,2 en un MP3 generado a 199) y en full el BPM pedido no se cumple (pedido 199 → medido 104,7 y 250,5). El cambio común de tempo solo es fiable con el BPM original revisado a mano; el defecto queda abierto como B6 en `spec/03-PENDIENTES.md`.

Los grupos de Demucs se validan como cuatro WAV float finitos, de duración y formato comunes; la caché requiere digest de fuente y firma de modelo/dispositivo/shifts/overlap/grupos/formato. Separación y preparación comprueban que la fuente no haya cambiado durante la operación. Estas validaciones técnicas no certifican la calidad de aislamiento ni el cumplimiento musical del cover.

**Contrato B6 autorizado, 2026-10-14 (memory CXXXIII; implementación en curso)**: en full con BPM elegido, el condicionamiento del motor se acompaña de medición independiente y ajuste DSP posterior de cada variante, sin cambio de tono. El preview declara pendientes la medición, relación de tempo y duración natural; la ejecución calcula un plan individual antes de ampliar y exportar. Si ninguna variante full se puede medir, si el BPM medido sale de la tolerancia, o si la duración pedida es inferior a la natural efectiva, se produce un error con causa y mínimo concreto. Si otra variante sí tiene pulso, se publica esa y la que no mide queda fuera. Por pistas mantiene su tempo PCM común y expone medición original revisable. Region conserva el BPM orientativo del motor sin aplicar un estiramiento global. Este contrato no está verificado todavía; criterios y estado en spec02 B6.

El análisis nativo devuelve metadatos, tramo analizado y base de clasificación; no inventa una probabilidad. Los grupos son únicamente voz, batería, bajo y acompañamiento restante (`other`). Transformar grupos mediante cover requiere separar el resultado antes de recombinar; no tratar una canción completa como un stem puro.

Intermedios de proyecto sin pérdida, exportación final y ficha con fuente/digest, operaciones, parámetros efectivos y metadata de variantes. Repaint equilibrado/conservador reinserta contexto; el modo agresivo cambia su tratamiento. La normalización del motor/exportación debe declararse y distinguirse de conservación PCM exacta.

### Frontend y persistencia

- Cliente único `frontend/src/api.js`, con `VITE_API_BASE_URL` opcional.
- Límites/defaults de configuración/capacidades API; preview enviado al backend en las rutas con prompt.
- Jobs `queued | running | succeeded | failed`; la cancelación se refleja con estado/error reales, no un éxito inventado.
- Borradores de CREAR en estado React: las pestañas permanecen montadas, por lo que se conservan al navegar. Actualmente no se guardan en localStorage al cerrar la aplicación. Historial de jobs en `backend/job_history.json` mediante snapshot atómico y campos declarados; no handles ni reloj monótono persistido.
- Al recuperar un job interrumpido se informa fallo; no se reanuda una inferencia anterior. Archivo y ficha permanecen en biblioteca.
- Electron carga la UI local, con contextIsolation y sandbox; la X se ignora, SALIR cierra la app y para servicios, y el bundle actualizado provoca recarga.

## Módulos

| Backend | Responsabilidad |
|---|---|
| `config.py`, `config.example.json` | defaults → JSON → variables MUSICIA_*, perfiles y límites |
| `music_service.py` | payload/submit/sondeo/descarga, semilla y parámetros efectivos, validación de audio |
| `prompt_constraints.py`, `prompt_constraints.json` | validación de contradicciones explícitas según patrones configurables; no comprensión semántica universal |
| `remix_project.py` | proyecto, fuente/referencia, cover/repaint/grupos, intermedios y recombinación |
| `source_understanding.py`, `source_categories.json` | análisis local de audio, catálogo de categorías, evidencia e incertidumbre |
| `separator_service.py`, `demucs_local.py` | separación real y gestión del proceso Demucs |
| `mixer_service.py` | ffmpeg: cuadre, atempo/adelay/loudnorm, loop, tempo, crossfade y grupos |
| `audio_analysis.py`, `audio_service.py` | medición DSP y ganancia/fade/recorte |
| `prompt_style.py`, `prompt_enhancer.py`, `genre_glossary.py` | catálogo/opciones reales y borradores optativos; el cuadro conserva el texto |
| `style_translator.py`, `style_translator_worker.py`, `nllb_languages.json`, `style_term_fixes.json` | el estilo pasa a inglés en local antes del envío; la letra no se traduce; batería/bombo mal traducidos se corrigen con el fichero |
| `main.py` | rutas, preparación de peticiones/preview, jobs/cancelación, fichas y UI estática |

| Frontend | Responsabilidad |
|---|---|
| `src/api.js` | HTTP, previews y configuración común |
| `src/App.jsx` | shell, navegación, salud/modelos y sondeo del trabajo activo. Desde el 2026-10-16 CREAR no lista la cola: la pista terminada está en BIBLIOTECA |
| `src/components/Composer.jsx` | creación, letra, controles y prompt |
| `src/components/Uploads.jsx`, `Library.jsx` | fuentes, biblioteca/fichas y acceso a herramientas |
| `src/components/RemixActions.jsx`, `RemixWorkspace.jsx` | mesa contextual sobre original, regiones/grupos y resultados |
| `src/components/RemixIAPanel.jsx` | acompañamiento nuevo con prompt y herramientas compartidas |
| `src/components/PromptTools.jsx` | herramientas compartidas GLOSARIO/AÑADIR/variantes y borrador MEJORAR optativo |
| `src/components/EffectivePreview.jsx` | parámetros y procedencia preparados por el backend para la operación elegida |
| `src/components/AudioComparator.jsx`, `src/audio_comparison.js` | reproducción única, posición e intervalo común de original/variantes |
| `src/components/VoiceBackingPanel.jsx` | acceso a voz original y base nueva, con controles y preview |
| `src/components/Waveform.jsx` | onda/selección regional |
| `src/components/MixLab.jsx` | mezcla real |
| `src/audio_player.js`, `src/vocal.js` | recursos de reproducción y estructura de canto |

La verificación final de los componentes nuevos corresponde al tester/reviewer. `Mixer.jsx` no está montado; `Sequencer.jsx` sigue fuera de navegación. La locución/edge-tts se retiró y no forma parte del contrato.

## Decisiones registradas

| Fecha | Decisión | Motivo/evidencia |
|---|---|---|
| 2026-10-01 | Motor como proceso separado | venv/torch propios del motor; API sin cargar el modelo como librería |
| 2026-10-01 | ACE-Step en vez de MusicGen | decisión de licencia registrada |
| 2026-10-01 | API sirve UI e historial inicial de canciones en localStorage | escritorio local sin cuentas; historial sustituido posteriormente por biblioteca/fichas |
| 2026-10-06 | Cola en disco y PARAR | Q1/Q2, memory LXI; implementación distinta de e2e cancelación |
| 2026-10-09 | SFT en toda la app | decisión explícita del usuario, LXXXVII |
| 2026-10-12 | R9/R10 con lo instalado | XCVIII: prompt fiel, original/grupos/regiones, análisis revisable; sin descargas |
| 2026-10-13 | Corregir el cierre tras auditoría | CI/CII: recuperar criterios y funciones faltantes; PASS/APPROVE nuevos obligatorios |
