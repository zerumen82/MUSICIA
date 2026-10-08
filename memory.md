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
- **TESTER — PASS** (evidencia de esta entrada: e2e de `remix_prompt`, lint 0, build 299.3 kB). No se reejecutó al cerrar papeles.
- **REVIEWER — APPROVE** (2026-10-02, cierre de papeles): el prompt editable y el remix compartido siguen en el código vigente (`RemixIAPanel`, biblioteca).

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
- **TESTER — PASS** (evidencia de esta entrada: canción real del usuario, BPM una sola vez, API reiniciada). No se reejecutó al cerrar papeles.
- **REVIEWER — APPROVE** (2026-10-02, cierre de papeles): `enhance_prompt` añade el BPM solo si el texto aún no lo contiene, y `unique_adds` no lo repite.

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
- **TESTER — PASS** (evidencia de esta entrada: lint 0, build 301.9 kB). No se reejecutó al cerrar papeles.
- **REVIEWER — APPROVE** (2026-10-02, cierre de papeles): `RemixIAPanel` es el panel compartido de SUBIR y BIBLIOTECA; el prompt queda visible y los chips reescriben el texto.

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
- **TESTER — PASS** (evidencia de esta entrada: `node --check` del main de entonces, lint, bundle `index-46PhbxgV.js` servido). No se reejecutó el audio.
- **REVIEWER — APPROVE** (2026-10-02, cierre de papeles): `startUiWatch` compara la huella `assets/index-*.js|css` cada 4 s y recarga; la X sigue ocultando a la bandeja.

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

## 2026-10-02 (IX) — [F1] Mezcla profesional: cuadrar la batería, -14 LUFS y separar voces
- **Petición**: "cuando hace la mezcla debe cuadrar las baterías y hacerlo
  bien… elegir si es con letra, extraer las voces y remezclarlas… la UI no la
  quiero saturada ni de ancho ni de alto".
- **Decisiones (ask_user)**: cuadrar **con confirmación previa** (no a ciegas);
  acabado = **-14 LUFS** (sin ducking ni filtro de graves); separación
  **profesional** (instalación ~2,5 GB aceptada).
- **Investigación previa (NO FAKE)**: ACE-Step **no tiene** separación de voces
  (revisadas sus 40 rutas); ffmpeg 9.0.2 sí tiene `atempo`, `loudnorm` y
  `sidechaincompress`.
- **Backend**:
  - `audio_analysis.detect_groove()`: BPM + fase del golpe (rejilla fina de
    10 ms e interpolación parabólica → 0,08 % de error de tempo) + confianza.
  - `mixer_service` REESCRITO con ffmpeg: `atempo` (tempo sin tocar tono),
    `adelay` para la fase, `amix`, `loudnorm I=-14 TP=-1`, y medición real de
    LUFS/pico del resultado. `plan_alignment()` propone el ajuste.
  - `separator_service` (nuevo, venv propio `backend/demucs-venv`): demucs
    `htdemucs` en local; elige GPU si hay VRAM libre ≥2,6 GB (si no, CPU).
  - Endpoints: `POST /audio/mix/plan`, `POST /audio/mix` (align, normalize_lufs,
    devuelve loudness medido), `GET /audio/separate/status`, `POST /audio/separate`.
- **Frontend**: `SelectBox.jsx` (desplegable compartido) y **MixLab** rehecha en
  UNA línea: BASE ▾ · VOZ ▾ · volúmenes · CUADRAR ▾ · -14 LUFS · MEZCLAR, y
  debajo solo el plan explicado y `EXTRAER VOCES DE LA BASE`.
- **TESTER — PASS (evidencia)**:
  - Cuadre: base 166,25 bpm vs voz al 85 % (141,19 bpm) → plan `×1,1775` y
    `-60 ms`, con explicación en texto. Error de tempo 0,08 %.
  - Mezcla real: `Prueba Voz Extraida.mp3` = voz **extraída** + base al 85 %,
    cuadrada, loudness medido **-13,88 LUFS / -0,99 dBTP** (objetivo -14/-1).
  - Separación real con demucs en **cuda**: voces + base generados (81,45 s).
  - Bugs encontrados y corregidos en el camino: `%` con periodo float
    (IndexError), salida sin extensión (ffmpeg no deducía formato),
    `adelay` negativo (rompía el grafo → se retrasa la base), parser del JSON
    multilínea de loudnorm, numpy/torchaudio ausentes en el venv de demucs.
  - Ficheros de prueba borrados (queda `Prueba Voz Extraida.mp3` para escuchar).
- **REVIEWER — APPROVE**: `mix` reutiliza `_unique_output_path` (nada se pisa),
  el plan se pide siempre antes de mezclar, y si no hay motor de separación la
  UI lo dice (`GET /audio/separate/status`) en vez de fingir.
- **Nota de red**: demucs descarga los pesos (~80 MB) la primera vez; a partir
  de ahí es 100 % local. Declarado por la regla LOCAL-FIRST.
- **Lección**: `adelay` no admite negativos; alinear "hacia atrás" se hace
  retrasando la otra pista (equivalente exacto y sin perder audio).

## 2026-10-02 (X) — [F2] REMIXER de bootlegs (8 acciones + crossfade)
- **Petición**: "que la IA para meterle música, sacar parte de la música y
  cambios/bases, o ambas" y "más cosas que se te ocurran para bootlegs". Sin
  transcripción (decisión del usuario).
- **Nuevo en el REMIXER** (un desplegable de acciones, una línea de estado):
  1. **VOZ + MÚSICA DESDE PROMPT** — separa la voz, genera base nueva con el
     prompt y mezcla (con cuadre si es seguro).
  2. **SOLO BASE NUEVA DESDE PROMPT** — instrumental nuevo generado.
  3. **INSTRUMENTAL** / **ACAPELLA** — demucs en un clic.
  4. **LOOP DE 4 COMPASES** — calcula los segundos con el tempo real.
  5. **MEDIO TIEMPO** / **DOBLE TIEMPO** — el clásico del bootleg.
  6. **FORZAR TEMPO A** — a un BPM concreto.
  7. **CROSSFADE** (en MEZCLA): 2+ pistas fundidas e igualadas por tempo.
- **Backend**: `POST /audio/remix/ai` + `GET /audio/remix/ai/{job}` (job con
  fases reales: separar → generar → descargar → cuadrar → mezclar),
  `/audio/groove/{name}`, `/audio/tempo`, `/audio/loop`, `/audio/crossfade`,
  y en el mixer `force_tempo`, `make_loop`, `crossfade`.
- **UI compacta (petición explícita del usuario)**: `RemixActions.jsx` = un
  desplegable + un campo de prompt/bpm que solo aparece si la acción lo
  pide + UNA línea de estado. Nada de bloques abiertos.
- **TESTER — PASS con 2 bugs serious encontrados y corregidos**:
  - Loop (1,5 s) ✅ · Forzar 90 bpm: 166,25 → **89,77 bpm** (0,26 % error) ✅ ·
    Crossfade de 2 pistas a **-14,51 LUFS** ✅ · Remix IA completo en ~230 s
    (separación + base techno + mezcla) ✅.
  - **BUG 1 (destrozaba el audio)**: la voz extraída se detectaba a 349 bpm
    con confianza 0,04 y se "cuadraba" con ratio 0,24 → voz a un cuarto de
    velocidad. Ahora `plan_alignment` devuelve None si la confianza del groove
    es < 0,12 o si el ratio sale de 0,8-1,25, y la mezcla avisa en `note`:
    verificado con el caso real (`plan: null` + "se mezclará sin tocar").
  - **BUG 2 (octava)**: el detector se quedaba en el doble del tempo en
    medio tiempo (163 en vez de 83). Corrección de octava (primer lag con
    ≥90 % del pico): ahora **166,25 → 83,09** (la mitad exacta).
  - **Calidad**: loudnorm en **dos pasadas** (render → medición → render con
    `measured_*`): de -15,76 a **-14,4 LUFS**.
- **Lección**: cuando el detector no tiene confianza, la respuesta correcta
  es NO tocar el audio y decirlo; "cuadrar" sin criterio destruye la pista.
- Ficheros de prueba borrados (biblioteca del usuario intacta).
- **REVIEWER — APPROVE** (2026-10-02, cierre de papeles): `plan_alignment` devuelve null bajo confianza 0.12 o con ratio fuera de 0.8–1.25; `RemixActions` muestra la fase del job y el error real. El PASS de ejecución es el de esta entrada (no se rehízo el audio al cerrar papeles). El usuario confirmó el mismo día que el flujo funciona.

## 2026-10-02 (XI) — Información de agentes y bitácora puesta al día

- **Qué** (pedido del usuario: completar la info de los agentes y de memory):
  - Agentes musicales a 0.1.0: ACE-Step 1.5, demucs, ffmpeg. `music-orchestrator` tiene `ask_user` y pregunta antes de decidir. `music-composer` entrega JSON y no cita MusicGen como motor. `audio-engineer` describe el stack que ya corre.
  - `sd-scout` 0.1.1 (en `~/.agents/`, fuera del repo): `ask_user` añadido a `toolNames`. El prompt ya lo exigía.
  - `spec/04-EJERCITO.md` reescrito: seis agentes globales, flujo con scout y researcher, y la capa musical aparte.
  - `knowledge.md` reescrito: el generate es un job real de ACE-Step. El texto viejo decía que era un stub de MusicGen.
  - `spec/01`, `spec/02`, `spec/03` y `Agents.md` alineados con el código: rutas de mezcla, separación, letra y renombre; T1 y el «falta la UI de voz» salen de pendientes; [A3] y [F2] quedan verificadas con la confirmación del usuario de que todo funciona; [A4] queda parcial (falta el compás).
  - Veredictos que faltaban, escritos en su entrada: PASS apoyado en la evidencia ya pegada (no se regeneró audio) y APPROVE de esta lectura, en las entradas I, II, III, VII y en [F2].
  - Comentario de `frontend/main.cjs`: la X oculta a la bandeja; SALIR apaga; el diálogo nativo es el de la bandeja.
- **Por qué**: un agente que leyera `knowledge.md` o los prompts viejos trataría el motor vigente como si no existiera.
- **TESTER — PASS** (esta pasada, papeles, no audio):
  - `node --check frontend/main.cjs` → código de salida 0.
  - Búsqueda en `.agents/`: los tres prompts nombran ACE-Step; MusicGen solo aparece como motor que no se usa. `music-orchestrator` declara `ask_user`.
  - `sd-scout.ts` línea de `toolNames` incluye `ask_user`.
  - `knowledge.md` y `spec/04` describen ACE-Step 1.5. No queda la frase de stub de `/music/generate`.
- **REVIEWER — APPROVE**: releídos los tres `.ts` musicales (cierran el objeto y exportan), `sd-scout.ts`, `spec/04`, `knowledge.md`, los bloques tocados de `spec/01` y `spec/02`, y `spec/03`. Los prompts no mandan instalar nada. El compositor no genera audio. El ingeniero no duplica los umbrales de `mixer_service.py`. [A4] no se marcó hecha del todo: el compás sigue abierto. Los PASS históricos quedan etiquetados como evidencia ya registrada, no como una ejecución nueva.
- **Lección**: la bitácora y los prompts tienen que nombrar el motor que está en marcha. Un documento de arranque desfasado pesa más que el código, porque es lo primero que lee el siguiente agente.

## 2026-10-02 (XII) — Propuesta de mejoras, solo en papel

- **Qué**: a petición del usuario, revisión a fondo de la UI y de las mejoras de producto, escrita en `spec/05-MEJORAS.md`. Ocho puntos: CREAR en una línea, un solo anuncio del motor, progreso visible al cambiar de pestaña, menú de BIBLIOTECA, menos chips en SUBIR y en «otra versión», nombre en mezcla y locución, ficha JSON junto al MP3, modelo y VRAM en el lateral. `spec/00` y `spec/03` apuntan a ese archivo.
- **Por qué**: la pantalla de CREAR no cabe en la ventana mínima (1080×700) con tres filas de chips y una columna SESIÓN de 360 px, y el progreso de un job lanzado desde BIBLIOTECA solo vive dentro de CREAR.
- **Resultado**: documento de propuesta. No aprobado. Ningún cambio de comportamiento. No hay PASS de producto porque no se ha tocado la app.
- **Lección**: el comparador A/B anuncia «listo para comparar» y solo abre dos reproductores. Hasta que haya un play conjunto, el texto no debe prometerlo.

## 2026-10-02 (XIII) — Persistencia, voz/letra y remix de estudio, en la propuesta

- **Qué**: el usuario pidió añadir a la propuesta tres cosas, y mirar el código antes de escribirlas. Quedaron como puntos 9, 10 y 11 de `spec/05-MEJORAS.md`.
  - **Pestañas**: `App.jsx` monta solo la pestaña activa. Prompt, letra, análisis, mezcla y el sondeo del job mueren al cambiar. El job sigue en el servidor (`remix_jobs` o el de música) y la UI olvida el id.
  - **Voz y letra**: CREAR ya exige letra, pone marcas y avisa si el LM no compone. BIBLIOTECA abre «otra versión» con `kind="musica"`, así que el campo de letra no sale.
  - **Remix**: `POST /audio/remix/ai` ya separa la voz (demucs, solo dos stems), genera una base instrumental con el prompt y mezcla a −14 LUFS. `RemixActions` ejecuta la acción al pulsar el menú y vacía la acción, así que el prompt de «voz + música nueva» no llega a escribirse. No hay stems de bajo, batería y armonía: hace falta htdemucs sin `--two-stems`, y eso queda como segundo paso.
- **Por qué**: el usuario quiere escribir la letra, cambiar de pestaña y seguir, y hacer bootlegs de verdad (sacar la voz y crear el bajo o lo que pida).
- **Resultado**: solo papel. Orden nuevo de la propuesta: persistencia, luego el remix usable, luego la letra en biblioteca. Sin aprobación no se codifica.
- **Lección**: el camino de «voz extraída + base generada» ya estaba en el servidor. El fallo visible es que el menú dispara la acción antes del prompt.

## 2026-10-02 (XIV) — Cómo se ven CREAR, remix, mezcla y biblioteca

- **Qué**: revisión visual de esas cuatro pantallas, añadida a `spec/05-MEJORAS.md` («Cómo se ven»). Mismo CONSOLE. La onda real (`Waveform`, `GET /audio/peaks`) y la barra `.vu` pasan a ser lo que se mira: en CREAR el porcentaje grande mientras genera; en el remix la onda de la pista con la línea CONSERVAR / CREAR / HACER; en mezcla dos columnas con onda y fader; en biblioteca una onda muda de 28 px por fila y un menú ACCIONES.
- **Por qué**: el usuario pidió mejoras reales y vistosas sin cambiar de interfaz. Hoy la onda solo aparece en el remix de sliders, y el porcentaje es una barra de 8 px bajo un muro de chips.
- **Resultado**: solo papel. No se ha tocado `frontend/`.
- **Lección**: lo vistoso que ya está construido (picos, fader verde, tarjeta «pista lista») no se usa en las pantallas donde el usuario mira.

## 2026-10-02 (XV) — Revisión de todas las funciones: el motor solo recibe text2music

- **Qué**: revisión de generación, letra, subida, remix DSP, remix IA, separación, mezcla, crossfade, locución, biblioteca y la API de ACE-Step 1.5. Escrito al inicio de `spec/05-MEJORAS.md` («Mejoras sustanciales»).
- **Hallazgos**:
  - `task_type` está fijo en `text2music`. En el turbo que ya cabe, el motor admite `cover` (cambia el estilo y guarda la forma) y `repaint` (regenera un tramo). `extract`, `lego` y `complete` exigen `acestep-v15-base` y no caben sin medirlo.
  - «Extender» y «re-crear» en SUBIR no usan el audio: lanzan otra generación desde el análisis.
  - MEZCLA, si hay biblioteca y subidas, enseña la base solo de una lista y la voz solo de la otra.
  - `POST /audio/separate` bloquea la API hasta que demucs acaba. Los jobs están en memoria y no se pueden parar.
- **Resultado**: solo papel. Orden propuesto: mesa cover/repaint, arreglar la mesa actual, medir el modelo base, luego ficha y cola.
- **Lección**: el remix profesional que el usuario pide está documentado en el propio motor. Musicia aún no le manda el archivo.

## 2026-10-02 (XVI) — Locución fuera. Cover y repaint en el turbo

- **Qué pidió el usuario**: quitar VOZ porque no es para eso, y aplicar las mejoras.
- **Qué cambió**:
  - La pestaña VOZ ya no está. `VoiceLab.jsx` se borró. El canto sigue en CREAR. `POST /tts/generate` y `GET /voices` siguen en la API (edge-tts, red) y la pantalla no los llama.
  - El motor acepta `text2music`, `cover` y `repaint`. `lego`, `extract` y `complete` se rechazan. Cover y repaint exigen la ruta absoluta del audio, apagan `thinking`, y si no se pide duración mandan `audio_duration=-1`. La fuerza de cover sale de `generation.cover_strength` (0,6). El idioma por defecto pasa a `es`.
  - Remixer: el menú solo elige. HACER lanza. Acciones nuevas: VERSIÓN (cover), TRAMO (repaint, con la onda) y AJUSTAR (el panel DSP). «Alargar o rehacer un tramo» en SUBIR abre el tramo, no otra canción.
  - MEZCLA lista biblioteca y subidas en BASE y en VOZ, con un campo de nombre. Si el nombre se deja vacío, el stem es el de `mixer.default_output_name` (`mixed_output`), sin duplicar `.mp3`. Si el mismo nombre está en los dos sitios, se usa el de la biblioteca.
  - `POST /audio/separate` responde `{job_id}` y el trabajo sigue en `GET /audio/separate/{job_id}`. `GET /audio/separate/status` sigue siendo la instalación de demucs.
  - Al terminar una generación se escribe `nombre.ficha.json` al lado del MP3. La biblioteca enseña BPM, tarea y prompt cuando la ficha existe. Las pistas viejas no tienen ficha.
  - CREAR, SUBIR, MEZCLA y BIBLIOTECA siguen montadas al cambiar de pestaña. La pastilla de arriba dice ACTIVO, APAGADO o CONECTANDO.
- **Qué no se hizo**: no se instaló `acestep-v15-base`. No hay botón PARAR (el motor no cancela). La cola sigue en memoria: al reiniciar la API se pierde. No se redibujó el muro de chips de CREAR ni las ondas de 28 px. No se generó una cover ni un repaint: el turbo ya estaba cargado y eso ocupa la GPU varios minutos.
- **API**: había dos procesos de `backend\main.py` (el venv y el Python 3.10 del sistema), los dos con el código viejo y sin jobs activos. Se pararon y se dejó uno, el del venv, pid 17440. El motor de `:8001` no se tocó y siguió en turbo.
- **TESTER — PASS del contrato, no del audio**:
  - Payload con el venv: cover lleva `src_audio_path`, `audio_cover_strength` 0,6, `thinking` false y `audio_duration` -1. text2music sigue igual, idioma `es`, duración 120. Repaint 12–20 lleva `chunk_mask_mode=explicit`. lego, extract, complete, cover sin origen y tramo 10–4 lanzan `MusicEngineError`. `py_compile` de `main.py`, `music_service.py` y `config.py`: salida 0.
  - `npm run lint` y `npm run build` en `frontend`: salida 0. El bundle `index-7YFpU78D.js` contiene VERSIÓN, TRAMO y AJUSTAR. No contiene `VoiceLab` ni «TEXTO A LOCUCIÓN».
  - API viva, `GET /music/config`: `language=es`, `cover_strength=0.6`, tareas `text2music,cover,repaint`, modelo `acestep-v15-turbo`.
  - `POST /music/generate` con `am.mp3` real: lego y extract → 503 «Tarea no disponible en el turbo de 8 GB». Repaint de 10 a 4 → 503 con el texto del tramo. Cover sin `source_name` → 503 «necesita el audio de origen». Cover con un nombre que no existe → 404. Después, `GET /music/jobs` → 0 trabajos. No se ocupó la GPU.
  - `POST /audio/separate` con un nombre falso → 404. `GET /audio/separate/status` → 200, `available=true`, `device=cuda`. `GET /audio/separate/no-existe` → 404 «Esa separación no existe» (no se confunde con `/status`).
  - Ficha: `_write_ficha` / `_read_ficha` sobre un temporal devolvieron `task_type=cover`, `bpm=130`, `prompt=bajo pesado`. El stem de mezcla vacío es `mixed_output`.
  - `GET /music/library` → 5 MP3. `GET /` → 200.
  - No se abrió el navegador: en esta sesión no hay herramientas de browser. La UI servida se comprobó por el bundle y por `GET /`.
- **REVIEWER — APPROVE con límites**: releídos `music_service.build_payload`, el alta del job en `generate_music`, `RemixActions.jsx`, el cableado de SUBIR (`extend` ya no abre el panel de otra canción), las dos listas de `MixLab` y el borrado de `VoiceLab`. La fuerza no está escrita a mano en la pantalla: sale de `/music/config`. No se marca HECHO [F3]: faltan el MP3 de cover y el de repaint.
- **Lección**: un `Start-Process` lanzado desde esta sesión muere al cerrarse el comando. La API que quedó en pie se creó con `Win32_Process.Create`.

## 2026-10-02 (XVII) — Remix al nivel de CREAR, y un solo modelo en la GPU

- **Qué pidió el usuario**: funcionalidades nuevas de exactitud, sonido profesional, usabilidad, un remix tan capaz como CREAR, y una gestión de modelos más eficiente. No eligió entre las opciones; se hizo el paquete que cabe en 8 GB sin descargar pesos.
- **Qué cambió**:
  - Versión y tramo llevan letra (vacío = instrumental), tono, semilla, nombre y el botón MEJORAR PROMPT. La ficha de la biblioteca rellena prompt, BPM, letra y tono. Una semilla escrita pone `use_random_seed` en falso: si no, el motor ignoraba el número y la comparación A/B no era real.
  - Al acabar un cover o un repaint, el MP3 pasa por `normalize_track` (loudnorm a −14 LUFS / −1 dBTP, las mismas constantes de la mezcla).
  - Si ya hay una generación, un remix IA o una separación en curso, el siguiente trabajo responde 409.
  - `allowed_models` es solo `acestep-v15-turbo`. Un XL, un base o un sft se rechazan y no se llama a `/v1/init`. `GET /music/models` dice el modelo cargado. El lateral lo muestra.
- **Qué no se hizo**: no se descargó el modelo base ni el XL. No se generó una cover en la GPU. El LM del motor estaba en null en `/health`; no se forzó a cargarlo.
- **API**: se reinició la de `:8000` (pid 1448, venv). El motor de `:8001` no se tocó.
- **TESTER — PASS del contrato y del master, no de una cover nueva**:
  - Payload: sin semilla, `use_random_seed` true. Con semilla 42, `use_random_seed` false. XL, base y sft lanzan `MusicEngineError`. `py_compile` salida 0.
  - Cola: con un job `running` de mentira en el diccionario, `_gpu_busy()` devuelve el texto de la GPU; al quitarlo, None.
  - Master real: `normalize_track` sobre `backend/outputs/am.mp3` hacia un temporal. Medición ffmpeg: `input_i` −13,66 LUFS, `input_tp` −1,28, `input_lra` 2,0. El temporal se borró. No se tocó el MP3 original.
  - `npm run lint` y `npm run build`: salida 0. El bundle contiene «MEJORAR PROMPT» y el texto de la letra.
  - API viva: `GET /music/models` → `loaded=acestep-v15-turbo`, `available=acestep-v15-turbo`, `loaded_lm` vacío, sin error. `POST /music/generate` con `model=acestep-v15-xl-turbo` → 503 «Modelo no residente en esta GPU de 8 GB». `GET /music/jobs` → 0.
