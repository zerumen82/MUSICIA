# Memory — Bitácora de Musicia

Proyecto: creación musical con IA en local (FastAPI + React/Vite).
Este archivo es la memoria viva del proyecto. Aquí se anota cada decisión,
prueba ejecutada y resultado, con fecha.

## Formato de entrada

```
## YYYY-MM-DD — Título
- **Qué**: qué se hizo o decidió
- **Por qué**: motivación
- **Resultado**: qué pasó (éxito/fallo, cómo se verificó)
- **Lecciones**: qué aprendimos para no repetir
```

---

## 2026-10-01 — Despliegue GLOBAL del ejército SDD (todos los CLIs, todos los proyectos)

- **Qué**: a petición del usuario, el método SDD y el ejército de agentes ya no
  son específicos de Musicia sino **globales**:
  - Agentes globales en `~/.agents/`:
    - `sd-coordinator.ts` — dirige el flujo, **pregunta al usuario antes de decidir**
    - `sd-editor.ts` — implementa historias aprobadas
    - `sd-tester.ts` — verifica con evidencia real (PASS/FAIL)
    - `sd-scout.ts` — **buscador de skills** (`npx skills find`), solo instala con aprobación
    - `sd-researcher.ts` — **buscador en internet** (docs, versiones, licencias) con fuentes
  - Reglas obligatorias para TODOS los CLIs y TODOS los proyectos:
    - `~/.agents/AGENTS.md` — fuente única de las reglas
    - `~/AGENTS.md` — Codebuff/Codex leen este del home y delegan en el anterior
    - `~/CLAUDE.md` — Claude Code
    - `~/.cursorrules` — Cursor
    - `~/.github/copilot-instructions.md` — Copilot
    - `~/.codex/AGENTS.md` — Codex CLI
  - Contenido común: jerarquía (el usuario es orchestrator supremo; los agentes
    preguntan antes de decidir), SDD obligatorio (spec/ antes de implementar),
    las 5 reglas (NO HARDCODE/NO STUB/NO FAKE/LOCAL-FIRST/BITÁCORA), Definición
    de Listo, flujo con scout+researcher antes de implementar, prohibición de
    instalar nada sin aprobación.
- **Por qué**: el usuario quiere el método en cualquier proyecto y cualquier CLI,
  con buscadores de skills y de internet de obligado uso.
- **Resultado**: 5 agentes + 6 archivos de reglas globales creados y verificados
  en disco. En este proyecto además existe `spec/04-EJERCITO.md` que documenta
  la jerarquía y el flujo.
- **Lecciones**: los CLIs leen reglas de ubicaciones distintas; la forma fiable
  de tener reglas globales es un archivo fuente único (`~/.agents/AGENTS.md`)
  y punteros desde la ubicación que espera cada CLI.

## 2026-10-01 — Añadido sd-reviewer al ejército global

- **Qué**: sexto agente global `sd-reviewer.ts` (claude-sonnet-4.6): revisa
  calidad/seguridad/mantenibilidad del código del editor y devuelve
  APPROVE/CHANGES_REQUESTED con comentarios accionables. Complementa a
  sd-tester (que verifica criterios funcionales).
- **Impacto en el flujo**: ahora HECHO exige **PASS del tester + APPROVE del
  reviewer**. Flujo actualizado en ~/.agents/AGENTS.md, spec/04-EJERCITO.md,
  sd-coordinator.ts y en los 4 punteros de CLIs.
- **Por qué**: el usuario pidió explícitamente un reviewer en el ejército.

## 2026-10-01 — Rediseño UI v3 (tercera iteración): sistema "CONSOLE" pro-audio

- **Qué**: tras rechazar el usuario la UI dos veces, se preguntó con ask_user y
  eligió: **mezcla FUTURISTA + PRO AUDIO**, odia "genérica" y "confusa", sin
  referencias (decide el agente). Cambios:
  - `frontend/src/index.css` reescrito: sistema "CONSOLE" — fondo oscuro neutro
    plano con grid de puntos, **un solo acento** (verde eléctrico #b8ff29,
    "señal"), paneles planos tipo rack (`rack/rack-head/rack-body` con etiqueta
    mono y LED), datos siempre en JetBrains Mono, botones cuadrados con texto
    uppercase (GENERATE tipo "signal"), slider tipo fader, VU-meter, progreso
    por pasos (QUEUE → SYNTH → RENDER). Eliminados: aurora, glass,
    glow-border, gradientes de texto.
  - `App.jsx`: barra superior tipo transport con breadcrumb + badge
    "GPU · ACE-STEP" + "100% LOCAL · SIN NUBE"; **estado del motor REAL** con
    polling a /health cada 10 s (antes era un "conectado" fijo = fake).
  - `Composer.jsx`: rack PROMPT con contador de chars y LEN, chips, botón
    GENERATE, rack JOB STATUS con EQ animado + pasos, rack OUTPUT con
    reproductor y descarga, rack SESSION LOG (historial).
  - `VoiceLab.jsx`: mismo sistema (rack VOICE, VOICES/SPEAK voces reales de
    /voices, rack OUTPUT).
  - **Sequencer y Mixer retirados de la nav** (archivos intactos): son
    decorativos sin backend real (peak -2.4dB hardcodeado, botón "AI Imagine"
    muerto, samples de batería descargados de tonejs.github.io = anti
    LOCAL-FIRST, deudas T1/T2 de spec/03). No falsear funcionalidad.
- **Por qué**: la UI anterior era "landing genérica" (lo que el usuario odia) y
  módulos fake dejan la app sin identidad de herramienta.
- **Resultado**: `npx eslint src --max-warnings=0` → 0 errores (LINT_OK);
  `npm run build` → OK, bundle **250 kB** (antes 624 kB, framer-motion fuera del
  bundle de las vistas activas). Pendiente: **aprobación visual del usuario**
  ejecutando `scripts\open_musicia.ps1`.
- **Lecciones**: (1) el generador inyectó tokens corruptos en Composer.jsx
  tres veces al escribirlo de una pieza → fiable: escribir en 2-3 trozos con
  marcadores y verificar con read; (2) no dejar estados de motor inventados:
  polling real a /health.  (3) Retirar temporalmente lo fake es mejor que mostrar maquetas (regla NO FAKE).

## 2026-10-01 — UI v4: opciones reales (género/mood/BPM/tono/seed), biblioteca y post-proceso

- **Qué**: feedback del usuario: "faltan cosas, info comprimida en un marco, todo
  muy pegado, quiero más opciones, solo música / solo voces". Cambios:
  - **Composer sin cajas**: secciones separadas por espacio y líneas; filas de
    selector visibles: GÉNERO (6), MOOD (5), BPM (auto/70/90/110/128/140),
    TONO (C mayor, La m...), MODO (MÚSICA/VOZ), LEN + SEED (con dado). El
    prompt final = género + mood + texto libre (todo lo que acepta
    MusicGenRequest del backend, nada inventado).
  - **Backend nuevo (todo real, sin stubs)**:
    - `GET /music/library` — lista MP3 reales de backend/outputs.
    - `DELETE /music/audio/{name}` — borra MP3 (con guard de ruta).
    - `POST /audio/process` — post-proceso pydub real (gain -24..+24 dB,
      fade in/out 0-10 s, recorte) → crea `-edit.mp3`, no toca el original.
    - Nuevo `backend/audio_service.py` con validación de rangos.
  - **Vista LIBRARY nueva**: lista real (nombre, tamaño, fecha), reproducir
    inline, descargar, borrar y editor de post-proceso con sliders.
  - `api.js` ampliado: library/deleteAudio/processAudio.
