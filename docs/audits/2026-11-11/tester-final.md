# sd-tester — PASS técnico limitado de la auditoría

2026-11-11. Veredicto independiente: **PASS** de las correcciones y recorridos
acreditados en esta auditoría. No equivale a cierre integral de Musicia,
R9/R10/B6/B7/Q2/R18 ni a aprobación artística del audio.

## Fuentes y regresión final

- Se recalcularon SHA-256 de las **20 fuentes** del snapshot final del reviewer:
  **20/20 coinciden**, sin ediciones posteriores al inicio de la última suite.
  Evidencia: `tester-final-source-sha256.json` y `reviewer-source-sha256.json`.
- Suite backend oficial final: `Ran 466 tests in 310.038s; OK (skipped=2)`,
  proceso **exit 0**. Son **464 PASS, 0 FAIL/ERROR y dos omisiones** por WAV
  históricos ausentes. Evidencias: `backend-suite-validated.log` y
  `backend-validated-process.json`. Ejecutada con HF_HUB_OFFLINE=1 y
  TRANSFORMERS_OFFLINE=1; no se instalaron dependencias para verificarla.
- Frontend posterior al cambio final de AudioComparator: **77/77**, lint y
  build **exit 0**; asset `index-CMqgxfl9.js`. Evidencias:
  `frontend-ab-final-process.json` y logs `frontend-*-ab-final.log`.
- La contención IPC conserva tres regresiones PASS; la identidad API y sus
  guardas de supervisor tienen 25 focales PASS. La suite completa final incluye
  los nuevos contratos, sin sustituirlos por el resultado focal.

## Comportamiento real contrastado

- `functional-05/result.json`: **21 PASS**, sin excepciones de renderer.
  Incluye las cuatro vistas a 1400×900 y 1080×700, controles y conflictos,
  selección y letras, reproducción, subida, las cinco acciones contextuales de
  remix, parámetros inválidos, región/teclado, exclusiones de grupos inactivos,
  ampliación sin prompt y mezcla SIN CUADRAR con plan 422 real.
- Sandbox/contextIsolation activos y nodeIntegration desactivado, bridge de
  preload real y navegación/popup bloqueados según el escenario registrado.
- `advanced-http-after.json`: **28/28 HTTP 422** reales sobre los cuatro
  endpoints de preview/generación/remix para lote, pasos y guidance inválidos.
- `recovery-03/result.json`: **5 PASS**, sin excepciones. Consola real, subida
  desde otro cliente, recuperación tras Chromium offline, DSP real y comparación
  A/B con posición/intervalo conservados y un único reproductor. Se inspeccionó
  la captura y el DOM finales: el AbortError falso de pausa ya no aparece.
- Se comprobaron con ffprobe los MP3 reales de ampliación **35 s**, mezcla
  **20 s** y ajuste 1.1× **18,182290 s**, todos existentes y con exit 0.
- Generación real desde CREAR: job `1a7bdbf4b1504a5ba764bba572f338e7`,
  **succeeded**, perfil **SFT/50 pasos/guidance 9/lote 2**, dos MP3 de **20 s**,
  321068 bytes cada uno, estéreo 48 kHz. El tester volvió a consultar ffprobe y
  a descargar ambos por HTTP 200: SHA-256 igual a disco y distinto entre
  variantes. Evidencia: `tester-production-audio.json`.
- El primer runner de ese job falló al buscar nombres con extensión en una UI
  que muestra el basename. Su FAIL se conserva. El mismo job se validó después
  con `production-delivery-validation/result.json`, **PASS** y
  `resumeValidation:true`, sin una segunda generación; capturas de CREAR y
  Biblioteca vistas. Motor idle y API disponible después de entregar.
- `strictmode-cancel-01/result.json`: **3 PASS** con Vite y StrictMode activos,
  cancelación real del job `086cb8b115ff40f9942d3a213ca301b7`,
  `cancelled:true`, controles recuperados y lifecycle idle/0 operaciones. Se
  canceló durante inicialización real, no durante difusión ni descarga.
- `api-responsiveness-controlled.json`: durante groove de **18,177 s**, las
  **57 consultas concurrentes health respondieron 200**, máximo **0,359 s**,
  baseline mediana **0,00258 s**. El resultado acredita esta concurrencia
  controlada; no todas las rutas DSP.

## Arranque, preservación y salida

- Arranque frío real y segundo arranque con las dos fixtures ajenas ya de
  **103,418/103,366 s antes del arranque** — superiores a la gracia de 60 s —:
  PASS, API propia con rutas absolutas, identidad de ambas fixtures conservada.
  Evidencias: `guard-cold-result.json`, `guard-aged-cold-result.json` y
  `guard-aged-cold-analysis.json`. El aviso inicial de health en el log de
  arranque se conserva; el reporte posterior acredita health 200 real.
- Parada PowerShell real **exit 0**, 0 APIs propias y 0 listeners 8000/8001,
  fixtures ajenas preservadas: `guard-stop-process.json` y
  `guard-stop-result.json`.
- SALIR mediante botón real y preload IPC del producto: captura previa vista,
  Electron **exit 0**, 0 APIs propias y 0 listeners, PIDs ajenos 8528/13204 con
  la misma identidad. `exit-01/result.json` guarda **EXIT_REQUESTED** antes de
  que app.exit cierre el verificador; el proceso externo acredita **PASS** en
  `exit-01-result.json` y exit 0 en `exit-01-process.json`. No se interpreta el
  estado intermedio del helper como fallo ni como prueba suficiente por sí solo.

## Límites y trazabilidad

Se conservan los intentos fallidos originales: restricciones de sandbox en
taskkill/CIM, cleanup ambiguo de una fixture en la suite de 457, WakeEngine BUSY
y expectativas equivocadas de runners. La suite final 466 PASS no borra esos
resultados; no se inventa una causa definitiva del fallo de cleanup.

Permanecen PENDING_USER la escucha y fidelidad artística; no se han generado
todas las opciones de remix ni cancelado todas las fases. Siguen declaradas las
rutas DSP de escritura síncronas, cómputo estéreo legado de B8, aviso de letra,
texto informativo de alineación y espera global de electron.exe del lanzador.
Se preservan deliberadamente las APIs antiguas con comando relativo sin
identidad acreditada; no se promete migración automática ni aislamiento
universal de herramientas ajenas.

Este rol releyó informes y drivers, contrastó salidas/códigos, hashes y capturas,
y ejecutó ffprobe/descargas de comprobación. En el cierre independiente no
editó producto ni controló servicios o procesos. El coordinador registra el
PASS junto al APPROVE del reviewer en spec/bitácora y deja el estado final de
la aplicación según la autorización del usuario.