- **REVIEWER — APPROVE con límites**: la fuerza, el LUFS y el modelo permitido salen de config, no de un número suelto en la pantalla. El listado del motor llegó en formato OpenAI (`id` con barra), no en el envoltorio de la documentación, y el endpoint lee los dos. No es HECHO una cover cantada: falta ese MP3.
- **Lección**: el `/v1/models` que está en marcha no coincide con el ejemplo de la documentación. Hay que leer la respuesta viva.

## 2026-10-03 (XVIII) — Cableado: ficha, barra y doble tiempo

- **Qué pidió el usuario**: dejarlo todo atado y cableado. No pidió funciones nuevas ni una cover en la GPU.
- **Qué estaba suelto**:
  - «Otra versión» (biblioteca) y re-crear (subir) generaban desde el texto y no mandaban el audio. Ahora van como `cover`, sin duración, para que el motor use la del origen. «Crear base» sigue siendo una cama nueva.
  - DOBLE TIEMPO mandaba `mode=doble`. El servidor solo conoce `half`, `double` y `bpm`, y cualquier otra palabra caía en medio tiempo. La pantalla decía «Doble» y el audio salía a la mitad.
  - Mezcla, tempo, loop, fundido, separación y remix IA dejaban el MP3 en la biblioteca sin ficha. Renombrar, borrar, el remix DSP y el post-proceso ya movían la suya.
  - La barra de arriba solo miraba las generaciones. Un remix IA o una separación no aparecían al cambiar de pestaña.
- **Qué cambió**: la ficha se copia en esas salidas (`task_type` mix, tempo, loop, crossfade, vocals, instrumental, remix). `GET /music/jobs` mete en la misma cola el remix IA y la separación, con su fase. DOBLE TIEMPO envía `double`. Un modo desconocido responde 400 y no llama a ffmpeg. El fundido de MEZCLA ya no repite los 4 segundos: usa el valor del servidor.
- **Qué no se hizo**: no se lanzó una cover. No se descargó ningún modelo. No se tocó el motor de `:8001`. No se rediseñó la pared de chips. La UI no se clicó: no hay navegador en esta sesión.
- **API**: estaba caída en `:8000`. Se arrancó de nuevo con el venv (pid 5840, el que escucha es su hijo 6900). El motor sigue en el pid 12024.
- **TESTER — PASS del cable, no de una cover**:
  - `py_compile` salida 0. Prueba en proceso: `_tempo_plan('half')` → 0,5; `'double'` → 2,0; `'bpm' 150` sobre 100 → 1,5; `'doble'` lanza ValueError. `_carry_ficha` de una mezcla conserva BPM 90, pone `task_type=mix`, `source_name` y el prompt nuevo. La vista de un remix `running` devuelve la fase y más de 4 s. La de una separación lista apunta a `tema-base.mp3`. Impreso `CABLE_OK`.
  - `npm run lint` y `npm run build` salida 0. Bundle `frontend/dist/assets/index-CsbZnEcZ.js` (328 kB, gzip 102 kB). Dentro: «Versión lanzada sobre esta pista», «Versión lanzada sobre este audio», «Base nueva lanzada», dos `task_type:"cover"`, y `mode:A==="doble"?"double":"half"`.
  - API viva: `GET /health` con motor alcanzable. `GET /music/models` → `loaded=acestep-v15-turbo`, disponible el mismo, sin error, LM vacío. `GET /music/jobs` → 0. `GET /` sirve `index-CsbZnEcZ.js` (200). `POST /audio/tempo` con `mode=doble` y `am.mp3` → 400 «mode debe ser half, double o bpm». No se escribió otro MP3.
- **REVIEWER — APPROVE con límites**: el modo inválido ya no se disfraza de medio tiempo. La ficha solo se escribe después de que el archivo exista. La barra y la cola leen el mismo `GET /music/jobs`. No es HECHO una canción cover: falta ese MP3.
- **Lección**: el id de un botón no es el valor del contrato. `doble` en la pantalla y `double` en la API tienen que traducirse en el sitio de la llamada.

## 2026-10-03 (XIX) — La UI cabe y se lee

- **Qué pidió el usuario**: revisar la UI para que sea usable.
- **Qué estorbaba**: CREAR abría género, mood, BPM y tono en filas de chips y, con el margen de 64 px y la columna de sesión de 360 px, en la ventana mínima el formulario no cabía. En BIBLIOTECA las acciones eran iconos sin texto en una sola fila que se salía por la derecha. El remix metía el prompt en un campo de 256 px y los campos decían «tono» sin etiqueta. «Otra versión» abría diez chips. Varios controles pintaban el botón entero de verde, y el de generar dejaba de verse como la acción.
- **Qué cambió**: género, mood, BPM y tono son desplegables en una línea. El verde de acción queda en GENERAR, HACER, MEZCLAR, FUNDIR y GENERAR OTRA VERSIÓN. Lo elegido se marca con el borde, no rellenando el botón. La biblioteca muestra REMIX, VERSIÓN, AJUSTES, NOMBRE, BAJAR y BORRAR, y borrar pide confirmación. El remix etiqueta letra, tono, semilla, nombre, BPM y el tramo. La dirección de «otra versión» es un desplegable. SUBIR encoge la zona de soltar cuando ya hay un análisis. El margen pasa de 64 px a 24 px (40 px en ventana ancha) y la sesión baja debajo del formulario por debajo de 1280 px.
- **Qué no se hizo**: no se clicó la ventana. No hay navegador en esta sesión. El asistente de calidad, que se abre aparte, sigue en pasos.
- **TESTER — PASS de build, no de clic**: `npm run lint` y `npm run build` salida 0. Bundle `index-D4v5Iosf.js` (330 kB, gzip 102 kB). `GET /` lo sirve (200) y el JS contiene GÉNERO, VERSIÓN, SÍ BORRAR, ELIGE UNA ACCIÓN, DIRECCIÓN y LETRA. La ventana, si está abierta, se recarga sola al ver el bundle nuevo.
- **REVIEWER — APPROVE con límites**: un botón verde por acción. Los desplegables no cambian el prompt que ya construían los chips. No se comprobó con el ratón.

## 2026-10-03 (XX) — Duración de 2:00 y estado sin falso arranque

- **Qué dijo el usuario**: la duración predeterminada había bajado, y la pantalla parecía no cargar y después ponía ACTIVO.
- **Causa**: CREAR abría el deslizador en 60 s (1:00). El valor del servidor es 120 s (2:00) y el tope 600 s. Hasta que llegaba `/music/config`, el número era la mitad. El lateral y la barra decían CONECTANDO, y CREAR decía «SYNC CON MOTOR LOCAL…», y al responder el motor pasaban a ACTIVO.
- **Qué cambió**: la duración abre en 2:00 y el tope en 10:00, los mismos números que `generation` en config. Si el usuario mueve el deslizador antes de que llegue la config, no se le pisa. El estado sale ACTIVO desde el primer pintado. APAGADO solo si el chequeo dice que el motor no responde. Se quitó el texto de sincronizando.
- **TESTER**: `npm run lint` y `npm run build` salida 0. Bundle `index-C43vO3kN.js`. `GET /music/config` sigue en `duration_seconds=120`, `max_duration_seconds=600`. No se clicó la ventana.

## 2026-10-03 (XXI) — Revisión a fondo: estados y acciones que fallaban

- **Qué pidió el usuario**: revisar a fondo. No quiere fallos.
- **Qué fallaba**:
  - El arreglo anterior pintaba ACTIVO antes de que `/health` respondiera. GENERAR exige motor activo, así que el botón podía estar muerto mientras la barra decía ACTIVO. CREAR además consultaba el motor una sola vez: si arrancaba tarde, GENERAR no se despertaba.
  - VARIAR lanzaba dos generaciones seguidas. La segunda siempre recibía 409: en 8 GB no caben dos trabajos a la vez. El botón se quedaba en error aunque la primera sí hubiera entrado.
  - Un corte de un solo sondeo daba por perdida la generación, el remix o la separación, aunque el trabajo siguiera en el servidor.
  - Un fallo de `GET /music/jobs` borraba la fase de la barra.
  - CUADRAR podía vaciarse y la mezcla pasaba a mostrarse como si no hubiera elección. La dirección de «otra versión» tenía una fila que no hacía nada.
  - El crossfade listaba dos veces un archivo que estaba en biblioteca y en subidas.
  - Los menús se abrían dentro del scroll de la página y se cortaban: las últimas acciones del remixer no se podían pulsar.
- **Qué cambió**: la pastilla no se pinta hasta el chequeo; antes, el lateral dice MOTOR. Luego ACTIVO o APAGADO, y CREAR usa ese mismo estado. VARIAR espera a que termine la primera pista y entonces lanza la segunda. El sondeo aguanta 5 cortes (`JOB_POLL_MAX_MISSES`) antes de marcar error; si el trabajo ya no existe, para al momento. CUADRAR y DIRECCIÓN no se pueden vaciar. El crossfade deduplica por nombre. Los menús se anclan a la ventana. La duración sigue en 2:00, tope 10:00. No vuelve CONECTANDO.
- **Qué no se hizo**: no se clicó la ventana. No hay navegador en esta sesión. No se lanzó una cover en la GPU. No se tocó el motor del puerto 8001 (pid 12024). La API del puerto 8000 estaba caída y se volvió a arrancar (venv pid 12188, escucha pid 17832).
- **TESTER — PASS de build y de servicio, no de clic**: `npm run lint` y `npm run build` salida 0. Bundle `index-C7sT90xb.js` (330.73 kB, gzip 103.05 kB). Contiene «Variación A en cola» y no contiene CONECTANDO ni «SYNC CON MOTOR». `GET /` lo sirve (200). `GET /music/config`: `duration_seconds=120`, `max_duration_seconds=600`. `GET /health`: motor reachable.
- **REVIEWER — APPROVE con límites**: no se maquilla el estado ni la cola. VARIAR ya no promete dos trabajos simultáneos. No se comprobó con el ratón. Un cover MP3 real sigue sin estar HECHO.

## 2026-10-03 (XXII) — El remix decía que el motor no responde

- **Qué pasó**: el usuario hizo un remix de «Animales muertos» (base techno). La separación en GPU terminó. El motor aceptó la tarea `bf814124-f087-4ad1-aa49-23feae28755c` y la acabó (81,4 s; 67 s de LM y 6 s de DiT). A los 35 s, un `POST /query_result` se cayó con un `httpx` sin mensaje. `wait()` dio el remix por muerto. El mensaje fue «El motor ACE-Step no responde (/query_result)». El motor siguió y guardó el MP3.
- **Causa**: un corte del sondeo abortaba toda la espera. Once consultas anteriores habían respondido 200. El motor estaba vivo.
- **Qué cambió**: `MusicService.wait` reabre el cliente y sigue sondeando. Solo se rinde si, tras 8 cortes (`acestep.poll_max_misses`), `/health` dice que el motor no está. El error ahora incluye el tipo de la excepción. La base ya hecha se descargó y se mezcló con la voz: `f11edb27-01-Animales muertos-remix.mp3` (81,5 s, 1 956 140 bytes) y la base `f11edb27-01-Animales muertos-base.mp3` (81,4 s). El tempo de la voz no era fiable, así que la mezcla no lo tocó.
- **Prueba**: un `wait` de esa tarea con el primer sondeo forzado a `httpx.ReadError` reintentó y leyó `status=1`. `verify_audio` dio 81,4 s y 81,5 s. `GET /music/library` lista los dos MP3. La API se reinició (escucha pid 2036). El motor del puerto 8001 sigue en el pid 12024. `GET /health`: motor reachable. No se lanzó otra generación.
- **REVIEWER — APPROVE con límites**: el corte ya no mata un trabajo vivo. La mezcla recuperada es la de esta pista, no una cover nueva. No se clicó el botón otra vez.

## 2026-10-03 (XXIII) — Ese aviso no sale en la UI

- **Qué dijo el usuario**: lo del remix es un fallo y en la UI no puede ocurrir.
- **Qué se veía**: el remix pasaba a error y la línea roja decía que el motor no responde, aunque el motor seguía y terminaba el audio.
- **Qué cambió**: un corte de `/query_result` o una respuesta a medias no cierra la espera, tampoco si el chequeo de salud falla en ese instante. El tope sigue siendo el de la tarea (`job_timeout`). La fase que pinta el remix es la de trabajo (`_human_phase`), no «Error». En la pantalla, RemixActions y CREAR no ponen en rojo un aviso de sondeo: la línea sigue en la fase. Un fallo real del trabajo (el motor terminó mal, el archivo no existe) sí se enseña.
- **Prueba**: tres cortes forzados con `httpx.ReadError` y el chequeo de salud en falso; el cuarto sondeo leyó la tarea real `bf814124` con `status=1`. `py_compile` salida 0. `npm run lint` y `npm run build` salida 0. Bundle `index-BXtARemE.js`. `GET /` lo sirve. `GET /health`: motor reachable. El motor del puerto 8001 sigue en el pid 12024. La API se volvió a arrancar (pid 19112). No se lanzó otra generación. No se clicó la ventana.

## 2026-10-03 (XXIV) — Una subida se reutiliza en el remix

- **Qué pidió el usuario**: al subir un audio, poder reciclarlo y no tener que volver a subirlo para hacer un remix.
- **Qué había**: la mesa de remix en SUBIR solo se abría para el archivo recién analizado en esa sesión. La lista de subidas guardadas tenía reproducir, nombre, bajar y borrar.
- **Qué cambió**: cada fila de SUBIDAS tiene REMIX. Lo abre o lo cierra. La mesa es la misma (`RemixActions`) y recibe el nombre de ese archivo. Borrar esa subida cierra la mesa. Renombrarla la sigue. No hay endpoint nuevo ni otra subida.
- **Prueba**: `npm run lint` y `npm run build` salida 0. Bundle `index-CiVVeDmv.js` (331.65 kB, gzip 103.18 kB). `GET /` lo sirve. `GET /audio/uploads` devolvió 0 archivos; `backend/outputs/uploads` está vacío. No se lanzó un remix ni se clicó la ventana.
- **TESTER — PASS de build y de servicio, no de clic**: el botón no llama a `uploadAudio`. El nombre viaja a `RemixActions` como `fileName`.
- **REVIEWER — APPROVE con límites**: REMIX va en gris; el verde sigue siendo HACER. No se comprobó con el ratón. La carpeta de subidas está vacía, así que la primera vez sigue haciendo falta soltar el archivo.

## 2026-10-03 (XXV) — El prompt se reescribía y el remix no dejaba elegir minutos

- **Qué pidió el usuario**: revisar los logs porque el prompt no hizo lo que pidió. Añadir en el remix una opción de minutos para que la canción dure más, y que la letra se adapte a esa duración.
- **Qué dicen los logs**: a las 22:20 el caption enviado fue «melodias con sintetizador roland, bATERIAS CONTUNDENTES HARDCORE DE ROTTERDAM» y la letra `[instrumental]`. El LM lo reescribió como orquesta de cuerda, cine, 113 bpm, 81 s. A las 21:17, «TECHO HARD BOUNCE» salió como metal industrial y guitarras. El DiT usó esa reescritura, no la frase. Los 81 s son la duración del audio de origen: la base nueva no tenía minutos.
- **Qué cambió**: `use_cot_caption=false` en el payload, así el prompt escrito es el caption. En VOZ REAL + BASE NUEVA y SOLO BASE NUEVA hay un desplegable MINUTOS (1 a 10, el máximo de config es 600 s) y una letra. Si hay letra, se adapta a esos minutos antes de generar. Vacía sigue siendo instrumental. Versión y tramo no cambian de duración: el motor la fija a la del audio.
- **Prueba**: `build_payload` de un prompt de hardcore con 180 s devolvió `use_cot_caption=False`, el mismo prompt y `audio_duration=180`. `resolve_remix_duration(None, 81.4)` sigue en 81.4; 300 s se acepta; 900 s falla. `npm run lint` y `npm run build` salida 0. Bundle `index-CaqMVu1i.js` (333.32 kB, gzip 103.59 kB). `GET /` lo sirve. La API se reinició (pid 19764). El motor del puerto 8001 sigue en el pid 12024. `GET /health`: motor reachable. No había trabajos en cola. No se lanzó otra generación. No se clicó la ventana.
- **TESTER — PASS de payload, build y servicio, no de una canción nueva**.
- **REVIEWER — APPROVE con límites**: no se finge que VERSIÓN o TRAMO puedan durar más. La adaptación de la letra no se ejecutó contra el LM en esta prueba.

## 2026-10-03 (XXVI) — El prompt llegaba y los códigos de audio lo tapaban

- **Qué pidió el usuario**: sigue sin hacer lo que pide en los prompts.
- **Qué dicen los logs de las 23:27**: el caption enviado y el que vio el DiT fue «MELORIA CON SINTETIZADORES AKAI, BATERIAS DE HARDCORE DE ROTTERDAM», 240 s, `use_cot_caption=false`. Antes, `/format_input` reescribió esa frase como orquesta de cuerda a 40 bpm, pero esa reescritura no se usó para el audio. Lo que sonó salió de 1200 códigos del LM (`thinking=true`) más la letra «BASE» y el BPM 166 del tema original.
- **Qué cambió**: la generación va al DiT con el prompt, sin códigos del LM (`thinking`, `use_cot_caption`, `use_cot_language` y `use_cot_metas` en false). Si el BPM está vacío no se copia el del audio viejo. Una palabra suelta en la letra («BASE») no se canta: la base sale instrumental.
- **Prueba**: `build_payload` devolvió `thinking=False`, los tres cot en false, bpm vacío y 240 s. `lyrics_are_song('BASE')` es falso. `npm run lint` y `npm run build` salida 0. Bundle `index-DW48uPDL.js` (333.53 kB, gzip 103.71 kB). `GET /` lo sirve. API reiniciada (pid 11576). Motor 8001 sigue en pid 12024. `GET /health` reachable. Sin trabajos en cola. No se generó otra canción. No se clicó la ventana.
- **TESTER — PASS de payload y de servicio, no de escucha**.
- **REVIEWER — APPROVE con límites**: el modelo puede seguir entendiendo mal un typo («MELORIA»). No se ha oído el resultado.

## 2026-10-04 (XXVII) — La pastilla decía APAGADO con el motor encendido

- **Qué pidió el usuario**: lo lanzó, estaba ACTIVO y pasó a MOTOR APAGADO. Eso no puede ocurrir. El motor no puede quedarse muerto: solo SALIR lo apaga. Cada vez que se apaga la UI y se vuelve a abrir, el motor tiene que estar otra vez en marcha.
- **Qué pasó de verdad**: el motor del puerto 8001 (pid 12024) no se apagó. A las 23:43 del 2026-10-03 el remix `d1c5e546` separó la voz en el mismo hilo de la API (hasta las 23:45:29) y a las 23:45:54 mezcló con ffmpeg (listo a las 23:46:30, `39628473-01-Animales muertos (2).mp3`). Mientras eso corría, `GET /health` no podía contestarse y la pastilla lo pintaba apagado. Al terminar, `/health` volvió a responder en 188 ms con el motor alcanzable. El MP3 del motor es `2f20ded9-a08c-f961-7e3a-42079dbbb23d.mp3`.
- **Qué cambió**: la separación, el análisis, la medición y la mezcla del remix IA van en un hilo, así el bucle de la API sigue contestando. `/health` usa `acestep.health_timeout` (3 s), no los 60 s de una generación. Si la API no contesta, o hay un trabajo en curso, la pastilla no pasa a APAGADO. Con la ventana abierta, `scripts/ensure_local.ps1` arranca el proceso que falte y no mata uno que ya existe. SALIR escribe `logs/stop.flag` y para motor y API. Abrir la ventana borra esa marca y los deja en marcha. La X sigue yendo a la bandeja.
- **Prueba**: `py_compile` salida 0. `node --check` de `main.cjs` salida 0. `npm run lint` y `npm run build` salida 0. Bundle `index-RaxfxUaQ.js` (333.65 kB, gzip 103.76 kB). `ensure` con todo vivo: `MOTOR=up`, `API=up`, el pid 12024 no cambió. Con `stop.flag` y sin `-Rearme` imprimió `HOLD`. Había 1 trabajo y estaba en `succeeded`; ninguno en curso. Se paró solo la API (pids 20988 y 8276) y `ensure -Rearme` la volvió a dejar (escucha pid 18400). `GET /health` en caliente: 101 ms, `reachable=true`. `GET /` sirve el bundle nuevo (200). El motor sigue en el pid 12024. Se abrió la ventana (electron pid 23108). No se clicó. No se lanzó otra generación.
- **TESTER — PASS de servicio y de build, no de clic**.
- **REVIEWER — APPROVE con límites**: un proceso que existe y no responde no se mata, porque podría estar a mitad de una canción. MEZCLA, tempo y picos siguen pudiendo ocupar el bucle un rato; la pastilla, en ese silencio, se queda como estaba. No se tocó el payload del prompt.

## 2026-10-04 (XXVIII) — La voz del remix no era poco fiable

- **Qué dijo el usuario**: está haciendo un remix y le dice que la voz no es fiable.
- **Qué pasaba**: el remix `9ca181e9` (00:07, «Animales muertos», prompt Roland 808 / hardcore 4x4, 180 s) separó la voz y luego midió el tempo en la voz sola. Salió 522 bpm con confianza 0,027. Por debajo de 0,12 no se cuadra: es la protección del 2026-10-02, cuando una voz sola a 349 bpm se estiró a un cuarto de velocidad. El aviso era «El tempo de la voz no es fiable». La mezcla `(3)` se hizo sin tocar la voz. El tempo de verdad está en la batería original: 170 bpm. La base nueva va a 200 bpm. El detector devolvía 43 y 50 porque el refinado se quedaba en el compás y tiraba la corrección de octava.
- **Qué cambió**: el refinado del tempo parte del golpe ya elegido, no del pico del compás. El remix cuadra la voz con el tempo de la batería original, no con el de la voz sola. Si aun así el ajuste deformaría el audio, el texto dice que la voz entra a su tempo.
- **Prueba**: batería original 170,41 bpm (confianza 0,244); base nueva 200,5 bpm (confianza 0,687); voz sola 521 bpm (confianza 0,027, el plan sigue en null). Plan con la batería: ×1,1766 y 20 ms. Mezcla real `39628473-01-Animales muertos (4).mp3`, 4 897 772 bytes, 204,0 s, alineación aplicada, −14,01 LUFS. `py_compile` salida 0. No había trabajos en curso. El primer rearranque de la API no la levantó: `ensure` tomaba cualquier `main.py` y ComfyUI ya estaba. El filtro pasó a `backend\main.py` (también en `stop_local`, para no matar ComfyUI con SALIR). Segunda arrancada: API pid 2600, `GET /health` con motor alcanzable. Motor 8001 sigue en el pid 12024. No se generó otra canción en la GPU. No se clicó la ventana.
- **TESTER — PASS de medición y de mezcla, no de clic**.
- **REVIEWER — APPROVE con límites**: la voz sola sigue sin usarse para el tempo. El umbral 0,12 y el rango ×0,8–×1,25 no se han bajado.

## 2026-10-04 (XXIX) — El prompt llegaba y el motor le ponía 100 BPM

