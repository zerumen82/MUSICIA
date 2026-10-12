# R9 — REMIX integral: plan autorizado y cierre en corrección

Plan fechado el 2026-10-12; estado actualizado el 2026-10-13: **AUTORIZADO, PARCIALMENTE CUMPLIDO Y EN CORRECCIÓN** (`memory.md` CI/CII). Las ocho sondas y APPROVE de XCIX fueron evidencia parcial; la auditoría posterior emitió FAIL del cierre integral + CHANGES_REQUESTED. Los criterios técnicos pendientes y la escucha del usuario son distintos. No declarar cierre antes del nuevo PASS integral y APPROVE de los archivos completos.

Autorización explícita: «arreglas el problema del prompting e implementas el plan, teniendo en cuenta la autodetección de si es electrónica o no». Incluye R10 compartido con CREAR. La autodetección se ejecuta sobre audio real, informa su procedencia/incertidumbre y permite corrección manual; no añade instrumentos, voces, patrones o estilos al prompt ni sustituye decisiones explícitas. Sin nuevas instalaciones/modelos. Sus inferencias no son certificaciones artísticas.

Aclaración incorporada al alcance aprobado: el usuario exige revisar las adiciones no pedidas también en CREAR. El contrato común de prompts se registra en `spec/02-REQUISITOS.md` [R10]. El texto literal ya tiene evidencia parcial, pero siguen pendientes conflictos y preview efectivo en el cierre auditado. REMIX no resuelve por sí solo ese contrato compartido.

## Contexto y objetivo

El usuario quiere un remix real más versátil respecto al modelo y a la calidad. Conservar voz/guitarra fue un ejemplo del requisito general: respetar el prompt completo. El remix debe trabajar sobre material de la canción original, con operaciones musicales revisables, en lugar de reducir todas las peticiones a generación de base nueva.

Actualmente cover y repaint ya existen en Musicia. Esta propuesta no los presenta como funciones nuevas: completa su uso con controles reales del motor, edición de grupos, referencias y una canalización de calidad. Borrado, historial y nombres largos ya tienen PASS técnico y APPROVE (memory XCIV).

## Reglas y decisiones vigentes

- LOCAL-FIRST y NO HARDCODE: capacidades, perfiles, límites y parámetros en configuración/datos; ninguna plantilla sustituye el prompt por decisiones musicales inventadas.
- NO STUB / NO FAKE: operaciones conectadas al motor real; incompatibilidades y errores explícitos; un MP3 válido no demuestra fidelidad artística.
- Mantener el SFT, batch 2 y los parámetros actuales como punto de partida. Los ajustes explícitos del usuario mandan. No reactivar `use_format` ni `thinking` como planificación automática: la memoria documenta resultados que contradijeron la petición.
- Sin instalar paquetes, modelos ni skills. El modelo base, XL y SFT-stems no están instalados y no se incluyen en la fase propuesta.
- No habilitar tareas solo por `/v1/models`: su implementación local puede anunciar tareas base para SFT. La compatibilidad debe contrastarse con checkpoint, código y documentación del fabricante.

## Fase autorizada con lo instalado