- **Por qué**: el motor ya aceptaba bpm/key_scale/seed y el frontend no los
  enviaba; no existía forma de ver ni reutilizar los MP3 generados.
- **Resultado**: lint 0 errores; build OK (259.9 kB); sintaxis Python OK;
  **E2E backend con TestClient sobre MP3 real e2e-lofi-20s.mp3**: library 200
  (2 items), process → e2e-lofi-20s-edit.mp3 (20.0 s verificado con pydub),
  gain_db=99 → 400, delete 200, re-delete 404. Pendiente validación visual del
  usuario con scripts\open_musicia.ps1.
- **Lecciones**: reutilizar capacidades del backend ya expuestas (bpm/seed) en
  lugar de dar por buena una UI con solo un textarea.

## 2026-10-01 — Musicia.exe (lanzador) + subida de audio con análisis y preguntas + wizard de calidad

- **Qué**:
  - **EXE**: `Musicia.exe` en la raíz del proyecto (5 KB, compilado con el
    csc.exe de .NET Framework que trae Windows, sin instalar nada; fuente en
    `scripts/launcher/Launcher.cs`) que ejecuta `scripts/open_musicia.ps1`
    oculto (el script ya era idempotente: comprueba /health de motor y API).
    Acceso directo `Musicia.lnk` creado en el escritorio del usuario
    (WScript.Shell, verificado: "LNK_OK").
  - **Subida + análisis + preguntas** (petición: "el sistema debe analizar lo
    que hemos subido y hacer preguntas o dar opciones"):
    - `backend/audio_analysis.py`: análisis DSP en Python puro (pydub+math,
      SIN numpy que no está en el venv): duración, loudness dBFS, dinámica
      (std de RMS), ZCR, bass_ratio (IIR 250 Hz), BPM por autocorrelación de
      envolvente (60-180). Devuelve hipótesis música/voz/mixta CON señales
      explicadas y nota de que el usuario decide.
    - Endpoints: `POST /audio/upload` (mp3/wav, 50 MB máx, guarda en
      outputs/uploads/ con UUID, analiza; borra el fichero si es inválido),
      `GET /audio/uploads`, `GET /audio/uploads/file/{name}`, `DELETE
      /audio/uploads/{name}`, `POST /audio/remix` (tempo 0.5-2x, pitch
      ±12 st por resample, reverse, gain, fades, recorte → MP3 en outputs/).
    - Vista UPLOADS: drop zone con progreso, muestra las features reales,
      hipótesis del sistema y **2 preguntas encadenadas**: (1) "¿qué es este
      audio?" (música/voz/mixta/otro — corrige al sistema), (2) "¿qué hacemos?"
      (remix DSP instantáneo / re-crear con IA usando BPM+graves+carácter
      detectados / crear base para voz). Panel de remix con sliders.
  - **Wizard de calidad opcional** (`QualityWizard.jsx`): modal de 5 pasos
    (propósito, género+mood, tempo+tono, duración, instrumentación) con
    sugerencias; al final prellena los selectores del Composer. Botón
    ASISTENTE junto a MÚSICA/VOZ.
- **Por qué**: el usuario pidió "siempre sea EXE" y "subir un audio, que el
  sistema analice si es música o voz, y pregunte opciones". La hipótesis
  automática se muestra pero SIEMPRE se pregunta (regla del usuario: preguntar
  antes de decidir).
- **Resultado**: E2E backend con TestClient y MP3 real: upload 200 + análisis
  (20.0 s, bpm 136, hipótesis con señales), .txt → 400, uploads list OK,
  remix tempo 1.25 + pitch +2 → duración 14.25 s (matemática correcta:
  20/1.25/2^(2/12)), tempo 5 → 400, remix visible en library, borrados OK.
  Lint 0 errores, build OK (281.5 kB). Pendiente validación visual del
  usuario. Ficheros de prueba limpiados.
- **Lecciones**: (1) csc.exe usa opciones con un solo guion (-out) y bash
  necesita escapar `..\\..`; (2) pitch por resample también cambia la duración
  (efecto cinta) — documentarlo en la UI futura; (3) escribir archivos en
  partes sigue siendo lo fiable ante las corrupciones del generador.

## 2026-10-01 — Las 7 mejoras de producto (prompts, cola, A/B, mixer real, onda, icono, apagado)

- **Qué**: usuario eligió las 7 mejoras propuestas. Implementadas:
  - **1 · Mejorar prompt**: `backend/prompt_enhancer.py` (reglas deterministas
    por género: instrumentación, estructura, mezcla; detección de género en
    español; mood; bpm). Endpoint `POST /music/enhance_prompt` (devuelve
    original/enhanced/additions para transparencia). Botón MEJORAR PROMPT en
    Composer que muestra qué se añadió.
  - **2 · Cola**: `GET /music/jobs` (activos primero, datos reales del dict
    jobs). Componente `JobsPanel.jsx` con polling de 3 s integrado bajo los
    controles del Composer; sobrevive a cerrar la ventana mientras la API viva.
  - **3 · Variaciones A/B**: botón A/B lanza 2 generaciones con seeds
    distintas; en JobsPanel se marcan hasta 2 pistas (etiquetas A/B) y se
    reproducen juntas para comparar.
  - **4 · Mixer real**: vista MIX (`MixLab.jsx`) conectada a `POST /audio/mix`
    (que ya existía): base de biblioteca + voz de subidas, ganancias dB.
    **Bug corregido**: /audio/mix no resolvía nombres contra outputs/ → ahora
    `_resolve_track` prueba outputs/ y uploads/; verificado con 2 MP3 reales
    (mezcla 20.0 s, pista inexistente → 404).
  - **5 · Editor visual**: `GET /audio/peaks/{name}` (picos 0..1, Python puro,
    buckets 50-2000, busca en outputs/ y uploads/) + `Waveform.jsx` (canvas
    con onda real, marcadores arrastrables para trim) integrado en el panel de
    remix de UPLOADS.
  - **6 · Icono propio**: `frontend/build/icon.ico` generado con PIL (branding
    CONSOLE: fondo oscuro + barras de señal verde); aplicado a la ventana
    Electron (`icon` en BrowserWindow) y a `Musicia.exe` (recompilado con
    `-win32icon:`, 15.8 KB); acceso directo refrescado con IconLocation.
  - **7 · Apagado limpio**: `main.cjs` captura `close` y pregunta: Cerrar todo
    (ejecuta stop_local.ps1, libera VRAM) / Dejar servicios (apertura
    instantánea) / Cancelar.
- **Por qué**: elevar la calidad de producto del flujo completo.
- **Resultado**: lint 0 errores, build OK (294 kB), e2e backend: jobs 200,
  enhance (techno detectado + adiciones), peaks 100 buckets max 0.79, mix con
  MP3 reales OK + 404. Pendiente validación visual del usuario.
- **Lecciones**: (1) csc soporta -win32icon directo (no hace falta .rc);
  (2) el mixer tenía un bug latente de resolución de rutas que solo se vio al
  conectarlo de verdad — probar endpoints con audio real destapa bugs que la
  inspección no ve; (3) los errores react-hooks/set-state-in-effect se
  resuelven moviendo el fetch al effect con flag cancelled y el reset vía key
  en el padre.

## 2026-10-01 — BUG RAÍZ DE LA UI: Tailwind NUNCA estuvo instalado

- **Qué**: el usuario insistió ("sigue pegada, todo arriba a la izquierda,
  ventana grande y contenido pequeño"). Investigando descubrí que
  `tailwindcss` **no estaba en package.json** ni como dependencia ni como
  plugin de Vite ni importado en index.css: **todas las clases de utilidad
  usadas desde el primer día (flex, px, w-, text-, gap-) no existían** y la
  app se renderizaba como HTML sin estilos apilado arriba-izquierda. Todos
  los rediseños anteriores nunca llegaron a renderizarse.
- **Fix**: `npm install -D tailwindcss @tailwindcss/vite` (frontend, local),
  plugin en `vite.config.js` y `@import 'tailwindcss';` al inicio de
  `index.css` (nuestras reglas custom van después y tienen prioridad).
  Además: escala global subida (btn h-46, chips 12.5px, labels 11px, nav
  13.5px, sliders 18x28), sidebar 230px, header 48px, Composer con
  contenido centrado verticalmente (my-auto), px-16/py-10, textarea 17px,
  botones h-12, historial 360px; VoiceLab/Library/Uploads/MixLab con px-16
  py-12 y tipografías mayores.
- **Resultado**: build OK — CSS de 6.7 kB a 35.7 kB con utilidades reales
  (verificado `.px-16`, `.h-12` en dist). Lint 0 errores. **El usuario debe
  cerrar y reabrir la ventana (Musicia.exe) para ver la UI de verdad por
  primera vez.**
- **Lecciones**: (1) verificar que el framework de estilos está INSTALADO y
  conectado antes de rediseñar — "build verde" no implica que el CSS
  exista; (2) cuando el usuario dice "se ve mal", pedir/buscar EVIDENCIA
  visual (screenshot o inspección del CSS generado), no asumir gusto; (3)
  la causa raíz estaba en el proyecto original, no en los cambios: toda
  la frustración venía de un bug de setup previo a esta sesión.

## 2026-10-01 — UI 100% en español + cableado revisado (2 bugs corregidos)

- **Qué**: el usuario confirmó que la UI ya renderiza y gusta ("me gusta mucho
  más") pero había mezcla inglés/español y pidió revisar la UI y el cableado.
  - **Traducción completa**: pestañas CREAR/SUBIR/MEZCLA/VOZ/BIBLIOTECA,
    MOTOR ACTIVO/APAGADO, DURACIÓN (era LEN), SEMILLA (era SEED), GENERAR
    (era GENERATE), CREANDO… (era WORKING…), VARIAR (era A/B),
    COLA→SÍNTESIS→RENDER (era QUEUE→SYNTH→RENDER), RESULTADO (era OUTPUT),
    VELOCIDAD/TONO/VOLUMEN/FUNDIDOS/INVERTIR (era TEMPO/PITCH/GAIN/FADES/
    REVERSE), ACTUALIZAR (era REFRESH), APLICAR/CANCELAR, FUNDIDO
    ENTRADA/SALIDA,wizard en español (GÉNERO Y CARÁCTER, APLICAR EN CREAR).
    Solo queda inglés en Mixer.jsx/Sequencer.jsx (fuera de la navegación).
  - **Cableado revisado** (mapa completo frontend↔backend): las 15 rutas
    coinciden. **Bug 1 corregido**: el remix enviaba trim_end_s como cadena
    vacía cuando no se recorta (el backend espera float|None → 422); ahora se
    convierte a null. **Bug 2 corregido**: la re-creación IA tras confirmar
    "voz" enviaba instrumental False sin letra (el motor la rechazaría); ahora
    siempre instrumental True. **Mejora de cableado**: el botón VOZ del
    Composer no hacía nada real → ahora es modo CANCIÓN CON VOZ: muestra
    campo LETRA, exige letra y envía instrumental False + lyrics al motor
    (esquema validado con pydantic). El test de /music/generate contra motor
    apagado se cuelga en submit (reintentos largos) — pendiente añadir
    fail-fast cuando el motor no responde (deuda nueva).
- **Por qué**: coherencia de idioma y flujo voz real.
- **Resultado**: lint 0 errores, build OK (295 kB), esquema del payload de voz
  validado, mapa de rutas frontend-backend completo y coincidente.
- **Lecciones**: (1) al añadir controles, cablearlos de inmediato o no
  mostrarlos (el VOZ muerto era fake); (2) los payloads con estados vacíos
  ('' vs null) deben normalizarse en el cliente; (3) music.submit debería
  fallar rápido si el puerto del motor rechaza conexión (deuda T7).

## 2026-10-01 — Progreso verbose: fases humanas, reloj en vivo y fail-fast (T7 resuelta)

- **Qué**: el usuario probó y "parece colgado"; pidió más verbose y mejor
  progreso. Cambios:
  - **T7 resuelta (fail-fast)**: `/music/generate` comprueba `music.health()`
    antes de enviar; si el motor no responde → 503 con mensaje accionable
    ("ejecuta scripts\\open_musicia.ps1...") en vez de colgar 60 s.
  - **Backend verbose**: cada job lleva `phase` (frase humana según el texto
    del motor: carga de modelo, difusión, VAE, letras...), `elapsed_seconds`,
    `events` (registro con timestamp +s de cada cambio de progreso, últimos
    30). `_human_phase()` traduce el progreso técnico a español; probado con
    6 entradas reales.
  - **Frontend**: bloque de progreso con reloj en vivo (interval de 1 s que
    incrementa elapsed_seconds entre polls de 3 s), fase en texto normal
    grande, expectativa de tiempo ("1-3 min con modelo cargado; primera vez
    5-6 min") y últimos 3 eventos con su timestamp. JobsPanel muestra fase y
    reloj por trabajo activo.
- **Por qué**: 2 min sin feedback se perciben como cuelgue; el progreso del
  motor es técnico y en inglés.
- **Resultado**: SYNTAX_OK, _human_phase con salidas correctas, lint 0,
  build OK (296 kB). Pendiente: prueba real del usuario con el motor activo
  para validar las fases contra los textos reales del motor.
- **Lecciones**: (1) feedback cada segundo aunque el dato solo cambie cada 3;
  (2) traducir el progreso técnico a fases humanas; (3) fail-fast antes de
  aceptar trabajo que no se puede hacer.

## 2026-10-01 — Botón SALIR + título de ventana correcto

- **Qué**: botón SALIR en la barra lateral (rojo al hover) + título de la
  ventana decía "frontend".
  - `frontend/preload.cjs` nuevo: puente seguro (contextBridge) que expone
    `window.musica.exit(action)` con 'ask' | 'stop-all' | 'keep'. En main.cjs
    se refactorizó la salida a `exitApp(action)` reutilizada por: el aspa de
    la ventana (diálogo nativo), el botón SALIR (mismo diálogo vía IPC), y
    acciones directas. sandbox=false para permitir el preload (contextIsolation
    sigue activa; el puente solo expone exit).
  - Botón SALIR llama `window.musica.exit('ask')` con fallback a window.close
    si se sirve en navegador.
  - Título: `index.html` tenía `<title>frontend</title>` → ahora "Musicia"
    (el título de BrowserWindow es 'Musicia' pero el de la página lo pisaba
    al cargar la URL).
- **Por qué**: el usuario pidió botón de salida y reportó el título "frontend".
- **Resultado**: node --check OK en main.cjs y preload.cjs, lint 0, build OK.
  Pendiente: prueba visual del usuario (cerrar y reabrir Musicia.exe).
- **Lecciones**: (1) el <title> del HTML pisa el title de BrowserWindow al
  cargar por URL; (2) con sandbox=true el preload no puede requerir electron:
  hay que relajarlo a false y mantener contextIsolation=true (el puente expone
  solo lo mínimo).

## 2026-10-01 — Fix: ReferenceError "win is not defined" al arrancar Electron

- **Qué**: al arrancar la app saltaba `UnhandledPromiseRejectionWarning:
  ReferenceError: win is not defined at createWindow (main.cjs:79)`. Causa: en
  el refactor del botón SALIR renombré la variable local `win` a `mainWindow`
  en la creación, pero quedaron 4 referencias a `win.` sin renombrar dentro de
  createWindow (setWindowOpenHandler, loadURL, on close, on closed).
- **Fix**: reemplazadas las 4 referencias por `mainWindow`. `node --check`
  OK y grep confirma que no queda ningún `win.` suelto.
- **Por qué**: str_replace con oldString parcial al refactorizar; debí leer
  el archivo entero tras el refactor.
- **Lecciones**: (1) tras un refactor de renombrado, buscar siempre las
  referencias restantes del nombre viejo antes de dar por hecho; (2) el error
  salía como UnhandledPromiseRejection porque el listener 'close' es asíncrono
  vía exitApp — un error de este tipo en el arranque de Electron no siempre
  mata el proceso, pero deja la ventana sin comportamientos.

## 2026-10-01 — Protocolo SDD formal aplicado: veredictos tester + reviewer

- **Qué**: el usuario recordó que los agentes SDD SE USAN. Se blindó el
  protocolo en AGENTS.md (protocolo de ejecución obligatorio: tester PASS +
  reviewer APPROVE explícitos en memory.md para todo HECHO; historias nuevas
  con spec + plan aprobado). Se cerró el trabajo de la sesión con el protocolo:
  - **sd-tester (veredicto: PASS tras 3 iteraciones)**: lint 0, build OK,
    sintaxis Electron y backend OK, e2e de 7 endpoints con audio real. El
    tester DESTAPÓ un bug real: `/audio/remix` daba 404 con audio de la
    biblioteca (solo buscaba en uploads/). Causa raíz aún más sutil:
    `_resolve_output` no lanza si el fichero no existe (solo si escapa del
    dir), así que el try/except nunca probaba uploads. Fix: bucle sobre
    resolvers probando `.exists()`. Verificado: remix desde library 200,
    desde uploads 200, mix con voz subida 200.
  - **sd-reviewer (veredicto: APPROVE con notas)**: sin `win.` sueltos en
    main.cjs, sin console.log en src, sin prints de debug en backend, sin
    TODO/FIXME pendientes (el único "TODO" es texto español legítimo del
    wizard), sin seeds hardcodeados. Nota: el fix del try/except anterior era
    un parche que parecía pasar el test y no lo hacía; el bucle con exists()
    es la solución correcta y definitiva.
- **Por qué**: el protocolo existe para esto — el tester formal encontró un
  bug que la verificación ad-hoc de la sesión había dado por buena.
- **Resultado**: PASS + APPROVE. AGENTS.md actualizado con el protocolo
  obligatorio para las próximas sesiones.
- **Lecciones**: (1) `_resolve_output` devuelve ruta inexistente sin lanzar:
  todo consumidor debe comprobar exists() y tener fallback; (2) un test que
  falla es el tester trabajando — no atajarlo; (3) el protocolo formal
  (tester+reviewer separados del implementador) destapa lo que la
  autocomprobación no ve.

## 2026-10-01 — Punteros SDD para OpenCode/Grok/Kilo + fix "la UI no abre"

- **Qué**:
  - **Reglas globales en 3 CLIs más** (rutas verificadas en docs oficiales y
    en disco): Grok CLI `~/.grok/AGENTS.md`, OpenCode
    `~/.config/opencode/AGENTS.md`, Kilo Code `~/.kilocode/rules/AGENTS.md`.
    Todas son punteros a la fuente única `~/.agents/AGENTS.md` (9 CLIs
    cubiertos en total).
  - **"La UI no abre"**: diagnóstico con procesos — había una instancia
    Electron viva con la ventana oculta (PID 16792, título "Musicia").
    Restaurada con ShowWindow/SetForegroundWindow (script PS temporal; bash
    se come los $ de las variables PowerShell). Fixes en main.cjs:
    `show:false` + `ready-to-show` (nunca ventana en blanco, fallback a los
    4 s), y **single instance lock**: si abres Musicia dos veces, la segunda
    restaura y enfoca la existente en vez de duplicar procesos.
- **Por qué**: completar la cobertura de CLIs del método SDD global y
  eliminar la clase de fallo "ventana invisible/zombi".
- **Resultado**: los 3 punteros verificados con grep; main.cjs syntax OK;
  ventana del usuario restaurada en vivo. Pendiente: usuario reinicia
  Musicia.exe para validar single-instance.
- **Lecciones**: (1) "no abre" ≠ "no está corriendo": comprobar procesos y
  MainWindowTitle antes de tocar código; (2) bash engulle $ en comandos
  PowerShell inline — usar script temporal; (3) single-instance lock es
  obligatorio en apps de escritorio con lanzador idempotente.

## 2026-10-01 — "No se ve nada": ventana heredaba estado oculto del lanzador

- **Qué**: el usuario seguía sin ver la ventana. Diagnóstico por pasos: API y
  motor OK (200); SIN procesos Electron al abrir desde el icono; lanzado a
  mano desde bash la ventana SÍ se creaba. Causa: `open_musicia.ps1` lanzaba
  `electron.cmd` (wrapper batch) desde PowerShell ejecutado de forma oculta —
  la ventana heredaba el estado oculto.
- **Fix**: el script lanza ahora `electron.exe` directamente
  (`node_modules/electron/dist/electron.exe`), no el wrapper .cmd. Verificado
  con el mismo flujo del icono: proceso con MainWindowTitle "Musicia" vivo.
- **Resultado**: ventana abierta vía open_musicia.ps1 (mismo camino del
  icono). Pendiente confirmación visual del usuario.
- **Lecciones**: (1) `Start-Process -WindowStyle Hidden` oculta la CONSOLA,
  pero lanzar un wrapper .cmd desde una consola oculta puede propagar el
  estado a la GUI hija; lanzar el exe final directamente; (2) diagnosticar
  comparando el camino que falla vs el que funciona (bash vs icono).

## 2026-10-01 — Pantalla negra resuelta: 3 fallos encadenados

- **Qué**: la ventana abría pero en negro. Cadena de causas:
  1. **TDZ error en Composer.jsx**: el useEffect del reloj del progreso
     verbose usaba `busy` antes de su declaración (`Cannot access 'busy'
     before initialization`) → React moría al montar → solo se pintaba el
     fondo. Fix: mover el useEffect después de la declaración. Detectado
     gracias al logging `console-message` añadido a main.cjs y un build sin
     minificar para ver nombres reales.
  2. **Caché HTTP de Electron**: tras corregir, la ventana seguía cargando el
     bundle VIEJO (index-ejyLryUl.js) por caché de sesión. Fix:
     `session.clearCache()` antes de loadURL en cada arranque.
  3. El lanzador oculto (ya arreglado antes) completaba la cadena.
- **Instrumentación nueva en main.cjs**: `console-message` (errores de la
  página al log con prefijo [UI:n]), `did-fail-load` ([CARGA FALLIDA]) y
  `render-process-gone` ([RENDER MUERTO]). Nunca más pantalla negra muda.
- **Resultado**: ventana viva (PID 22260), bundle nuevo servido
  (index-BJP9YOFX.js), CERO errores de UI en el log. Lint 0, build OK.
- **Lecciones**: (1) un `useEffect` que referencia una const declarada después
  es TDZ y mata toda la app en el mount — orden de declaraciones importa;
  (2) la caché de sesión de Electron sobrevive a los rebuilds: clearCache en
  apps que cargan de un servidor local con assets renombrados; (3) sin
  logging de la página, una pantalla negra es ind diagnosticable —
  instrumentar SIEMPRE las ventanas.

## 2026-10-01 — Estado CREANDO desde el inicio + salida directa sin preguntar

- **Qué**:
  - **Progreso "en cola" eterno corregido**: `_finalize_generation` ponía el
    job a `running` solo vía callback (y el estado inicial era `queued`):
    ahora marca `running` nada más aceptar la tarea y lo refuerza en cada
    update mientras no sea terminal. La UI distingue COLA → CREANDO → LISTA.
  - **Reproductor protagonista**: el bloque RESULTADO ahora es un panel
    destacado (borde/acento, icono grande, "SE REPRODUCE AQUÍ MISMO",
    autoplay, altura 44px, botón MP3 tipo señal). La respuesta a la pregunta
    del usuario: sí, se reproduce en el mismo sitio al terminar.
  - **Botón SALIR sin diálogo**: manda `exit('stop-all')` → apaga UI + API +
    motor sin preguntar (verificado que stop_local.ps1 mata por CommandLine
    los python de main.py y acestep.api_server). El aspa de la ventana
    mantiene el diálogo (cierre menos intencionado).
- **Por qué**: feedback del usuario: progreso nulo en cola y salida directa.
- **Resultado**: SYNTAX_OK, lint 0, build OK (296.9 kB). Pendiente validación
  del usuario con generación real (requiere reiniciar servicios para cargar
  el backend nuevo).
- **Lecciones**: (1) el estado inicial de un job asíncrono debe transitar
  explícitamente por cada fase; (2) separar cierre intencionado (botón:
  directo) de cierre ambiguo (aspa: preguntar).

## 2026-10-01 — Progreso REAL del motor: campos progress y stage (0-100%)

- **Qué**: el usuario seguía viendo "Trabajando en el motor" fijo. Diagnóstico
  con el motor REAL: envié una tarea por curl a :8001 y hice polling de
  /query_result. Hallazgo: el motor devuelve por pista los campos **progress**
  (float 0.0-1.0) y **stage** ('queued'/'infer'/...), que el servicio ignoraba:
  solo leía progress_text (última línea de log, a menudo repetida e inútil).
  - `music_service.py`: EngineStatus con progress/stage; _parse_tracks los
    extrae; status() toma el máximo progress de las pistas. Verificado con la
    respuesta real capturada (progress 0.42, stage 'infer' parseados OK).
  - `main.py`: job lleva progress_ratio/stage; _human_phase usa stage
    (queued → "En cola del motor (esperando turno en la GPU)", infer →
    "Sintetizando...", tiled/vae → "Convirtiendo a audio final").
  - Composer: **barra de progreso real** con % del motor + fase; el porcentaje
    sube de verdad durante la síntesis.
- **Por qué**: el motor SÍ da progreso granular; lo estábamos desperdiciando.
- **Resultado**: SYNTAX_OK, parseo verificado con payload real, lint 0, build
  OK (297.2 kB). Pendiente: usuario genera con servicios reiniciados y ve la
  barra subir.
- **Lecciones**: (1) ante "el progreso no se mueve", capturar la respuesta
  cruda del motor antes de adivinar; (2) los logs (progress_text) no son
  progreso: el estado estructurado (progress/stage) sí.

## 2026-10-01 — Cola atascada: causa raíz VRAM=0 por instancias duplicadas

- **Qué**: el usuario esperaba con "En cola" perpetuo. Investigación con
  nvidia-smi + árbol de procesos: **había 2 motores y 2 APIs** corriendo
  (instancias zombis de reaperturas sin stop_local). La VRAM quedó en 0.00 GB
  libre durante el decode → el motor hizo VAE en CPU por tiles (lentísimo) y
  las tareas nuevas quedaban encoladas detrás. Mi tarea de test siguió
  'queued' 40 min. Tras matar todo: VRAM de 2048 MB → 518 MB.
- **Hallazgo importante**: el venv de Windows (venv\Scripts\python.exe) es un
  shim que lanza el python real como hijo — Get-CimInstance ve "2 motores" pero
  es un par padre-hijo inofensivo. Criterio: padre vivo = par legítimo; padre
  MUERTO = huérfano/zombi.
- **Fix aplicado**: limpieza total (con permiso del usuario) + reinicio limpio
  con start_local (1 motor + 1 API) + ventana abierta. El motor carga los
  modelos en la primera generación (models_initialized: false al arrancar).
- **Resultado**: API OK, motor alcanzable, VRAM limpia (574 MB base), ventana
  viva (PID 17632). El usuario puede generar con el progreso real (barra 0-100
  + stages).
- **Lecciones**: (1) las reaperturas sin parada previa acumulan motores
  duplicados que compiten por la GPU — el single-instance lock evita esto para
  la UI, pero los servicios siguen necesitando stop_local antes de relanzar;
  (2) open_musicia.ps1 ya comprueba /health antes de arrancar, por eso NO
  creó duplicados esta vez: los zombis venían de sesiones anteriores; (3)
  "En cola" eterno = mirar nvidia-smi y la cola del motor, no la UI.

## 2026-10-01 — Fix: TypeError "keyword progress" en EngineStatus

- **Qué**: al generar, la API lanzaba un error por keyword inválida. Causa:
  al añadir progress/stage a _parse_tracks, el dict de pista pasó a incluir
  esas claves y `GeneratedTrack(**track)` explotaba (el dataclass no las
  tiene). Cada polling del job rompía.
- **Fix**: filtrar el dict a los campos del dataclass al construir
  GeneratedTrack: `{k: v for k, v in t.items() if k in
  GeneratedTrack.__dataclass_fields__}`. Verificado con el payload REAL del
  motor y test de integración de status() con HTTP mockeado: progress 0.6,
  stage 'infer', 1 pista parseada OK.
- **Resultado**: servicios reiniciados (stop + start), API OK y motor
  alcanzable. Listo para generación real con barra de progreso.
- **Lecciones**: (1) cuando un dict que alimenta un dataclass gana claves,
  filtrar por __dataclass_fields__ o actualizar el dataclass; (2) probar
  SIEMPRE el método completo (status()), no solo el parseo interno — el
  primer test pasó y el fallo estaba en la construcción del EngineStatus.

## 2026-10-01 — VERIFICACIÓN FINAL: generación real con barra de progreso OK

- **Qué**: generación e2e lanzada por el agente contra la API real
  (POST /music/generate, lo-fi 15 s) y polling cada 12 s:
  - running 0% "En cola del motor" (el motor recién reiniciado recargaba el
    modelo: logs 'loading 5Hz LM tokenizer')
  - running 10% "Cargando el modelo en la GPU"
  - running 59% "Trabajando en el motor"
  - **succeeded 100% "Lista" en 194 s**
  - MP3 real: 23e60c86...-lo-fi-t.mp3, 15.0 s verificado, servido con HTTP 200.
- **Resultado**: todo el flujo funciona: cola → carga → síntesis con % →
  descarga → verificación → reproducción en UI. Las fases por stage y el
  porcentaje REAL del motor confirmados en vivo.
- **Lecciones**: (1) tras reiniciar el motor, la primera generación carga el
  modelo (2-3 min extra); las siguientes ~70 s; (2) la barra 0-100% procede
  del campo progress por pista del motor — confirmado en tres puntos (10, 59,
  100).

## 2026-10-01 — Experiencia completa desde Musicia.exe: generación narrada

- **Qué**: recorrido e2e final usando el mismo camino del usuario: Musicia.exe
  abrió la ventana (PID 5804, single-instance lock ok) y se lanzó generación
  (synthwave 20 s) por el mismo endpoint que usa el botón GENERAR. Progreso
  narrado capturado:
  - 0% "En cola del motor" mientras el motor cargaba el LLM (logs reales)
  - 10% "Cargando el modelo en la GPU" (evento: Loaded LLM to cuda)
  - 50% "Trabajando en el motor"
  - 100% "Descargando el audio desde el motor" → "Lista" en **108.9 s total**
  - MP3: 8637371d...-synthwa.mp3, 20.0 s verificados, HTTP 200 (321 KB).
- **Nota**: en la biblioteca aparecía 'e2e-lofi-20s-edit-remix-remix-remix.mp3'
  — el usuario estuvo probando remix encadenado; funcionó, aunque el nombre
  crece con cada remix (cosmético; posible deuda: límite de slug ya existe,
  el encadenado simplemente acumula sufijos).
- **Resultado**: flujo completo correcto desde el lanzador real. Motor
  caliente: 109 s para 20 s de música.
- **Lecciones**: (1) confirmar la experiencia abriendo la app por el mismo
  camino del usuario (icono → single-instance → ventana), no solo por API;

## 2026-10-01 — Prompt sugerido para remix IA + remix encadenable desde BIBLIOTECA + X = minimizar

- **Qué** (tres peticiones del usuario):
  - **Prompt para el remix**: nuevo endpoint `POST /audio/remix_prompt` —
    re-analiza el audio (DSP real) y compone un prompt sugerido según el tipo
    confirmado (música/voz/mixta/otro) + bpm + graves + dinámica, enriquecido
    con las reglas de producción. En UPLOADS, al elegir re-creación, aparece
    el prompt **editable** con nota de qué se añadió; el usuario lo lanza tal
    cual o editado (runAIGeneration acepta promptOverride).
  - **Remix encadenable**: `RemixPanel` extraído a componente compartido
    (Uploads + Library). En BIBLIOTECA cada pista tiene botón REMIX (Shuffle)
    que abre la onda + sliders y crea un remix que vuelve a la biblioteca —
    se puede remixar un remix tantas veces como se quiera. Arreglo colateral:
    el progreso del remix ahora muestra "procesando en local…" mientras
    corre.
  - **La X ya no cierra**: minimiza a la bandeja (Tray con icono propio, clic
    restaura). Única salida: botón SALIR (cierra todo sin preguntar).
- **Por qué**: el usuario quiere iterar sobre su audio (remixes encadenados)
  y que la IA le proponga la dirección; y salir solo por el botón.
- **Resultado**: e2e del endpoint remix_prompt con WAV real (prompt compuesto
  con basis), kind inválido no rompe; lint 0, build OK (299.3 kB). Servicios
  pendientes de reinicio por el usuario para cargar el backend nuevo.
- **Lecciones**: (1) al extraer un componente compartido, verificar qué más
  vivía después de él en el archivo (el corte se llevó RemixPromptPanel);
  (2) la bandeja (Tray) complementa al single-instance lock: la ventana
  nunca se pierde, solo se esconde.

## 2026-10-02 — Fix prompt en SUBIR verificado + servicios reiniciados + repo en GitHub
- **Qué**:
  - Reclamación del usuario repetida ("SUBÍ LA CANCIÓN Y NO ME DEJA METER
    PROMPT") → causa raíz confirmada: la API corría código VIEJO sin
    `/audio/remix_prompt`, y el panel viejo se quedaba en "PREPARANDO
    SUGERENCIA…" bloqueado. Ya aplicado el fix de `RemixPromptPanel`
    (textarea SIEMPRE visible/editable, fallback sin backend, flag `touched`).
  - **Verificado**: `npx eslint src --max-warnings=0` (0 errores) +
    `npm run build` OK (bundle 299.4 kB / gzip 94.4 kB).
  - **Servicios reiniciados** (stop_local + start_local): API :8000 OK, motor
    :8001 OK (models_initialized=false hasta la 1ª generación, que recargará
    modelo ~2-3 min extra). Endpoint `/audio/remix_prompt` verificado vivo:
    responde validación 422 (ya no 404).
  - **README.md creado** con descripción del proyecto (arquitectura, pestañas,
    puesta en marcha, privacidad local).
  - **Repo subido a GitHub**: `git init -b main` (el proyecto NO era repo),
    `.gitignore` raíz nuevo (excluye vendor/ 17 GB, venvs, outputs, logs,
    node_modules, config.json), commit raíz `e863c35` (61 archivos, 14.494
    líneas) y push a `git@github.com:zerumen82/MUSICIA.git` branch `main`
    (SSH funcionó a la primera).
- **Resultado**: todo el código actual está en GitHub; la API tiene el
  endpoint nuevo; el frontend compila el fix del prompt. Falta SOLO que el
  usuario repruebe: SUBIR canción → confirmar tipo → el textarea del prompt
  debe aparecer YA visible y editable → GENERAR CON IA.
- **Nota**: para futuros pushes, `git push` a secas (tracking ya configurado).

## 2026-10-02 (II) — Re-test flujo SUBIR + fix BPM duplicado
- **Qué** (petición del usuario: reprobar SUBIR):
  - E2e backend con la canción REAL del usuario (`89a08f15-01-Animales-muertos.mp3`):
    `/audio/uploads` la lista OK; `/audio/remix_prompt` (kind=music y mixta)
    devuelve prompt + basis (167 bpm, 81.4 s, bass_ratio 0.385, dyn 14.2 dB).
  - **Bug detectado y corregido**: el BPM salía triplicado ("167 bpm, 167
    bpm, 167 bpm"). Causa: `enhance_prompt` lo añadía a `parts` Y otra vez
    vía `unique_adds`, y `remix_prompt` ya lo había metido antes. Fix en
    `prompt_enhancer.py`: solo `additions.append` y solo si el prompt base
    no lo contiene ya (`if bpm and f"{bpm} bpm" not in low`). Verificado:
    ahora "167 bpm" aparece UNA vez en music y mixta.
  - Revisión del código de `RemixPromptPanel` (Uploads.jsx): textarea
    incondicional (línea ~353), flag `touched`, fallback con nota si el
    backend falla, botón GENERAR CON IA deshabilitado solo si prompt vacío.
    Flujo confirmado: subida → hipótesis → P1 tipo → P2 acción → panel con
    prompt para recreate/backing/extend.
  - API reiniciada con el fix (stop/start local, health OK).
- **Pendiente**: validación visual del usuario (reabrir Musicia.exe para
  cargar el dist nuevo) y probar generar desde el prompt editado.

## 2026-10-02 (III) — OTRA VERSIÓN del mismo tema: RemixIAPanel compartido
- **Qué** (usuario: "una vez la he subido y lo ha creado no hay mecanismos
  para hacer otra versión del mismo tema" + "quiero más opciones cuando
  subes un audio, más opciones de remix... que cambien según el prompt"):
  - Diagnóstico: tras generar, en SUBIR no había botón de re-lanzar y en
    BIBLIOTECA solo había remix DSP (Shuffle) y AJUSTES — ninguna vía para
    re-crear con IA sobre una pista existente.
  - **Nuevo componente compartido `RemixIAPanel.jsx`** (usado por SUBIR y
    BIBLIOTECA):
    - Prompt SIEMPRE visible/editable, pre-rellenado desde
      `/audio/remix_prompt` (análisis DSP real del fichero).
    - **10 chips de variantes que REESCRIBEN el prompt** (toggle añade/quita
      su frase): MÁS ENERGÍA, MÁS CALMA, OSCURA, LUMINOSA, ACÚSTICA,
      ELECTRÓNICA, ORQUESTAL, LO-FI, ÉPICA, MINIMAL.
    - **Dado de semilla**: semilla aleatoria por defecto, clic para fijar
      una concreta (misma base → resultado distinto, comparable A/B), X para
      volver a aleatoria. Backend ya aceptaba `seed`.
    - Botón GENERAR OTRA VERSIÓN + muestra la base (bpm/duración).
  - **SUBIR**: `RemixPromptPanel` eliminado (el corte de la extracción
    anterior se lleva bien esta vez); `runAIGeneration` simplificada: firma
    única `({prompt, seed, duration_seconds, bpm})` con fallback al análisis
    local; `seed` pasa al payload.
  - **BIBLIOTECA**: nuevo botón ✨ (Sparkles) por pista junto a Shuffle →
    despliega RemixIAPanel con kind=musica; `runIAFromLibrary` lanza el job
    y anota el job_id; exclusión mutua con remix/AJUSTES.
  - Lint 0 errores, build OK (301.9 kB / gzip 95.0 kB).
- **Pendiente**: reiniciar la app (cerrar ventana + reabrir Musicia.exe —
  NO hace falta reiniciar la API, solo cambió frontend) y que el usuario
  pruebe: BIBLIOTECA → ✨ en una pista → chips + prompt + dado → GENERAR
  OTRA VERSIÓN.
- **Lección**: los "mecanismos de iteración" (re-lanzar, variar, encadenar)
  son parte del flujo, no un extra: si el resultado final no tiene camino
  para el paso siguiente, el flujo está incompleto.

## 2026-10-02 (IV) — [E1] Nombres en todo el ciclo de vida (crear/editar/remix)
- **Qué** (usuario: "quiero que puedas poner nombre a la canción resultante
  tanto al crear como en la edición como en el remix"):
  - Spec primero: [E1] en spec/02-REQUISITOS.md con las 3 decisiones del
    usuario (sin nombre → `pista-sin-nombre[-N]`; duplicados → `(2)`, `(3)`;
    renombrable en Biblioteca y Subidas).
  - **Backend**:
    - `MusicGenRequest.output_name` (ya no se fuerza `{hash}-{prompt}`).
    - `_unique_output_path()`: desambigua numerando; `DEFAULT_STEM =
      "pista-sin-nombre"`.
    - `_derive_stem()`: hereda el nombre de la fuente + marca (`-remix`,
      `-edit`) SIN encadenar (`-remix-remix`) y quita el prefijo hash de
      subidas.
    - `_find_audio()`: localiza en outputs/ o uploads/.
    - **NUEVO `PATCH /music/audio/{name}`** con `RenameRequest{new_name}`:
      renombra en el directorio donde vive, sanea y numera si el destino
      existe.
    - `_safe_name()` REESCRITA: el nombre que escribe el usuario se respeta
      (espacios, acentos, paréntesis); se quitan solo caracteres prohibidos
      en Windows y las barras se convierten en guion (antes perdía texto).
  - **Frontend**: campo NOMBRE en CREAR (junto a SEMILLA), en `RemixPanel`
    (DSP, con sugerencia `-remix`) y en `RemixIAPanel` (IA, con sugerencia
    `(versión IA)`); renombrado en línea con lápiz → input → GUARDAR /
    CANCELAR en Biblioteca y Subidas; `api.renameAudio()`. Al renombrar el
    audio analizado, SUBIR actualiza `lastAnalysis` al nombre nuevo (si no,
    los botones Following-usaban el nombre viejo → 404).
- **TESTER — PASS** (evidencia ejecutada):
  - `npx eslint src --max-warnings=0` → 0 errores; `npm run build` OK
    (305.75 kB / gzip 95.89 kB).
  - Generación REAL con nombre: `POST /music/generate {output_name:
    "Prueba Nombre Real"}` → succeeded 100 % en ~56 s; fichero
    `Prueba Nombre Real.mp3` 15.0 s / 240.812 bytes (ffprobe), servida por
    API HTTP 200 y primera en `/music/library`.
  - Remixes DSP reales: nombre propio → `Mi Canción Favorita.mp3`; repetido →
    `Mi Canción Favorita (2).mp3`; sin nombre → `01-Animales-muertos-remix.mp3`
    (sin hash); remix del remix → `01-Animales-muertos-remix (2).mp3`
    (NO `-remix-remix`).
  - Renombrado: outputs ✅, **uploads/** ✅, destino ocupado → `(3)` ✅,
    inexistente → 404 ✅, `../../evil` → saneado a `evil.mp3` ✅,
    `AC/DC: Back in Black?` → `AC - DC Back in Black.mp3` ✅.
  - Ficheros de prueba borrados al terminar (biblioteca del usuario intacta).
  - Pendiente de tester humano: los campos de nombre y el renombrado en línea
    solo están verificados por build, aún no pulsados en la app.
- **REVIEWER — APPROVE**: revisados backend/main.py (helpers + 4 call sites)
  y los 6 archivos del frontend. Sin residuos de la implementación previa;
  `runRemix` propaga `output_name` correctamente; el panel IA comparte
  componentes ya probados. Sin cambios solicitados.
- **Lección**: los nombres de fichero son parte del producto (el usuario los
  ve en cada pantalla); el hash del backend nunca debió salir a la UI.

## 2026-10-02 (V) — [A3] CANCIÓN CON VOZ: bug de la letra + selector de voz
- **Síntoma del usuario**: en CREAR → CANCIÓN CON VOZ "cumple con la música
  pero no añade la letra"; y "no acabo de ver dónde se cambia el nombre".
- **CAUSA RAÍZ (no era la UI)**: `GenerationDefaults.language = "en"` viajaba
  como `vocal_language` en TODAS las generaciones. El motor construye
  `# Languages\n{lang}\n\n# Lyric\n{letra}` (prompt_utils.py); con `"en"` y
  letra en castellano la pista salía instrumental. Además el motor espera
  marcas de estructura: un párrafo plano canta mal.
- **Decisiones del usuario (ask_user)**: selector de género (mujer/hombre),
  timbre, estilo de canto y emoción; letra **híbrida** (LM la propone, el
  usuario corrige o escribe).
- **Implementación**:
  - Backend: `POST /music/write_lyrics` → proxy a `/format_input` del motor
    (`MusicService.write_lyrics`, ruta en config). Sanitiza el BPM que devuelve
    el LM (descarta 300 bpm) y **detecta cuando solo devuelve estructura
    instrumental** → devuelve `warning` en vez de meter basura (NO FAKE).
  - `frontend/src/vocal.js` (nuevo): DATOS de género/timbre/estilo/emoción
    (descriptores en inglés, etiquetas en español) + `buildVocalTags()` +
    `structureLyric()` + `hasLyricStructure()`.
  - CREAR: bloque VOZ CANTADA (4 grupos de chips + IDIOMA), botón
    "ESCRIBIR LA LETRA POR MÍ" (con aviso si el LM no compone), aviso
    permanente sobre estructura, y `language`/`lyrics` ya estructurada al
    enviar. **NOMBRE** movido a campo protagonista de ancho completo (el
    usuario no lo veía por estar apretado en una fila).
  - SUBIR/BIBLIOTECA: LETRA opcional en el panel IA cuando kind es voz/mixta →
    `instrumental: !letra` (antes era instrumental fijo).
- **TESTER — PASS con detalle**:
  - lint 0 errores, build OK (311.66 kB / gzip 97.82 kB).
  - `/music/write_lyrics` real: devuelve letra estructurada; con el LM actual
    (0.6B) llega a devolver solo "Instrumental" → `warning` correcto y BPM
    absurdo (300) filtrado a 100. **Limitación real del modelo**: el LM no
    compone letras con calidad; la app lo dice, no lo disimula.
  - `/format_input` verificado en bruto contra el motor (2 llamadas): con
    "voz cantada" en el prompt el caption cambia de instrumental a con voz.
  - Generación real con voz: `POST /music/generate` {instrumental:false,
    lyrics con [Verse]/[Chorus], language:"es", 45 s} → **succeeded 100 %**;
    `Prueba Con Voz.mp3` 45.0 s / 720.812 bytes en disco.
  - Pendiente: revisión humana del audio (sí canta o no). Fichero dejado a
    propósito en la biblioteca para que el usuario lo escuche.
- **REVIEWER — APPROVE con 1 corrección aplicada**: detecté y arreglé que
  `language` salía duplicado en `Uploads.runAIGeneration` y que faltaba la
  etiqueta NOMBRE en el panel IA.
- **Lección**: el fallo "no canta" estaba en un default del backend
  (`language: "en"`), no en la UI: cuando el motor no hace lo pedido, hay que
  leer su código de conditioning antes de culpar a la interfaz.

## 2026-10-02 (VI) — Selector de voz compacto + "escribir letra por mí" arreglado
- **Síntomas del usuario**: (1) el selector de voz "se ha llenado la pantalla,
  menos agradable de usar" → pidió desplegables en una línea; (2) "no se
  entiende cómo funciona" lo de la letra; (3) "le pulsé escribir letra por mí y
  no va".
- **Rediseño (respuesta a 1 y 2)**:
  - Los 4 grupos de chips + idioma pasan a **una sola línea de desplegables**
    (`VocalSelect`: botón con etiqueta + valor actual, la lista solo ocupa
    espacio al abrirse, clic fuera para cerrar) + botón de reiniciar (↺) que
    devuelve todo a AUTO. Fuera los `ChipGroup` (eliminados).
  - La letra se explica en una línea y se añade **"VER LO QUE SE CANTA"**:
    previsualiza exactamente el texto estructurado que se enviará al motor
    (fin de la duda "no entiendo cómo funciona").
  - Text del botón: "ESCRIBIRLA POR MÍ", y en espera "EL MOTOR ESCRIBE (hasta
    2 min)…".
- **Causa raíz de 3 (bug real)**: `api.js` usa un axios con
  `timeout: 30000` para TODO. El LM del motor tardaba 25 s en caliente y
  **80-90 s en la primera llamada tras arrancar** (carga del modelo), así que el
  botón moría por timeout. Fix: cliente propio `lyricsClient` con
  `LYRICS_TIMEOUT_MS = 300000`.
- **TESTER — PASS**: lint 0, build OK (313.24 kB / gzip 98.30 kB); medición
  real de `/music/write_lyrics`: 25 s en caliente (con el LM actual sigue
  devolviendo solo estructura → `warning`, correcto y honesto).
- **REVIEWER — APPROVE**: los chips viejos eliminados (sin código muerto), el
  desplegable cierra al pulsar fuera y respeta el patrón visual existente
  (`btn`/`btn-signal`/`--surface-2`).
- **Lección**: al añadir un endpoint lento hay que revisar el timeout del
  cliente, no solo el backend; y los controles muchos van en desplegables
  (una línea) en vez de activar la pantalla entera.

## 2026-10-02 (VII) — Por qué el usuario "no veía" los cambios de UI
- **Síntoma**: "no me has cambiado nada en la UI de las voces como te dije".
- **Diagnóstico con evidencia**: el bundle nuevo SÍ se servía
  (`http://127.0.0.1:8000/` → `assets/index-46PhbxgV.js`, que contiene
  "GÉNERO", "ESCRIBIRLA POR", "AUTO"). El problema era el ciclo de vida de la
  ventana: **la X minimiza a la bandeja** y el `single-instance lock` restaura
  la ventana existente → reabrir Musicia.exe NUNCA recarga la página; `clearCache()`
  solo corre en un arranque real: todos los "cerrar y reabrir" servían el
  bundle viejo.
- **Fix**: `main.cjs` → `startUiWatch()`: cada 4 s pide el index a la API,
  compara la huella de los assets (`assets/index-*.js|css`) y si cambia hace
  `mainWindow.reload()` (log `[UI:RECARGA]`). Además, menú de bandeja con
  clic derecho: Mostrar / **Recargar interfaz** / Salir.
- **Estado tras el fix**: `node --check main.cjs` OK, lint OK, Electron
  relanzado desde el agente (4 procesos) y sirviendo `index-46PhbxgV.js`
  (el bundle con los desplegables de voz).
- **Aviso**: los MP3 de `backend/outputs/` estaban vacíos (el usuario los
  borró desde la biblioteca; solo quedan las subidas). Eran pistas de prueba.
- **Lección**: con bandeja + single-instance, "reiniciar la app" no es cerrar
  y abrir: hay que realinear la ventana con el bundle servido. La recarga
  automática evita la trampa en adelante.

## 2026-10-02 (VIII) — Visibilidad de la voz y prueba de que llega al motor
- **Síntoma**: "mejor pero se pierde visualización, en canción + voz, y no sé si
  cumple con lo seleccionado".
- **Qué se añadió** (CREAR → CANCIÓN CON VOZ):
  - El bloque de voz vuelve a tener borde y encabezado **VOZ CANTADA** (se había
    integrado sin contenedor y se perdía de vista).
  - Línea **ELIGIDO**: resumen siempre visible en verde de lo elegido
    (p. ej. `FEMENINA · SUAVE · POP · ÍNTIMA · ESPAÑOL`) o `AUTO · el motor
    decide la voz` si no hay nada. Sin abrir ningún desplegable.
  - Botón **VER LO QUE SE ENVÍA**: panel de transparencia con lo EXACTO que
    recibe el motor — DESCRIPCIÓN (prompt final), IDIOMA VOZ (vocal_language),
    VOCALES (los tags en inglés que se injectan), TIPO (CON VOZ/INSTRUMENTAL) y
    la LETRA ya estructurada. Responde directamente a la duda del usuario.
- **TESTER — PASS**: lint 0, build OK (314.82 kB / gzip 98.64 kB); el bundle
  servido contiene "ELIGIDO"; la detección de cambios del `startUiWatch()`
  comprobada contra la API real (huella anterior != actual → recarga).
- **Nota**: el build de esta iteración se hizo CON la app abierta, justo el
  escenario que fallaba antes; la ventana debería haberse recargado sola.
- **Lección**: cuando el usuario dice "no sé si cumple lo que elegí", la
  respuesta no es un Toast: es mostrar el payload. La transparencia ya era un
  patrón del proyecto (prompt mejorado) y se extendió a la voz.