- **Qué dijo el usuario**: además, no hace caso al prompt.
- **Qué dicen los logs de las 00:07**: la tarea `c83776d1-cb95-48b6-8f4c-ec4eb26b6692` recibió la frase «MELODIAS CON SINTETIZADORES ROLAND 808, BATERIAS HARDCORE TECHNO 4X4», 180 s, `thinking=false` y los tres cot en false. El proceso viejo igual registró `use_cot_metas=True` y la fase 1 escribió `bpm: 100`, `keyscale: D major`, `timesignature: 4`. El DiT se quedó con la frase y, encima, con ese tempo y ese tono. La misma invención salió a las 23:45 con 300 BPM. El caption no se reescribió: `use_cot_caption` sí se quedó en false.
- **Causa**: el modelo de `release_task` no tenía el campo `use_cot_metas`, Pydantic tiraba el false, y `job_generation_setup` lo forzaba a encendido salvo en `sample_mode`.
- **Qué cambió**: el campo existe, el parser lo lee (si no viene, sigue en true) y el setup hace `use_cot_metas=(not sample_mode) and bool(getattr(req, "use_cot_metas", True))`. Musicia ya mandaba false. Con los tres cot y `thinking` en false el LM no corre, y un BPM vacío se escribe como `N/A`. La duración pedida sigue yendo en `audio_duration`.
- **Prueba**: el test `test_explicit_use_cot_metas_false_is_honored` está en `job_generation_setup_test.py` y la pasada anterior de `unittest acestep.api.job_generation_setup_test` dio 10 OK. No se relanzó en esta recarga para no meter un segundo torch junto al motor. Cola vacía. Se paró solo el motor viejo (pids 8716 y 12024). `ensure -Rearme` por Win32_Process.Create devolvió 0 (pid 24364). El motor nuevo es el par 4520/5348, arrancado a las 00:25:28, después del parche (00:19:46). `GET http://127.0.0.1:8001/health` 200. `models_initialized` sigue en false hasta la primera generación: es el arranque perezoso de siempre. La API sigue en el pid 2600. `GET /health` de Musicia: motor alcanzable. Cero trabajos. No se generó canción. No se clicó la ventana. El `(4).mp3` no se tocó: esa mezcla usa la base de 100 BPM.
- **TESTER — PASS de recarga y de código, no de escucha**.
- **REVIEWER — APPROVE con límites**: el turbo sigue con guidance 1.0, así que la frase condiciona poco. No se promete que el próximo hardcore suene exacto hasta que se oiga. El análisis de hardware (`job_analysis_runtime`) sigue con el cot de metas encendido; no es el camino del remix. El valor por defecto del motor, si el cliente no manda el campo, sigue siendo true.

## 2026-10-04 (XXX) — Revisión del remix (5), sin cambiar código

- **Qué pidió el usuario**: revisar el último remix.
- **Qué es**: job `7ed34870`, 00:34–00:38, prompt «MELODIAS PARECIDAS A LAS ORIGINALES PERO EN ESTILO TECHNO, BATERIAS HARDCORE TECHNO DE ROTTERDAM», 180 s, letra instrumental. Salida `39628473-01-Animales muertos (5).mp3` (240,02 s, 5 761 772 bytes, −14,19 LUFS, pico −0,92). Base `39628473-01-Animales muertos-base (3).mp3` (180,00 s). Tarea del motor `d0bddd7b-6b64-42a8-adb3-13019fc0f24e`.
- **Qué hizo el motor**: a las 00:37:28, `thinking=False`, `use_cot_caption=False`, `use_cot_language=False`, `use_cot_metas=False`, `use_lm=False`. El caption del DiT es la frase del usuario. Los metas son `bpm: N/A`, `timesignature: N/A`, `keyscale: N/A`, `duration: 180 seconds`. El turbo bajó `guidance_scale` de 7 a 1. La difusión tardó 5 s; antes, la primera petición cargó el DiT y el LM (00:34:58–00:37:28).
- **Qué suena, medido y no oído**: el pulso más fuerte de la base nueva está a 130 BPM (autocorrelación 0,66). La batería original sigue a 170,41 (confianza 0,244). `detect_groove` de la base nueva da 136,36 con confianza 0,113, por debajo de 0,12, y `plan_alignment` devuelve null. La UI dijo que estirar la voz la deformaría. La mezcla usa `amix=duration=longest`: la voz dura 4:00 y la base 3:00, así que el último minuto es la voz sola. No se tocó código.

## 2026-10-04 (XXXI) — Crear sí; el remix no oía el tema

- **Qué dijo el usuario**: el tema creado desde cero más o menos cumple. El remix no. Hay que solucionarlo.
- **Qué es cada uno**: `ZSFINORTIO.mp3` (00:46, 175 s) llevó la frase de techno oscuro, «160 BOM» y la letra «LA FORY / ZAFINORIO COMO MOLLY». `use_cot_metas=False` y el caption era esa frase. El remix `(5)` era text2music: el motor no oyó «Animales muertos», midió ~130 BPM y la voz se quedó a 170. El último minuto era la voz sola.
- **Qué cambió**: VOZ REAL + BASE NUEVA hace un cover del instrumental (`remix_cover_strength` 0.2, duración la de esa pista) y vuelve a mezclar la voz grabada. SOLO BASE NUEVA sigue siendo text2music con minutos. Un chequeo que no contesta a tiempo ya no se pinta como motor apagado. Si hay frases escritas, ESCRIBIRLA POR MÍ no llama al LM.
- **Prueba**: `build_payload` del cover devolvió `task_type=cover`, `audio_duration=-1`, `audio_cover_strength=0.2`, cot y thinking en false. `py_compile` salida 0. `npm run lint` y `npm run build` salida 0. Bundle `index-CKfsgNnq.js` (333.89 kB, gzip 103.84 kB). `GET /` lo sirve. API nueva en el puerto 8000; el motor sigue en el pid 5348 y `GET /health` lo ve. `POST /music/write_lyrics` con las dos frases devolvió `source=tus_frases` y el mismo texto. No había trabajos en curso. No se generó otro remix. No se clicó la ventana.
- **TESTER — PASS de payload, build y servicio, no de un remix nuevo**.
- **REVIEWER — APPROVE con límites**: el próximo VOZ REAL usa el tema como guía y el prompt como estilo. No se ha oído. La fuerza 0.2 es la de transferencia de estilo del motor. SOLO BASE NUEVA no oye el tema: es una base desde cero, como CREAR.

## 2026-10-04 (XXXII) — El remix enseña el avance, y el loop y el cover hacían otra cosa

- **Qué pidió el usuario**: el mismo detalle en vivo que al crear, pero en remix. Y que el resto de opciones haga lo que dice.
- **Avance**: versión, tramo, voz real y solo base usan el panel de CREAR (reloj, porcentaje real, eventos, COLA→SÍNTESIS→RENDER). Quitar voces y solo la voz enseñan el reloj y la fase de demucs: no hay porcentaje. Tempo, loop y ajustar enseñan el reloj y la fase real, sin un porcentaje inventado.
- **Loop**: «LOOP DE 4 COMPASES» cortaba `240/bpm` desde el segundo 0. A 170 bpm eso es un compás, y el mínimo de 2 s lo dejaba en 2 segundos. Ahora son `loop_bars` × `beats_per_bar` golpes (4 × 4) desde `phase_ms`. En la batería `39628473-01-Animales muertos-orig-base.mp3`: 170,41 bpm, golpe a 0,04 s, corte de 5,633 s. ffprobe del mp3 temporal: 5,633 s. El hash desde el golpe (`f3f1d6f511524652`) no es el de desde cero (`b26ba7297d5cd445`). El temporal se borró. La voz sola (521 bpm, confianza 0,028) queda por debajo de 0,12 y el loop se niega. No se escribió nada en la biblioteca.
- **Cover rechazado**: el remix `08b6ab6f` (00:58, hardtek / Rotterdam, voz real) separó la voz y a las 01:00:42 el motor contestó HTTP 400 en `/release_task`. El texto decía «no responde», así que la pantalla lo trataba como un corte. La causa es `validate_audio_path`: una ruta absoluta fuera de la carpeta temporal se rechaza. VERSIÓN, TRAMO y VOZ REAL mandaban esa ruta. Ahora se copia el audio a un temporal `musicia-src-*`, el validador lo acepta, y al terminar el trabajo se borra. Prueba: la batería absoluta → 400 `absolute audio file paths are not allowed`; la copia (5 762 237 bytes) → aceptada y borrada. Un 400 ya dice «rechazó», con el motivo.
- **Resto de opciones, leídas y ya honestas**: VERSIÓN es cover con fuerza. TRAMO es repaint (hasta vacío = el final). AJUSTAR es el panel DSP. VOZ REAL cubre el instrumental y devuelve la voz grabada, con la duración de la canción. SOLO BASE es text2music con minutos y letra. QUITAR VOCES devuelve la base; SOLO LA VOZ, la voz. MEDIO y DOBLE son ×0,5 y ×2 sin cambiar el tono. FORZAR TEMPO lleva al BPM escrito, también sin cambiar el tono. Se quitó la frase muerta que prometía minutos en VOZ REAL.
- **Prueba de servicio**: `py_compile` salida 0. `npm run lint` y `npm run build` salida 0. Bundle `index-Ba4nHLc1.js` (338.44 kB, gzip 104.99 kB). Cola sin trabajos activos (el `08b6ab6f` ya estaba en failed). Se paró solo la API vieja (pids 21088 y 11672). API nueva en el puerto 8000, pid 19860, arranque 01:23:18. `GET /health` motor alcanzable, turbo cargado. `GET /` sirve el bundle nuevo. `POST /audio/loop` sin segundos y con un nombre que no existe devuelve «Audio no encontrado». El motor sigue en el pid 5348. `logs/stop.flag` sigue (escrito a las 01:11, «salir»); SALIR no había parado los procesos. No se generó canción. No se clicó la ventana. No se tocaron ZSFINORTIO ni las mezclas (3) (4) (5).
- **TESTER — PASS de corte, de ruta y de servicio, no de escucha ni de clic**.
- **REVIEWER — APPROVE con límites**: el primer golpe medido no tiene por qué ser el 1 del compás; el corte es de 16 golpes de 4/4 desde ese golpe. El cover nuevo no se ha oído. La copia temporal vive hasta que el trabajo termina.

## 2026-10-04 (XXXIII) — Cierre de la app: el motor seguía

- **Qué dijo el usuario**: acaba de cerrar la app.
- **Qué había**: a las 01:25 no quedaba ventana ni Electron. `logs/stop.flag` seguía en «salir» desde las 01:11. La API del 01:23 seguía en el puerto 8000 (pids 11260 y 19860) y el motor en el 8001 (pids 4520 y 5348).
- **Qué se hizo**: `scripts/stop_local.ps1`. Paró la API y el motor. Un segundo después el 5348 aún escuchaba; al momento siguiente ya no. Puertos 8000 y 8001 libres. La marca de SALIR se dejó.
- **TESTER — PASS de parada**: no hay proceso `backend\main.py` ni `acestep.api_server`.
- **REVIEWER — APPROVE con límites**: abrir Musicia otra vez borra la marca y los arranca. La X de la ventana no es este cierre: esa solo esconde a la bandeja.

## 2026-10-04 (XXXIV) — La app se quedaba colgada al cerrar y al fallar un trabajo

- **Qué pidió el usuario**: se había quedado colgada y quería soluciones reales.
- **Qué había ya**: a la hora de mirarlo no quedaba Electron. Los puertos 8000 y 8001 estaban libres. `logs/stop.flag` seguía en «salir» desde las 01:11. El cuelgue está en el cierre y en la primera carga, no en un proceso vivo.
- **Cierre**: Salir de la bandeja abría un diálogo sobre la ventana escondida. Ese diálogo no se ve y el proceso se queda ahí. `app.quit` esperaba al renderer, y `window-all-closed` volvía a llamar a `quit` contra el hide de la X. Ahora Salir (botón y bandeja) no pregunta: tira la ventana, ejecuta `scripts/stop_local.ps1` con un tope de 20 s y sale con `app.exit`.
- **Parada**: el script hacía `Stop-Process` del padre y el hijo de uv seguía en el 8001. Ahora `taskkill /F /T` sobre python, pythonw y uv cuya línea es `backend\main.py`, `backend/main.py` o `acestep.api_server`, y espera hasta 12 s a que esos procesos y sus puertos desaparezcan. Un `main.py` suelto no entra.
- **Primera pantalla**: si la API no responde, la ventana enseña «ARRANCANDO EL MOTOR LOCAL…» y reintenta `/health` cada segundo. Una carga fallida ya no deja la ventana en blanco.
- **Reloj**: en CREAR y en REMIX un trabajo `failed` paraba el sondeo solo si el texto no parecía un corte. Si decía «no responde», el reloj seguía para siempre. Ahora un `failed` siempre termina y enseña el error. Un corte de red del sondeo, con el trabajo aún vivo, sigue reintentando.
- **Prueba**: `node --check` de `frontend/main.cjs` y `frontend/preload.cjs`, salida 0. El script de parada parsea con 0 errores. Ejecutado con todo ya parado: «[Musicia API] no estaba corriendo», «[ACE-Step] no estaba corriendo», «[Musicia] puertos libres», salida 0. La marca sigue siendo la de las 01:11. Puertos libres después. No había ComfyUI. `npm run lint` salida 0. `npm run build` salida 0. Bundle `index-DJsfXUjm.js` (338.27 kB, gzip 104.92 kB). En ese bundle no está el texto «Sigue en el motor». No se arrancó la app. No se generó canción. No se clicó la ventana. No se tocaron ZSFINORTIO ni las mezclas.
- **TESTER — PASS de cierre, de parada en seco y de build. No de un clic.**
- **REVIEWER — APPROVE con límites**: hace falta abrir Musicia para verlo. Esa apertura borra la marca y arranca API y motor. La X sigue escondiendo a la bandeja. El cover con la copia temporal sigue sin oírse.

## 2026-10-04 (XXXV) — La voz larga se arregla en trozos

- **Qué pidió el usuario**: usar la voz de una canción aunque la base nueva sea más larga. El sistema debe cortarla en trozos y colocarlos, sin que él marque cada uno.
- **Qué no se hizo**: devolver los minutos al cover de VOZ REAL. El motor tira esa duración y fija la del audio. Estirar la voz queda fuera.
- **Qué hace MEZCLA**: si la voz dura menos del 85 % de la base, la corta por silencios y, si una frase ocupa más de un compás, la parte en golpes. Los trozos se reparten desde el primer golpe hasta el final. No hay atempo. Si las dos duran parecido, la mezcla de siempre no se parte.
- **Prueba**: el tema subido contra sí mismo no arregla. Un corte de 12 s sobre una base de 40 s, los dos sacados de `uploads/39628473-01-Animales muertos.mp3`, dio 9 trozos. El primero entra a 0,04 s y el último a 39,00 s. El MP3 dura 40,000 s, −13,96 LUFS, pico −1,0. El original no cambió de fecha y el archivo de prueba se borró. `py_compile` salida 0. `npm run lint` y `npm run build` salida 0. Bundle `index-BqqXHVz2.js`. No se abrió la ventana. No se generó canción.
- **TESTER — PASS de corte y de duración. No de un clic.**
- **REVIEWER — APPROVE con límites**: hace falta la base larga (SOLO BASE NUEVA, con minutos) y la voz sacada (SOLO LA VOZ), y mezclarlas. La pantalla lo anuncia antes de MEZCLAR. Esa frase no se ha visto en la ventana.

## 2026-10-04 (XXXVI) — Las opciones que no hacían lo que decían

- **Qué pidió el usuario**: continuar con el resto de opciones.
- **MEJORAR PROMPT**: ya no pega otro género. La frase se queda. Si hay un BPM elegido y no está escrito, se añade al final. «rotterdam hardcore, bombo distorsionado, techno oscuro» con 175 bpm salió igual más «, 175 bpm». Sin BPM, el texto no cambia.
- **BIBLIOTECA · VERSIÓN**: el BPM medido se enseña y no se envía. Un prompt vacío no inventa una frase.
- **FUNDIR**: solo iguala el tempo si el factor cabe entre 0,8 y 1,25 y el golpe es fiable. Un metrónomo de 160 contra uno de 100 no se estiró. Uno de 120 sí. La pantalla lo dice.
- **VOZ REAL**: sin minutos, o con menos de los que dura la canción, sigue el cover y dura lo que dura el tema. Con bastantes más minutos (300 s sobre 240 s) la base nueva no oye el tema y la voz se reparte en trozos. Esa generación no se lanzó en la GPU.
- **Prueba**: `py_compile` salida 0. `npm run lint` y `npm run build` salida 0. Bundle `index-D-nHuYoJ.js`. No se abrió la ventana. No se generó canción. El tema subido no se modificó.
- **TESTER — PASS de prompt, de fundido y de la decisión de alargar. No de un clic ni de una cover.**
- **REVIEWER — APPROVE con límites**: en CREAR, el desplegable de género sigue poniéndose delante de la frase al generar. El BPM de CREAR sigue acabando en 140. La vía larga de VOZ REAL no se ha oído.

## 2026-10-04 (XXXVII) — La X no cierra. Solo SALIR. Revisión de opciones

- **Qué pidió el usuario**: deshabilitar y eliminar la X; que solo funcione SALIR. Revisar que todas las opciones respondan.
- **Cierre**: la ventana nace con `closable: false`. Windows deja la X gris y Alt+F4 no cierra. Si aun así llega un `close`, se ignora y la ventana se queda. Ya no se esconde en la bandeja. SALIR (botón y menú de bandeja) sigue apagando motor y API sin diálogo. Minimizar sigue disponible.
- **Revisión de opciones**: cada botón de CREAR, SUBIR, MEZCLA y BIBLIOTECA llama a un endpoint real. El fallo encontrado estaba en SUBIR: re-crear y crear base mandaban el BPM medido, y un prompt vacío inventaba una frase. Ahora el prompt vacío se para, el BPM medido no se envía, la re-creación es un cover sin duración y crear base usa la duración del audio (tope el máximo del motor). El rótulo «Alargar o rehacer un tramo» pasó a «Rehacer un tramo»: ese camino regenera un trozo y el resto se queda.
- **Siguen cableadas**: GENERAR, VARIAR, MEJORAR, asistente y letra en CREAR. En el remixer: VERSIÓN, TRAMO, AJUSTAR, VOZ REAL, SOLO BASE NUEVA, QUITAR VOCES, SOLO LA VOZ, LOOP, MEDIO TIEMPO, DOBLE TIEMPO y FORZAR TEMPO. En MEZCLA: MEZCLAR, EXTRAER VOCES y FUNDIR. En BIBLIOTECA: REMIX, VERSIÓN, AJUSTES, NOMBRE, BAJAR y BORRAR.
- **Prueba**: `node --check` de `frontend/main.cjs` salida 0. `npm run lint` salida 0. `npm run build` salida 0. Bundle `index-fcDRqhJk.js`. El JS servido contiene «Rehacer un tramo» y «Escribe un prompt antes de la versión». No se abrió la ventana. No se generó canción. No se arrancaron los servicios. `logs/stop.flag` no se tocó.
- **TESTER — PASS de sintaxis, lint y build. No de un clic en la X ni en las opciones.**
- **REVIEWER — APPROVE con límites**: la X sigue dibujada por Windows, en gris, y no hace nada. Quitarla del marco pediría una barra propia. En CREAR el género sigue delante de la frase al generar y el BPM del desplegable acaba en 140. Nada de esto se ha pulsado en la ventana.

## 2026-10-04 (XXXVIII) — El texto «timeout exceeded» no se enseña

- **Qué pidió el usuario**: desaparece el mensaje de timeout exceeded.
- **Qué era**: axios, cuando su reloj acaba, dice `timeout of 30000ms exceeded`. Ese texto llegaba tal cual a la pantalla. El envío de una canción cortaba a los 30 s y el motor espera hasta 60 s. La consulta de modelos usaba esos 60 s. Si la ventana no llegaba a cargar, Chromium dejaba su página de «took too long».
- **Qué cambió**: ese corte se traduce y no se pinta en biblioteca, subidas ni mezcla, ni durante el sondeo de un trabajo. El envío espera 90 s. Modelos usa el tope corto del chequeo (3 s en el servidor, 8 s en la ventana). Una carga fallida de la ventana enseña «ARRANCANDO EL MOTOR LOCAL…». Un error HTTP de verdad sigue viéndose.
- **Prueba**: `node --check` de `frontend/main.cjs` salida 0. `py_compile` de `music_service.py` salida 0. El texto `timeout of 30000ms exceeded` cuenta como corte; un rechazo HTTP 400 no. `npm run lint` salida 0. `npm run build` salida 0. Bundle `index-Ctq9_WJE.js`. No se abrió la ventana. No se generó canción. La marca de SALIR sigue.
- **TESTER — PASS de la regla del corte, de sintaxis, de lint y de build. No de un clic.**
- **REVIEWER — APPROVE con límites**: hace falta abrir Musicia para dejar de ver el texto viejo. El proceso que estaba en marcha ya se cerró con SALIR, así que el arreglo de modelos entra al abrir. No se ha vuelto a ver la pantalla.

## 2026-10-04 (XXXIX) — Los cuatro remixes de «Animales muertos» terminaron; dos no podían cumplir la frase

Revisión pedida por el usuario («revisa los últimos logs de remixes porque no acabé de ver que haga lo que pido»). Sin cambio de código. Sin canción nueva. El audio no se ha escuchado: la prueba es el log, ffprobe y el hash.

### Sesión y archivos que hay que dejar quietos

- API pid 20720 arrancó 22:53:30. Motor ACE-Step pid 22604 en :8001, modelo `acestep-v15-turbo`, FlashAttention no disponible (SDPA).
- Original intacto: `backend/outputs/uploads/39628473-01-Animales muertos.mp3`. ffprobe 2026-10-04: 81,400 s, 2.609.152 bytes, 256 kbps, SHA256 empieza `1910ABBA424AAC34`.
- Mezcla que queda: `backend/outputs/Animales muertos-VERSION1.mp3`. 180,000 s, 4.321.196 bytes, 192 kbps, SHA256 empieza `2C7EF8FA2EDC26CF`. Es el remix 1 (renombrado 23:06:12). Su ficha guarda el prompt Roland. No pisarla.
- No borrar `logs/stop.flag` si existe, ni regenerar estos temas, ni tocar ComfyUI.

### Los cuatro trabajos (todos llegaron a −14 LUFS)

El mismo tamaño de 2.880.812 bytes en las cuatro bases es 180,000 s a 128 kbps. No es el mismo audio: cuatro SHA256 distintos. Latentes del DiT `[1, 4500, 64]` = 180 s (4500 × 1920 / 48000). En los cuatro: thinking=False, use_cot_caption/language/metas=False, letras `[instrumental]`, idioma `es`, metas bpm/timesignature/keyscale = N/A. El turbo forzó guidance_scale 7,0 → 1,0 (el prompt de estilo pesa poco). Nadie envió un BPM numérico.

1. `bf6a2535` 22:57:18–23:01:07. Prompt exacto: `BATERIAS CONTUDENTES DE TECHNO HARDCORE, MELODIAS SIMILARES A LA ORIGINAL CON SINTETIZADORES ROLAND`. Tarea motor `252c3436-cf08-4cd6-a8e2-4701df37ccb4`, dur=180,0 s, text2music («Fill the audio semantic mask»). Separación cuda, VRAM libre 7395 MB. La primera generación tardó ~3 min porque cargó el DiT y el LM 5Hz (tokenizer 35,76 s); la difusión en sí fue 5,07 s. Base `f07bcbff-a6b7-00c6-a423-a19fb800a2f1.mp3` (SHA256 `FD2224EDB30BB192`). Log: «No oye el tema: es una pieza nueva». Voz 81 s en 20 trozos, primero a 0,00 s, último a 178,00 s. Loudness previo: input_i −13,3, tp −0,88, lra 7,4. «Melodías similares a la original» solo fue texto: este camino no manda el audio.