1. **Un proyecto de remix asociado al original.** Prompt libre, origen y referencia opcional; operación y zonas/grupos elegidos revisables. Mantener el texto exacto del usuario y mostrar los parámetros efectivos. No inferir silenciosamente otra operación mediante palabras sueltas. La interfaz enseña controles útiles y el resultado de las operaciones, con opciones avanzadas plegadas.
2. **Transformar la canción completa.** Cover con audio original y prompt completo; conservar la distinción entre fidelidad al original, intensidad de transformación y referencia tímbrica. Exponer `cover_noise_strength` y el audio de referencia, además de los controles ya existentes, solo con rangos del contrato real del motor.
3. **Editar secciones.** Repaint con intervalo/máscara explícitos, intensidad y transiciones. Modo conservador/equilibrado para reinsertar el audio original fuera de la sección; el modo agresivo debe identificar que transforma también ese contexto. Repetir operaciones sobre el resultado elegido permite trabajar varias secciones sin fingir extensión mediante `-1`.
4. **Trabajar con material conservado.** Demucs instalado puede producir batería, bajo, voz y `other`. El usuario selecciona grupos que conserva y grupos que transforma; el material a transformar entra como audio al motor, y después se recombina. `other` es acompañamiento agrupado, no guitarra/piano aislados. Conservar una grabación, aproximar su composición y resintetizar canto son decisiones diferentes. La falta de letra nueva no debe forzar instrumental en todo remix.
5. **Canalización de calidad.** Intermedios WAV o FLAC coherentes con su contenedor; MP3 solo en la exportación final elegida. Mezcla/alineación y medidas técnicas existentes, sin etapas de compresión sucesivas ni normalizaciones duplicadas. Parámetros en config; no afirmar que más pasos o una medición de volumen garantizan mejor música.
6. **Dos variantes y comparación con el original.** Escuchar A/B, comparar tramos alineados y guardar fuente, prompt, operación, zonas/grupos, semillas y parámetros efectivos. Distinguir mediciones técnicas de aprobación musical del usuario.

La interpretación artística corresponde al condicionamiento real del modelo sobre texto y audio. Musicia debe transmitir intención, material y controles de forma fiel, validar el contrato y permitir revisar operaciones. No se promete que un análisis LM produzca por sí solo un planificador universal.

## Integración de UI y selección de grupos — diseño autorizado 2026-10-12

El usuario pidió selección de instrumentos integrada en la UI y menos opciones redundantes. La autorización de XCVIII incluye este diseño; `RemixWorkspace.jsx` ya implementa los tres ámbitos, con criterios abiertos identificados en CI. «HAZLO» en CII autoriza completar esas correcciones sin nuevas instalaciones.

- **Una misma mesa dentro de SUBIR y BIBLIOTECA**, reutilizando el panel actual. Encabezado con original y tres ámbitos: canción completa, tramo y por pistas. Prompt y botón REMIX siempre visibles; el resto aparece según el ámbito. No crear una pantalla independiente ni mantener once acciones en el desplegable.
- **Canción completa**: prompt, un control de transformación/conservación y BPM con opción de mantener el original. La duración nativa de cover se muestra como dato de la fuente: no se ofrece un campo de duración que el motor ignore. Cambiar longitud requiere una operación explícita de recorte/arreglo soportada, dentro de ajustes; no se presenta como un parámetro de cover ni como extensión automática. Referencia opcional en un panel plegable. Los parámetros expertos y el detalle de lo enviado se despliegan cuando se necesitan.
- **Tramo**: forma de onda del original, selección de intervalo y los controles de edición regional. No renderizar opciones de pistas si no se trabaja por grupos.
- **Por pistas**: acción SEPARAR con progreso real; después filas compactas de los grupos realmente producidos. Con el separador instalado: voz, batería, bajo y acompañamiento restante. Cada fila permite escuchar en solo y elegir una única acción: conservar, transformar o quitar. Volumen y opciones de mezcla en un desplegable adicional. La UI obtiene IDs/etiquetas/capacidades del backend/configuración; no se añade una lista de instrumentos supuestos en React.
- **Selección sin engaño**: acompañamiento restante puede contener varios instrumentos. No presentar guitarra, piano o sintetizador como stems independientes. Un cambio libre solicitado por prompt sigue condicionando el motor, pero eso no acredita aislamiento exacto de un instrumento ni una operación que el checkpoint no soporte.
- **Transformación y recombinación**: transformar un grupo no equivale a ofrecer Lego/Extract ni a garantizar que SFT emita un stem puro. Si cover genera mezcla completa, separar el resultado con el motor instalado, recuperar los grupos elegidos y recombinarlos con los originales declarados como conservados. Ese camino exige pruebas reales de contaminación, alineación y calidad antes de habilitarlo; una salida musical completa no se mezcla ciegamente como si fuera batería aislada.

### Simplificación propuesta del menú actual

