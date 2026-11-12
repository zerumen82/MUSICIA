# Glosario B9c y regeneración de Musicia.exe — 2026-11-12

Registro consolidado de esta sesión. Los informes y datos completos permanecen en `logs/glossary-20261112/` local; los audios, en `backend/outputs/`. No se publicaron modelos, dependencias ni audio en servicios externos. La bitácora cronológica está en `memory.md`.

## Petición, decisiones y cambio

El usuario comunicó que el glosario no aplicaba una descripción que ayudase al modelo, insistió en que ACE-Step entendiera el estilo y pidió anotar todo y regenerar el EXE. Eligió descripciones documentadas y aprobó el plan y el texto concreto de la primera ficha.

El vocabulario contiene etiquetas, no una biblioteca exhaustiva de definiciones. La combinación literal `techno hard house` carecía de ficha exacta y producía solo `Predominantly techno hard house.`. La reproducción inicial y cuatro POST reales están conservados en `diagnostic.json`, `tester.json` y sus scripts. La investigación no localizó una definición exacta del híbrido publicada por ACE-Step.

Se implementó una ficha editorial de Musicia, aceptada expresamente por el usuario, basada en ejemplos documentados de sus componentes. Su procedencia se conserva y muestra; no se presenta como definición oficial del fabricante:

> A high-energy electronic track with a steady four-on-the-floor rhythm, hard kicks, driving basslines and hypnotic synth patterns.

La ficha entra en el caption efectivo enviado al motor. Las descripciones se pueden leer antes de seleccionar y se muestra cuál se aplicó realmente. QUITAR, detalles propios, exclusiones, principal y matices se conservan. No hay asignación por subfrases: `acid jazz` permanece sin ficha. Las 29 reglas/opciones anteriores se mantienen y no se amplía silenciosamente la detección de texto libre. La cobertura del resto de etiquetas sin ficha queda declarada en spec/03.

Fuentes y argumentos completos: `research.md`, `official-corpus-inspection.json`, `plan-fichas-documentadas.md`. La consulta web fue documental; el producto no consulta web ni LM al seleccionar una ficha. No hubo instalaciones ni cambios al perfil SFT, separación, BPM, mezclador o continuación.

## Verificación ejecutada y límites

| Comprobación | Resultado y evidencia local |
|---|---|
| Backend focal de la implementación | 111/111 OK; `editor-backend-tests-final.log` |
| Frontend completo | 79/79, exit 0; `frontend-suite-summary.txt` |
| ESLint / Vite build | exit 0 / exit 0; logs `editor-frontend-*`; bundle `index-KYToTfcH.js` |
| API final real | 12/12 PASS; `tester-api-b9c.json` |
| UI real final | 8/8 PASS; `ui-functional-02/result.json`, capturas |
| A/B real desde UI y motor | Cuatro MP3 válidos de 20 segundos; `ui-ab-01/ab-evidence.json` |
| Reviewer de código | APPROVE; `reviewer-code-final.md`, diez hashes en `reviewer-code-sources.json` |
| Suite backend global | 483 tests, 6 fallos/subcasos y 2 omitidos; `backend-suite-offline.log`. No se declara verde |
| Repetición de las dos fixtures que fallaron | 2/2 OK, exit 0; `fixture-recheck.log` |

Los otros cuatro fallos/subcasos globales pertenecen al archivo preexistente no rastreado `test_pending_audio_contracts.py`, sobre T10/T11; ese archivo y el producto de esos pendientes no se modificaron. No se cierra ese alcance ni el resto de historias integrales. La primera ejecución global quedó interrumpida durante la carga del traductor; se conserva `backend-suite.log`. La repetición usó modo offline solo en el entorno de prueba, con pesos ya instalados.

Se conserva el FAIL del primer driver UI: exigía mayúscula inicial y recibió `predominantly acid jazz` en minúscula, manteniendo la etiqueta. Solo se corrigió el driver; el recorrido posterior pasó. La detección del idioma activó traducción innecesaria, pero no se acreditó sustitución musical de esa etiqueta.

En Por pistas, `ui-groups-01` verificó realmente separación en cuatro grupos, herencia/aplicación de ficha y veto por exclusión cruzada. El cuarto caso adicional de `acid jazz` propio quedó NO VERIFICADO: se destruyó la ventana y el arnés registró IPC de salida sin handler. Se conserva el FAIL del driver sin atribuir la autoría del cierre ni convertirlo en un fallo productivo probado. No hubo nueva generación ACE-Step de grupos.

## Audios para escuchar

Ambos trabajos terminaron `succeeded`. Cada archivo tiene 20,000000 segundos y 321.068 bytes, `ffprobe` y decodificación exit 0, descarga HTTP 200 y SHA-256 idéntico al disco. Los parámetros efectivos coinciden salvo el prompt.

Primera pareja, con semilla registrada 424242 en ambos casos:

- Etiqueta sola: `backend/outputs/glosario-b9c-label-only-1794477987886.mp3`; job `21a56cbf2d11425f9fbad934ff18faeb`.
- Con descripción: `backend/outputs/glosario-b9c-descriptive-1794478194389.mp3`; job `12100209bc7a40929ba3e939a6be3575`.

Las segundas variantes usan semillas diferentes (4292549306 y 2592926165); no constituyen una pareja equivalente. Tener la misma semilla registrada no acredita determinismo completo del motor. El texto sí llegó al modelo y los audios existen; la comprensión/fidelidad musical y la aceptación artística quedan pendientes de la escucha del usuario.

## Ejecutable solicitado

Se recompiló el lanzador existente desde `scripts/launcher/Launcher.cs` con el `csc.exe` de .NET Framework instalado en Windows, destino Windows GUI, referencia `System.Windows.Forms.dll` e icono `frontend/build/icon.ico`. Compilación exit 0; fuente e icono intactos. No se creó un instalador ni un ejecutable autónomo nuevo.

Publicado: `Musicia.exe`, 15.872 bytes, SHA-256 `9413edd3b997f246071791d011450c754c5834547f7d606f8d740e34f3bc9804`. Backup previo: `logs/glossary-20261112/Musicia-before.exe`. Cabeceras PE/.NET/GUI, recursos, candidato, publicado y backup verificados. Reviewer: APPROVE en `reviewer-exe.md`, seis identidades sin discrepancias. Comando, salidas y manifiesto completos: `editor-exe.md`, `exe-build.json`, `rebuild_launcher.py`.

La prueba de arranque real y el veredicto consolidado del tester se incorporarán tras su ejecución. Compilar el binario no sustituye esa comprobación.

## Preservación y continuidad

Se conservaron cambios anteriores de memory/spec, `test_pending_audio_contracts.py` y el backup JSX. No hubo commits, push, instalaciones ni cierre de tareas ajenas. La API/ventana originales desaparecieron antes de cualquier actuación del coordinador sobre ellas; no se atribuye causa. Se arrancó la API final con el lanzador del proyecto y se verificó salud real después del aviso temprano del script.

El usuario autorizó liberar modelos de ComfyUI solo con cola vacía y sin cerrar la aplicación. No fue necesario utilizar ese permiso: la VRAM se liberó externamente antes del A/B. Los procesos ajenos se preservaron. No se atribuyen los WinError10054 originales a la ausencia de ficha sin evidencia causal.