2. `90580f8c` 23:03:00–23:05:54. Prompt exacto: `BATERIAS CONTUDENTES DE TECHNO HARDCORE, SIN MELODIAS`. Tarea `55fa3164-a515-4085-bf5a-6e7e2776b103`, task_type=cover, dur=−1 en el envío de Musicia, fuerza `remix_cover_strength` 0,2. Separación cpu (VRAM libre 2308 MB: el turbo seguía residente; no es un fallo). El motor procesó audio de origen, puso el caption tal cual y fijó la duración al wave cargado: el texto al DiT dice `duration: 180 seconds`. Difusión 3,04 s. Base `b5f18397-adea-c1cb-02a9-d8054f303091.mp3` (SHA256 `F98223AE5BC7F761`), 180,000 s exactos. Log de la app: «Esos minutos no acortan el tema: el cover dura lo que dura la canción» y luego «La voz entra a su tempo: estirarla hasta la base nueva la deformaría». No hubo troceo (el arreglo solo sale si la voz es claramente más corta que la base). Loudness previo: input_i −13,74, tp −1,06, lra 8,6. Mezcla escrita `39628473-01-Animales muertos (2).mp3`, borrada por el usuario 23:07:06.

3. `a8b3b515` 23:08:12–23:09:52. Prompt exacto: `TECHNO HARDBOUNCE, OSCURO, CONTUNDENTE`. Tarea `d14b3c41-be46-4e77-b455-f79c204f67e1`, dur=180,0 s, text2music, sin audio de origen. Separación cpu, VRAM libre 2014 MB. Difusión 3,00 s. Base `fd376f7a-e362-19c1-e2e0-8f2a13d5d3e6.mp3` (SHA256 `3356DBF608C1DFAD`). Voz 81 s, 20 trozos, 0,00–178,00 s. Loudness previo: input_i −13,37, tp −0,92, lra 8,0. El usuario borró la mezcla 23:10:59 y los stems justo después.

4. `9f683c71` 23:11:55–23:13:36. Prompt exacto: `BATERIAS 4X4 ESTILO TECHNO HARD HOUSE, OSCURO`. Tarea `af00dece-3d4c-40a3-ade6-64b251ee6d5c`, dur=180,0 s, text2music. Separación cpu, VRAM libre 2061 MB. Difusión 3,07 s. Base `83665174-b90f-98c5-aaab-c36ad86b3a4f.mp3` (SHA256 `23B230387F4F74C8`). Misma voz en 20 trozos. Loudness previo: input_i −13,46, tp −0,66, lra 6,8. Borrada 23:14:08. «4x4» no llevó un BPM.

Las cuatro bases siguen en `vendor/ACE-Step-1.5/.cache/acestep/tmp/api_audio/` con esos nombres. Las mezclas 2, 3 y 4 no están en la biblioteca. Los stems `*-base`, `*-orig-base` y `*-orig-voces` de esta noche se borraron.

### Por qué el 2 no hizo lo pedido

`_find_audio` (`backend/main.py`) mira `outputs/` antes que `uploads/`. El remix 1 escribió la mezcla en `outputs/39628473-01-Animales muertos.mp3` (180 s), el mismo nombre que la subida. A las 23:03 el remix 2 separó ESE archivo. Con una fuente de ~180 s, 3 minutos no superan `fuente / 0,85` (~211 s), así que `voz_real_quiere_mas_larga` es falsa, se entra al cover y `duration_seconds` se manda como None (`audio_duration=-1`). El motor (`acestep/inference.py`, cover/repaint) ignora esa duración y usa el wave: 180 s. El cover a fuerza 0,2 oye el instrumental de la mezcla anterior, que ya trae melodía; «SIN MELODIAS» fue solo el caption. A las 23:06:12 el usuario renombró la mezcla del 1 a VERSION1; el 3 y el 4, al no encontrar ya ese nombre en `outputs/`, volvieron a la subida de 81,4 s y por eso sí alargaron.

### Qué queda decidido y qué no

- Hecho de esta nota: diagnóstico. No hay parche. No hay PASS de un arreglo porque no se tocó código.
- Pendiente, solo si el usuario lo pide: que el remix use el archivo elegido (la subida no debe perder contra una mezcla homónima en `outputs/`) y que «melodías como la original» / «sin melodías» manden el audio que corresponde. Hasta entonces no se cambia `voz_real_quiere_mas_larga`, el guardia 0,8–1,25, `MIN_GROOVE_CONFIDENCE` 0,12, ni se reactivan thinking/cot ni el caption del LM.
- Los tres primeros caminos largos cumplieron el troceo de la voz (20 piezas, sin atempo). El cover del 2 no trocea: mezcla la voz a su tempo.

## 2026-10-05 (XL) - El remix usa el archivo elegido y la fuerza oye el prompt

Lo que pidió el usuario: «acabemos» lo pendiente de la nota XXXIX (él lo llamó «arreglalo todo»).

### 1. La UI dice de qué lista viene (`source_kind`)

- `_find_audio(name, kind)` (`backend/main.py`): con `kind="upload"` mira `uploads/` primero, con `"output"` mira `outputs/` primero; la otra carpeta es reserva. Sin kind, orden viejo (outputs primero). Kind inválido = 400.
- Campo `source_kind` nuevo en: `AiRemixRequest`, `MusicGenRequest` (origen del cover/repaint), `RemixRequest` (DSP), `TempoRequest`, `LoopRequest`, `SeparateRequest`, `RemixPromptRequest`, `RenameRequest`.
- `/audio/remix_prompt` resolvía al revés que el resto (uploads primero): desde BIBLIOTECA sugería el prompt analizando la subida mientras el remix usaba la mezcla. Ahora usa `_find_audio` con el kind.
- `/audio/remix` (DSP) duplicaba el bucle de resolución: ahora usa `_find_audio`.
- Frontend: `RemixActions` y `RemixIAPanel` aceptan `sourceKind`; BIBLIOTECA pasa `"output"`, SUBIR pasa `"upload"`. `renameAudio` también lo manda. MEZCLA no se toca: su desplegable ya desambigua a favor de bib, igual que el backend por defecto.
- El job del remix guarda `source_dir` (uploads/outputs): la próxima revisión de logs lo ve directo.
- No se cambia `voz_real_quiere_mas_larga`, el guardia 0,8–1,25 ni `MIN_GROOVE_CONFIDENCE`.

### 2. La fuerza del cover oye «sin melodías» / «como la original»

- Corrección a mi pregunta previa (la dije al revés): verificado en el motor (`acestep/models/*/modeling_*.py`, `cover_steps = int(num_steps * audio_cover_strength)`, docs: «higher = closer to reference, lower = more freedom»). Fuerza ALTA = se parece al original; BAJA = manda el caption.
- `remix_cover_strength_for(prompt)` (`backend/main.py`, función pura): «sin melod(ía/s)», «no melody», «solo batería/ritmo/percusión» → `remix_cover_strength_no_melody` (0,1, config); «como/similar/misma/igual/fiel … original» (singular y plural) → `remix_cover_strength_like_original` (0,5, config); resto → 0,2 de siempre. Los dos valores nuevos están en `config.py` y `config.example.json`.
- El paso elegido se enseña en la ventana («fuerza 0,10 (manda el prompt)»): lo que el usuario no veía en la XXXIX ahora se ve.
- Conflicto honesto: «melodías como la original» + más minutos cae en text2music (no oye el tema, imposible cumplirlo) y el paso lo dice antes de generar.
- El 0,1 y el 0,5 NO están medidos en GPU: el job registra la fuerza usada para ajustarlos con datos reales, no de oído.

### Prueba (sin GPU, sin ventana, sin tocar audios)

- Script temporal (borrado tras pasar): homónimos `tema.mp3` en outputs (contenido MEZCLA) y uploads (contenido SUBIDA). 11/11 PASS: upload→SUBIDA, output→MEZCLA, sin kind→MEZCLA (orden viejo), recurso cruzado en ambos sentidos, kind inválido→400, ausente→404, «SIN MELODIAS»→0,1, «MELODIAS SIMILARES A LA ORIGINAL»→0,5+aviso (el plural falló primero y se añadió), neutro→0,2, «solo bateria/no melody»→0,1.
- `py_compile` de `main.py` y `config.py` salida 0. Config real cargada: 0,1 / 0,5 / 0,2. Rutas `/audio/remix/ai` registradas; modelos pydantic aceptan `source_kind`.
- `npm run lint` salida 0. `npm run build` salida 0. Bundle `index-kopcdQs6.js` (340,31 kB, gzip 105,48 kB) con `source_kind` dentro.
- No se abrió la ventana, no se generó canción, no se arrancaron servicios. ZSFINORTIO, las mezclas y VERSION1 intactos.
- **TESTER - PASS de resolución, de intención, de sintaxis, de lint y de build. No de un clic ni de una cover (falta GPU).**
- **REVIEWER - APPROVE con límites**: el 0,1/0,5 hay que oírlos en un remix real; el primer remix con «sin melodías» dirá si 0,1 suelta demasiado el groove. `GET /audio/peaks` y `/audio/groove` siguen resolviendo outputs-primero (solo vistas; la onda podría dibujar el homónimo equivocado). Pendiente menor anotado, no bloquea.

## 2026-10-05 (XLI) - Tests mínimos, T7 anotada, letra en biblioteca y % global

Lo que pidió el usuario: «HAZLO TODO» sobre el resumen de mejoras (tests+spec, punto 10, punto 3).

### 1. Tests que corren sin GPU ni ventana (T6, parcial)

- `backend/test_remix_logic.py` (unittest de la stdlib: cero paquetes nuevos, la prohibición de instalar lo exigía): 16 tests de `_find_audio` (orden por kind, recurso cruzado, 400, 404), `remix_cover_strength_for` (baja/alta/neutra/vacía) y `voz_real_quiere_mas_larga`.
- `python -m unittest backend.test_remix_logic`: OK en Python 3.11 del sistema y en `backend/venv`, 0,03–0,07 s.
- Falta de T6: `build_payload`, cuadre y `verificar_audio`. Anotado en `spec/03-PENDIENTES.md`.
- T7 registrada como cerrada (el fail-fast con 503 existe en generate y remix/ai; se citaba en código sin estar en el spec). T3 remedida: bundle 340,31 kB (+7 kB); umbral de partir en 400 kB.

### 2. «Otra versión» ya no pierde la letra (punto 10, parcial)

- `RemixIAPanel`: props `initialPrompt`, `initialLyrics`, `showLyrics`. BIBLIOTECA los rellena desde la ficha (`item.prompt`, `item.lyrics`) y enseña el campo de letra aunque el kind sea `musica`. `runIAFromLibrary` ya mandaba la letra si venía: con letra canta, vacía es instrumental.
- Límite honesto: la ficha no guarda idioma ni descriptores de voz, así que la voz exacta no se restaura (el doc pedía los 4 selectores). Sin ficha, el campo sale vacío para pegar. Los botones VERSO/ESTRIBILLO/PUENTE/FINAL del doc siguen sin hacerse.

### 3. El % viaja contigo (punto 3)

- El header ya sondeaba `/music/jobs` y pintaba la fase; la API ya daba `progress_ratio`, `prompt` y `output_name`. Solo faltaba pintarlo: ahora enseña nombre (o 40 letras del prompt), % y fase en una línea (`App.jsx`).
- No se tocó el sondeo (3 s) ni la cola.

### Prueba

- `py_compile` salida 0. unittest 16/16 OK (dos intérpretes). `npm run lint` salida 0 (un error mío de paréntesis en el primer intento, corregido y re-verificado). `npm run build` salida 0. Bundle `index-CYhHOPH7.js` (340,59 kB) con `con letra canta` y `showLyrics` dentro.
- No se abrió la ventana, no se generó canción, no se arrancaron servicios. Audios y mezclas intactos.
- **TESTER - PASS de tests, sintaxis, lint y build. No de un clic (header), ni de pegar letra, ni de GPU.**
- **REVIEWER - APPROVE con límites**: el header con % y la letra pre-rellenada no se han visto en la ventana; el primer «otra versión» de una cantada dirá si el cover canta afinado con esa letra.

## 2026-10-05 (XLII) - Auditoría a fondo y cuatro lotes (obediencia, bugs, canto, limpieza)

Lo que pidió el usuario, en mayúsculas: revisar A FONDO mejoras, obediencia al prompt y UI posible. Dos agentes en paralelo (34 endpoints backend, 15 pantallas frontend) + traza propia extremo a extremo. De ~40 hallazgos verifiqué los que pesan; uno era falso (`/audio/process` SÍ se usa en AJUSTES).

### Lote A — obediencia y textos que mentían

- `thinking: True` → `False` en `config.py`: el default mentía, `build_payload` lo fija en `False` (decisión 2026-10-03).
- `mood` fuera de `EnhancePromptRequest` y de `enhance_prompt` (nadie lo mandaba, el backend lo tiraba). Pydantic ignora extras: clientes viejos no rompen.
- `isTransportBlip` reconoce «no contesta» (`api.js`): `describeError` dice «La API no contesta.» y ese caso no contaba como corte.
- Textos: «hasta 2 min» → «hasta 5 min» (el timeout real, `api.js:47`); `VOCALES: AUTO (instrumental)` → «AUTO · el motor elige la voz»; `TIPO` sin jerga; `GÉNERO` vocal → `VOZ` (chocaba con género musical); hints y placeholder con `[Verse]/[Chorus]` (lo que `vocal.js` manda de verdad).
- `vocalSummary` ya no cuenta el idioma (siempre 'es', impedía ver AUTO); `resetVocal` también resetea el idioma.
- MEZCLA enseña `dB`; borrar subida pide SÍ/NO como en biblioteca; EXTRAER se deshabilita sin motor de separación.

### Lote B — bugs funcionales

- Asistente↔CREAR: `Orquestal/Acústico/Electrónica`, `Alegre/Épico/Oscuro/Chill` y BPM 100 del wizard caían al vacío (tags sin pareja). Añadidos a `Composer.jsx` con los mismos tags y textos del wizard.
- JobsPanel: el play de fila solo cambiaba el icono. Ahora suena inline (`<audio>` bajo la fila).
- Waveform: al cambiar de pista con `key={fileName}` (como ya hacía `RemixPanel`); el reset dentro del efecto lo vetó el linter y se quitó.
- MEZCLA con `source_kind`: `base_kind/vocal_kind` en `MixRequest`/`MixPlanRequest`, `track_kinds` en crossfade (400 si no cuadra en número), `kindOf` desde las listas (`bib→output`). `_mix_alignment` acepta kinds.

### Lote D — la base nueva canta (cambio de comportamiento, aprobado)

- Regla: **si hay letra cantable (≥8 palabras), la base nueva la canta y la voz original NO se superpone** (se entrega separada; dos voces a la vez no es un bootleg). Vale en cover y en camino largo. El paso lo anuncia; `result.sung_base=True`, `with_vocals=False`.
- `voz_prompt` tiene campo LETRA (estructurada con `structureLyric` antes de enviar) y lo dice en su hint. Sin letra, todo igual que antes.

### Lote C — limpieza

- Fuera `POST /tts/generate`, `GET /voices`, `TTSRequest`, import, `tts_service.py` (borrado), `edge-tts` de requirements. Era red: anti LOCAL-FIRST y sin UI desde el 2026-10-02.
- `Mixer.jsx`/`Sequencer.jsx` SE QUEDAN en disco (el 05-MEJORAS lo prohíbe expreso y el lote aprobado decía «fuera del build»): verificado que el bundle no los trae (0/3 marcadores).
- README sin pestaña VOZ ni TTS; `knowledge.md`, `AGENTS.md`, `spec/01/02/04` sin edge-tts; docstring de cabecera de `main.py` corregido (`/api/info`, sin TTS).

### Prueba

- `py_compile` salida 0. unittest 16/16 OK (el import ya demuestra que `main.py` vive sin `tts_service`).
- `npm run lint` salida 0 (dos tropiezos míos corregidos: paréntesis JSX y `setState` en efecto → `key=`; más un `useCallback` por `exhaustive-deps`).
- `npm run build` salida 0. Bundle `index-GG6banhc.js` (342,47 kB, gzip 106,31 kB): `base_kind`, `track_kinds`, `hasta 5 min`, `Orquestal`, `source_kind` dentro. TTS 0/4 restos en `main.py`.
- No se abrió la ventana, no se generó canción, no se arrancaron servicios. Audios y mezclas intactos.
- **TESTER - PASS de tests, sintaxis, lint y build. No de clics (play inline, letra que canta, kinds de mezcla), ni de GPU (base que canta sin oír).**
- **REVIEWER - APPROVE con límites**: el primer remix con letra dirá si el cover canta afinado y si no duplicar la voz era lo correcto; el primer cruce bib/sub en MEZCLA dirá si `kindOf` acierta. Queda fuera de los lotes: `time_signature` (sigue en [A4]), `audio_format=wav` (biblioteca ciega + MIME fijo), `fade_seconds` sin validar, `pollUntilDone` infinito con red caída (diseño: el corte no para el sondeo).

## 2026-10-05 (XLIII) - Menú ACCIONES, CREAR sin SESIÓN, compás, y escucha real con GPU

Lo que pidió el usuario: «realizalas» (las valiosas: menú, SESIÓN, compás + escucha).

### Código (sin GPU)

- **BIBLIOTECA con menú ACCIONES** (punto 4): una palabra por acción (OTRA VERSIÓN, BOOTLEG, AJUSTES, NOMBRE, BAJAR, BORRAR). Reutiliza los paneles y el SÍ/NO de borrado. `task_type` crudo traducido (`cover→versión…`). BAJAR usa `api.audioUrl` como el resto.
- **CREAR sin SESIÓN** (punto 1): fuera la columna, `history`, `remember`, `clearHistory`, `historyKey`. Una columna. `pollUntilDone(jobId)` sin `meta`; `launchGeneration` devuelve solo `{created}`.
- **[A4] Compás**: selector COMPÁS (Auto/4-4/3-4/6-8) en CREAR, viaja en `time_signature` al motor (ya lo aceptaba) y a la ficha (`job` + `_write_ficha`). Anotada como hecha en `03-PENDIENTES`.
- Prueba: `py_compile` 0, unittest 16/16, lint 0 (dos avisos míos corregidos: `meta` sin uso, `key=` en onda, `kindOf` en deps), build 0 (`index-sAn-_MQR.js`, 341,02 kB).

### Escucha real (con GPU, servicios arriba)

El motor ya estaba corriendo (pid 21256, no tocado); solo se arrancó la API con `scripts/start_local.ps1`. Fuente de las tres pruebas: la subida `39628473-01-Animales muertos.mp3` (solo lectura; intacta). Todo queda en BIBLIOTECA para oír, con nombre `prueba-auditoria-*`.

1. **Remix SIN MELODIAS** (job `7d4c5de7`, 297 s): `source_dir: uploads` (el kind funciona), log «fuerza 0.10 (manda el prompt)», mezcla+base+voces de ~81 s, -14,03 LUFS. `prueba-auditoria-sin-melodias.mp3`.
2. **Repaint tramo 10-20 s** (job `b0283cb0`, 26 s): `prueba-auditoria-tramo.mp3`, 81 s, ficha `task_type: repaint`, duración 81,4.
3. **Base que canta** (job `997de831`, 612 s): el paso «la voz original se guarda aparte, no se mezcla encima» salió; `prueba-auditoria-canta-base.mp3` 81 s + `…-orig-voces.mp3`. El sondeo se cortó al final pero el servidor terminó `succeeded` (verificado por `/music/jobs` + fichero en disco).
- Sin oír (sin oídos aquí): si la base de (1) trae melodía, 0,1 es poco; si (3) desafina o duplica voz, el lote D se revisa. El usuario escucha y sentencia.
- Servicios: se dejan CORRIENDO (motor+API) para oír ya. SALIR al terminar.
- **TESTER - PASS de código (tests/lint/build) + PASS de generación real (3 MP3, duración > 0, -14 LUFS). No de oído.**
- **REVIEWER - APPROVE con límites**: falta el oído del usuario en las tres piezas; el 0,5 «como la original» sigue sin probarse en GPU.

## 2026-10-05 (XLIV) - Confirmación cableada: bundle servido + API en vivo
El usuario no ha abierto la app y pide confirmación de que la UI funciona y las mejoras están cableadas. Sin clicar (no hay ojos aquí): verificación estática + API viva, sin GPU y sin tocar sus archivos.

- Bundle servido `index-sAn-_MQR.js` trae: ACCIONES, OTRA VERSIÓN, BOOTLEG, COMPÁS, LETRA, SÍ/BORRAR, `base_kind`, `track_kinds`, `showLyrics` (7/7 True).
- `build_payload(time_signature='3/4')` → `'3/4'` al motor; default `''`. A4 viaja de verdad.
- `POST /audio/crossfade` con `track_kinds` desparejado → 400 en vivo.
- `POST /audio/mix/plan` con kinds sobre piezas de prueba → 200 con explicación (DSP puro, sin GPU).
- Límite honesto: el clic píxel a píxel (ver el % en el header, abrir ACCIONES, pegar letra) lo tiene que hacer un humano. Todo lo automatizable, verificado.

## 2026-10-05 (XLV) - Obediencia al prompt: glosa inglesa + FUERZA manual

Lo que pidió el usuario: que obedezca al prompt y saque remixes buenos y cuadrados. La funcionalidad vale; el motor obedecía poco.

### Lo que el motor NO deja (verificado en su código, no adivinanza)

- `guidance_scale` forzado a 1,0 en turbo (CFG destilado; `generate_music.py:312`, dos `modeling_*_turbo.py`). Más obediencia por guidance: imposible en este modelo.
- Prompt negativo solo LM (`lm_negative_prompt`); con CFG=1,0 es inerte en turbo.
- `thinking` encendido obedecería MENOS (el 03-10 los códigos del LM mandaron sobre la frase).

### Lo implementado

- **`frontend/src/prompt_gloss.js`**: glosario ES→EN (~40 entradas). `glossPrompt` añade los gemelos ingleses entre paréntesis SIN tocar tu frase; si no reconoce nada o ya está en inglés, la deja igual. Se aplica al enviar en CREAR (también se ve en VER LO QUE SE ENVÍA), versión, tramo, voz+base, base nueva, biblioteca, SUBIR y MEJORAR. Ejemplo real: `BATERIAS CONTUNDENTES DE TECHNO HARDCORE, SIN MELODIAS (drums, hard-hitting, melody, without melody)`.
- **FUERZA manual en VOZ REAL**: botón AUTO/MANUAL + slider. En AUTO deduce del prompt (lo de XL); en MANUAL manda `cover_strength` (nuevo campo en `AiRemixRequest`, validado 0-1, paso visible «Fuerza manual X»). La detección de intención no se rompe con la glosa («sin melod» sigue matcheando).
- La letra (idioma cantado) NO se glosa: se canta tal cual.

### Prueba

- node directo a `glossPrompt`: ES→glosado, EN intacto, vacío intacto, sin duplicados.
- `py_compile` 0, unittest 16/16, modelo acepta `cover_strength`, lint 0, build 0 (`index-BeMZTHAf.js`, 343,39 kB) con `four-on-the-floor`, `MANUAL` y `cover_strength` dentro.
- **TESTER - PASS de glosa, modelo, lint y build. No de GPU (efecto real en el oído).**
- **REVIEWER - APPROVE con límites**: la glosa puede meter ruido («melody» junto a «without melody»); si al oír confunde, se quita la entrada. La FUERZA manual y la glosa se juzgan oyendo el próximo remix. Criterio para el usuario: mismo prompt de antes, ¿obedece más y suena cuadrado?