| Opciones actuales | Tratamiento propuesto en la UI |
|---|---|
| VERSIÓN / REESTILAR | Una sola transformación de canción completa; comparten cover |
| TRAMO | Ámbito tramo, con selección de onda |
| VOZ + BASE NUEVA | Conservar su recorrido de generación de base desde cero y mezcla con voz original mediante acceso contextual en la mesa. La transformación cover de grupos no demuestra equivalencia; restaurar el acceso perdido identificado por CI |
| MEDIO TIEMPO / DOBLE TIEMPO / FORZAR TEMPO | Un control de tempo; multiplicadores como accesos dentro de ajustes |
| QUITAR VOCES / SOLO LA VOZ | Acciones de los grupos: quitar voz o conservar voz y quitar los demás |
| LOOP DE 4 COMPASES | Herramientas de recorte/loop dentro de ajustes, con medidas reales |
| AJUSTAR | Panel plegable de tempo, tono, recorte, fundidos y mezcla |

No se borran endpoints ni se rompe la apertura de trabajos/funciones existentes por reorganizar su acceso en la UI. La migración debe mantener una ruta equivalente para las funciones útiles; el nuevo modo por grupos no se presenta como equivalente musical a la antigua generación desde cero sin haberlo verificado. Glosario y AÑADIR siguen disponibles en la zona del prompt, compactos; no se filtran datos reales del catálogo arbitrariamente.

**Criterios UI añadidos**: misma experiencia en SUBIR/BIBLIOTECA; selección por grupo serializable y persistida; una sola acción por grupo; preescucha real; controles contextuales, accesibles con teclado; sin dos sliders de FUERZA ni dos acciones cover distintas; comprobar en las dimensiones reales de Electron que no se satura la vista. Los paneles expertos no son necesarios para lanzar el recorrido básico.

La UI no muestra controles editables sin efecto en la tarea elegida. En particular, cover mantiene la duración de la fuente; un cambio de longitud se representa como otra operación explícita y verificable sobre la timeline.

## Pasos de implementación y archivos

1. Registrar capacidades comprobadas y contratos/configuración: `backend/config.py`, `backend/config.example.json` y catálogo de capacidades como datos; fuente visible en API. Definir validación de referencias, grupos, regiones y parámetros.
2. Adaptar cliente y trabajos: `backend/music_service.py`, `backend/main.py`; distinguir transformación de canción, edición regional y recombinación. No aceptar `text2music` como conservación del original: el motor ignora la fuente en esa tarea.
3. Adaptar separación y mezcla: `backend/separator_service.py`, `backend/mixer_service.py`; grupos actuales, contenedores sin pérdida, duración/timeline y errores honestos. Mantener la función de voz existente para compatibilidad.
4. Integrar el proyecto de remix en `frontend/src/components/RemixActions.jsx`, los paneles que lo usan y `frontend/src/api.js`: prompt, original/referencia, controles de transformación, regiones/grupos y A/B. Evitar seis etiquetas para operaciones iguales y textos explicativos repetidos.
5. Tests de contratos/regresiones, reviewer independiente y tester con audio real. Actualizar spec y memory con artefactos, resultados y límites.

## Criterios de aceptación

- Cada transformación guarda y utiliza una fuente real, con tarea y parámetros verificables en el motor. No crea simplemente otra canción al pedir un remix basado en el original.
- Prompt y valores explícitos del usuario no se sustituyen por presets ni metadatos inferidos. Si algo no está soportado, la operación no anuncia éxito.
- Cover, repaint y recombinación son caminos distintos, con errores y cancelación reales y resultados persistentes.
- Repaint conservador/equilibrado permite verificar el audio fuera de la región y sus transiciones sobre intermedios sin pérdida, con tolerancias justificadas por la operación. La máscara se deriva del intervalo admitido por el contrato; no se ofrecen máscaras arbitrarias. Declarar cualquier normalización posterior y no confundir cambios globales de nivel con conservación exacta.
- Los grupos declarados como conservados se reutilizan en la mezcla; no se presentan instrumentos individuales inexistentes en la separación.
- La duración/estructura resultante corresponde al plan explícito. Una base corta no produce una cola de voz larga inadvertida como si fuera la duración pedida.
- Archivos válidos, sin clipping introducido por la canalización, medidas reales, dos variantes y comparación con el original. La adecuación artística requiere escucha del usuario.
- Lint/build/suites verdes, PASS del tester con evidencia real y APPROVE del reviewer de archivos completos. Sin regresiones de biblioteca, historial, nombres, cola y controles existentes.