## 2026-10-05 (XLVI) — El remix obedece: glosa sin contradicciones + sft con CFG de verdad

Lo que pidió el usuario: «revisa remix porque no obedece al prompt». Confirmó
el síntoma («suena a otra cosa, no cumple el prompt»), eligió **Rápido + SFT**
y añadió la condición: **«pero no quiero hardcoding»**.

### Diagnóstico (logs de los remixes de las 19:27–19:42)

La frase SÍ llegaba intacta al DiT (caption = prompt del usuario + glosa,
`thinking=False` y los tres cot en `false`). Tres causas reales:

1. **La glosa se contradecía (bug nuestro)**: «sin melodías» se glosaba como
   `(drums, melody, without melody)` — el motor recibía la orden de meter
   melodía y de quitarla a la vez. En `prompt_gloss.js` la regla `melodías`
   se disparaba dentro de «sin». El reviewer lo había avisado en XLV.
2. **Glosa rota en silencio**: `sintetizadores?` nunca coincidía con
   «sintetizador» (el `?` solo cubre la «s»), así que «melodias con
   sintetizador roland» glosaba solo `melody`. Preexistente, no se había visto.
3. **El turbo no puede obedecer (límite del modelo, spec [M1])**: el motor
   fuerza `guidance 7.0 → 1.0` (CFG horneado en la destilación) — el caption
   pesa poco. Los metas iban `bpm: N/A` y la glosa no conocía gabber/hardstyle.

### Solución, sin un solo literal fuera de config

- `config.py` + `config.example.json`: `allowed_models` = (turbo, sft),
  `remix_model = acestep-v15-sft`, `remix_tasks = (cover, repaint)`,
  `steps_by_model = {turbo: 8, sft: 50}` y `guidance_by_model = {turbo: 1.0,
  sft: 7.0}`. Regla única: `GenerationDefaults.model_for(task, requested)`.
- `music_service.build_payload` calcula tarea y modelo primero y elige
  pasos/guidance de las tablas del modelo; el log de envío ya dice
  `modelo=… | pasos=… guidance=…` (evidencia en cada trabajo).
- Los tres `GenerationRequest` de `/audio/remix/ai` mandan `remix_model`;
  VERSIÓN/TRAMO (cover/repaint) van a remix_model por `model_for`; CREAR
  (text2music) sigue en `model` (turbo). El job y la ficha guardan el modelo
  efectivo.
- `scripts/ensure_local.ps1`: `ACESTEP_ON_DEMAND_MODEL_LOAD=true`. **Sin esta
  variable el motor ignora en silencio el modelo pedido y usa el primario**
  (`job_model_selection.py`), es decir, un remix que dice sft pero corre en
  turbo. Es la pieza que convertía el cambio en FAKE si faltaba.
- Glosa: cada entrada puede llevar `without` (forma cuando está negada) y se
  detecta la negación («sin/no/without»); palabra negada sin forma contraria
  → no se añade nada. + géneros y matices (gabber, hardstyle, frenchcore,
  trance, reggae, metal, distorsionado…). `_NO_MELODY_WORDS` gana
  «without melody» para que la intención se lea también en prompt inglés.
- Lateral (`App.jsx`): modelo cargado + LM + VRAM libre + modelo de remix,
  refrescados cada 10 s con `/music/models` (antes solo se leía una vez al
  montar). `free_vram_mb` pasa a público en `separator_service`.
- El paso del remix anuncia en la UI: «Modelo del motor: acestep-v15-sft
  (guidance 7, 50 pasos: el prompt pesa más que en el turbo)».

### Prueba real (con GPU, servicios arriba)

- **Remix completo** job `93ef9310` (21:17–21:21, 247,7 s) con el prompt del
  usuario glosado «…sin melodias, sonido hardstyle (drums, without melody)»:
  - envío: `modelo=acestep-v15-sft | pasos=50 guidance=7.0 | dur=-1s`;
  - motor: `/health` → `loaded_model: acestep-v15-sft` (cambio on-demand
    real, no solo la petición);
  - log del motor: barra `50/50` pasos y **0** líneas «overriding guidance»
    (es decir, guidance 7.0 efectiva; en turbo esa línea sale siempre);
  - **VRAM pico 6 607 MB de 8 025 MB** (mínimo 1 418 MB libres, sin OOM),
    muestreo cada 3 s en `logs/vram-sft-remix.log`;
  - salida: `prueba-sft-obediencia.mp3` 81,45 s / 1 956 140 bytes, mezclada a
    -14 LUFS, con ficha. Se queda en la biblioteca para oírla.
- **Vuelta a turbo**: `POST /music/generate` 20 s → `modelo=acestep-v15-turbo
  | pasos=8 guidance=1.0`, `/health` → `loaded_model: acestep-v15-turbo`,
  `prueba-vuelta-turbo.mp3` 20,0 s. El cambio de modelo funciona en ambos
  sentidos (CREAR después de un remix no se queda en sft).
- Peso del sft verificado: 4 787 825 604 bytes (igual que el turbo). La
  medición de VRAM de las 00:13 (`logs/vram-sft2.log`, pico 7 914 MB) ya
  existía y **no estaba anotada** en la bitácora: ahora lo está.
- Lateral en vivo: `GET /music/models` devuelve `remix_model` y
  `vram_free_mb` (7 573 MB con el motor frío).

### Prueba de código y estado de los servicios

- `py_compile` 0 · unittest **24/24** (7 nuevas: `model_for`, pasos/guidance
  por modelo, allowlist, «without melody») · `node --test` glosa **7/7** ·
  lint 0 · build 0 (`index-Cn46Nu5b.js`, 345,47 kB / gzip 106,93 kB, umbral
  T3 400 kB). API reiniciada con el código nuevo (proceso 21:25:43, posterior
  a la última edición) y motor en pie: **servicios dejados corriendo**.
- Ficheros tocados: `config.py`, `config.example.json`, `music_service.py`,
  `main.py`, `separator_service.py`, `test_remix_logic.py`,
  `prompt_gloss.js`, `prompt_gloss.test.js` (nuevo), `App.jsx`,
  `ensure_local.ps1`, specs 02/03/05. Stems de prueba borrados.
- **TESTER - PASS (evidencia ejecutada)**: los 5 comandos de arriba en verde;
  remix real con sft terminado en `succeeded` con MP3 verificado por ffprobe;
  ida y vuelta de modelo comprobadas por `/health`; VRAM pico medida con
  nvidia-smi. **No es PASS de oído**: nadie ha escuchado el resultado.
- **REVIEWER - APPROVE con límites**: releídos los 11 ficheros (diff completo
  + glosa entera). Ni un literal de modelo/pasos/guidance fuera de config; la
  glosa sigue sin reescribir la frase; el turbo no pierde sus 8 pasos; la
  allowlist sigue cortando modelos ajenos. Límites: (1) el oído del usuario
  decide si la obediencia mejora — `prueba-sft-obediencia.mp3` está en la
  biblioteca para eso; (2) el sft añade ~2 min al remix (50 pasos + cambio de
  modelo) y eso se oye en la espera; (3) sin `ACESTEP_ON_DEMAND_MODEL_LOAD`
  el motor vuelve al silencio de usar el primario — si algún día se arranca
  el motor a mano, el /health es la única prueba fiable; (4) `remix_model`
  cubre cover/repaint y remix/ai, pero un texto2music lanzado a mano desde
  BIBLIOTECA con «base nueva» pasa por remix/ai, y el de CREAR se queda en
  turbo por diseño.

### Lecciones

1. **Un cambio de modelo hay que verificarlo por `/health`, no por lo que
   mandas**: el motor fallback-ea al primario en silencio si no tiene
   habilitado el cambio on-demand.
2. **Glosar sin gramática mete órdenes al revés**: toda glosa con negaciones
   necesita forma contraria (`without …`) o no añadir nada.
3. **`print()` del motor a fichero con buffer**: para saber qué corre, manda
   `/health` y la barra de pasos, no el log recién escrito.
4. Los `?` en regex cubren un carácter: `sintetizadores?` no matchea
   «sintetizador». Revisar las reglas con palabras reales del usuario.

## 2026-10-06 (XLVII) — Fase 2 «Estilo + 3 minutos» y diagnóstico del «no es lo que pedí»: la solución es VOCABULARIO + modificadores composibles

### Contexto
El usuario oyó el A/B del 2026-10-05 (job `f776483c`, caption gabber, bpm 180)
y dijo «revisa, no es lo que pedí». Con ask_user concretó: falla el ESTILO
(«base con baterías hardcore»), el BPM objetivo es 180 y sugirió «¿tags?».

### Diagnóstico (todo ejecutado, nada imaginado)
- **El BPM 180 SÍ se cumplió**: detección fina de golpes (envolvente de
  graves ≤120 Hz, hop 10 ms, umbral mean+1.5σ, interpolación parabólica)
  sobre `prueba-estilo-ab-base.mp3` → **180.63 bpm** (n=223); mix 180.49.
  El «193» anterior era artefacto de `detect_groove` (autocorrelación,
  conf 0.143). **Lección: `detect_groove` sobreestima tempo en bases
  generadas; medir con envolvente de golpes.**
- **`/format_input` (LM 0.6B) está DESCARTADO**: pruebas en vivo contra
  :8001 con el caption gabber, con tags y a temperatura 0.1/0.3 → nunca
  dice «hardcore» ni «gabber»; lo reescribe a house/EBM/darksynth/
  hardstyle. El LM no conoce el término y `use_format` destruiría el estilo.
- **El formato frase-EN es el correcto**: 200/200 captions de
  `vendor/ACE-Step-1.5/examples/text2music/` empiezan por «A/An», media
  312 chars, 0 llevan «bpm» en el texto (va en metas). Los tags puros
  contradicen el entrenamiento del DiT.
- **El fallo es de VOCABULARIO**: el motor nunca produce «gabber/hardcore»
  pero sí usa «hardstyle, distorted kick, snares, dark».

### A/B/C/D/E real en GPU (semilla 42 fija, sft 50 pasos, guidance 9.0,
bpm 180, instrumental 60 s; solo cambia el caption; jobs 59de2282, a92782f1,
4871bb6d, 97344d55, 2f24614d)
- A «gabber-actual» (el que no gustó) | B «hardstyle-vocab» | C «híbrido
  hardcore+vocab» | D = B + «rapid-fire double bass kick…» | E = C +
  «fast double bass kick drumming, kicks on every beat».
- MP3 en `backend/outputs/ab-estilo-{A,B,C,D,E}.mp3`, 60.0 s cada uno,
  verificados (duración > 0). DSP: B 180.9 bpm y low% 70.6 (kick más
  dominante); los BPM de la ronda de 5 ms (342/474) son artefactos del
  detector contando colas del kick — **no usarlos como veredicto**.
- El usuario escuchó: «el sonido se parece, pero faltó el doble bombo a
  mucha velocidad» y «la parte final de E es lo que quiero». Y exigió que
  nada vaya hardcodeado: los detalles (doble bombo hoy, otra cosa mañana)
  deben salir de SU frase.

### Implementación (fase 2 + composición, sin hardcodear el ganador)
- `backend/prompt_style.py`: regla «hardcore holandes» reescrita con el
  vocabulario que el motor reconoce (hardstyle/distorted kick/snares/dark
  raver; SIN «gabber»); nueva capa **STYLE_MODIFIERS** (datos: claves ES/EN
  + cláusula EN) con `find_modifiers()`: «doble bombo», «rápido»,
  «distorsionado», «baterías», «oscuro», «épico». `style_caption()` compone
  frase usuario + estilo + modificadores detectados en SU texto. Nada del
  doble bombo va pegado al estilo: es componible y solo entra si se pide.
- `backend/test_prompt_style.py`: +4 tests de composición/independencia de
  capas. **TESTER - PASS**: 45/45 unittest OK (backend/venv, 0.034 s).
- **Verificación GPU final**: caption COMPUESTO desde el prompt del usuario
  «baterias techno hardcore holandes (drums) con doble bombo a toda
  velocidad» (433 chars, datos, nada fijo a mano) → job `beaa7a57`,
  succeeded, `backend/outputs/ab-estilo-F.mp3` 60.0 s; DSP: 207 golpes de
  graves en 50 s (≈4.1/s: densidad de doble bombo), low% 58.3.
- **Verificación en vivo**: API reiniciada (pid 17648 y 11204 muertos,
  relanzada con backend\venv) y `POST /music/enhance_prompt` devuelve el
  caption compuesto + `suggested_bpm: 180`.
- **REVIEWER - APPROVE**: releídos íntegros `prompt_style.py` y
  `test_prompt_style.py`. Sin literales mágicos nuevos (los BPM siguen
  siendo datos por estilo); `style_caption` sigue sin recortar (si se pasa
  de MAX_CAPTION_CHARS devuelve el prompt); los modificadores no activan
  estilos y un estilo no arrastra modificadores (tests). Límites: (1) el
  oído del usuario decide si F («la parte final de E») es el sonido final —
  `ab-estilo-F.mp3` en biblioteca para oírlo; (2) el detector de BPM propio
  sigue sin ser fiable para veredictos finos (usar envolvente de golpes y
  desconfiar de medianas con colas); (3) los modificadores solo cubren
  detalles con claves declaradas — nuevos deseos = nueva entrada de datos,
  no código.

## 2026-10-06 (XLVIII) — Chips sugeridos + separación de capas del prompt (diseño aprobado por el usuario)

### Qué se pidió y qué se decidió
El usuario preguntó cómo se gestionaban las dos capas (estilo/modificadores).
Tras explorar opciones con ask_user (chips estáticos descartados: «siempre
serán los mismos»; sugerencia por LM descartada: destruye el estilo),
eligió: **chips + texto en el mismo prompt, con las capas visibles debajo**.
Fuente de los chips: el catálogo de datos del backend (no el modelo, no la
UI); no son siempre los mismos porque se filtran por género detectado y por
lo ya escrito. Un detalle nuevo = nueva fila de dato (tras probarla en GPU).

### Implementación
- `backend/prompt_style.py`: STYLE_MODIFIERS ahora lleva `label`, `text`
  (frase que se inserta al prompt), `suggest_with` (géneros; "*" =
  genérico) y `clause`. Nueva `analyze_prompt()` = capas separadas +
  chips con `active` (ya escrito) / `suggested` (proponible). Única
  fuente de verdad de detección y chips.
- `backend/main.py`: `GET /music/style_options?prompt=...` (determinista,
  sin LM, barato: pedible en cada pulsación).
- `frontend/src/api.js`: `styleOptions(prompt)` (GET, silencioso si falla).
- `frontend/src/components/Composer.jsx`: bajo el textarea, fila «+ AÑADIR»
  con los chips sugeridos (clic = añade su texto al MISMO prompt) y línea
  de capas «ESTILO: … · bpm | DETALLES: …». Debounce 300 ms; guardado
  con aliveRef para no pintar tras desmontar.
- `backend/test_prompt_style.py`: +6 tests (capas separadas, chip activo
  no se sugiere, chips según género, genérico siempre, vacío, integridad
  de datos del catálogo).

### Verificación (TESTER - PASS)
- **51/51 unittest OK** (backend/venv, exit 0).
- **ESLint OK** en Composer.jsx y api.js (exit 0).
- **`npm run build` OK**: nuevo bundle `dist/assets/index-DWz2HTj4.js`
  (la UI en producción la sirve la API desde frontend/dist).
- **API viva reiniciada**: `GET /music/style_options?prompt=baterias techno
  hardcore holandes con doble bombo` → `detected_genre: hardcore holandes`,
  `suggested_bpm: 180`, «Doble bombo» y «Baterías protagonistas» activos,
  sugeridos solo los relevantes. Con prompt vacío: sin género ni activos.
- **REVIEWER - APPROVE**: releídos íntegros prompt_style.py, main.py
  (solo los dos puntos tocados), api.js y Composer.jsx. La UI no hardcodea
  chips (los pide al backend); analyze_prompt no duplica sugeridos; el
  prompt sigue siendo un solo texto (compatible con MEJORAR PROMPT, glosa
  y remix). Límites: (1) el catálogo inicial son 6 modificadores — crece
  añadiendo filas de dato tras validarlas en GPU; (2) la previsualización
  de capas es orientativa: el caption real que viaja al motor lo compone
  enhance_prompt en el momento de generar; (3) falta oído del usuario con
  la UI montada (los MP3 de referencia ya están en biblioteca).

## 2026-10-06 (XLIX) — Chips y capas en TODOS los prompts de la app

El usuario probó el REMIX y no veía chips: estaban solo en CREAR. Pidió que
se aplicara a todos los prompts de la app. Inventario hecho por grep: los
campos de prompt de la app son tres (Composer, RemixActions, RemixIAPanel);
Library/Uploads/QualityWizard no tienen input de prompt propio.

- `RemixActions.jsx`: chips + preview de capas bajo el textarea de las
  acciones con prompt (VERSIÓN, TRAMO, VOZ REAL + BASE NUEVA, SOLO BASE
  NUEVA). Mismo contrato: chip = inserta su texto en el MISMO prompt; el
  análisis sale de `GET /music/style_options` (debounce 300 ms). Con la
  acción sin prompt (separar/ajustar/loop...) no se pide nada.
- `RemixIAPanel.jsx` (OTRA VERSIÓN CON IA en biblioteca): ídem, convive con
  sus chips VARIANTS existentes (los de direcciones fijas) sin tocarlos.
- Verificación: ESLint exit 0 en los dos ficheros; `npm run build` OK
  (bundle `index-B7ZE2NIl.js`); el endpoint ya vivo respondió correctamente
  a «techno oscuro» (genre techno, bpm 135, chip Oscuro activo).
- Límite: la ventana de Electron debe recargarse (Ctrl+R) para cargar el
  bundle nuevo; si la API está parada, los chips no aparecen (silencioso
  por diseño, no bloquea escribir).

## 2026-10-06 (L) — Bug real del «no es lo que pedí» en REMIX: el prompt viajaba en crudo

El usuario probó el remix («Animales muertos», prompt «TECHNO CONDUNDENTE,
SIN MELODIAS, SOLO PERCUSIONES A VELOCIDAD 180 BPM») y volvió a decir que no
era lo pedido. Log del motor examinado (job `3422aa27`, 00:58): el caption
que llegó al DiT era el prompt EN CRUDO — sin caption de estilo compuesto.
El BPM 180 sí viajó en metas. Causa: `_run_ai_remix` calculaba el BPM con
`style_bpm()` pero los tres `GenerationRequest` enviaban `request.prompt`
literal. La composición de estilo solo se aplicaba en CREAR (vía
enhance_prompt en el frontend) y en enhance/remix_prompt, no en el remix.

- Fix en `backend/main.py` (`_run_ai_remix`): `caption_remix =
  style_caption(request.prompt)` una vez al inicio; los tres envíos
  (cover, text2music por alargar, base nueva) mandan `caption_remix`.
  Nota en log del trabajo: «Caption compuesto con el estilo que pides».
- Con el prompt del usuario el caption compuesto queda: frase + «A hypnotic
  techno track…» (regla techno; «hardcore» no aparece en su frase y por eso
  no pega hardcore — los BPM de metas los marca el usuario: 180).
- Verificación: 51/51 unittest OK tras el cambio; API reiniciada y viva
  (PID 5324, /health ok, /music/style_options ok). Recordatorio de arranque:
  el relanzamiento via Start-Process del .ps1 temporal murió sin rastro en
  el log; arrancado en primer plano de la sesión y quedó vivo.
- Límite: el remix REAL con este fix no se ha generado todavía (requiere
  GPU y la decisión del usuario); la próxima generación de remix mostrará
  en la línea de eventos «Caption compuesto…» como confirmación visible.

## 2026-10-06 (LI) — «A 180 no sale 4x4»: el patrón rítmico es un modificador más + docencia en placeholders

El usuario achacó al sistema que a 180 bpm la base no iba en 4x4. Razón
verificada: el BPM es una meta suelta; el patrón rítmico lo define el
caption, y nada en su frase lo pedía. Es la misma regla de siempre (el
motor no deduce lo que no se escribe) aplicada al patrón.

- Datos: nuevo modificador «4x4 (bombo a cada pulso)» en STYLE_MODIFIERS
  (claves «4x4», «four on the floor», «bombo a cada pulso»…; cláusula EN
  «a steady four-on-the-floor kick drum pattern…»). Docencia también en la
  cabecera del módulo. Comprobado: «techno oscuro en 4x4 a 180 bpm sin
  melodías» compone el caption con el four-on-the-floor dos veces reforzado
  (regla techno + modificador).
- UI sin labels gordos: la docencia va en los PLACEHOLDERS de los tres
  cuadros de prompt (Composer, RemixActions con ejemplos por acción,
  RemixIAPanel): «nombra el estilo + patrón + detalles; el motor no
  adivina». Desaparecen al escribir: cero espacio ocupado.
- Verificación: 51/51 unittest OK; ESLint exit 0 (3 ficheros); build OK
  (bundle index-CYJXE_Zg.js). El usuario debe recargar la app (Ctrl+R).

## 2026-10-06 (LII) — El acompasamiento de la voz usa el BPM DECIDIDO como dato, en todos los caminos del remix

El usuario pidió que la base del remix «debe acompasar lo que se haya
decido» y que valiera «para cualquier cosa del remix». Diagnóstico del
código: la base sí se genera al BPM decidido (dato), pero al CUADRAR la voz
se volvía a detectar el groove de la base GENERADA — y detect_groove lee mal
el audio generado (conf 0.14; en stems de voz inventa 357 bpm). Con la
confianza baja, plan_alignment devolvía None y la voz quedaba «a su tempo»:
ahí estaba el desfase que oía el usuario.

- `backend/main.py` (_run_ai_remix): en el cuadre por atempo, la base es
  {bpm: decidido, confidence: 1.0} (dato autoritativo: LA PEDIMOS a ese
  bpm) y la voz usa el groove del tema original (la voz se cantó a eso y
  ese audio SÍ tiene batería detectable). Si no se decidió BPM, detección
  como antes. Aplica a los tres caminos: cover con voz, base alargada con
  voz troceada y base nueva.
- `backend/mixer_service.py` (plan_vocal_arrangement): nuevo parámetro
  `base_bpm` — el dato manda sobre detect_groove; sin dato, como antes.
  El reparto de frases usa compases del BPM decidido.
- 51/51 unittest OK. API reiniciada con el cambio (viva, /health ok).
- Límite: verificación de oído pendiente (el usuario está probando); el
  cuadre atempo está limitado por diseño a ratio 0.8-1.25 (deformaría más)
  — para BPM muy distintos entre voz y base, la voz se reparte en trozos
  (arrangement), que ahora también cae en compases del BPM decidido.

## 2026-10-06 (LIV) — Estado del remix IA: diagnóstico y cambio de flujo para voz + base

- **Síntoma reportado**: en el remix IA con voz + base nueva, el resultado final no suena como la música que pide el prompt.
- **Diagnóstico**: en `backend/main.py` la rama `keep_vocals` del remix IA estaba lanzando un **cover del instrumental original** con `task_type="cover"` y `source_path=ritmo`. Esa tarea conserva la melodía del tema viejo, así que el usuario percibe que el prompt no se obedece, sobre todo cuando pide un cambio de estilo fuerte (ej. hardcore). No era un fallo de ruta ni de archivo: el flujo completo llegaba al motor, pero el **camino del remix estaba enfocado a retener el tema original** en vez de generar música nueva desde el prompt.
- **Cambio aplicado**: esa rama ahora lanza una **base completamente nueva** (`task_type` por defecto = text2music, sin `source_path`, con `duration_seconds` resuelto), igual que `solo_base`. La voz original se separa y se mezcla después del mismo modo. Así el resultado final sí depende del prompt en todos los caminos del remix IA.
- **Qué se preserva**: `solo_base` y la rama sin voz siguen igual; la glosa del prompt (`glossPrompt`) se mantiene; el slider AUTO/MANUAL de fuerza sigue funcionando, pero ya no se usa en este camino porque no hay `task_type="cover"` aquí.
- **Verificación actual**: 24/24 unittest OK; build y lint, pendientes de re-ejecutar tras el cambio. Validación real de oído pendiente: hay que lanzar un remix IA de voz + base y comprobar que el estilo cambia respecto al original.
- **Lección**: cuando el usuario dice “no hace lo que pido” sin 422 ni 404, el problema suele estar en qué tarea se envía al motor, no en el transporte del archivo. Aquí el transporte funcionaba; el flujo del remix elegía `cover` por defecto y ese es el cambio que había que corregir.

## 2026-10-06 (LV) — Divergencias memory↔código cerradas: kind en onda/groove, resto TTS, spec al día
- **Qué pidió el usuario**: arreglar lo que no coincide entre memory y código.
- **1. Onda y groove con `source_kind` (deuda menor de XL, confirmada)**: `GET /audio/groove/{name}` y `GET /audio/peaks/{name}` resolvían outputs-primero y con homónimos bib/sub la onda dibujaba el archivo equivocado. Ahora aceptan `?source_kind=upload|output` y van por `_find_audio` (400 si el kind es inválido, 404 si falta). Frontend: `api.groove(name, sourceKind)`, `api.audioPeaks(name, buckets, sourceKind)`, `Waveform` acepta `sourceKind`, `RemixPanel` lo reenvía a la onda, `RemixActions` pasa el suyo en TRAMO y AJUSTAR. Sin kind, orden viejo (no rompe a MEZCLA).
- **2. Resto de TTS fuera**: quedaba `TtsSettings` + campo `tts` en `backend/config.py` y bloque `tts` en `config.example.json` (rutas/import/requirements ya estaban limpios desde XLII). Borrados; `build_settings()` ya no expone `tts` y `grep TtsSettings` en backend da 0.
- **3. `spec/03` al día (decía 2026-10-03)**: T6 = 51 tests (remix_logic + prompt_style) + 7 de glosa; T3 = bundle `index-DYMB-EMz.js` 349.40 kB (gzip 108.19 kB), umbral 400 kB intacto; W1 recoge el pico sft (6 607 MB, log previo 7 914 MB); el párrafo de covers pasa a decir lo medido (repaint `prueba-auditoria-tramo.mp3`, remixes sft y serie A–F generados; falta el oído); [F3] pasa a veredicto de oído.
- **4. Salto LII→LIV**: la entrada LIII nunca existió (hueco de numeración, no contenido perdido). Se deja constancia aquí y no se reescribe la historia.
- **Prueba**: `py_compile` 0; unittest 51/51 OK; glosa `node --test` 7/7; `eslint` 0; `npm run build` OK (`index-DYMB-EMz.js` 349.40 kB). TestClient: groove/peaks con kind inválido → 400, inexistente → 404, reales con `source_kind=output` → 200 (groove bpm 160.08, peaks 50 buckets) sobre `39628473-01-Animales muertos (2).mp3`. Sin GPU, sin ventana, sin tocar audios.
- **TESTER — PASS de contrato, tests, lint y build. No de clic (onda con kind en ventana) ni de oído.**
- **REVIEWER — APPROVE con límites**: el kind es optativo y conserva el orden viejo por defecto; el waveform pide el kind solo donde la lista se conoce (RemixActions); `api.groove` sigue sin llamantes pero ya no mentiría con homónimos cuando se use. La historia no se reescribe: LIII queda como hueco declarado.

## 2026-10-06 (LVI) — [L1] BIBLIOTECA auto-actualizada + [L2] borrado en bloque
- **Qué pidió el usuario**: que la biblioteca se auto-actualice, borrar en bloques, y una revisión técnica de mejoras. Decisiones por ask_user: modo SELECCIONAR explícito, refresco al terminar jobs (sin sondeo), endpoint múltiple.
- **Spec primero**: [L1] y [L2] en `spec/02-REQUISITOS.md` con decisiones y criterios.
- **Backend**: `POST /music/audio/delete_many` (`DeleteManyRequest{names: 1–100}`) — resuelve y borra igual que el individual (con ficha); inexistente/`../evil` → `not_found` sin tumbar el resto.
- **Frontend**: cabecera con SELECCIONAR → casilla por fila (clic en fila marca, controles no marcan) + barra (N, TODAS, NINGUNA, BORRAR con un solo SÍ/NO, SALIR). `App.jsx` avisa con `libraryTick` cuando la cola pasa de activa a vacía; `Library({externalRefresh})` recarga (poda la selección, no la vacía; el `<audio>` por nombre no se corta). Sin jobs, cero tráfico extra. ACTUALIZAR intacto.
- **Prueba**: `py_compile` 0; unittest 51/51; glosa 7/7; `eslint` 0; `build` OK (`index-hi3xe_Ft.js` 352.31 kB, trae SELECCIONAR/delete_many/externalRefresh/TODAS/NINGUNA). TestClient con ficheros temporales `zz-bulk-test-*`: bloque 200 (2 borrados + ficha fuera + 1 `not_found`), `[]`→422, 101→422, `../evil`→`not_found` sin borrar. Temporales verificados ausentes; biblioteca del usuario intacta.
- **TESTER — PASS de contrato, tests, lint y build. No de clic (modo SELECCIONAR en ventana) ni de ciclo vivo (job real terminando con BIBLIOTECA abierta).**
- **REVIEWER — APPROVE con límites**: el bloque es solo de biblioteca (uploads tiene su propio borrado); si la API reinicia a mitad de un job se pierde el aviso (queda ACTUALIZAR); VARIAR genera un aviso a mitad (inofensivo: recarga de más).
- **Revisión técnica (sin código, propuestas)**: (1) `api.groove()` no tiene llamantes — usarla (p. ej. enseñar BPM medido en MEZCLA/BIBLIOTECA, spec [M3]) o borrarla; (2) `GET /music/audio/{name}` sirve `audio/mpeg` fijo — si algún día hay wav, mentiría el MIME; (3) bundle 352 kB < umbral 400 kB, aún no partir; (4) sin `console.log`, sin TODO reales (los 2 matches son texto español de UI), los `except Exception` del backend mapean a HTTP con mensaje; (5) jobs en memoria sin cancelar — ya declarado en spec (cola en disco pendiente).

## 2026-10-06 (LVII) — Prompts a fondo: el estilo viajaba en crudo en 5 de 6 caminos + TEMPO medido en BIBLIOTECA
- **Qué pidió el usuario**: cablear el groove y revisar a fondo prompts y demás.
- **Auditoría (mapa completo de caminos a `/music/generate`)**: el caption de estilo (`style_caption`: frase + EN + modificadores) solo entraba por MEJORAR PROMPT y por remix IA. En crudo iban: CREAR directo (género+mood+glosa, sin caption), VERSIÓN/TRAMO, OTRA VERSIÓN de bib y re-crear/base de SUBIR. El modelo si era el correcto en covers (sft por `model_for`), pero el caption no.
- **Fix estructural**: `style_caption` idempotente (si la cláusula del estilo ya viaja — MEJORAR ya lo compuso o el desplegable la traía — no la duplica) y `/music/generate` compone en el servidor para TODOS los caminos. La ficha y la barra guardan la frase del usuario; el job anota el evento «Caption compuesto…» cuando compone. El BPM pedido no se toca (el vacío sigue siendo N/A por decisión XXVI/XXIX). Transparencia: VER LO QUE SE ENVÍA añade la línea ESTILO (el texto exacto se ve con MEJORAR PROMPT).
- **Groove cableado**: botón TEMPO en ACCIONES de BIBLIOTECA (`api.groove` con `source_kind=output`, medido a mano y cacheado, nada automático por fila) + `PEDÍA x · SALE y` si la ficha trae BPM con diferencia ≥3 ([M3] parcial: la medición automática al generar sigue pendiente). MEZCLA ya enseñaba los BPM absolutos en el plan: ahí no faltaba nada.
- **Demás (propuestas, sin tocar)**: géneros Acústico/Electrónica del desplegable no tienen regla de estilo (no componen caption: habría que añadir filas de dato y validarlas en GPU); `GET /music/audio/{name}` con MIME fijo; bundle 353.62 kB < 400 kB.
- **Prueba**: `py_compile` 0; unittest 53/53 OK (+2 idempotencia); glosa 7/7; `eslint` 0; `build` OK (`index-XazjoeOF.js` 353.62 kB, trae TEMPO/MEDIDO/PEDÍA). Compose en vivo: prompt hardcore → 299 chars con caption techno; «cancion bonita» intacta; doble composición estable. Sin GPU (el endpoint con motor no se ejercitó), sin ventana, sin tocar audios.
- **TESTER — PASS de composición, tests, lint y build. No de escucha (si el caption compuesto obedece más se juzga oyendo) ni de clic (TEMPO en ventana).**
- **REVIEWER — APPROVE con límites**: el compose no recorta (si pasa 800 chars va la frase); la idempotencia es por cláusula exacta; el evento del job solo sale cuando compone de verdad.

## 2026-10-06 (LVIII) — Reglas en toda la app: 3 estilos + calma + «sin voz»
- **Qué pidió el usuario**: si esas reglas se pueden mejorar en toda la app.
- **Medición previa**: 5 frases de la propia UI sin regla (synthwave, acústico/folk ×2, tranquila/dormir) + electrónica cayendo en el caption genérico de electro.
- **Filas de dato (sin tocar lógica)**: `electronica` (ANTES que electro: la contiene), `synthwave` (100 bpm), `folk acustico` (antes que rock: «folk rock» lo pide el folk, 95 bpm); ambient suma calma/dormir/meditación; modificador «Sin voz» (refuerzo instrumental, nunca sugerido como chip: la voz se decide con letra/modo); 4x4/Baterías/Distorsión sugieren también electronica/synthwave. Efecto app-wide sin build: ESTILO, chips y MEJORAR salen del catálogo.
- **No se añade**: clave «rap» (sería subcadena de «rápido» y robaría tempos); «más energía»/«minimal» sin vocabulario de motor (la glosa ya cubre `energetic`). Quirk documentado en test: «lo-fi hip hop» gana hip hop (orden previo, sin cambio).
- **Prueba**: 60/60 unittest OK (+7 catálogo, test de integridad admite `suggest_with` vacío deliberado); `/music/style_options` en vivo: synthwave/100, folk/95, techno+`Sin voz`/135. Sin GPU (obediencia de las filas nuevas, por oído), sin ventana, sin tocar audios.
- **TESTER — PASS de catálogo, endpoint, tests y lint. No de escucha ni de clic.**
- **REVIEWER — APPROVE con límites**: las 3 cláusulas EN son nuevas sin medir en GPU (el próximo remix con esos estilos dirá); el orden manda (específico antes que genérico) y está cubierto por tests.
- **Aviso de repo**: `backend/prompt_style.py`, `test_prompt_style.py` y `prompt_gloss.test.js` siguen sin commit (untracked desde que nacieron); último commit `ae80327`. No se commitea sin orden.

## 2026-10-06 (LIX) — Compose en TODOS los caminos + revisión completa de bugs
- **Pregunta del usuario**: ¿está aplicado a cualquier prompt? Sí, verificado camino por camino: `/music/generate` (CREAR, VERSIÓN, TRAMO, OTRA VERSIÓN, re-crear/base) compone en el servidor; `_run_ai_remix` (voz+base, solo base, alargue) manda `caption_remix`; `write_lyrics` no compone a propósito (es semilla del LM, y el LM ya destruye el estilo por diseño). Sitios `music.submit`: 1008/1034/1053 (remix, con caption) y 1412 (generate, con caption).
- **Revisión completa**: 35 rutas backend ↔ 31 llamadas frontend, todas casadas (`/api/info` es la única sin UI: diagnóstico manual). Timeouts coherentes (30 s base, 90 s envío, 300 s letra, 900 s estudio). Sin `console.log`, sin TODO reales, los `except` mapean a HTTP.
- **Bugs encontrados y corregidos**:
  1. `_finalize_generation` borraba `job["events"]` al arrancar: mataba el evento «Caption compuesto» de LVII. Ya no se vacía (el alta deja los suyos; el tope 30 sigue).
  2. `jobs`/`remix_jobs`/`separate_jobs` crecían sin límite (`/music/jobs` sondeado cada 3 s engordaba). Nuevo `_remember` + `job_history: 30` en config: activos intocables, terminados podados por antigüedad (con `created_at` añadido a remix/separación).
  3. `describeError` mostraba «Request failed with status code 422» en validaciones: la lista `detail` de FastAPI ahora se enseña legible.
  4. MEZCLA no se enteraba de trabajos terminados: acepta `externalRefresh` igual que BIBLIOTECA.
- **Prueba**: `py_compile` 0; 61/61 unittest OK (+1 `_remember`: 35 terminados→30, running sobrevive); prune en vivo verificado; `eslint` 0; `build` OK (`index-DFVSMREg.js` 353.85 kB). Sin GPU, sin ventana, sin tocar audios.
- **TESTER — PASS de poda, errores, tests, lint y build. No de clic ni de ciclo vivo.**
- **REVIEWER — APPROVE con límites**: el tope 30 vale para sesiones normales; un `pollUntilDone` sobre un job podado vería 404 (solo si el job es antiquísimo y se sigue sondeando: la UI para al terminar). Nota: al editar el alta toqué por error `"seed": request.seed`→`seed` y lo revertí tras comprobar que no existe variable local (py_compile + tests en verde después).
- **Propuestas sin tocar**: JobsPanel y App sondean `/music/jobs` por duplicado cada 3 s (compartir el tick); `/api/info` sin UI; `GET /music/audio/{name}` con MIME fijo; cola en disco y botón parar GPU (ya en spec).

## 2026-10-06 (LXI) — [Q1] cola en disco + [Q2] PARAR con reinicio del motor
- **Decisiones (ask_user)**: historial + interrumpidos; soltar + matar motor (recarga tarda minutos); PARAR por fila activa.
- **[Q1]**: `backend/job_history.json` (gitignore) con foto atómica al terminar/cancelar (campos declarados por familia + últimos 5 eventos); al arrancar se carga y lo activo se marca failed «Interrumpido: la API se reinició». `created_at` añadido a remix/separación para podar con criterio.
- **[Q2]**: `POST /music/jobs/{id}/cancel` (404 inexistente, 409 terminado): marca `cancelled`, los runners abortan en el siguiente paso/sondeo (guards en `step`, `on_update`, post-wait, post-demucs + salidas tempranas) y queda failed «Cancelado» sin descargar nada. Si el motor trabajaba (generación en marcha; remix salvo fase Separando; nunca en separación/cola), mata el PID del :8001 (netstat stdlib) y relanza con `ensure_local.ps1` (respeta HOLD, mutex del script evita duplicados). Botón PARAR por fila activa con aviso del reinicio.
- **Prueba**: 65/65 unittest OK (+4: `uses_motor` ×6 casos, snapshot, roundtrip save/load con interrumpido, endpoint 404/409); `eslint` 0; `build` OK (`index-D6_O5H3w.js` 354.38 kB, trae PARAR/cancelJob). Roundtrip real a tmp (el log «recuperado» del test era el tmp, sin tocar estado real). Sin GPU (cancel real + kill + relaunch, sin ejercer), sin ventana, sin tocar audios.
- **TESTER — PASS de contrato, tests, lint y build. No de ciclo vivo con GPU.**
- **REVIEWER — APPROVE con límites**: matar por puerto asume que el :8001 es el motor (es su URL de config); si el relaunch cae en HOLD, el motor queda parado hasta reabrir Musicia (la nota lo dice); la cola de demucs en hilo no se aborta a mitad (termina en silencio sin publicar).
- **Lección**: al tocar el dict del alta, revisar la variable exacta (`"seed": seed` inexistente casi entra; revertido y verificado).

## 2026-10-06 (LXII) — [R1] biblioteca robusta + [R2] remix = cover nativo + [R3] batch 2 + use_format + [R4] UI honesta
- **Raíz (auditoría con la doc del modelo)**: el REMIX IA nunca mandó `task_type=cover` (el motor jamás oyó la pista) y `cover_strength` era un campo muerto; batch 1 contra 2-4 recomendados; `use_format` sin probar; tick de biblioteca frágil (cola activa→vacía; nada para DSP síncrono ni encadenados).
- **[R1]**: `/music/jobs` devuelve `library_version` (máx. mtime de `outputs/*.mp3`, el mismo glob que enseña la biblioteca); App refresca al cambiar la huella. Condición vieja retirada.
- **[R2]**: `_run_ai_remix` envía cover + `src_audio_path` + fuerza real (manual o auto); duración `-1` y BPM auto salvo petición; sin letra = instrumental honesto (el motor no clona voces). UI: un solo modo REESTILAR (fuera `voz_prompt`/`solo_base`, minutos, `keep_vocals`); escala de fuerza de la doc en los textos. Retirado: `voz_real_quiere_mas_larga`, `resolve_remix_duration` (+ tests).
- **[R3]**: `batch_size: 2` (config; las variantes se guardan `-v2` en CREAR y remix, el usuario elige); `use_format: true` (config + override por petición; `thinking` sigue off); el log de envío ya dice `use_format` y `batch`.
- **[R4]**: nota bajo GENERAR (rápido no obedece detalles → REESTILAR/SFT); VER LO QUE SE ENVÍA enseña modelo + formato + variantes.
- **Prueba**: 66/66 unittest OK (+5: huella, cover, formato, rango); `eslint` 0; `build` OK (`index-z1_5SLrK.js` 353.48 kB, trae REESTILAR/library_version/use_format); TestClient: remix/ai inexistente→404, prompt corto→422, config batch 2/use_format true, jobs trae `library_version`. Sin GPU (app cerrada: ni API ni motor en marcha), sin ventana, sin tocar audios.
- **Pendiente GPU (con la app abierta)**: A/B del banco (hardstyle/gabber, «Animales muertos»): reestilar con cover+formato+batch vs lo de antes; si `use_format` no mejora, se apaga. El oído del usuario decide el PASS.
- **TESTER — PASS de contrato, tests, lint y build. No de ciclo vivo con GPU.**
- **REVIEWER — APPROVE con límites**: el cover no conserva tu timbre de voz (reescribe todo al estilo; la UI lo dice); batch 2 dobla tiempo y VRAM por tirada; si el motor rechaza `use_format`, el error viajará honesto en el job.
- **Lección**: al reescribir un runner por tramos, releer la zona entera antes de dar por bueno el encaje (quedó un bloque huérfano del flujo viejo; detectado por lectura y eliminado).

## 2026-10-06 (LXIII) — [R5] conservar la voz + base nueva
- **Petición directa**: conservar la voz y cambiar la música. El cover (R2) no sirve: reescribe la voz. Segundo modo del remix IA: `mode: reestilar | voz` (otro valor → 422).
- **Modo voz**: demucs separa la voz → base instrumental SFT (obedece el prompt) al tempo medido del tema (el pedido manda) y de su duración → cuadre `plan_vocal_arrangement` (reserva `mix_tracks` + tempos) → mezcla a -14 LUFS. Sin letra (la pone tu grabación) y sin fuerza (no hay cover). Se guardan mezcla(s) + base(s) + voz; batch 2 = 2 mezclas, eliges en BIBLIOTECA.
- **Prueba**: 67/67 unittest OK (+1: modo inválido→422, voz→404 del audio); `eslint` 0; `build` OK (`index-CrQXnhZp.js` 354.43 kB, trae VOZ + BASE NUEVA). Sin GPU (app cerrada), sin ventana, sin tocar audios.
- **TESTER — PASS de contrato, tests, lint y build. No de ciclo vivo con GPU.**
- **REVIEWER — APPROVE con límites**: el cuadre voz-base nueva es el punto frágil histórico (si el arreglo no sale, la reserva mezcla a tempo y lo dice); la base la pide al tempo medido, no al que el detector lea de la base generada (lección LI).
- **Lección**: al añadir una rama con edit, verificar que la cabecera `else if` no se coma la anterior (pasó con `reestilar`; detectado por grep y reparado).

## 2026-10-06 (LXIV) — El LM inventa en español + piloto VOZ real + catálogo a JSON
- **Medición `format_input` en vivo**: «hardcore en 4x4 con doble bombo» → piano contemplativo a **300 bpm** (lo ignoró todo; mismo fenómeno que el 2026-10-03 con orquesta a 40 bpm). Con caption inglés + bpm 180 explícito SÍ pule bien (hard trance coherente, bpm respetado). Conclusión: el LM no traduce del español, solo pule inglés. La cadena ES→EN (glosa + catálogo) es el puente necesario.
- **`use_format=false` por defecto** (código + example): con true el servidor SUSTITUYE caption y BPM por el invento (`llm_generation_inputs.py:149-187`). Override por petición para A/B. API reiniciada sola (había 2 APIs: la del venv sin escucha y la de Python310 en :8000; se deja una sola del venv).
- **Corpus 200 ejemplos**: media 312 caracteres; pop 28, rock 34, hip-hop 17, trap 16, metal 8; hardstyle/gabber/hardcore 0, four-on-the-floor 0. Encoder Qwen3-Embedding (multilingüe, sin vocabulario cerrado). Tokenizador: trap/rap token propio; gabber/dembow fragmentados. El catálogo es hipótesis de distribuzione, no solución (estrategia LM-primero aprobada).
- **Catálogo a `backend/style_catalog.json`** (NO HARDCODE; test de esquema + orden trap>hip hop) + 6 agujeros cerrados (hardcore, tecno→`re:`, rap→`re:\brap\b`, trap, dembow, chill→`re:`) + detalles sin género ya viajan + idempotencia real (resto sin cláusulas).
- **Piloto VOZ (job `15d06c4b`)**: demucs + base SFT (guidance 9, 50 pasos, batch 2, `use_format=false`) + cuadre + mezcla en 191 s. 2 mezclas + 2 bases + voz, todo 81.4 s; mezcla a 166.7 bpm (origen 166.25). Archivos en BIBLIOTECA.
- **Prueba**: 72/72 unittest OK; glosa 7/7; eslint 0; build `index-TDrzCsCU.js` 354.44 kB. Falta: oído del usuario sobre las 2 mezclas.
- **TESTER — PASS de contrato, tests, lint, build y piloto real. No de calidad musical (oído pendiente).**

## 2026-10-06 (LXV) — [R6] glosario documental minado del fabricante
- **Minería**: guía oficial (5 capas; faltaban estilo vocal y tempo feel), 400 textos (frecuencias), encoder Qwen3-Embedding, tokenizador (trap/rap propios; gabber/dembow rotos). El catálogo es hipótesis de distribución, no vocabulario cerrado (estrategia LM-primero).
- **17 modificadores nuevos** con redacción del fabricante (voz ×7, tempo ×4, épica ×4, instrumentos ×3) + glosa ES→EN ampliada. 6 agujeros de género cerrados (LXIV) + `re:` regex (rap/rápido/rapid) + idempotencia por resto.
- **Prueba**: 73/73 unittest OK; glosa 8/8; eslint 0; build `index-Don8Zd9O.js` 354.96 kB. Test viejo `rap_no_secuestra_rapido` mandó (revertir «rap» plano → regex).
- **Lección**: el test que prohíbe una clave manda sobre el arreglo rápido; leer los tests del catálogo antes de añadir claves.