## Impacto y límites

La propuesta reutiliza motor, separación, DSP y UI existentes. Amplía operaciones reales sobre la canción y evita pérdidas evitables en la canalización, manteniendo las funciones ya utilizadas. La separación de grupos es estimada y el cover conserva rasgos musicales de forma aproximada: no equivale a copiar muestras exactas.

Más regiones/grupos implican más tiempo y cómputo; las operaciones se serializan para no solapar generación y separación en la GPU de 8 GB. No se modifica software ajeno ni se presupone margen de VRAM.

**Fuera de esta primera fase:** lego/extract/complete del modelo base, aislamiento universal de instrumentos, XL y puntuación automática que certifique calidad musical. El análisis local `full_analysis_only` ya está integrado en `source_understanding.py` y tiene evidencia de ejecución real en XCIX; esa sonda no certifica su precisión universal. Sus inferencias son revisables y no se convierten en órdenes del prompt. Base o SFT-stems requieren elección y autorización de descarga, pruebas de memoria y comparación musical antes de ofrecerlos.

## Evidencia de capacidades y fuentes

Inventario local: turbo y SFT con pesos de 4.787.825.604 bytes cada uno; LM 0.6B y 1.7B completos, VAE y embedding presentes; no base, XL ni SFT-stems. Se mantiene LM 0.6B para el perfil medido, sin cargar 1.7B por su mera presencia.

Investigación de `sd_researcher`: `release_task_models.py`, `job_generation_setup.py`, `job_analysis_runtime.py`, handler de generación y `repaint_waveform_splice.py`, además de clientes/backend/UI de Musicia. Controles rastreados desde contrato hasta ejecución; no solo nombres de un menú.

- [Tabla oficial de modelos](https://github.com/ace-step/ACE-Step-1.5#-model-zoo)
- [API del fabricante](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/API.md)
- [Contrato implementado](https://github.com/ace-step/ACE-Step-1.5/blob/main/acestep/api/http/release_task_models.py)
- [Inferencia y tareas](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/INFERENCE.md)
- [Guía de GPU](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/GPU_COMPATIBILITY.md)

Las fuentes remotas orientan el diseño; el comportamiento del vendor instalado y las pruebas locales mandan ante discrepancias.

Revisión independiente inicial `sd_reviewer`: **APPROVE del plan**. XCIX registró ocho sondas GPU PASS y APPROVE de la implementación; C afirmó el cierre. **La auditoría CI del 2026-10-13 corrige ese estado:** FAIL del cierre integral + CHANGES_REQUESTED del producto, con APPROVE de la exactitud del informe. Las pruebas anteriores se conservan dentro de su alcance.

## Correcciones autorizadas tras auditoría (2026-10-13)

- Comparación A/B con una posición y tramo comunes entre original y variantes; dos reproductores independientes no cumplen el criterio.
- Conflictos explícitos texto/BPM/voz resueltos antes de generar y preview de los parámetros que realmente se enviarán. No presentar el request de Musicia como payload efectivo del motor.
- Restaurar voz original + base nueva y GLOSARIO/AÑADIR/variantes en acompañamiento, manteniendo las funciones útiles existentes.
- Compartir el estado de región entre onda y campos; persistir procedencia de clasificación y semillas por variante; mostrar advertencias de modo agresivo y normalización.
- Verificar recorridos reales en Electron a ambas dimensiones, cancelación/liberación/recuperación y audio con oráculos adecuados; completar reviewer/tester separados. La escucha artística sigue siendo del usuario.

Implementación y contratos concretos en `spec/01-ARQUITECTURA.md`; estado final únicamente según `spec/02`, `spec/03` y evidencia de `memory.md` CII y entradas posteriores.