## 2026-10-06 (LX) — Tick compartido, MIME por extensión, `/api/info` verificado
- **Qué pidió el usuario**: hacer las propuestas (menos cola en disco y parar GPU: diseño pendiente, abajo).
- **Tick compartido**: App sondea `/music/jobs` UNA vez cada 3 s en `jobsFeed` y reparte: barra, auto-refresh bib/mezcla y `JobsPanel({items})` presentacional (sin sondeo propio) vía `Composer({jobs})`. Una petición menos cada 3 s con CREAR abierto.
- **MIME**: `/music/audio/{name}` usa `mimetypes` por extensión (mp3→`audio/mpeg` igual que antes; un futuro wav no mentiría). TestClient: 200 `audio/mpeg`.
- **`/api/info`**: responde 200 (`Musicia/local`). Se queda como diagnóstico sin UI: no hay nada que enseñar de él en la ventana.
- **No se tocan (falta diseño, hay que preguntar)**: cola en disco (formato, qué sobrevive al reinicio, quién limpia) y parar GPU (el motor no cancela tareas: habría que definir si se mata el proceso o se espera). Siguen en spec/05.
- **Prueba**: `py_compile` 0; 61/61 unittest; `eslint` 0; `build` OK (`index-B4OI1rGi.js` 353.69 kB). Sin GPU, sin ventana, sin tocar audios.
- **TESTER — PASS de tick único, MIME, tests, lint y build. No de clic.**
- **REVIEWER — APPROVE con límites**: JobsPanel sin items enseña nada (igual que antes con cola vacía); `mimetypes` es stdlib sin dependencias.

## 2026-10-06 (LXVII) — [R7] SUBIR en negro + vocabulario de la UI auditado
- **Qué pidió el usuario**: «lo primero es la UI: en SUBIR, al dar a REMIX la pantalla se pone en negro» + «revisa si chips y acciones coinciden con lo que reconocen los modelos». Alcance elegido: completo (reescribir textos + catálogo).
- **Raíz del negro**: `RemixActions.jsx` perdió la cabecera de imports (sin React/hooks/api/lucide → `ReferenceError` al montar). Además el menú se montaba siempre con `box` nulo (revienta `style.left`) y ofrecía LEGO/EXTRACT/COMPLETE (exigen `acestep-v15-base`, no instalado). Fix: imports restaurados, menú solo con `open && box`, esas 3 acciones ocultas con comentario.
- **Auditoría (200 captions del fabricante minados)**: 5 VARIANTS + moods Melancólico/Luminoso + textos de género no disparaban nada; 16 tags de voz con 0 apariciones (`husky`, `sung vocals`, `brooding`, `happy`…). Reescritos con su vocabulario (`female/male vocal` 66/142, `whispered` 8, `choir` 9, `ad-libs` 15…); Melancólico + Luminoso al catálogo; lo-fi ahora gana a hip hop (quirk viejo corregido).
- **Lección de glosa**: «nostálgico/minimalista/clímax» contienen a su glosa inglesa y viceversa → el anti-duplicado las traga. No necesitan entrada; se documenta en tests. Misma trampa que el bug 2026-10-05 pero al revés.
- **Prueba**: 75/75 unittest backend; glosa 9/9; eslint 0; build `index-l4ULbvMX.js` 359.57 kB. Spec [R7] verificada.
- **TESTER — PASS** (evidencia de esta entrada: tests + lint + build reales).
- **REVIEWER — APPROVE**: imports, menú condicional, textos alineados con catálogo; sin hardcode nuevo (todo en catálogo/vocal.js).

## 2026-10-07 (LXVIII) — [R7·R5] Chips compactos + vuelta de MINUTOS (más largo que el tema)
- **Qué pidió el usuario**: «los chips de remix me parecen falsos, el tamaño es muy grande» + «me has eliminado la posibilidad de hacerlo más largo que el tema original».
- **Chips falsos**: con prompt vacío salían 23 botones genéricos (los `suggest_with: '*'`) ocupando media pantalla. Fix: los chips viven ahora en UN desplegable AÑADIR (en RemixActions y en RemixIAPanel: direcciones fijas + chips del catálogo que sugiere el backend), cada opción con su texto real en el tooltip; ESTILO/DETALLES inline en una línea; consejo plegable (botón CONSEJO); textarea 3→2 filas (88→64 px en RemixIAPanel); glosa en una línea.
- **Duración perdida**: el refactor de la mesa (voz_prompt+solo_base → `mode:'voz'`) se comió el desplegable MINUTOS que mandaba `duration_seconds`. El backend lo seguía aceptando (`AiRemixRequest.duration_seconds`, usado en `_modo_conservar_voz` y en cover). Restaurado: estado `extendMinutes` + `maxMinutes` desde `/music/config max_duration_seconds` (NO HARDCODE, fallback 10 min igual que antes) + envío `duration_seconds` en `api.remixAi({mode:'voz'})` + aviso honesto (la voz se reparte en trozos, no se estira).
- **Prueba**: eslint 0; build `index-Bs9olcDD.js` 360.38 kB; 75/75 unittest backend; glosa 9/9. Spec [R7]/[R5] actualizados.
- **TESTER — PASS** (evidencia: lint + build + tests ejecutados en esta entrada).
- **REVIEWER — APPROVE**: sin hardcode (maxMinutes de config), sin stubs; los paneles solo reorganizan widget existentes (SelectBox ya usado en CREAR/MEZCLA).

## 2026-10-07 (LXIX) — [L3] BIBLIOTECA: solo versiones finales, base/voz aparte
- **Qué pidió el usuario**: «se generan muchos audios que en BIBLIOTECA marean. Quiero solo las versiones finales. Si después se quiere base y voz separadas deben estar no tan visibles».
- **Diagnóstico**: outputs/ traía 8+8 ficheros mezclados. Un remix de voz dejaba 6 por corrida: mezclas (final), 2 bases generadas (ficha `remix`, indistinguibles), voz separada (`vocals`) y base separada de demucs (**sin ficha** → task `None` → parecía final).
- **Fix backend** (`main.py`): en `_modo_conservar_voz`, la base separada por demucs lleva ahora ficha `instrumental` y la base generada pasa de `remix` a `instrumental` (la final es la mezcla `-con-voz`).
- **Fix frontend** (`Library.jsx`): partición `finals` vs `parts` (`task vocals|instrumental` o nombre `-(base|voces)(-vN)?.mp3` para fichas antiguas). Por defecto solo finales; al final de la lista, botón `VER/OCULTAR BASE Y VOZ SEPARADAS · n`; las piezas, atenuadas (opacity-60) y al final; cabecera `N versiones finales · M base/voz aparte`; TODAS selecciona solo lo visible; nota si no hay finales.
- **Evidencia (NO FAKE)**: script node contra outputs/ REALES → FINALES 8 (con-voz-v1/v2 ×2 proyectos, variantes) · PIEZAS 8 (base-v1/v2, orig-base, orig-voces) · 0 cruces. eslint 0; py_compile OK; 75/75 unittest; build `index-dFl4Y9JR.js` 361.17 kB.
- **TESTER — PASS** (evidencia de esta entrada).
- **REVIEWER — APPROVE**: filtro es UI (el backend sigue sirviendo todo: MEZCLA y borrado siguen viendo las piezas); sin borrar nada; regex de nombre solo actúa donde la ficha no alcanza.

## 2026-10-07 (LXX) — «La UI es antigua»: era la API caída, no el bundle
- **Síntoma del usuario**: en remix no se ve REESTILAR ni VOZ + BASE NUEVA; la UI parece anterior. Revisadas memory + spec/02 + spec/03 + `RemixActions.jsx` + `Library.jsx` (lint 0 en los tres ficheros de remix, `test_remix_logic` 31/31 OK).
- **Causa**: `frontend/dist` YA estaba al día (bundle `index-dFl4Y9JR.js`, 361.17 kB, contiene REESTILAR ×11 y VOZ + BASE; `npm run build` OK sin cambiar el bundle). Lo caído era la API (`:8000` connection refused, sin Electron vivo, puertos libres): la ventana no podía cargar nada nuevo.
- **Fix**: `scripts/start_local.ps1` (sin salida en el log del agente, pero levantó ambos: `:8000` pid 9388 y `:8001` pid 21232). Verificado: `GET /health` reachable=True y `GET /` sirve `index-dFl4Y9JR.js`.
- **Vigilancia**: el oyente de `:8000` es el hijo Python310 del shim del venv (par 15064→9388, patrón conocido de XXVIII/LXIV); funciona con el mismo código, no se tocó. Par legítimo en el motor (23784→21232).
- **Pendiente usuario**: abrir Musicia.exe (no había ventana viva) y comprobar REMIXER con REESTILAR y VOZ + BASE NUEVA.
- **TESTER — PASS de servicio y build. No de clic.**
- **REVIEWER — APPROVE con límites**: el duplicado FUERZA en REESTILAR (`RemixActions.jsx:563-595`, slider genérico + AUTO/MANUAL) y MEJORAR/SEMILLA solo en VERSIÓN/TRAMO siguen abiertos; spec/02 [F3]/[M2] desfasados frente al código (R2/R5/XL).

## 2026-10-07 (LXXI) — Chips de voz fuera de VOZ + BASE + AÑADIR solo con contexto
- **Qué pidió el usuario**: si las opciones de AÑADIR en VOZ + BASE NUEVA son las reales que entiende el modelo; si «Baterías protagonistas» pinta ahí; y que los chips parecen falsos.
- **Verificación previa (corpus real, 200 captions del fabricante)**: anthemic 28, driving 32, catchy 31, four-on-the-floor 14, whispered 9, choir 9, ad-libs 18, falsetto 5, spoken 10, shouted 3, rapped 1. Todo el vocabulario de chips existe en su corpus (rapeada flojo: 1/200); «distorted kick»/«reverse kick» literales 0/200 (hipótesis composicional, no cita).
- **Decisión**: «Baterías protagonistas» SÍ pinta (cláusula de mezcla sin voces; la voz se mezcla encima). Los 7 de voz NO (susurrada, potente, falsete, gritada, rapeada, hablada, armonías): meten cláusulas vocales en una base que es instrumental por diseño → doble voz.
- **Causa de «parecen falsos»**: con prompt vacío el backend sugería 19 genéricos sin contexto (medido: '' → 19, 'techno' → 23 con género). Y el comentario de `RemixIAPanel.jsx:110-112` prometía ocultarlos pero el código no lo hacía.
- **Fix (datos, no hardcode)**: `style_catalog.json` + `voice:true` en los 7 de voz (+ `_doc`); `analyze_prompt` lo expone en cada chip; AÑADIR se enseña solo con contexto (género detectado o detalles escritos) en RemixActions/Composer/RemixIAPanel; en acción `voz` se excluyen los de voz (en VERSIÓN/OTRA VERSIÓN se quedan: el cover sí canta).
- **Prueba**: 76/76 unittest OK (+1 voices); eslint 0 (3 ficheros); build `index-CWxvsVHN.js` 361.31 kB (fuentes 11:15:09 < bundle 11:15:59). En vivo: endpoint devuelve 7 voice:true; bundle servido con filtro `==="voz"&&X.voice` y gate `?[]:` dentro; `GET /health` reachable.
- **Lección**: en el bundle minificado los nombres locales desaparecen: buscar `hasStyleContext`/`c.voice` da 0 aunque el código esté (falso negativo); hay que buscar formas minificadas (`==="voz"&&*.voice`) + orden de mtimes.
- **TESTER — PASS de datos, tests, lint, build y endpoint. No de clic (ventana del usuario).**
- **REVIEWER — APPROVE con límites**: lo escrito a mano con palabras de voz en modo voz sigue componiendo cláusulas vocales (el filtro es de sugerencia, no de composición); rapped con 1/200 queda como hipótesis débil.

## 2026-10-07 (LXXII) — Que lo que ofrece la app sea real para el modelo
- **Qué pidió el usuario**: no su preferencia personal, sino «que sea realista lo que me ofrece la app con lo que entiende el modelo», tras pedir mantener guitarra + voz y «baterías techno contundentes».
- **Lo que medí con su frase exacta** (`manteniendo la guitarra y la voz, baterias techno contundentes`): glosa → `(drums, guitars, vocals, hard-hitting)` + caption techno + cláusula `the drums are the clear lead element of the mix`. Dos fallos: (a) **no existe ningún modificador de guitarra** en el catálogo (solo la palabra `guitars` entre paréntesis); (b) `lead element` **0 veces** en el corpus → cláusula inventada. Además, en VOZ + BASE NUEVA la glosa mete `vocals` y el motor puede meter su propia voz encima de la del usuario.
- **Oráculos (dos, con papel distinto)**: B = **400 captions** del fabricante (`examples/text2music` + `examples/simple_mode`, 225.489 chars) → vocabulario de prosa; A = **`acestep/genres_vocab.txt`** (2.116 tokens únicos de 178.572 líneas) → vocabulario de géneros. Lección: con solo 200 captions salían falsos positivos (`drum-machine` ≠ `drum machine`), y con A como oráculo de prosa se colaban `robotic`/`film` porque aparecen dentro de nombres de género.
- **Resultado de la auditoría**: antes **9/28 chips, 16/29 estilos y 6 términos de glosa** con vocabulario no real; después **0, 0 y 0**.
- **Cambios (datos, NO HARDCODE)**: `style_catalog.json` → 9 cláusulas de chip rehechas con frecuencias reales (`squarely` fuera, `played at maximum speed` → `a fast tempo with relentless, driving energy`, `the drums are the clear lead element of the mix` → `driving drums as the lead of the track`, `luminous optimistic` → `bright feel with upbeat energy`, `strictly instrumental` → `instrumental…`) y **15 captions de estilo** (`snares`→`snare` 5, `90s raver`→`rave` 6, `saturated`→`heavy`, `warehouse`→`club`, `repetitive`→`punchy`, `robotic`→`synth`, `shuffling`→`crisp`, `unplugged`→`acoustic`, `skanking`→`offbeat`, `shiny`→`warm`, `montuno/congas`→`piano/percussion`, `rasgueos/palmas`→`percussion`, `film-score`→`powerful`, `calm`→`soft`, `improvised phrasing`→`improvisation`); `prompt_gloss.js` → `moderate`→`mid tempo`, `calm`→`gentle` (×2), `saturated`→`distorted`, `dirty`→`gritty`, `optimistic`→`bright`.
- **Guarda para que no vuelva**: `backend/test_realism.py` (4 tests: chips, captions, claves de género vs `genres_vocab`, términos de glosa); se salta si no están los datos del motor. Control: detecta `robotic/shuffling` y deja pasar `a dark driving club groove`.
- **Prueba**: `unittest discover` **80/80 OK** exit 0; `node --test src/prompt_gloss.test.js` **9/9** exit 0; `eslint src --max-warnings=0` exit 0; `vite build` exit 0 → `index-BsJn5CqK.js`. Servicios relanzados (motor :8001, API :8000 pid 27060 arrancada **16:57:01** > catálogo 16:50:14 → cargó lo nuevo); `/health` reachable=True; endpoint con su frase → `techno` / 135 bpm / `Baterías protagonistas`.
- **TESTER — PASS**: evidencias ejecutadas (80 tests, 9 tests JS, lint 0, build 0, API reiniciada y endpoint en vivo).
- **REVIEWER — APPROVE con límites**: (1) sigue sin existir chip de guitarra (pedido pendiente); (2) `gabber` está en `genres_vocab` pero el A/B del 2026-10-06 dijo que no funciona → `genres_vocab` acredita vocabulario, no obediencia; (3) las cláusulas siguen siendo prosa compuesta (ninguna literal en el corpus), solo que con palabras que el modelo sí usa.

## 2026-10-07 (LXXIII) — La misma regla comprobada en CREAR
- **Qué pidió el usuario**: «has recompilado para ver la UI correctamente; revisa que eso ocurra en CREAR».
- **Estado previo al revisar**: servicios y ventana caídos (SALIR de la bandeja a las 17:20, según `logs/musicia-api.err.log`) → relanzados con `start_local.ps1` + `open_musicia.ps1` (Win32_Process.Create).
- **Lo que sí estaba en CREAR ya**: el gate de contexto está compilado en el bundle servido (`.chips?.some(` ×1, `detected_genre||` ×5, `modifiers?.length??0)>0` ×3) y los chips venían del catálogo nuevo (glosa `mid tempo` presente, `saturated`/`optimistic` ausentes). Prompt vacío → AÑADIR oculto ✓.
- **Lo que NO estaba**: CREAR **no filtraba los 7 chips de voz**. Medido contra el endpoint en vivo, con «techno» ofrecía 23 chips **con los 7 de voz**, incluso cuando la salida iba a ser instrumental (`mode !== 'voice'` → `instrumental: true`, o modo voz sin letra → «Sin letra el motor hace un instrumental»). Mismo problema de fondo que en VOZ + BASE NUEVA: el prompt pedía voz mientras al motor se le decía instrumental.
- **Fix (mismo patrón, datos)**: `Composer.jsx:398-402` → `habraVoz = mode === 'voice' && lyrics.trim().length > 0` y `chipsSugeribles` = gate de contexto + `voice` del catálogo. Sin ese gate, con prompt vacío el backend marca `suggested` en los genéricos y AÑADIR volvía a abrirse (bug introducido a medias y corregido en el mismo paso).
- **Prueba (4 casos contra el endpoint vivo)**: instrumental+vacío → OCULTO; instrumental+«techno» → 16 chips **0 de voz**; instrumental+«baterias contundentes» → 12 chips **0 de voz**; con LETRA+«techno» → 23 chips **7 de voz**. `eslint src --max-warnings=0` exit 0; `vite build` exit 0 → **`index-Do1EUr0c.js`**, que es el que sirve `:8000`.
- **TESTER — PASS** (simulación de la lógica de CREAR contra el endpoint real + lint + build + bundle servido verificado).
- **REVIEWER — APPROVE**: el filtro es de sugerencia, no de composición: si el usuario escribe a mano «voz susurrada» en un instrumental, `style_caption` la compone igual (limitación conocida, ya anotada en LXXI).

## 2026-10-07 (LXXIV) — Revertido: los chips no se esconden
- **Qué pidió el usuario**: «has vuelto a eliminar los chips… cuando los chips son reales del modelo son geniales». Es decir: el problema era la REALIDAD de los chips, no su cantidad. Una vez reales, hay que mostrarlos.
- **Qué había escondido yo (mi interpretación, no su petición)**: (1) AÑADIR completo con prompt vacío (gate de contexto), (2) los 7 chips de voz en VOZ + BASE NUEVA, (3) los 7 chips de voz en CREAR cuando la salida iba a ser instrumental. Todo ello en tres componentes.
- **Decisión**: se quitan LOS FILTROS y se conserva SOLO el trabajo de realismo (`backend/test_realism.py` sigue garantizando que todo lo ofrecido es vocabulario del modelo). El `voice` del catálogo se queda como dato (lo siguen usando el test de backend y el filtro de VOZ si se retoma).
- **Cambios**: `Composer.jsx` → `chipsSugeribles = (styleInfo?.chips ?? []).filter(c => c.suggested)` (sin `habraVoz`, sin `conContexto`); `RemixActions.jsx` → `chipOptions` sin `hasStyleContext` ni `action === 'voz' && c.voice` (el `styleInfo &&` de la línea de ESTILO/DETALLES pasa a usar `styleInfo` directamente); `RemixIAPanel.jsx` → `extraOptions` con `styleInfo?.chips ?? []` sin gate.
- **Prueba (6 casos contra el endpoint vivo)**: CREAR vacío **19**, CREAR «techno» **23**, CREAR «baterias contundentes» **19**, VOZ vacío **19**, VOZ «techno» **23**, VERSIÓN «techno» **23** — todos VISIBLES, con los 7 chips de voz incluidos. `eslint src --max-warnings=0` exit 0; `vite build` exit 0 → **`index-Dh_eIlaI.js`** (es el que sirve `:8000`, con glosa nueva y sin prosa vieja); `unittest discover` **80/80** exit 0.
- **Lección**: confundí «los chips parecen falsos» (realidad, sí era suyo) con «menos chips» (mi inferencia). Dos veces seguidas añadí filtros que no me había pedido. Regla: si el dato es real, se muestra; solo se filtra cuando el usuario lo pida.
- **Incidencia operativa**: servicios y ventana vuelven a caer cuando se cierra la app (SALIR de la bandeja); relanzados con `start_local.ps1` + `open_musicia.ps1` (Win32_Process.Create) a las 17:34.

## 2026-10-07 (LXXV) — Chips más pequeños + GLOSARIO del modelo (y combinar)
- **Peticiones**: «los chips de CREAR deben ser más pequeños» + «glosario directo del modelo de estilos y subestilos que entiende el modelo» + «combinar estilos, como techno hardcore».
- **Chips más pequeños**: `Composer.jsx` AÑADIR pasa de `h-4 px-2 text-[9px]` a `h-3.5 px-1.5 text-[8px] leading-none` y la fila de `gap-2` a `gap-1.5` (los de remix/otra versión son desplegables, no botones).
- **Fuente del glosario (hallazgo, no inventado)**: `vendor/ACE-Step-1.5/acestep/genres_vocab.txt` = **178.572 líneas**, y `acestep/constrained_logits_processor.py:187-191,953-1002` lo carga en un **trie** para usarlo como **whitelist sobre los logits del campo `genres`** (`:1939-1961`): lo que no está en el archivo, el modelo no puede escribirlo. Si la frase trae palabras que casan, recorta el sub-trié a esas entradas (`:1004-1058`). Es literalmente «lo que el modelo entiende».
- **Combinar**: comprobado antes de prometerlo — el archivo SÍ tiene formas combinadas (`hardcore techno`, `industrial techno`, `techno industrial`, `techno ambient`, `drum and bass`); 1.374 entradas con «techno» y 2.277 con «hardcore». `combine()` solo devuelve lo que existe (exactas primero) y **0** si la mezcla no está.
- **Plan aprobado por el usuario** (decidido antes de tocar código): alcance = catálogo + buscador completo; clic = añadir al prompt; sitio = todas las opciones con prompt; después, sobre la marcha, + combinación de dos estilos.
- **Backend**: `backend/genre_glossary.py` (carga con caché por mtime igual que el motor, `search`, `combine`, `catalog_styles`, límite 200 nunca el archivo entero; sin archivo → vacío y avisa, **nunca rellena con datos inventados**) + endpoints `GET /music/genre_glossary` y `GET /music/genre_glossary/combine` en `main.py` (def síncrono: FastAPI lo manda al threadpool, la búsqueda no bloquea el evento).
- **Frontend**: `frontend/src/components/Glossary.jsx` reutilizable (botón, panel posicionado como SelectBox, buscador con debounce de 250 ms y protección contra respuestas fuera de orden, sección *Estilos de Musicia* con BPM, sección del vocabulario y bandeja COMBINAR con ⇄) + `api.genreGlossary/api.genreCombine`. Se conecta en `Composer.jsx`, `RemixActions.jsx` y `RemixIAPanel.jsx` vía `addTexto()` (refactor mínimo de `addChip`).
- **Pruebas**: backend **88/88** (8 nuevas en `test_genre_glossary.py`, incluida la NO-FAKE: *todo resultado es una línea literal del archivo* y la de archivo ausente), `node --test` 9/9, `eslint src --max-warnings=0` exit 0, `vite build` exit 0 → **`index-DzctidoK.js`**.
- **Prueba real contra :8000**: `?limit=3` → `total=178572`, `styles=29` · `q=house` → `4836` con «house» el primero · `techno+hardcore` → `total=181`, exacta **`hardcore techno`** · `techno+industrial` → `industrial techno` y `techno industrial` · `zzqq+wxyz` → `0` · bundle servido con «GLOSARIO DEL MODELO», «ESTILOS DE MUSICIA», «COMBINAR».
- **Fallo mío corregido en el acto**: una edición en `api.js` borró la línea `musicModels: async () => {`; lo vi al releer el archivo y lo restauré junto con los dos métodos nuevos. Lección: tras editar un objeto grande, releer el trozo antes de seguir.
- **Incidencia operativa**: servicios caídos otra vez (SALIR), relanzados a las 20:29 y ventana abierta.

## 2026-10-07 (LXXVI) — Ver y enviar el mismo idioma: chips y variantes en inglés
- **Peticiones encadenadas**: «los chips de remix los pones en castellano y cuando eliges el estilo lo pone en inglés» → «me ha gustado el tema de los estilos» → «lo quiero igual con las variantes, presentes en todos los prompts» → «yo creo que al revés, los chips deberían ser en inglés también». Decisión final aprobada: **todo lo que se muestra y se añade, en inglés, marcado como ELEGIDO si ya está en tu frase, y variantes en los tres prompts**.
- **Por qué se veía inglés**: la incoherencia la metió el glosario (LXXV), que añadía la caption `style` (inglés) mientras los chips añadían `text` (español). El resto del pipeline ya era inglés: `style_caption` compone en inglés y `glossPrompt` glosa es→en.
- **Backend**: `prompt_style.analyze_prompt` expone ahora `clause` en cada chip (la cláusula literal del catálogo, ya validada por `test_realism`). La etiqueta y el `text` en español siguen saliendo (útiles para detección y tests).
- **Chips en inglés en los 3 sitios**: `Composer.jsx` (botones), `RemixActions.jsx` y `RemixIAPanel.jsx` (SelectBox AÑADIR) muestran y añaden `chip.clause`; `addChip` usa `clause ?? text`.
- **Variantes en módulo compartido**: `frontend/src/variants.js` (10 entradas con `label` y `add` en inglés + `toggleVariantText`/`removeTexto`) y `frontend/src/components/VariantChips.jsx`, que se pinta en **CREAR, remix y OTRA VERSIÓN** (antes solo en esta y en español; salen del desplegable AÑADIR para no duplicarse).
- **Minado de las 10 variantes (ojo, no a ojo)**: script de validación contra los 400 captions + `genres_vocab` y contra `analyze_prompt`. Correcciones que hizo falta: `calm` y `few` no estaban en el corpus; `powerful` disparaba el chip **Voz potente** (instrumenal con voz mandada); `double bass` disparaba **Doble bombo**. Final: 10/10 con prosa real y 10/10 disparando estilo o modificador (antes «minimal» no disparaba nada y el motor improvisaba).
- **Glosario**: los estilos de Musicia se muestran en inglés (su caption real) con el nombre+bpm en el tooltip; lo que ya está en tu frase se marca **ELEGIDO** y pulsarlo lo quita (`removeTexto`). `genre_glossary.catalog_styles` añade `genre` = primera clave cuyas palabras están todas en el vocabulario del modelo (**26/29**; las 3 restantes caen al nombre y no se inventa nada). Props del componente: `prompt` + `setPrompt` (mismo patrón que `VariantChips`).
- **Pruebas**: backend **90/90** (2 nuevas: `test_chip_lleva_su_clausula_en_ingles` y `test_realism.test_variantes_del_modelo`), `node --test` 9/9, `eslint src --max-warnings=0` exit 0, `vite build` exit 0 → **`index-D9hCQ3I7.js`**.
- **Prueba real contra :8000**: chips con `clause` en inglés (`A toda velocidad → a fast tempo with relentless, driving energy`), glosario con `genre` (26/29), bundle servido con `MORE ENERGY`, `high energy driving rhythm`, `VARIANTES`, `ELEGIDO` y **sin** las etiquetas viejas (`MÁS ENERGÍA` → False).
- **Lección**: traducir un texto a inglés **no basta**: hay que pasarlo por el mismo control (corpus + `analyze_prompt`), porque palabras normales en español chocaban con el catálogo (`double bass` = doble bombo, `powerful` = voz potente).
- **Incidencia operativa**: el usuario remezcló hasta las 20:44 («Animales muertos-con-voz-v2»), cerró la app y los servicios se pararon (SALIR); relanzados a las 20:56 y ventana abierta.

## 2026-10-07 (LXXVII) — AÑADIR de CREAR en lista
- **Petición**: «¿me has puesto en CREAR los chips? Los chips además deben ser pequeños o en una lista». Sí estaban, pero como botones en línea: con las cláusulas en inglés (LXXVI) cada uno era una frase larga y la fila se desbordaba.
- **Cambio**: `Composer.jsx` deja de pintar botones y usa el mismo `SelectBox AÑADIR` de remix (`chipOptions` + `addChipById`, `clearable={false}`), con GLOSARIO al lado y VARIANTES debajo. Es además el criterio que ya estaba anotado en el propio archivo («las filas de chips llenaban la ventana») y el que pidió el usuario: lista.
- **Verificación**: `eslint --max-warnings=0` exit 0, `vite build` exit 0 → **`index-mzWwSKtF.js`**; bundle servido con `DETALLE DEL CATÁLOGO` ×2 (CREAR + remix, antes ×1), sin restos de los botones inline, y con `MORE ENERGY`/`ELEGIDO`/`GLOSARIO`. Servicios y ventana relanzados a las 22:04 (SALIR otra vez).

## 2026-10-07 (LXXVIII) — El glosario añade el género, no la definición; y AÑADIR decía por qué estaba vacío
- **Peticiones**: «en el glosario me has puesto la definición que pone en el prompt y yo solo quiero el género» y «en AÑADIR no despliega nada».
- **Glosario = solo género**: cada fila de ESTILOS DE MUSICIA muestra y añade `genre` (p. ej. `gabber`, `hard techno`), no `text` (la caption completa, que es la «definición» que antes se colaba). El tooltip mantiene `nombre · bpm` para saber de qué estilo va. La caption la completa el motor por su cuenta al enviar (`style_caption`). El buscador filtra **también** el catálogo de Musicia (antes solo aparecía con consulta vacía, así que buscar «hardcore» no mostraba el estilo propio).
- **AÑADIR vacío = API caída, no código**: `api.styleOptions` devuelve `null` si la petición falla → 0 opciones → menú vacío sin explicación. La API estaba otra vez caída (SALIR). Ahora el estado se dice: `AÑADIR · SIN DATOS DEL MOTOR` (sin conexión) o `AÑADIR · SIN SUGERENCIAS`, y solo se pinta el desplegable si hay opciones. Con la API arriba: 19 chips con prompt vacío, 21 con «techno oscuro en 4x4», **116 ms** (timeout de axios 8000 ms, margen amplio).
- **Bug real encontrado al mirarlo**: `catalog_styles()` exigía que **cada palabra** de la clave fuera una línea de `genres_vocab.txt`, así que descartaba claves multipalabra cuya frase completa sí existe: `hard techno` y `hard house` son líneas literales y no se asignaban. Ahora la regla es *frase literal exacta* (las claves `re:` se ignoran): **26/29 → 28/29** estilos con género real; solo `uptempo hard dance` no tiene forma literal y cae a su nombre (sin inventar). Además `catalog_styles()` sin argumentos carga el vocabulario él mismo: antes `catalog_styles()` devolvía `genre=None` para todos (trampa que me encontré al probarlo a mano).
- **Pruebas**: backend **91/91** (nueva `test_genre_es_una_linea_literal_del_vocabulario`: todo `genre` es línea literal + regresión de `hard techno`/`hard house`), `node --test` 9/9, `eslint` exit 0, `vite build` exit 0 → **`index-D78TFyRM.js`**.
- **Prueba real contra :8000 tras reiniciar**: `con genre: 28/29`, `hard techno→hard techno`, `hard bounce→hard house`, `hardcore holandes→gabber`; `/music/style_options` con prompt vacío → 19 sugeridos; bundle servido = `index-D78TFyRM.js`; ventana «Musica» abierta y `health reachable=True`.
- **Lección**: un desplegable que no despliega casi nunca es la vista: en este stack suele ser que el servicio está caído. Diagnosticar con la petición real antes de tocar el componente.

## 2026-10-07 (LXXIX) — AÑADIR: en español al elegir, en inglés al añadir
- **Petición**: «en AÑADIR me pones la definición en inglés. Debes ponerla cuando se selecciona, en inglés, pero en el desplegable en español, más sintético».
- **Cambio en los tres AÑADIR** (`Composer`, `RemixActions`, `RemixIAPanel`): la opción del desplegable es ahora la **etiqueta corta del catálogo en español** (`A toda velocidad`, `Oscuro`) y el `title` es `Se añade: «…»` con la **cláusula en inglés**, que es la que se mete en el prompt al pulsar (sigue mandando `addChip` → `chip.clause ?? chip.text`; el motor recibe inglés, que es el idioma de las captions). El botón del desplegable no cambia (`DETALLE DEL CATÁLOGO` / `DIRECCIÓN O DETALLE`).
- **Pruebas**: sin cambios de backend → `unittest` 91/91, `node --test` 9/9, `eslint` exit 0, `vite build` exit 0 → **`index-B0ijN-oY.js`**.
- **Prueba real contra :8000**: bundle servido = `index-B0ijN-oY.js` con los 3 `Se añade: «` (antes mostraba la cláusula como etiqueta); `/music/style_options` → `label='A toda velocidad' | clause='a fast tempo with relentless, driving energy'`, 19 chips sugeridos. Como la API sirve `dist` desde disco, recargar basta; la ventana Electron hay que abrirla de nuevo.
- **Incidencia operativa**: a las 22:19 la API y el motor desaparecieron **sin error en el log** (el `musicia-api.log.bak` termina en 200 OK a las 22:18:49, con el usuario escribiendo `prompt=gabber`): proceso terminado desde fuera, el mismo patrón de SALIR del bandeja. Relanzado a las 22:21:30 y ventana nueva (PID 18564).

## 2026-10-07 (LXXX) — Resumen de la sesión: criterios consolidados y estado verificado
- **Arco del día (LXVIII → LXXIX)**: chips compactos → BIBLIOTECA → «la UI es antigua» (era la API caída) → chips de voz → realismo (NO FAKE aplicado a chips/captions/glosa) → misma regla en CREAR → **revertido el filtro de chips** → chips pequeños + **GLOSARIO** → **todo en inglés** (chips, variantes, ELEGIDO) → **AÑADIR en lista** → **glosario solo con el género** → **AÑADIR: lista en español, añade en inglés**.
- **Decisiones del usuario, con sus palabras (el orden importa, hubo que deshacer inferencias)**:
  1. «cuando los chips son reales del modelo son geniales» → *si el dato es real se muestra; solo se filtra si lo pido* (se desmontaron dos rondas de filtros no pedidos).
  2. «los chips de CREAR deben ser más pequeños» → `h-3.5 px-1.5 text-[8px]`.
  3. glosario = catálogo + buscador completo, clic añade, en **todas** las opciones con prompt, combinar estilos, estado ELEGIDO, variantes en **todos** los prompts → aprobado.
  4. «al revés, los chips deberían ser en inglés también» + variantes en inglés → ver y enviar el mismo idioma.
  5. «los chips deben ser pequeños o en una lista» → AÑADIR pasó de botones en línea a `SelectBox` (los botones con cláusulas inglesas desbordaban la fila).
  6. «en el glosario me has puesto la definición… yo solo quiero el género» y «en AÑADIR no despliega nada».
  7. «en el desplegable en español, más sintético, pero que al seleccionar se ponga en inglés».
- **Criterios consolidados (aplicar sin que los vuelvan a pedir)**:
  - **NO FAKE**: todo lo que se ofrece sale de los oráculos (`genres_vocab.txt` + 400 captions del fabricante); nada inventado, y si falta el archivo se dice, no se rellena.
  - **Ver en español, enviar en inglés**: etiquetas cortas de los desplegables en español; lo que se añade al prompt es la cláusula/caption/variante en inglés (idioma de las captions de entrenamiento); el tooltip siempre enseña lo que se va a añadir.
  - **Nunca un menú vacío sin explicación**: si `styleOptions` falla → `AÑADIR · SIN DATOS DEL MOTOR`; si no hay sugerencias → `SIN SUGERENCIAS`. Casi siempre el culpable es el servicio caído, no la vista.
  - **Listas, no filas de botones** («las filas de chips llenaban la ventana»).
  - **El glosario añade solo el género literal** del modelo; la caption completa la rellena el motor con `style_caption`.
  - **Validar textos nuevos** contra corpus + `analyze_prompt` (lección: `powerful` disparaba *Voz potente*, `double bass` *Doble bombo*, `calm`/`few` no estaban en el corpus).
  - **Releer el archivo tras cada edición de objetos grandes** (lección: se borró `musicModels` de `api.js`).
- **Estado verificado (2026-10-07 22:2x)**: `unittest discover` **91/91** · `node --test src/prompt_gloss.test.js` **9/9** · `eslint src --max-warnings=0` exit **0** · `vite build` exit **0** → **`index-B0ijN-oY.js`** (367.52 kB), que es el que sirve `:8000` · API `:8000` + motor `:8001` arriba, `health reachable=True` · ventana «Musica» abierta · `/music/style_options` (19 chips con prompt vacío, 116 ms) · `/music/genre_glossary` **28/29** estilos con `genre` literal (solo `uptempo hard dance` cae a su nombre).
- **Ficheros tocados hoy en esta ronda**: `backend/genre_glossary.py` (regla de `genre` = frase literal + carga auto del vocabulario), `backend/test_genre_glossary.py` (nueva `test_genre_es_una_linea_literal_del_vocabulario`), `frontend/src/components/Composer.jsx` (AÑADIR en lista + estado honesto), `frontend/src/components/Glossary.jsx` (solo género + buscador filtra el catálogo), `frontend/src/components/RemixActions.jsx` y `RemixIAPanel.jsx` (etiqueta en español, añade inglés), `spec/02-REQUISITOS.md` (criterios LXXIV-LXXIX).
- **Incidencia operativa recurrente (RESUELTA, sin cambio)**: el stack se ha caído y relanzado **varias veces hoy** (20:29, 20:56, 22:03, 22:21), siempre con el log cortado en 200 OK sin error. Investigado: `open_musicia.ps1` deja los procesos vivos al cerrarse y la única parada programada es la de `main.cjs` al pulsar **SALIR** (que llama a `stop_local.ps1`). **Decisión del usuario: «los maté yo, déjalo así»** → no se cambia nada; comportamiento actual (SALIR = apagar motor y API) es el correcto. Si en una ronda posterior todo está caído, solo hay que relanzar con `scripts/start_local.ps1` + `scripts/open_musicia.ps1` y verificar `/health`.

## 2026-10-08 — Revisión y corrección de cláusulas de chips y estilos contra corpus real

- **Qué**: Revisión exhaustiva de TODAS las cláusulas (chips/modificadores y captions de estilos) en backend/style_catalog.json para garantizar que usen EXCLUSIVAMENTE vocabulario que el modelo ACE-Step entiende, basado en los 400 captions del fabricante (vendor/ACE-Step-1.5/examples/text2music/ + simple_mode/).

- **Por qué**: El usuario reportó: revisa lo que ha creado no es lo que pedí. los chips no son géneros, son definiciones que añades extra para el prompt. y yo quiero que las entienda el modelo. También quería saber si los estilos se pueden mezclar (ej: FLAMENCO POP).

- **Resultado**:
  - 11 problemas identificados: cláusulas con palabras NO presentes en el corpus: grit, pulse, rave, hardcore, pumping, hands, liquid, half, long, loud, improvisation.
  - 11 correcciones aplicadas: todas las cláusulas ahora usan vocabulario literal del corpus.
  - Validación: 0 problemas tras re-ejecutar validación contra corpus.
  - Tests: 91/91 pasan (46 test_prompt_style.py + 5 test_realism.py + 40 otros).
  - Sobre mezcla de estilos: SÍ, el sistema permite mezclar estilos (ej: FLAMENCO POP detecta ambos y añade sus captions).

- **Cambios específicos en backend/style_catalog.json**:
  - MODIFICADORES: Voz gritada (with grit -> eliminado), Pulso constante (pulse -> beat).
  - ESTILOS: hardcore holandes (rave -> eliminado), frenchcore (hardcore -> eliminado), uptempo hard dance (pumping/rave -> driving), hard bounce (hands-up -> energetic), drum and bass (liquid -> eliminado), dubstep (half-time -> eliminado), trance (long -> eliminado), metal (loud -> powerful), jazz (improvisation -> solo).

- **Lecciones**:
  1. Las cláusulas deben usar vocabulario LITERAL del corpus, no composicional (aunque suene bien).
  2. El test test_realism.py es la fuente de verdad para validar vocabulario.
  3. El usuario confirma: chips son definiciones EXTRA (no géneros), deben entenderse por el modelo.
  4. La mezcla de estilos SÍ funciona: el prompt del usuario puede contener múltiples géneros y todos se detectan y añaden.

## 2026-10-08 — UI: colores más vibrantes para texto y placeholders

- **Qué**: A petición del usuario, se mejoró la legibilidad y visibilidad de los textos en la UI.

- **Por qué**: El usuario pidió: 'quiero en los CSS las letras en colores más vibrantes... y los placeholders también, más vistosos de leer'.

- **Resultado**: 
  - Texto principal (--text): #ffffff (más brillante)
  - Texto secundario (--muted): #c8c8d4 (más visible)
  - Texto tenue (--faint): #8f8f9a
  - Acento verde (--acc): #d4ff4a (más vibrante)
  - Placeholders: ahora usan var(--muted) con opacity: 0.85
  - Chips: texto en var(--text) en lugar de var(--muted), hover y active más brillantes
  - Labels y títulos: ahora en color var(--acc) para mayor visibilidad
  - Botones: texto en var(--acc), hover con box-shadow verde
  - Inputs: border en var(--acc) al focus, con box-shadow
  - Nav: hover y active en var(--acc) en lugar de var(--text)
  - Build: OK, bundle index-C6yc2Vr9.js (367.52 kB)

## 2026-10-08 — Glosario vacío: backend apagado

- **Qué**: El usuario reportó: 'LAS UIS NO MUESTRAN NADA EN EL GLOSARIO'.

- **Por qué**: El endpoint /music/genre_glossary depende del backend (puerto 8000) y el motor (puerto 8001).

- **Resultado**:
  - Diagnóstico: ambos servicios (8000 y 8001) estaban apagados.
  - Acción: ejecutado scripts/start_local.ps1 para iniciar servicios.
  - Verificación: endpoint /music/genre_glossary responde con 178,572 géneros.
  - Test con curl: devuelve items y styles correctamente.

- **Lección**: El glosario NO usa el catálogo local, depende del backend en ejecución para leer genres_vocab.txt.

## 2026-10-08 (LXXXI) — Glosario de géneros y chips verificados contra el modelo + UI visible + commit

- **Qué pidió el usuario**: «REVISA QUE ESTÉ BIEN EL GLOSARIO DE GÉNEROS Y CHIPS SEGÚN EL MODELO, Y SE VEA EN LA UI. COMITEA Y PUSHEA TODO Y ANOTALO».
- **Auditoría del glosario/chips vs. el modelo (oráculos de datos, no de código)**:
  - `test_realism.py` — 6/6 OK **con datos presentes** (400 captions del fabricante en `vendor/ACE-Step-1.5/examples/` + `acestep/genres_vocab.txt`): cláusulas de chips, captions de estilo, claves de estilo, términos de glosa, VARIANTES del UI y tags de voz usan solo vocabulario que el modelo escribe. No se salta (verificado con `-v`: los 6 salen `ok`, no `skipped`).
  - Suite backend completa: **92/92 OK** (`test_realism` + `test_prompt_style` + `test_genre_glossary` + `test_remix_logic`).
  - Glosa frontend: **9/9 OK** (`node --test src/prompt_gloss.test.js`).
- **Endpoints en vivo (API y motor arrancados con `scripts/start_local.ps1`)**:
  - `GET /music/genre_glossary?q=techno` → 1.374 coincidencias + estilos con caption/bpm/claves (hardcore holandes 180, frenchcore 170…); carga 178.572 géneros de `genres_vocab.txt`.
  - `GET /music/genre_glossary/combine?a=flamenco&b=pop` → «Flamenco pop», «flamenco pop», «pop flamenco» (mezcla de estilos real).
  - `GET /music/style_options?prompt=baterias techno hardcore holandes sin melodias a 180 bpm` → `detected_genre: hardcore holandes`, `suggested_bpm: 180`, chips con `clause` del corpus (four-on-the-floor, double bass drumming…), «Baterías protagonistas» `active: true`.
  - **UTF-8 correcto** en respuesta («Baterías», no mojibake).
- **UI visible**:
  - `GET /` sirve el bundle nuevo `index-BNy2M9oo.js` (368,46 kB / gzip 113,84 kB).
  - El bundle contiene `GLOSARIO`, `GLOSARIO DEL MODELO`, `genre_glossary`, `style_options`, `AÑADIR`, `CONSEJO`, `ESTILO`.
  - `Glossary.jsx` cableado en los 3 puntos de prompt: `Composer.jsx` (CREAR), `RemixActions.jsx` (acciones de remix), `RemixIAPanel.jsx` (otra versión).
- **Limpieza previa al commit**:
  - `backend/requirements.txt` estaba borrado sin registro en la bitácora y la Quickstart de AGENTS.md lo sigue usando → **restaurado** idéntico a HEAD (fastapi, uvicorn, pydub, python-multipart, aiofiles, loguru, httpx; sin edge-tts, que ya se quitó en XLII). Dependencias cruzadas con los imports reales del backend y con el pip list del venv: sincronizado.
  - `.gitignore` ya excluye `backend/job_history.json` (estado de ejecución, se regenera solo).
- **TESTER — PASS (evidencia ejecutada)**: 92/92 backend + 6/6 realism con datos + 9/9 glosa + lint 0 (`eslint src --max-warnings=0`) + build 0 (`index-BNy2M9oo.js`) + API viva con los 3 endpoints respondiendo + motor en `/health` `status: ok` + UI serviendo el bundle nuevo con el glosario dentro. **No es PASS de clic en ventana** (no hay browser tooling en esta sesión): el cableado está verificado por bundle y endpoints, no por un clic humano.
- **REVIEWER — APPROVE con límites**: el glosario depende de la API en ejecución (si los servicios están caídos, la UI lo muestra vacío — ya anotado en la entrada anterior); el «estilo» que añade cada género sale de `style_catalog.json` validado contra corpus. Límite: la calidad de la mezcla de estilos (FLAMENCO POP) se juzga oyendo, no con tests.
- **Commit**: todo el trabajo desde el último commit (`ae80327`) queda commiteado y pusheado en esta entrada.
- **Lección**: el «FALTA: AÑADIR» de un grep sobre el bundle fue falso —`Get-Content` sin UTF-8 mojibakea—; releer con `[System.IO.File]::ReadAllText(..., UTF8)` antes de concluir que algo no está en el bundle.
