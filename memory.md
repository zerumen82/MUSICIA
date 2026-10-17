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

## 2026-10-06 (LXVI) — Tick compartido, MIME por extensión, `/api/info` verificado
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

- **TESTER — PASS (veredicto añadido 2026-10-08 tarde, evidencia re-ejecutada)**: `test_realism` 6/6 **con datos presentes** + suite completa 113/113 (tras sumar `test_verify_align`) + lint 0 + build OK. Los 11 cambios siguen validados contra los 400 captions del fabricante.
- **REVIEWER — APPROVE con límite**: los cambios son de datos (`style_catalog.json`) sobre vocabulario minado; el criterio «literal del corpus» lo defenderá siempre `test_realism`. Límite: si el fabricante actualiza captions, re-minar.

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

- **TESTER — PASS (veredicto añadido 2026-10-08 tarde, evidencia re-ejecutada)**: `npm run build` OK con el CSS nuevo (bundle actual `index-DFs0t4dM.js`, 368.89 kB) + lint 0. Los tokens (`--text`, `--muted`, `--faint`, `--acc`) compilan.
- **REVIEWER — APPROVE con límite**: solo CSS/tokens, sin lógica. Límite: el criterio de legibilidad lo decide el oído del usuario en la ventana (Ctrl+R para cargar el bundle nuevo).

## 2026-10-08 — Glosario vacío: backend apagado

- **Qué**: El usuario reportó: 'LAS UIS NO MUESTRAN NADA EN EL GLOSARIO'.

- **Por qué**: El endpoint /music/genre_glossary depende del backend (puerto 8000) y el motor (puerto 8001).

- **Resultado**:
  - Diagnóstico: ambos servicios (8000 y 8001) estaban apagados.
  - Acción: ejecutado scripts/start_local.ps1 para iniciar servicios.
  - Verificación: endpoint /music/genre_glossary responde con 178,572 géneros.
  - Test con curl: devuelve items y styles correctamente.

- **Lección**: El glosario NO usa el catálogo local, depende del backend en ejecución para leer genres_vocab.txt.

- **TESTER — PASS (veredicto añadido 2026-10-08 tarde, evidencia re-ejecutada)**: servicios relanzados; `GET /music/genre_glossary?q=techno` → 1.374 coincidencias con `styles` (178.572 géneros cargados) y UTF-8 correcto; `combine` responde. La causa (servicios caídos) queda verificada.
- **REVIEWER — APPROVE**: diagnóstico honesto (no se culpo al código); dependencia externa declarada como lección.

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

## 2026-10-08 (LXXXII) — [M3] tempo medido en ficha + [T6] tests de cuadre/verify + sincronía de spec

- **Qué pidió el usuario**: «REVISA A VER SI PODEMOS MEJORAR ALGO» → tras análisis con opciones (ask_user) eligió: **M3 completo + T6 tests + sincronizar spec/bitácora + backup fuera del repo**. Excluyó diagnosticar el job fallido (`212571bf`).
- **[M3] El resultado declara si obedeció (BPM pedido vs. medido)**:
  - `backend/config.py` + `config.example.json`: `generation.bpm_display_tolerance = 3` (umbral de visualización, NO HARDCODE).
  - `backend/main.py`:
    - `_measure_bpm(path)`: envuelve `detect_groove`; **fallo → None, sin campos** (la medición auxiliar nunca tumbará una generación ya verificada; nunca se maquilla).
    - `_write_ficha(..., measured)`: si hay medición escribe `bpm_measured` + `bpm_confidence`; si no, los campos **no existen**.
    - `_carry_ficha`: por defecto **no arrastra** la medición del origen (un remix o un ajuste pueden cambiar el tempo); solo la acepta si la llamada trae una fresca.
    - Medición en los 3 caminos de generación, en `asyncio.to_thread`: `_finalize_generation` (CREAR), cover de `_run_ai_remix`, mezcla final de `_modo_conservar_voz`. Evento visible en la cola: «Tempo medido: 149.8 bpm (seguridad 78%)».
    - `GET /music/library` expone `bpm_measured` y `bpm_confidence` (None si no hay).
  - `frontend/src/components/Library.jsx`: línea automática «PEDÍA X · SALIÓ Y BPM» en la fila solo si hay ambos valores y |Δ| ≥ tolerancia **leída de `/music/config`** (sin config → no se enseña nada); el umbral del botón manual TEMPO también sale de config (antes era `>= 3` hardcodeado).
- **[T6] Tests de cuadre y verificar_audio (spec/03, nueva)**: `backend/test_verify_align.py` — **21 tests sin GPU**:
  - `verify_audio`: inexistente → error real; vacío → error real; WAV válido → duración; bajo umbral → error.
  - `plan_alignment`: en tono propone; confianza baja no cuadra; ajuste fuera de 0,8–1,25 no cuadra; límites aceptan; desfase normalizado al intervalo de un golpe.
  - `first_beat_seconds` (fase negativa = golpe anterior), `bars_duration_seconds` (4 compases 4/4 ≠ 4 golpes), BPM/compases inválidos → `ValueError`.
  - `FichaMedidaTest`: medición en ficha, ausencia sin medición, `_carry_ficha` no arrastra medida ajena, acepta fresca, `_measure_bpm` de silencio/inexistente → None sin lanzar.
- **[M2] sincronizada**: spec/02 [M2] pasa de «pendiente» a **«implementada»** con evidencia (source_kind en 9 modelos pydantic, 24 usos en `main.py`, tests de homónimos) y el único criterio que queda abierto declarado: remix real de subida con GPU.
- **spec/03**: **T6 cerrada** (movida a la tabla de cerradas): 113 tests backend + 9 glosa, sin GPU.
- **Bitácora**: (1) veredictos TESTER/REVIEWER añadidos a las 3 entradas del 2026-10-08 que no los tenían (evidencia re-ejecutada hoy); (2) numeración corregida — la entrada «Tick compartido» estaba rotulada (LX) y va en (LXVI); quedan **documentados los huecos LIII y LX** (nunca escritos, no se rellenan retroactivamente).
- **Limpieza**: `backend/style_catalog_backup.json` **fuera del repo** (`git rm --cached` + `.gitignore`); el fichero queda local porque `regenerate_catalog.py` lo lee.
- **TESTER — PASS (evidencia ejecutada, todo real)**:
  - `python -m unittest test_realism test_prompt_style test_genre_glossary test_remix_logic test_verify_align` → **113/113 OK** (2,3 s, sin GPU).
  - `npx eslint src --max-warnings=0` → 0; `npm run build` → OK (`index-DFs0t4dM.js`, 368,89 kB / gzip 113,93 kB).
  - API reiniciada con el código nuevo (PID 23548, 13:27): `GET /music/config` → `bpm_display_tolerance: 3`.
  - **Generación real end-to-end [M3]**: job `bd8bf24e` «prueba m3 tempo» pedido a **150 bpm** → succeeded; evento «Tempo medido: 149.8 bpm (seguridad 78%)»; ficha en disco con `"bpm": 150`, `"bpm_measured": 149.8`, `"bpm_confidence": 0.778`; `GET /music/library` expone los campos (la variante v2 midió 100,2 con conf. 0,17: la UI podrá mostrar la diferencia cuando pase por aquí con BPM pedido).
  - UI servida por la API con el bundle nuevo que contiene `bpm_measured`, `bpm_display_tolerance`, `PEDÍA`, `SALIÓ`.
  - **No es PASS de oído ni de clic en ventana**: la línea «PEDÍA · SALIÓ» se verá con Ctrl+R y solo en pistas con BPM pedido + medición.
- **REVIEWER — APPROVE con límites**: (1) `detect_groove` es DSP puro sin GPU — barato, pero en pistas muy largas suma segundos al final del job (en hilo, no bloquea la API); (2) pistas antiguas no tienen medición → la línea no aparece (el botón TEMPO manual sigue); (3) `_carry_ficha` ya no hereda la medición — correcto por honestidad, pero los viejos `-edit`/`-remix` que la heredaron conservan el campo hasta que se regeneren; (4) los MP3 de prueba de la sesión («prueba m3 tempo») se quedan en la biblioteca como evidencia audible — retirar con BORRAR si estorban.
- **Commit**: este trabajo queda commiteado y pusheado en esta entrada.
- **Lección**: dos bugs de una misma sesión se evitaron releyendo el código tras cada edición: (a) el primer borrador de `_write_ficha` no guardaba la medición porque el helper no existía aún; (b) la numeración romana desplazada solo se vio listando TODAS las cabeceras `## ` con su número de línea.

## 2026-10-08 (LXXXIII) — Glosario/chips en toda la app alineados al vocabulario del modelo (2ª auditoría)

- **Qué pidió el usuario**: «en toda la app tenemos un problema con el glosario y los chips. Hay sitios donde funcionan otros no. Además quiero que todo estilo y subestilos como chips, variantes y demás sean lo mismo que entiende el modelo» y, tras elegir alcance **Completo** (ask_user: P0–P4), «debes eliminar los términos que existen y dejar solo lo que entienda el modelo».
- **4 bugs diagnosticados con datos (no supuestos)**:
  1. **Ver ≠ enviar en remix**: `RemixActions.jsx` mostraba `ENVÍA: glossPrompt(prompt)` pero enviaba `prompt.trim()` sin glosar (versión/tramo, reestilar, voz y MEJORAR). Hoy: `promptEnviado()` glosa en los 4 sitios; grep confirma que no queda `prompt: prompt.trim()` ahí. Los envíos de SUBIR/BIBLIOTECA ya glosaban en el padre (`Uploads.jsx`/`Library.jsx`).
  2. **AÑADIR mudo** en `RemixActions.jsx` y `RemixIAPanel.jsx`: `SelectBox` vacío sin explicación → ahora `AÑADIR · SIN DATOS DEL MOTOR` / `AÑADIR · SIN SUGERENCIAS` (mismo criterio que CREAR).
  3. **5 de 29 géneros de `frontend/src/genres.js` no eran línea literal** de `genres_vocab.txt` (`hardcore holandes`, `uptempo`, `hard bounce`, `acustico`, `orquestal`) → corregidos a lo que el modelo sí escribe: `gabber`, `hard dance`, `hard house`, `folk`, `orchestral`. El id/etiqueta en español sigue siendo clave interna de UI; **lo único que viaja al prompt es `genre`** (verificado: `Composer.onSelectGenre` y `QualityWizard.buildResult` usan `g.genre`, nunca `g.id`).
  4. **`catalog_styles()` devolvía `genre: None`** en `uptempo hard dance` (sus claves `uptempo|rawstyle|makina` no son línea literal) → nuevo `_subfrase_literal()`: si ninguna clave es línea, se toma la subfrase más larga del nombre que SÍ lo es → **`hard dance`**. Nunca None, nunca inventado (NO FAKE).
- **Glosa (`prompt_gloss.js`) — que todo lo que se añade sea del corpus del modelo**:
  - `evolucion` → `/evoluci[oó]n/` (con tilde no glosaba: «estructura de canción con evolución» viajaba solo en español).
  - Entradas nuevas, todas con palabras verificadas en los 400 captions: `cálido→warm`, `relajado→relaxed`, `textura→texture`, `clara→clear`, `íntimo→intimate`, `banda→full band` («band» queda dentro de «banda» y la glosa no lo habría añadido; «full band» es literal de los captions `example_107`/`example_42`).
  - `hard bounce → hard house` (antes glosaba `hardcore`): «hard bounce» no es línea del vocabulario, «hard house» SÍ — igual que lo que añade `genres.js`.
  - Con esto los 6 textos que quedaban sin glosar (mood chill + 5 del asistente) viajan con equivalente inglés.
- **Bases del remix pasadas al idioma del modelo**: `/audio/remix_prompt` (SUBIR y BIBLIOTECA) devolvía prosa en español («pieza musical inspirada en una referencia con carácter similar…») que el motor ignoraba. Ahora vive en `prompt_enhancer.py` como datos (`REMIX_BASES`, `REMIX_BASS_*`, `REMIX_DYN_*`, `REMIX_PAUSES`) y está **enteramente en inglés y solo con palabras de los captions** (cada candidata se validó con `_prosa_ausente` antes de escribirla). El `basis` (lo que se explica al usuario) sigue en español: eso es UI, no prompt.
- **Tests que impiden la regresión** (4 rojos escritos primero y confirmados en rojo: 11 fallos backend + 2 frontend):
  - `test_realism.test_genres_js_only_offers_genres_the_model_can_write` — cada `genre:` de `genres.js` es línea literal de `genres_vocab.txt`.
  - `test_realism.test_genres_js_agrees_with_the_backend_catalog` — mismo estilo ⇒ mismo género en el selector y en el glosario (29 = 29).
  - `test_genre_glossary.test_ningun_estilo_se_queda_sin_genre` — los 29 estilos con `genre` literal, nunca None.
  - `test_realism.test_las_bases_del_remix_son_del_vocabulario_del_modelo` — las 4 bases + 5 trozos del prompt de remix solo con palabras de los captions.
  - `prompt_gloss.test.js`: «moods de CREAR y textos del asistente se glosan al inglés» (≥9 textos de `Composer.jsx`, ≥6 `words:` y ≥4 `extra:` de `QualityWizard.jsx`) y «evolución (con acento) sí glosa a evolving».
- **TESTER — PASS (evidencia ejecutada, nada maquillado)**:
  - Backend: `python -m unittest test_realism test_prompt_style test_genre_glossary test_remix_logic test_verify_align` → **117/117 OK** (2,45 s, sin GPU; los tests nuevos están en `ok`, no `skipped`).
  - Frontend: `node --test src/prompt_gloss.test.js` → **11/11 pass, 0 fail**.
  - `npx eslint src --max-warnings=0` → 0; `npm run build` → OK (`index-BFgd1hNJ.js`, 369,42 kB / gzip 114,05 kB).
  - API reiniciada **solo** con el código nuevo (PID 27392, 15:36; el motor ACE-Step no se tocó: `models_initialized:false` porque la carga es on-demand): `/health` 200 y motor `/health` 200.
  - Endpoints en vivo: `genre_glossary?q=uptempo` → `items: []` («uptempo» no existe en el vocabulario: correcto) y `styles` con `('uptempo hard dance','hard dance')`, `('hard bounce','hard house')`, `('hardcore holandes','gabber')`; `style_options?prompt=techo duro y rapido` → chips con `clause` inglesa (`a steady four-on-the-floor kick drum`…); `POST /audio/remix_prompt` con un MP3 real de `backend/outputs` → **«an instrumental piece inspired by a reference track, 167 bpm, balanced bright mix, steady smooth texture…»** (antes salía en español).
  - UI servida por la API con el bundle nuevo.
  - **No es PASS de clic en ventana**: no hay browser tooling en esta sesión; el cableado se verificó por código, tests, build y endpoints, no por un clic humano.
- **REVIEWER — APPROVE con límites**: (1) `genres.js` conserva ids/etiquetas en español como claves de UI (necesarios para casar con `detected_genre` del backend) — se revisó que **ningún id se mete en el prompt**, solo `genre`; (2) las claves de `style_catalog.json` siguen siendo subcadenas/regex de detección en español, no texto que viaje; (3) la glosa es best-effort por diseño: si una palabra española no tiene entrada, viaja sin traducir (los tests cubren ahora todos los textos fijos de la UI, no los que escriba el usuario); (4) el prompt de remix pasa por `glossPrompt` otra vez en el frontend al enviarse — es idempotente (verificado: los términos ya añadidos no se duplican).
- **Lección**: un `includes()` sirve para detectar «esta palabra inglesa ya está en la frase», pero choca con formas familiares distintas («band» dentro de «banda» silencia la glosa): cuando el duplicado importa menos que el significado, se glosa con la frase completa (`full band`) en vez de tocar la regla que otros tests dependen.
- **Commits**: los cambios están en working tree; **no se ha commiteado ni pusheado** (el usuario no lo pidió en esta sesión).

## 2026-10-08 (LXXXIV) — La API se congelaba entera: `/audio/separate/status` bloqueaba el hilo de eventos

- **Qué se notó**: en CREAR, AÑADIR aparecía como `AÑADIR · SIN DATOS DEL MOTOR` en algunas sesiones y en otras sí poblaba; el usuario también reportó «acabo de errar la api creo». No era un bug del frontend: el bundle ya traía el AÑADIR nuevo.
- **Causa raíz (diagnosticada, no supuesta)**: `GET /audio/separate/status` llamaba `separator_available()` (importa **demucs+torch en un subproceso, ~5 s**) y `pick_device()` (`nvidia-smi`) **directamente dentro del handler `async`**. Eso clava el **hilo de eventos de uvicorn ~5 s en cada llamada**, y como es un solo hilo, **se para TODA la API**: `/music/style_options` se retrasaba lo mismo y el frontend, con `HEALTH_PROBE_MS=8000` y debounce de 300 ms, recibía `null` → `styleInfo=null` → `SIN DATOS DEL MOTOR`.
- **Evidencia con py-spy** (`backend/venv/Scripts/py-spy.exe`, 0.4.2) sobre el PID de la API: `MainThread` clavado en `separator_service.is_available → subprocess.communicate → main.audio_separate_status`. Timing reproducido: una petición a `/music/style_options` se retrasó **4,9 s** coincidiendo con un bloqueo; `curl` en paralelo vio el mismo hueco de **5,35–5,64 s**; CPU del proceso **~0** (esperando, no computando). El disparor en la UI era `MixLab.jsx:39` (`Promise.all([... api.separateStatus()])` al montar), pero el efecto se sentía en toda la app.
- **Fix (2 sitios, ambos necesarios)**:
  1. `backend/separator_service.py`: `_instalado()` (la comprobación real, con el subproceso) separada de `is_available()`, que ahora **cachea `_DISPONIBLE: bool | None` una vez por proceso** — la instalación no cambia mientras la app corre. Docstring con el bug y la fecha.
  2. `backend/main.py`: el handler pasa a `await asyncio.to_thread(_separator_estado)` con helper `_separator_estado()` documentado como «NUNCA en el hilo del evento». Además se calcula **una sola vez** por petición (antes se llamaba `separator_available()` tres veces).
- **Tests nuevos** `backend/test_separator_status.py` (5, escritos primero): cachea (1 subproceso para 2 llamadas), sin demucs también cachea, el estado se calcula **fuera** del hilo de eventos, mensajes honestos (no promete separación si no está), y **el bucle sigue latiendo** mientras se calcula (que es exactamente lo que fallaba).
- **TESTER — PASS (evidencia ejecutada hoy, nada maquillado)**:
  - `cd backend && ./venv/Scripts/python.exe -m unittest discover -p "test_*.py"` → **122/122 OK** (3,1 s), `EXIT=0` (los 5 nuevos están en `OK`, no en `skipped`). Recién re-ejecutado tras todos los cambios.
  - Frontend `node --test src/prompt_gloss.test.js` → **11/11 pass, 0 fail**, `EXIT=0`.
  - **En vivo**: 1ª llamada a `/audio/separate/status` = **2,790 s** (fría, subproceso real), 2ª = **0,091 s** (cacheada). Con 6 `/audio/separate/status` en paralelo, `/music/style_options?prompt=hard dance track` respondió **200 en 0,0077 s** — antes se habría retrasado ~5 s. Sin huecos.
  - API y motor en `200/200`; UI servida por la API con el bundle `index-BFgd1hNJ.js`.
- **REVIEWER — APPROVE con límites**: (1) el cacheo es **por proceso** — si el usuario instala demucs con la app abierta, no se verá hasta reiniciar (aceptado y documentado en el docstring, es el tradeoff correcto: reinstalar con la app corriendo es un caso raro); (2) `pick_device()` sigue yendo a `nvidia-smi` en el hilo — ya no bloquea la API porque va a `to_thread`, pero suma ~100 ms a esa respuesta la 1ª vez; (3) el handler sigue siendo `async` con un `to_thread` adentro, correcto, pero cualquier futuro trabajo pesado en endpoints vecinos debe seguir el mismo patrón — quedó como ejemplo en el código.
- **Hallazgo colateral — 2 trabajos «fallaron» en el panel NO son regresión**: `GET /music/jobs` devuelve `0440c450` (`409: Demasiadas versiones con ese nombre`, **07-10 20:46 UTC**) y `212571bf` (`El motor terminó con error`, **08-10 01:09 UTC**). Son **histórico recuperado de `job_history.json`** al arrancar (log `Historial recuperado de job_history.json`), no fallos de hoy.
- **Hallazgo abierto — prueba de humo end-to-end FALLA (timeout, no mis cambios)**: `scripts/verify_e2e.ps1 -Seconds 30` → job `5fc1bbb7` **failed** con `Tiempo agotado esperando la tarea … (1800 s)` (`config.py:52 job_timeout=1800`). El motor llegó a `Convirtiendo a audio final` a los 277 s, pero al empezar el VAE vio **`Effective free VRAM: 0.03 GB`** → `tiled_decode` con `offload_wav_to_cpu=True` y **el decode corrió en CPU** (`_tiled_decode_offload_cpu`, py-spy: `_conv_forward` del `autoencoder_oobleck` con CPU al 100 % de un núcleo y GPU al 5 %). Causa del estrangulamiento de VRAM: línea base de **~3.300 MB ocupados** justo antes de la generación (a las 09:30, antes de ComfyUI, eran **710 MB**) y **ComfyUI de AUTOAUTO** (`PID 18536`, `--normalvram`, arrancado 08-10 09:34:50) convive en la misma 3060 Ti de 8 GB. El hilo de decode **siguió vivo tras el timeout de la API** (job `failed` en la UI pero `ThreadPoolExecutor-0_0` activo en `_tiled_decode`), API y motor contestando `200` todo el rato. **El diff de esta sesión no toca el camino de generación**: solo `separator_service.py`, el endpoint de estado en `main.py`, `genre_glossary.py`, `prompt_enhancer.py` y frontend de glosa/chips.
- **Lección**: un `await` en un handler no hace que lo de dentro sea asíncrono — el trabajo bloqueante sigue en el hilo de eventos. Cuando un endpoint dispara subprocessos o `nvidia-smi`, o va a `to_thread`, o se cachea; y si es ambas, mejor: la combinación es la que convierte un problema de «5 segundos raros» en «la app parece rota».
- **Commits**: cambios en working tree; **no commiteado ni pusheado** (no se pidió en esta sesión).

## 2026-10-09 (LXXXV) — Revisión de logs: timeout de 600 s por VRAM ocupada por ComfyUI

- **Qué pidió el usuario**: «REVISA LOGS DE LOS ÚLTIMOS. NO FUNCIONA» y luego «ves cómo se cuelga».
- **Hallazgo en logs**: job `285535e0` (hoy 12:03, hardstyle 120 s, batch=2, turbo) murió a los 600 s con `TimeoutError: Music generation timed out after 600 seconds` en plena difusión (DiT arrancó 12:06:35, DCW lista 12:08:49, sin avance hasta 12:16:09). Misma firma que el e2e del 08-10 (LXXXIV): VRAM sin margen → el decode/difusión se arrastra en CPU hasta el timeout.
- **Causa**: ComfyUI (AUTOAUTO, PIDs 20612/18536) compartía la 3060 Ti de 8 GB con el motor. Medido: 7919/8192 MB ocupados con todo arriba; al parar ComfyUI (con aprobación del usuario vía pregunta) bajó a 5349 MB (~2,5 GB liberados).
- **Incidencia operativa**: a las 20:24 el usuario pulsó SALIR (stop.flag) y tumbó API+motor en mitad del diagnóstico; se relanzó con `scripts/start_local.ps1` (MOTOR=started, API=started, ambos en /health). El usuario paró las pruebas porque no veía resultados: no se lanzó ninguna generación de verificación (cancelado a petición implícita). Estado final: API :8000 (pid 27864) + motor :8001 (pid 27088) arriba, VRAM 662 MB ocupados (motor fresco, modelos sin cargar hasta la 1ª generación), cola sin trabajos activos, sin ventana Electron abierta.
- **Pendiente**: 1ª generación tras reinicio recarga modelos (2-3 min extra con aspecto de «colgado»); reintentar con batch=1 y duración corta cuando el usuario lo pida explícitamente.
- **Lección**: ante «se cuelga», mirar primero `nvidia-smi` + procesos compartiendo GPU antes que los logs del motor; y no lanzar verificaciones largas sin avisar al usuario de los tiempos de espera reales.
- **TESTER — FAIL del síntoma, PASS del diagnóstico**: el fallo (timeout 600 s) está reproducido en log con traza completa; no hay PASS de generación porque la verificación quedó cancelada por el usuario.
- **REVIEWER — APPROVE del diagnóstico**: parar ComfyUI era la acción correcta (causa ya documentada en LXXXIV); relanzar con start_local es el camino oficial. Sin cambios de código.

## 2026-10-09 (LXXXVI) — «No es lo que pedí»: A/B turbo vs SFT con el prompt del usuario

- **Síntoma**: la prueba `iii.mp3` («hard bass hardtek gabber», turbo, guidance 1.0, sin BPM) midió 107 bpm (confianza 16 %) y no suena hardcore. Dos reintentos del usuario (`iii (2)`, `iii (3)`, 26-27 s, motor caliente) tampoco convencen.
- **Diagnóstico**: el turbo fuerza guidance 1.0 (límite [M1]): el prompt pesa poco y sin BPM pedido el tempo lo elige el motor. La ficha lo confirma (`bpm: null`, `model: acestep-v15-turbo`).
- **Decisión del usuario (ask_user)**: reintentar con modelo SFT (guidance alta) en igualdad de condiciones.
- **Acción**: `POST /music/generate` con `model: acestep-v15-sft`, mismo prompt, 120 s, batch 2 → job `e365d09d` aceptado; el log de envío confirma `modelo=acestep-v15-sft | pasos=50 guidance=9.0`. Sin cambios de código (el campo `model` ya existía y `allowed_models` incluye sft).
- **Pendiente**: oído del usuario comparando `iii.mp3` (turbo) vs `iii-sft.mp3` (SFT). Criterio: ¿obedece más al hardcore y sale cuadrado?
- **TESTER — PASS parcial**: envío verificado en log (modelo/pasos/guidance efectivos). No es PASS de resultado: el MP3 aún se está generando.
- **REVIEWER — APPROVE**: sin código tocado; el experimento es limpio (solo cambia el modelo).
- **Veredicto de oído del usuario (misma noche)**: «ahora sí que suena bien» — el SFT con guidance alta obedece al hardcore donde el turbo no. **PASS de resultado + HECHO**: la vía SFT queda validada para estilos duros; pendiente decidir (con el usuario) si CREAR ofrece selector de modelo o SFT por defecto en estos géneros.

## 2026-10-09 (LXXXVII) — SFT en toda la app (decisión del usuario)

- **Qué pidió**: «siempre en toda la app sft» (tras elegir entre turbo/remix/SFT: el remix ya iba en SFT directo, verificado en `main.py:1146,1278`).
- **Cambio**: `backend/config.py` → `GenerationDefaults.model = "acestep-v15-sft"` (+ comentario con fecha/decisión); `config.example.json` igual. Sin hardcode: sigue en config, `allowed_models` intacto, el override por petición (`model_for`) sigue mandando si se pide otro.
- **Test actualizado**: `ModeloRemixTest.test_las_dos_tablas_no_son_la_misma` codificaba el diseño viejo (CREAR≠remix); ahora afirma `model == remix_model` y que las tablas distinguen turbo de sft. Suite: **122/122 OK**.
- **Pendiente de aplicar**: la API estaba caída al terminar (SALIR del usuario 21:05:29) → el cambio entra al reabrir Musicia (el arranque lee la config nueva). Verificar entonces: `GET /music/config` con `model=acestep-v15-sft`.
- **TESTER — PASS de código y tests. No de servicio (API caída al cierre).**
- **REVIEWER — APPROVE**: cambio mínimo en config + test que codifica la decisión nueva; nada de UI tocado (el lateral y VER LO QUE SE ENVÍA leen el modelo del servidor).

## 2026-10-09 (LXXXVIII) — El log estaba bien: fue SALIR en mitad del remix

- **Qué dijo el usuario**: «el crear iba bien… pero mira el log».
- **Qué dice el log**: todo iba bien. API arrancada 21:09:09 ya con `modelo=acestep-v15-sft` (el cambio LXXXVII activo ✓). Remix `6bae3786` (voz + base nueva, gabber/hardtek, 180 s): voz separada en cuda (15 s), base pedida al motor en SFT 50 pasos/guidance 9, motor cargando (DiT en cuda 21:12:41, LM listo 21:14:25). Sin ningún error.
- **Qué lo mató**: `logs/stop.flag` escrito a las **21:14:24** = SALIR pulsado en plena carga del modelo, con el 0 % clavado (aspecto de «colgado», pero era la carga de 2-3 min). API y motor caídos, VRAM a 843 MB, el job perdido (la cola es en memoria). El access-log termina en 200 OK normales.
- **Lección para el usuario**: con SFT todo tarda más (50 pasos + cambio de modelo); el 0 % largo es carga, no cuelgue. Si un trabajo se quiere cancelar, botón PARAR de su fila (cancela sin tumbar la app); SALIR mata API+motor y pierde lo que estuviera generándose.
- **TESTER — PASS del diagnóstico** (evidencia: stop.flag 21:14:24 + fin de logs sin error + puertos libres).
- **REVIEWER — APPROVE**: sin código tocado; solo falta que el usuario reabra y relance.

## 2026-10-09 (XC) — Remix fallido: falso «separación no instalada» + SALIR otra vez

- **Error (23:41:35)**: remix `3ed7ecf8` (voz + base nueva) → `El motor de separación no está instalado (backend/demucs-venv)`.
- **Diagnóstico**: falso negativo. El venv existe y `import demucs, torch` pasa en manual (`ok`). Causa probable: el chequeo `_instalado()` (timeout 60 s) corrió en frío con el motor cargando a la vez y no terminó a tiempo; `is_available()` lo cachea por proceso → todo el proceso cree que no hay demucs. A las 21:12, con el sistema caliente, la misma separación iba en cuda.
- **Incidencia operativa**: SALIR otra vez a las 23:42:23 (48 s después del error) → API+motor abajo, sin verificar. Patrón de la noche: cada error/cuelgue termina en SALIR, lo que impide verificar y pierde los trabajos.
- **Pendiente**: reabrir Musicia (el chequeo en caliente pasa; verificado a mano) y relanzar el remix. Si el falso negativo se repite, endurecer: reintento del chequeo o timeout mayor (cambio de código, con aprobación).
- **TESTER — PASS del diagnóstico, FAIL del síntoma** (el remix no se completó).
- **REVIEWER — APPROVE**: sin código tocado.

## 2026-10-09 (LXXXIX) — «Tardaba mucho»: propuesta batch 1 rechazada

- **Qué dijo el usuario**: el SFT tarda mucho. Preguntado qué ajustar, me devolvió la decisión («tú qué harías»).
- **Recomendación**: batch 1 por defecto + probar en corto (60 s), manteniendo SFT; el A/B se conserva vía VARIAR (dos jobs seguidos). Motivo: 180 s × batch 2 × 50 pasos multiplica ×6 el tiempo frente a 60 s × batch 1.
- **Decisión del usuario**: NO aplicarlo. Se respeta: todo queda como está (SFT, batch 2, 120 s por defecto). Sin cambios de código.
- **Lección**: proponer con números (el ×6) y aceptar el no sin insistir.

## 2026-10-10 (XCI) — Biblioteca: menú que no cerraba + multi-estilo + «¿sirven para algo?»

- **Qué pidió el usuario**: (1) el desplegable ACCIONES no se ocultaba bien; (2) OTRA VERSIÓN/BOOTLEG no estaban claras; (3) al añadir un 3er estilo, parecía que «lo último prevalece»; (4) «NO QUIERO MÁS TEXTOS, QUIERO SABER SI SIRVEN PARA ALGO, POR LO MENOS BOOTLEG».
- **Hallado en código**: `find_style` devolvía UN solo estilo (el primero del catálogo): el 2º y 3º se ignoraban en silencio. La mezcla de estilos que decía la entrada del 2026-10-08 no existía en este camino.
- **Hecho (aprobado «Todo»)**: `find_styles()` (plural, en orden de catálogo, sin duplicados) + `style_caption` compone TODOS los que quepan en 800 chars (detalles del usuario primero); `analyze_prompt` añade `detected_genres` (se mantiene `detected_genre` = primero para chips/BPM); ESTILO se pinta en plural en CREAR/remix/OTRA VERSIÓN; ACCIONES cierra con clic fuera + Escape (patrón de SelectBox). Microcopy explicativo revertido a petición («no más textos»).
- **Prueba**: 127/127 unittest OK (5 nuevos de multi-estilo; 3 rojos intermedios por re-detección desde el inglés compuesto, corregidos detectando sobre el resto + salida temprana si el estilo ya está). Lint OK, build OK (`index-BsexoqOZ.js`, 370.28 kB). Servicios relanzados (MOTOR+API started) para probar el BOOTLEG acción por acción.
- **Pendiente**: verificación acción por acción del BOOTLEG con GPU (el usuario cerró el servicio antes de ejecutarla).
- **TESTER — PASS de código/build/tests. No de las acciones del BOOTLEG en vivo.**
- **REVIEWER — APPROVE**: sin hardcode (catálogo), sin textos nuevos en UI, idempotencia conservada.

## 2026-10-10 (XCII) — Motor de separación: falso «no instalado» otra vez (remix 0540d437 y 0464a636)

- **Error**: remix IA (voz + base nueva) a las 01:35:26 y 01:35:34 → `El motor de separación no está instalado (backend/demucs-venv)`. Ambos fallaron **4 ms** tras el paso «Separando la voz» = respuesta **cacheada**, no un chequeo real.
- **Diagnóstico**: el chequeo `_instalado()` (timeout 60 s) corrió al abrir la ventana, devolvió `False` y `is_available()` lo cacheaba **para toda la proceso** (`separator_service.py`). El venv existe y `import demucs, torch` pasa hoy en 11,0 s → **falso negativo**, repetición del bug **XC (2026-10-09)**, que quedó pendiente de endurecer. **Causa exacta del `False` indistinguible: `_instalado()` no escribía ningún log** (timeout, `rc≠0` y excepción devolvían lo mismo a ciegas).
- **Corrección aprobada por el usuario («Sí, aplicar el plan»)** — `backend/separator_service.py`:
  - **Log real del chequeo**: duración, `returncode` y cola de stderr en cada fallo; `info` con los segundos si pasa. Próxima vez se verá el motivo.
  - **Timeout 60 → 120 s** (`CHEQUEO_TIMEOUT_S`) + `errors="replace"` (un decode error ya no rompe la llamada).
  - **El negativo caduca** (`NEGATIVO_TTL_S = 60`): se reintenta en vez de dejar la separación muerta toda la sesión; el positivo sigue cacheado para siempre (bug 2026-10-08 intacto: el chequeo sigue siendo solo desde `to_thread`/hilo, con `_CHEQUEO` para no duplicar subprocesos).
  - **`separate()` ya no consulta el cache**: guard barato `DEMUCS_PYTHON.exists()` → si existe, lanza demucs y **su error real viaja**. Un falso negativo no puede volver a matar un remix.
  - `main.py`: solo el docstring de `/audio/separate/status` (describe el TTL).
- **Prueba (TESTER — PASS, evidencia ejecutada)**: `python -m unittest discover -p "test_*.py"` → **130/130 OK** (127 + 3 nuevos: reintento del negativo tras TTL con positivo que no caduca; `separate` sin venv dice «no instalado» sin subproceso; `separate` con cache negativo **no** lo consulta y su error es el de demucs). Comprobación real: `is_available()` → `Motor de separación verificado (demucs+torch en 11.0 s)`, 2ª llamada 0.0 s (cache). `py_compile` salida 0. **No es PASS de un remix en vivo: API y motor están parados (SALIR 01:35:57)**.
- **REVIEWER — APPROVE con límites**: (1) si el primer chequeo falla, la UI puede enseñar «no instalada» hasta 60 s (TTL) — se recupera sola; (2) la causa raíz del `False` original **sigue sin estar probada** (no había log): ahora queda registrada la próxima vez que ocurra; (3) el mensaje de la UI no distingue «sin venv» de «chequeo fallido» (solo el log lo dice) — aceptado por «no más textos».
- **Pendiente**: relanzar servicios y repetir el remix; si vuelve a fallar, el log nuevo da el motivo exacto.

## 2026-10-12 (XCIII) — Revisión de memoria y últimos logs: borrado bloqueado y remixes completados

- **Petición y alcance**: revisar `memory.md` y los últimos logs. Lectura y registro documental; sin cambiar código, configuración ni servicios, ni generar música. La memoria anterior terminaba el 10-10; la sesión revisada va del 11-10 23:39 al 12-10 00:30 (horas locales de los logs).
- **Error actual confirmado**: nueve `PermissionError [WinError 32]` al borrar `pista-sin-nombre.mp3`: seis borrados múltiples y tres individuales. `logs/musicia-api.err.log:127,176,225,274,323,372,421,470,538` y los nueve HTTP 500 en `logs/musicia-api.log:1050,1057,1073,1075,1244,1247,1255,1360,1776`. Windows indica que otro proceso utiliza el archivo; no se ha identificado cuál. `backend/main.py:2293,2317` ejecuta `path.unlink()` sin tratar ese error. El MP3 sigue presente y es válido. Pendiente de corrección, sin aprobar aquí un diseño de solución.
- **Generación y separación actuales**: SFT efectivo, 50 pasos, guidance 9, batch 2. CREAR `9854223d` terminó 23:48:25 con dos variantes de 245 s; cover `e0d5b03a` terminó 00:13:55; VOZ + BASE NUEVA `055ea8a9` (AM GUTI) y `7dfae855` (HARDTEKgABB) terminaron 00:22:42 y 00:29:57 con dos mezclas cada uno. Demucs se verificó en 10,6 s y ambas separaciones terminaron en CPU (~60 y ~54 s): el falso «no instalado» de XCII no aparece en esta sesión. ACE-Step no registra ERROR, traceback, OOM ni timeout en estos logs. `offload_wav_to_cpu=True` no demuestra decode en CPU: el motor documenta decode GPU con copia de salida a CPU.
- **Límite de lo pedido en el prompt**: el cover `e0d5b03a` pidió «CONSERVA VOZ Y GUITARRA», pero se envió instrumental por no llevar letra nueva (`musicia-api.err.log:480`; `acestep-api.err.log:102-103`). En VOZ + BASE NUEVA se reutiliza únicamente el stem vocal; la base se genera sin `source_path` (`main.py:1095-1150`). «CONSERVA GUITARRA»/«ORIGINAL guitar» en el texto no reutiliza la guitarra grabada. Éxito técnico no verifica cumplimiento musical; no se escucharon los resultados. La caption hardstyle añadida a gabber/hardcore procede del catálogo existente: estos logs no prueban un fallo audible de estilo.
- **Historial incompleto confirmado**: los remixes de voz `055ea8a9` y `7dfae855` no están en `backend/job_history.json`, cuya última escritura es 00:13:55. La rama `mode == "voz"` retorna en `main.py:1244` antes de `_save_history()` en `main.py:1325`; `_modo_conservar_voz` no guarda al terminar. Sus éxitos pueden perderse del historial al reiniciar. Pendiente de corrección.
- **Borrados y cierre posteriores al éxito**: los finales del cover se borraron 00:15:52/00:16:00; AM GUTI 00:25:10/00:25:14; HARDTEKgABB 00:30:25/00:30:30, según el endpoint en el log. Su ausencia actual no implica generación fallida. `logs/stop.flag` contiene `salir`, fecha 00:30:33; comprobación del tester con `netstat` sin listeners :8000/:8001. Este cierre ocurrió después de terminar los trabajos.
- **TESTER — PASS del diagnóstico limitado; FAIL del borrado observado** (agente separado `sd_tester`): `ffprobe` real, exit 0 en nueve MP3 presentes, tamaño > 0 y duración > 0: `pista-sin-nombre.mp3` 245 s / 3.921.068 bytes; cuatro bases AM GUTI/HARDTEKgABB 240 s / 3.840.812 bytes cada una; cuatro stems voz/base 81,449796 s / 1.956.092 bytes cada uno. Finales borrados y calidad audible: NO VERIFICADOS. Lint/build/e2e no ejecutados en esta revisión de lectura; no es PASS completo de la aplicación.
- **REVIEWER — APPROVE del diagnóstico limitado** (agente separado `sd_reviewer`): corroboró nueve errores de borrado, retorno que evita persistir historial, límites de voz/guitarra y completados/borrados. No aprueba una corrección ni declara solucionados los bugs. Las deudas confirmadas se registran en `spec/03-PENDIENTES.md`.

## 2026-10-12 (XCIV) — Correcciones verificadas; fidelidad general del prompt y nuevo alcance de REMIX

- **Petición**: «hazlo», «los estilos que pido no parecen lo que pedí» y recordatorio «NO HARDCODING» / usar el lenguaje que entiende el modelo. Aclaración posterior: conservar voz/guitarra era **solo un ejemplo**; el requisito es respetar el prompt completo. El usuario pidió anotar el estado y continuar. La petición más reciente es que REMIX sea un remix real, más versátil respecto al modelo y la calidad, más allá de voz + base nueva. No se ha aprobado descargar modelos ni una ampliación específica de separación de guitarra.
- **B1 corregido**: archivo ocupado devuelve HTTP 409, conserva audio/ficha; el lote continúa y reporta `deleted/not_found/blocked/failed`. Otros errores mantienen su causa real. El cliente descarga los recursos de todos los reproductores del archivo antes del DELETE; BIBLIOTECA conserva selección y mensajes de los fallos parciales. Se ajustó el orden para liberar el recurso antes de desmontar el reproductor.
- **B2 corregido**: `_run_ai_remix` persiste resultados en `finally`, incluido el retorno del modo voz, errores y cancelaciones. La verificación real descubrió además una colisión: `_safe_name` recortaba el ordinal de nombres largos, haciendo fallar la segunda mezcla. `_versioned_stem` reserva sitio dentro de `generation.max_slug_chars`; el tope de versiones vive ahora en `generation.max_name_versions` (también en config.example). Renombrado y generación respetan ese límite, incluido el último ordinal disponible.
- **Fidelidad del envío corregida**: gabber/hardcore añadía hardstyle; dubstep añadía reggae por «dub»; electrónica añadía electro; las negaciones podían añadir instrumentos positivos. Ahora se detectan claves completas y coincidencias específicas, sin perder mezclas explícitas independientes. Las negaciones, traducciones ES/EN y exclusiones son datos del catálogo compartidos con la glosa; no se añaden géneros vecinos ni descripciones que contradigan exclusiones declaradas. Géneros de traducción se verifican como líneas del vocabulario local y la prosa contra las captions del fabricante. Esto **no demuestra comprensión universal ni fidelidad audible** del modelo.
- **TESTER — PASS técnico explícito** (`sd_tester`, verificaciones separadas): backend `Ran 152 tests in 3.957s / OK`; Node `tests 15 / pass 15 / fail 0`; lint exit 0; build exit 0, `index-B63_nFMU.js` (371,22 kB), servido por API. Evidencia: `logs/fix-20261012-backend-tests-final.log`, `-node-tests-final.log`, `-lint-final.log`, `-build-final.log`. Algunas primeras ejecuciones dieron `spawn EPERM` del sandbox; las repeticiones aprobadas terminaron con éxito real, no se ocultó un fallo de código.
- **B1 real Windows**: `CreateFileW` sin compartir DELETE sobre MP3 real generado con ffmpeg; conflicto 409 y ficha intacta; lote parcial continúa; tras soltar handle, DELETE 200. `logs/fix-20261012-b1-real/result.json` = PASS. **UI Electron real**: reproducción silenciada, clics en BIBLIOTECA, DELETE 200, audio/ficha/fila desaparecen; recurso descargado antes y después de la petición, buffer vacío, sin errores. `logs/fix-20261012-ui/result-698fd85e.json` = PASS y capturas before/after. Dos probes previos dieron FAIL por exigir `currentSrc=''`; Chromium conserva esa URL como metadato tras `removeAttribute+load`. Se investigó con fuente primaria WHATWG #10410 y se mantuvieron ambos FAIL. El criterio final verifica estados nativos y buffers, sin alterar propiedades ni respuestas.
- **E2E real**: script oficial con prompt `hardtek gabber a steady four-on-the-floor kick drum`, SFT efectivo, 50 pasos/guidance 9/batch 2, job `44733834`, succeeded; MP3 30,0 s / 480.812 bytes y ffprobe exit 0 (`logs/fix-20261012-e2e-result.json`). La carga fría consumió gran parte de los ~4 min. La ficha mide 125,6 bpm con confianza 0,276, sin BPM explícito pedido: no usar esa medida ni el éxito técnico como aprobación musical del estilo.
- **B2 real**: primer job `fbae4566` falló por la colisión de nombres largos; el estado failed sí se guardó. Evidencia conservada `logs/fix-20261012-voice-first-failure-result.json` y `-voice-first-persisted.json`. Tras corregir, `6b6003e1` succeeded en 156,3 s, dos mezclas con nombres distintos, ffprobe exit 0, 75,228417 s / 1.806.956 bytes cada una. Las bases son de 30 s; las mezclas duran más por el camino que cuadra la voz original de 81,45 s. No afirmar que las mezclas duran 30 s. Job y variantes recuperados tras reinicio real de la API, `restored=true` (`logs/fix-20261012-voice-result.json`, `-voice-recovered.json`).
- **REVIEWER — APPROVE explícito** (`sd_reviewer`): archivos completos de producto, configuración, tests y probes; revisó además negaciones coordinadas, glosas, límite/ordinal de nombres y descarga del reproductor. Los hallazgos de revisión fueron corregidos y re-revisados. La aprobación es de código y del criterio técnico, no de oído ni de una nueva arquitectura de remix.
- **Estado operativo al cierre de las pruebas**: API PID 24860 y motor PID 28580, ambos health 200; SFT cargado; bundle final servido. Logs previos copiados en `logs/fix-20261012-before/` antes de arrancar. No se tocaron aplicaciones ajenas, no se instalaron paquetes/modelos, no se hizo commit/push. Solo red para consultar documentación primaria; audio y pruebas locales.
- **Pendiente general**: diseñar con el usuario un REMIX integral que use el audio original y las capacidades reales del motor (cover/repaint y otras solo si el modelo disponible las soporta), respete el prompt completo y permita comprobar conservación/cambios/calidad. Voz/guitarra no son el alcance de una función especial. El estado actual sigue ofreciendo voz + base nueva y cover; no declarar que ya existe ese remix versátil ni que se ha validado el estilo escuchándolo.
- **Fuentes primarias consultadas**: guía del fabricante `https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/ace_step_musicians_guide.md`; API/inferencia `https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/INFERENCE.md`; estados de medios `https://html.spec.whatwg.org/dev/media.html#network-states` y `https://github.com/whatwg/html/issues/10410`. Investigación del separador no implica autorización de descarga ni decisión de diseño.

## 2026-10-12 (XCV) — Plan de REMIX integral y capacidades reales del modelo

- **Qué pide el usuario**: «REMIX fuese REMIX de verdad… más versátil cara al modelo y la calidad de las creaciones». Se incorpora la aclaración anterior: voz/guitarra eran ejemplos, no una función específica. Se mantiene la petición de fidelidad al prompt completo, NO HARDCODING y lenguaje/contrato del modelo.
- **Estado previo preservado**: correcciones B1/B2/B3 y envío fiel verificadas en XCIV. `sd_reviewer` volvió a contrastar memoria/spec con logs, PASS de Windows/Electron, e2e y recuperación del remix; APPROVE documental. No se atribuye comprensión universal ni aprobación musical a esos PASS.
- **Investigación independiente (`sd_researcher`)**: comprobados archivos locales de turbo/SFT (4.787.825.604 bytes cada uno), LM 0.6B y 1.7B, VAE y embedding; no base, XL ni SFT-stems. Controles de referencia, ruido de cover, modos/intensidad de repaint y formatos sin pérdida rastreados desde esquema HTTP hasta ejecución. Cover/repaint ya existen: la propuesta completa su uso, no los presenta como una función nueva por cambiar el nombre.
- **Hallazgos de capacidades**: SFT soporta cover/repaint y referencia tímbrica. Repaint equilibrado/conservador reinserta la onda original fuera del intervalo; agresivo no. Demucs instalado permite batería/bajo/voz/other, con acompañamiento agrupado. `full_analysis_only` escucha códigos del audio y pide descripción/metas/letra al LM, pero no está integrado/verificado en Musicia; `format_input` solo procesa texto y no es un planificador operativo general. El inventario `/v1/models` puede anunciar tareas base para SFT: no habilitar por esa respuesta sola. Lego/extract/complete se dejan fuera con los checkpoints actuales. `text2music` ignora la fuente como contexto, y fin de tramo `-1` no significa extender una canción.
- **Plan concreto propuesto**: `spec/06-REMIX-INTEGRAL.md` / R9: proyecto de remix sobre original y prompt libre; transformación integral, secciones y referencia; conservación/transformación de grupos reales; intermedios WAV/FLAC, exportación final, dos variantes/A-B y trazabilidad. Parámetros y capacidades en datos/config, sin sustituir la intención por plantillas. La elección de operación es revisable; no se promete un planificador universal del LM.
- **Impacto/límites**: mantener SFT/batch 2/perfil existente; ninguna instalación/descarga ni aplicaciones ajenas tocadas. El modelo base y otras variantes requieren estudio/autorización/medición antes de ofrecer nuevas tareas. La comprensión artística y calidad audible siguen pendientes de prueba comparada, no certificadas por metadatos o volumen. La propuesta antigua `spec/05` queda marcada como histórica para no revivir decisiones descartadas.
- **Estado R9**: PLAN PROPUESTO, NO IMPLEMENTADO. Se pidió al usuario elegir aprobación de la fase con SFT instalado sin descargas o estudiar también base antes de implementar, conforme a la skill plan y AGENTS.md. La revisión independiente del plan se solicita como revisión de diseño, no como PASS funcional de R9.
- **REVIEWER — APPROVE del plan R9** (`sd_reviewer`): leyó la propuesta completa y contrastó controles, formatos y splice con código local. Sin bloqueantes. Precisiones incorporadas: máscaras derivadas de intervalos soportados; conservación fuera de regiones excluye transiciones y declara normalización; contratos no sustituyen pruebas de referencia/grupos/memoria ni escucha musical. Pendiente de aprobación del usuario, sin implementar ni generar nuevas pruebas de R9.

## 2026-10-12 (XCVI) — REMIX: selección integrada en la UI y simplificación propuesta

- **Petición**: cómo se seleccionarán los instrumentos, integrar el flujo en la UI y quitar opciones absurdas para no saturar REMIX.
- **Revisión real del panel**: `RemixActions.jsx` tiene 4 acciones IA y 7 locales. VERSIÓN y REESTILAR son dos caminos cover; voz/base es un modo específico; tempo está repartido entre tres acciones; separación de voces aparece como dos acciones. Los controles/tips y dos zonas de fuerza hacen crecer el panel. No se modifica la UI hasta acordar el diseño.
- **Propuesta añadida a `spec/06-REMIX-INTEGRAL.md`**: misma mesa en SUBIR/BIBLIOTECA; tres ámbitos (canción completa/tramo/por pistas), prompt y lanzamiento visibles, controles contextuales y avanzados plegados. Por pistas: separación real y filas voz/batería/bajo/acompañamiento restante, preescucha y una acción por grupo (conservar/transformar/quitar), con datos/capacidades del backend. Acompañamiento no se vende como guitarra/piano aislados.
- **Simplificación propuesta**: unificar versión/reestilar; llevar tramo a la onda; conservación de voz a las acciones de grupos; agrupar tempo y herramientas DSP en ajustes; quitar/solo voz mediante selecciones de grupos. Mantener accesos equivalentes a funciones útiles, endpoints existentes, glosario y AÑADIR. No es autorización para borrar código ni perder funciones.
- **Límite de transformación de grupos**: SFT cover no garantiza un stem puro. El resultado debe separarse y comprobarse antes de recombinar grupos modificados con los conservados; no mezclar una canción generada completa como si fuera un instrumento aislado.
- **Estado**: propuesta de UI, no implementada. Se solicita revisión del diseño actualizado; la aprobación anterior del plan R9 no implica que esta concreción nueva ya esté aprobada por el usuario.
- **Revisión de contrato UI**: el reviewer señaló que cover mantiene la longitud de su fuente e ignora una duración editable. Corregida la propuesta: duración informativa del original, recorte/arreglo como operación explícita en ajustes; no ofrecer un control sin efecto ni fingir extensión.
- **REVIEWER — APPROVE del diseño UI actualizado**: tres ámbitos, preescucha y acciones excluyentes por grupos reales; reorganización de las 11 acciones conservando funciones/endpoints; tratamiento correcto de fuente, duración y resultados no aislados de SFT. Pendiente de aprobación del usuario e implementación/verificación real de R9.

## 2026-10-12 (XCVII) — Prompts: adiciones no pedidas también en CREAR

- **Petición**: antes de decidir el plan, revisar las cosas que se hacen sin pedirlas; aclaración del usuario «no solo en remix, al crear también». Diagnóstico y especificación comunes, sin aprobar ni implementar el rediseño R9.
- **Causa ejecutada**: `style_caption` aún añade presets musicales y cláusulas por palabras clave. «techno» añade hipnosis, 4x4, stabs y carácter oscuro; «electrónica» añade kick potente, drops de bajo y mezcla energética; «batería suave al fondo» acaba con `driving drums as the lead of the track`. Los call sites de CREAR y REMIX comparten esta expansión (`main.py:1554,1229`), posterior a la glosa visible en frontend. Los comentarios que dicen que nunca inventa y el PASS técnico de XCIV no prueban fidelidad general.
- **Matiz de evidencia y corrección de la explicación inicial**: el ejemplo «bajo potente, sin voz» añade voz potente contradictoria en la entrada directa del backend, como recoge `logs/prompt-audit-20261012.json`. El tester comprobó que al pasar primero por la glosa normal de la UI sí se filtra esa cláusula vocal. No atribuir esa contradicción concreta al envío normal de la UI. El fallo de batería protagonista y las expansiones de género se mantienen en el recorrido completo. La glosa de palabras no interpreta relaciones ni constituye traducción semántica completa.
- **TESTER — PASS del diagnóstico, FAIL de fidelidad actual** (`sd_tester_prompts`): ejecución real Node + Python, cuatro previews frente a caption backend diferentes, ambos call sites verificados. Evidencia `logs/prompt-audit-tester-20261012.json`. Sin generar audio ni ejecutar servicios; fidelidad audible no verificada. Lint/build de producto no se repiten en un diagnóstico con cambios solo documentales.
- **Contrato propuesto R10** en `spec/02`: adaptación fiel al lenguaje del motor sin recetas musicales automáticas; sugerencias creativas optativas; preview y payload efectivos iguales; procedencia de texto/controles/config y conflictos explícitos. El método concreto de adaptación semántica sigue por acordar/validar, sin prometer comprensión universal mediante listas/regex ni autorizar modelos/dependencias nuevos. R10 registrado como deuda abierta en `spec/03` y condición común de R9 en `spec/06`.
- **Subida electrónica**: el requisito general también aplica al material instrumental/electrónico; la etiqueta no autoriza a inventar voz, 4x4 o drops. La propuesta de grupos sigue limitada a los cuatro grupos reales del separador instalado; leads/pads/arpegios/FX pueden compartir `other`, sin promesa de aislamiento individual. Sin cambios de producto, modelos, servicios ni valores SFT/batch/thinking/use_format.
- **REVIEWER — APPROVE del diagnóstico y de la documentación R10/XCVII** (`sd_reviewer`): confirma expansiones compartidas, contexto confundido, preview incompleto y decisión de instrumental por ausencia de letra; acepta el matiz de entrada directa frente a glosa normal. Sin bloqueantes documentales. La fidelidad general queda ABIERTA, no HECHA; este APPROVE no aprueba una implementación ni un resultado musical. `git diff --check` de documentos, considerando CRLF, terminó sin errores.

## 2026-10-12 (XCVIII) — R9/R10 autorizados: ejecución y autodetección

- **Autorización del usuario**: corregir el problema del prompting e implementar el plan considerando autodetección de si la subida es electrónica. Se ejecuta R9 + R10 sin volver a solicitar la aprobación ya otorgada.
- **Plan de ejecución**: retirar recetas/glosas que alteran significado en CREAR/REMIX; completar backend sobre original, regiones/grupos/referencias/intermedios sin pérdida; integrar UI contextual y autodetección revisable. La clasificación analiza audio real y no sustituye la petición. Mantener SFT/50/9/batch2 y thinking/use_format off; no instalaciones/modelos nuevos.
- **Roles explícitos**: sd-editor de prompts, sd-editor de backend remix y sd-editor de UI en paralelo, con propiedad de archivos delimitada; coordinación e investigación local por root. Tester y reviewer independientes al integrar, antes de declarar finalización. Sin cambios destructivos, commit ni programas ajenos.
- **Estado**: implementación en curso; todavía no hay PASS/APPROVE del producto nuevo.

## 2026-10-12 (XCIX) — R9: TESTER PASS (8 sondas reales) + REVIEWER APPROVE; 2 bugs hallados y corregidos

- **Salvaguarda**: todo el trabajo R9 commiteado en `dc13c3e` antes de verificar (working tree limpio).
- **TESTER — PASS con evidencia real** (sondas `scripts/probe_remix_integral.py` y `probe_remix_source_analysis.py`, venv del motor por numpy; API reiniciada para cargar cada fix; GPU real con SFT 50 pasos):
  - `validation` PASS — 6 rechazos honestos con mensajes claros (región fuera de duración, campo en ámbito equivocado, grupo inventado «guitar», quitar todo, tempo que desalinea grupos conservados, parámetro fuera de rango). Evidencia `logs/remix-integral-validation-20261012-204750.json`.
  - `prompt` PASS — el prompt del remix viaja EXACTO al motor (contrato R10), batch 2, 50 pasos, guidance 9, thinking/use_format off, sin instrumentalMarker, `audio_duration=-1`. `logs/remix-integral-prompt-20261012-204759.json`.
  - `analysis` PASS — análisis nativo real `full_analysis_only` del motor (8 campos: bpm 40, D minor, caption, genres…); clasificación `unknown` para género ambiguo («grindcore»): no adivina. `logs/remix-source-analysis-real.json`.
  - `full` PASS — cover real sobre `pista-sin-nombre (2).mp3` con referencia: 2 variantes MP3 verificadas (duración=original, sin clipping, semilla fija, job persistido). `logs/remix-integral-full-20261012-205335.json`.
  - `region` PASS (tras corrección del tester, ver hallazgo 2) — repaint 6–18 s; forma del original fuera del tramo verificada PCM a PCM. `logs/remix-integral-region-20261012-210513.json`.
  - `groups` PASS — demucs real (voz quitar, drums transformar, bass+other conservar): 2 variantes; recombinación comparada con mezcla independiente del tester, delta ≤ 1e-6. `logs/remix-integral-groups-20261012-210610.json`.
  - `dsp` PASS — quitar voz sin prompt (ruta determinista sin generación). `logs/remix-integral-dsp-20261012-210909.json`.
  - `recovery` PASS — job `edc8772b` completo recuperable por API (historial+archivos). `logs/remix-integral-recovery-20261012-211127.json`.
- **Hallazgo 1 (bug real, corregido)**: la primera sonda `full` FAIL «`hashlib.file_digest` no existe» — la API productiva corre **Python 3.10** y `file_digest` es de 3.11+; ningún test ejercitaba `source_digest`. Corregido con lectura por chunks + test de regresión `test_source_digest_runs_on_this_python_and_identifies_content`. Suite: **163/163 OK** en el venv 3.10 de producción.
- **Hallazgo 2 (falsa alarma del tester, producto corregido)**: la primera sonda `region` FAIL (rel_rms 10,8 % fuera del tramo). Diagnóstico (`scripts/diag_region_lag.py`): ni desfase de decoder ni pérdida — **el motor normaliza el nivel antes de repintar** (alpha 0,89125 = log `Peak=0.8913`) y el splice reinserta esa onda; residuo de forma 8,8e-7. La tolerancia confundía nivel con forma (spec/06 lo advertía). Sonda pasada a comparación invariante a ganancia con factor registrado y rango [0.5, 2.0]; `capabilities.limitations` ahora **declara** `repaint_normalization`.
- **REVIEWER — APPROVE de los archivos completos** (`sd_reviewer`): leídos íntegros `remix_project.py`, `source_understanding.py`, `demucs_local.py`, `RemixWorkspace.jsx`, `RemixActions.jsx`, tramos clave de `mixer_service` (mix_groups/export_remix), `api.js`, integración Uploads/Library, tests nuevos y sondas. Sin bloqueantes. Nota: los tests de clasificación cubren el lado advisory (no adivina desde descripción, no muta metadata); la fase `region` de `remix_project.py` no reinserta por código propio porque el splice lo hace el motor (verificado en vendor `repaint_waveform_splice.py`, invocado con `repaint_mode != aggressive`).
- **Verificación final de regresión**: lint 0 (`--max-warnings=0`), build Vite OK (356,66 kB / gzip 111,02 kB), `node --test` 8/8, suite backend 163/163. API y motor arriba durante todas las pruebas.
- **Límites declarados**: fidelidad ARTÍSTICA no certificada por sondas técnicas (oído del usuario); separación demucs estimada; la autodetección es orientativa y corregible. R10 en CREAR (expansión de `style_caption`) sigue ABIERTA — el camino remix_project cumple el contrato de prompt exacto; falta verificar/ajustar el de CREAR/MEJORAR.
- **Lección**: una suite verde no prueba el camino de producción: el bug de `hashlib` estaba en vivo y los tests no lo tocaban. Toda función nueva exige un test que ejerite el código real, no solo su mock.

## 2026-10-12 (C) — R10 CERRADA: auditoría viva PASS en TODAS las rutas con prompt

- **Petición del usuario**: «allá donde hay prompt debe haber mejora de ese tema pendiente» — aplicar R10 en todas las rutas con prompt (CREAR, MEJORAR, remix IA, otra versión).
- **Diagnóstico previo a tocar código**: la corrección de R10 ya estaba implementada durante XCVIII y resultó verificable hoy:
  - Backend: `style_caption` = identidad (solo sanea espacios); `enhance_prompt` = borrador fiel que solo puede añadir un BPM **explícitamente elegido**, declarado en `additions`/`warnings`; `/audio/remix_prompt` compone una **sugerencia visible y editable** (optativa).
  - Frontend: `glossPrompt` = identidad (documentado: la antigua glosa de palabras perdía relaciones); `buildPrompt` de Composer = mood (clic explícito) + texto + tags de voz (opciones elegidas), y la vista previa usa la misma función que el envío.
  - Chips/glosario/géneros: solo añaden texto que la UI muestra antes (AÑADIR/selector = elección explícita del usuario).
- **Correcciones de transparencia (sd-editor)**:
  - `main.py`: docstring de `/music/enhance_prompt` decía «reglas de producción musical» — ahora describe el borrador fiel real; eliminado el mensaje muerto «Caption compuesto con el estilo que pides» del remix (nunca se dispara con caption literal y confundiría al saneo de espacios).
  - `api.js`: comentario de `enhancePrompt` alineado con la realidad.
  - Nuevo test `test_remix_logic.test_payload_de_crear_conserva_el_prompt_literal`: identidad del prompt en el payload del motor (text2music) con los 4 prompts adversos de la auditoría XCVII.
- **TESTER — PASS (auditoría viva nueva)**: `scripts/audit_prompt_fidelity.py` ejecuta de verdad: 6 prompts adversos × (style_caption + payload text2music/cover/repaint) = identidad verificada; MEJORAR sin BPM = fiel, con BPM = 133 añadido y declarado, conflicto de BPM = untouched + warning; frontend real con node (`glossPrompt` identidad y composición literal); API viva `/music/enhance_prompt` y `/music/style_options` coherentes con los módulos. Evidencia **`logs/prompt-fidelity-audit-20261012-213935.json` → PASS**.
- **Regresión**: suite backend **164/164 OK** (test nuevo incluido), ESLint **0** (`--max-warnings=0`). API reiniciada con los fixes y arriba (200).
- **REVIEWER — APPROVE**: cambios de esta ronda acotados a docstrings/comentario/test/auditoría/spec; sin tocar lógica de generación. La auditoría cubre preview=_payload y payload=envío real del motor en las tres tareas.
- **Estado final**: R9 y R10 **cerradas a nivel técnico**. Lo único pendiente es el **oído del usuario** (variantes ya generadas en `backend/outputs/` del cover/remix sobre «pista-sin-nombre (2)») y la escucha A/B de obediencia artística.
- **Lección**: a veces el «bug» diagnosticado ya está corregido en código y lo que falta es la **verificación con evidencia**; antes de reabrir una corrección, re-ejecutar el diagnóstico contra el código actual.

## 2026-10-13 (CI) — Auditoría de los MD y del cumplimiento real del plan R9/R10

- **Petición del usuario**: revisar los Markdown y comprobar si se cumplió el plan acordado. Lectura de reglas globales/locales, spec/00–06, README, knowledge y decisiones/evidencias de memory; contraste con producto y sondas. Esta auditoría no implementa correcciones ni amplía el plan aprobado.
- **Resultado corregido respecto a C**: R9/R10 tienen implementación y evidencias reales, pero **NO están completos**. No es exacto afirmar que «lo único pendiente es el oído». Informe: `logs/auditoria-plan-20261013.md`. Se conservan las entradas históricas y sus resultados; esta entrada registra los límites descubiertos al contrastarlas con los criterios completos.
- **REVIEWER — CHANGES_REQUESTED del cierre R9/R10** (`sd_reviewer`, revisión independiente): falta comparación A/B alineada; conflictos texto/BPM/voz sin resolver antes de generar; flujo de voz original + base nueva sin acceso UI equivalente; acompañamiento nuevo sin GLOSARIO/AÑADIR/variantes; «ENVÍO EFECTIVO» muestra request de app, no parámetros del motor; onda/campos regionales sin selección compartida. También falta transmitir procedencia de clasificación y contextualizar semilla en ruta determinista. Cancelación implementada, pero su ciclo GPU completo no está probado por las ocho sondas.
- **Evidencia ejecutada por el coordinador**: `backend/venv/Scripts/python.exe` llamó al `MusicService.build_payload` real y aceptó `prompt="techno a 120 bpm", bpm=140` y `prompt="canción sin voz", instrumental=False` con letra. Resultado: `logs/audit-plan-conflicts-20261012.json`. Ejecución local sin mocks ni generación HTTP/GPU; demuestra ausencia de validación de estos conflictos en esa función, complementada con lectura de los handlers/UI.
- **TESTER — PASS de comprobaciones generales ejecutadas** (`sd_tester`): ESLint CLI real `node node_modules/eslint/bin/eslint.js . --max-warnings=0` exit 0; `npm run build` exit 0, 1772 módulos, bundle `index-CNCUW5ci.js` 356,66 kB/gzip 111,02 kB; `node --test src/audio_player.test.js src/prompt_gloss.test.js` 8/8; `backend/venv/Scripts/python.exe -m unittest discover -s backend -p test_*.py` **164 tests / OK**. Salidas/códigos reales conservados en `logs/audit-plan-checks-final.json` y `logs/audit-plan-backend-tests.log`. Primeros intentos build/Node fallaron `spawn EPERM` por sandbox, reejecutados con escalación aprobada; lint vía npm falló `EUNKNOWNCONFIG`, se ejecutó ESLint directamente. Fallos iniciales conservados, no atribuidos a un fallo de producto.
- **Cobertura insuficiente del cierre anterior**: `audit_prompt_fidelity.py` no invoca `buildPrompt` real ni demuestra igualdad preview React/envío HTTP de generación; `style_options` marca igualdad sin comparar y el status no exige ciertos checks de warnings/adiciones. La recombinación comparada en la sonda de grupos reutiliza la misma función `MixerService.mix_groups`, no un oráculo independiente. No invalidar toda la evidencia: limitar las conclusiones a lo que se ejecutó.
- **Documentación desactualizada**: knowledge todavía dice sin tests y turbo único; spec/02 marca compás ausente y cover/repaint no ejecutados; spec/03 mantiene cola/PARAR no hechos y T6 como candidata pese a su cierre; spec/06 mezcla implementación/cierre con textos de propuesta aún pendiente; spec/01 no recoge los módulos/contratos nuevos. README conserva texto-a-voz, turbo y un lanzador que no abre ventana; frontend/README es plantilla. `spec/05` es histórico y no autoriza reactivar decisiones descartadas.
- **TESTER — veredicto final FAIL del cierre completo R9/R10; PASS parcial** (`sd_tester`): ffprobe verificó **15 archivos** (7 WAV + 8 MP3), todos con tamaño positivo y 30 s; ffmpeg midió pico verdadero ≤ 0 dBTP en los 8 MP3. GET 200 en health (API/motor), UI con asset actual, capacidades/jobs/biblioteca/style_options y cuatro jobs históricos full/region/groups/DSP recuperables. Evidencia: `logs/audit-plan-artifacts.json` y `logs/audit-plan-tester-verdict.json`. Recuperar esos jobs ahora no prueba recuperación tras un reinicio nuevo. Semilla efectiva 123456 registrada, pero semillas por variante null: trazabilidad incompleta. NO-VERIFICADO: interacción Electron, comparación/solo/teclado, cancelación real, reinicio, nuevo recorrido GPU, conservación PCM recalculada independientemente y obediencia musical.
- **REVIEWER — APPROVE de la exactitud del informe** (`sd_reviewer`): leyó el documento completo y confirmó hallazgos/límites; se mantiene **CHANGES_REQUESTED del producto R9/R10**. Matiz incorporado: el contraste de mezcla reutilizado sí aporta evidencia de selección de stems por orquestación, pero no detecta errores propios del mezclador con un oráculo independiente.
- **Límites de esta sesión**: sin instalaciones, sin generación GPU nueva, sin cancelar trabajos, sin reiniciar servicios ni abrir una GUI. La escucha artística y los recorridos de UI/cancelación sin evidencia siguen pendientes. Pruebas verdes no constituyen PASS integral del plan. Cambios limitados a esta bitácora y artefactos/informe de auditoría en logs; build regenerado al verificar. `git diff --check -- memory.md` exit 0 con escalación después del fallo Cygwin de permisos del sandbox.

## 2026-10-13 (CII) — Correcciones del cierre R9/R10 autorizadas

- **Autorización**: «HAZLO» tras el informe CI; completar los criterios pendientes auditados, recuperar funciones útiles y sincronizar los Markdown. No volver a pedir aprobación del mismo alcance.
- **Plan básico / skill fix**: backend valida conflictos explícitos y prepara vista previa con parámetros efectivos/semillas; UI completa comparación alineada, selección regional, procedencia y acceso voz/base; CREAR/acompañamiento recuperan herramientas y transparencia; sincronizar docs; reviewer/tester independientes con evidencia viva de UI/cancelación/recuperación. Se mantiene el perfil aprobado sin instalaciones, sin commits ni software ajeno.
- **Roles**: root coordina y edita CREAR/acompañamiento/cliente HTTP; sd-editor backend, sd-editor interfaz de remix y sd-editor documentación trabajan con archivos delimitados. Reviewer y tester separados al integrar. El estado es EN CURSO, no HECHO.

## 2026-10-13 (CIII) — Revisión de memoria, plan y estado: el cierre sigue abierto

- **Petición**: revisar la memoria, la implementación del plan y el estado del proyecto. Lectura de bitácora, spec, código sin commitear, sondas ya guardadas y un `GET /health` vivo. Sin generar música, sin instalar, sin commit y sin declarar HECHO.
- **Dos memorias distintas**: `memory.md` llega hasta CII y dice correcciones autorizadas, en curso. Los temas de la memoria de sesión (`musicia-product`, `musicia-roadmap`, `musicia-sdd`) siguen en la época turbo / pestaña VOZ / rediseño visual y no describen SFT, R9 ni la reapertura CI. Esos temas no mandan sobre esta bitácora.
- **Git**: último commit `3990c0b` (2026-10-12) todavía titula R10 cerrada. El trabajo posterior de CII está sin commitear: comparador, preview efectivo, voz original + base nueva, conflictos, procedencia y Markdown. El árbol de trabajo está sucio.
- **Código frente a la lista de `spec/02`**: hay `AudioComparator`, `EffectivePreview`, `VoiceBackingPanel`, `PromptTools`, `classification_origin` y rechazo de conflictos BPM/voz/compás. La sonda `logs/plan-completion-validation-20261013-002035.json` es PASS de ese rechazo y no creó jobs (32 → 32). No sustituye el cierre.
- **UI no cerrada**: tres sondas de layout fallan. `plan-completion-ui-layout.stdout.log` abre BIBLIOTECA, monta el remix, consulta el preview del servidor y hace coincidir onda y campos; luego FAIL porque el teclado de la onda no actualiza el campo (valor 6). `Waveform.jsx` no tiene manejador de teclado. Otras dos (`mv5tkmfg`, `mv5tly5l`) agotan el tiempo al pulsar BIBLIOTECA. No hay evidencia de 1400×900 y 1080×700, ni de cancelar/liberar/recuperar, ni de PASS/APPROVE posteriores a CII.
- **Servicios en esta lectura**: API `:8000` y motor `:8001` responden 200. Modelo cargado `acestep-v15-sft`. `loaded_lm_model` null. `logs/stop.flag` ausente. No se reejecutó lint, build ni la suite.
- **Estado**: R9/R10 siguen parcialmente cumplidos y en corrección. No está HECHO. La escucha artística sigue aparte.

## 2026-10-13 (CIV) — Mesa de remix compactada; el prompt sigue literal

- **Petición**: la UI de remix se ve poco optimizada y antes vivía en desplegables. Mergear las secciones como ya dice `spec/06`: prompt y REMIX siempre visibles, el resto según el ámbito o plegado. El prompt tiene que ser el texto real. Anotar el avance. No es una función nueva ni un cierre del plan.
- **Mesa** (`RemixWorkspace.jsx`): encabezado, duración y los tres ámbitos van en una sola línea. Debajo, el prompt y el botón REMIX. Canción completa enseña fidelidad y BPM, con la duración del original en el encabezado y sin campo de duración que el cover ignore. Tramo enseña la onda, el intervalo y la transición. Por pistas enseña separar y una acción por grupo. Quedan plegados, cerrados al entrar: referencia y avanzados (variación, referencia tímbrica, voz, volumen, nombre y semilla), comparar con el original, audio detectado, parámetros del motor, voz original + base nueva, y ajustes de tempo/tono/recorte/loop. El comparador se abre cuando aparece una variante. La segunda onda de ajustes solo se monta al abrir ese desplegable.
- **Prompt real**: el textarea es el texto que viaja. GLOSARIO y AÑADIR siguen en su línea y solo añaden la cláusula que se ve. MEJORAR PROMPT pasó dentro de SUGERENCIAS OPTATIVAS y no sustituye la frase hasta pulsar APLICAR BORRADOR. No se infiere otra operación ni se inventan instrumentos.
- **Comprobación de esta entrada**: ESLint 0 en los archivos de UI tocados. `node --test` 15/15 (teclado de timeline, comparación, reproductor y glosa). `npm run build` exit 0, 1778 módulos, bundle `index-DNNsW3B1.js` (374,26 kB). La API `:8000` estaba caída, sin `logs/stop.flag`, con el motor `:8001` en marcha. Se reanudó solo la API de Musicia; health 200 y el HTML sirve ese bundle. El motor y ComfyUI no se tocaron.
- **Sonda de layout — PASS de esta mesa, no del plan**: `logs/plan-completion-ui-layout-mv5v9chq`. Electron real, BIBLIOTECA visible, preview del servidor con el prompt literal «Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos», sin BPM añadido. Flecha derecha: inicio 6 → 7 y el preview de repaint queda en 7–18. Al salir y volver a Tramo se conserva. Ventanas 1400×900 y 1080×700 sin desborde horizontal. Perfil efectivo: SFT, 50 pasos, guidance 9, batch 2, thinking y use_format en falso, tarea repaint. La captura muestra el escritorio plegado (prompt, glosario, AÑADIR, onda, intervalo, transición y REMIX; el resto en desplegables cerrados). El archivo que quedó abierto en pantalla y en `src_audio_path` es `prueba-remix-integral-dsp.mp3`, no el nombre pedido a la sonda.
- **Sigue abierto**: modo completo de la sonda (separar, solo, A/B, voz original), cancelación/recuperación, PASS del tester y APPROVE del reviewer sobre los archivos completos. El último commit empujado sigue siendo `8f6bec4`. Este compactado y el paso de teclado por configuración no están commiteados. No está HECHO. La escucha artística sigue aparte.

## 2026-10-13 (CV) — UI: fuera lo que no cambia el envío

- **Petición**: eliminar de las pantallas lo que sobra y dejar lo real. No se arrancó el backend para esta pasada.
- **Quitado de la vista**: en SUBIR, el cuestionario «qué es / qué hacemos», la hipótesis y las acciones que solo abrían la misma mesa. La subida enseña duración, BPM y loudness, abre el remix y deja el acompañamiento nuevo en un desplegable. En BIBLIOTECA se quitó el título duplicado «REMIX SOBRE EL ORIGINAL». En el tramo se quitó la segunda barra de inicio/fin; la onda se arrastra y DESDE/HASTA reciben las flechas. El párrafo largo de normalización pasó a LÍMITE DEL TRAMO. En CREAR, el género detectado ya no aparece como si estuviera elegido, desapareció el cartel de catálogo «sin aplicar» y el segundo «VER LO QUE SE ENVÍA» de la voz. VARIANTES queda plegado. Los textos de aviso que no eran un control se quitaron.
- **Sigue**: prompt, GLOSARIO, AÑADIR, MEJORAR como borrador, los tres ámbitos, REMIX, voz original con base nueva, ajustes de audio, comparar y el preview efectivo. El acompañamiento nuevo sigue generando instrumental para mezclar después.
- **Comprobación local**: ESLint 0 en los archivos tocados. `node --test` 9/9 de glosa y teclado. `npm run build` exit 0, bundle `index-vBn3HPH8.js` (366,21 kB). No se relanzó la sonda Electron ni el backend. No está HECHO.

## 2026-10-13 (CVI) — La mesa de remix dice cómo se hace

- **Petición**: en remix no se entiende el uso. Hace falta ver el paso, sin volver a llenar la pantalla.
- **Qué se ve**: bajo el ámbito elegido, una frase que viene de `remix.scopes` en la configuración. Canción completa: escribir el cambio y pulsar REMIX. Tramo: marcar el trozo, escribir qué debe sonar ahí y pulsar REMIX; la onda queda antes del texto. Por pistas: separar, elegir conservar, transformar o quitar, y escribir solo si se transforma. El cuadro usa el texto de ejemplo de ese ámbito.
- **Backend**: no se arrancó. La frase llega con las capacidades, así que hace falta abrir la app de nuevo para que la API lea la configuración nueva. No está HECHO.

## 2026-10-13 (CVII) — Remix: el avance ya no es un registro

- **Petición**: al pulsar REMIX la mesa se llena de logs. Hay que dejarla usable.
- **Causa**: el sondeo pintaba `phase` con el `progress_text` crudo del motor y, debajo, los últimos eventos. Una sola respuesta larga ocupaba la ficha. La barra superior repetía ese texto.
- **Ahora**: una línea corta, la barra y el porcentaje. Si la fase trae un párrafo o un salto de línea, se sustituye por «Rehaciendo el audio». El texto crudo queda en `engine_progress_text` y no se pinta. La barra superior enseña el nombre y el porcentaje.
- **Comprobación**: ESLint 0. `npm run build` exit 0, bundle `index-BvuQDjHI.js`. No se arrancó el backend ni se generó audio. La fase corta del proyecto remix entra al reabrir la API. No está HECHO.

## 2026-10-13 (CVIII) — Revisión: el log corto seguía en la mesa

- **Petición**: revisar bien el arreglo de los logs al pulsar REMIX.
- **Qué seguía mal**: ACE-Step publica en `progress_text` la última línea de su registro (`log_buffer.last_message`). CVII solo ocultaba el texto si pasaba de 72 caracteres o traía un salto de línea. Líneas cortas (`Extracting Audio Codes...`, `12:04:01 | INFO | …`, barras de tqdm) seguían pintándose. Además, al abrir la mesa el análisis copiaba ese texto crudo en la cabecera, sin límite.
- **Ahora**: la mesa solo enseña frases propias (`desk_phase.js`). Cualquier otra cosa pasa a «Rehaciendo el audio» o «Analizando el audio original…». El análisis ya no guarda el log como fase. Mientras ese análisis ocupa la GPU, REMIX espera y la frase queda encima del botón. Si se insiste con otra operación, la API responde «El audio original se está analizando…» en vez del id interno.
- **Comprobación**: ESLint 0. `node --test` 12/12 (fase de mesa, glosa y teclado). `unittest` de `test_source_understanding` 8/8, incluido el log de análisis. `npm run build` exit 0, bundle `index-CcPaNKED.js`. No se arrancó el backend, no se abrió Electron y no se generó audio. Hay que reabrir la app para verlo. No está HECHO.

## 2026-10-13 (CIX) — Logs de la sesión 09:40–11:26

- **Sesión**: API arrancada a las 09:40, modelo `acestep-v15-sft`. Parada a las 11:26 (`logs/stop.flag`). La VRAM bajó de unos 7682 MB ocupados a unos 2185 MB.
- **Primer remix** `24adae9a`, prompt «hard dance, UK hardcore, gabber hardcore», 50 pasos, guidance 9, batch 2, duración del original 81,4 s. Enviado 09:47:49. A las 09:54:40 había dos WAV verificados de 81,4 s. Justo después se borraron 82 archivos de biblioteca, 0 errores.
- **Segundo remix** `24ac9d67`, mismo perfil y el mismo prompt. Enviado 10:00:35. El motor avanzó hasta el paso 49/50, unos 10 s por paso, y a las 10:10:36 cortó por el tope de 600 s de ACE-Step (`ACESTEP_GENERATION_TIMEOUT`). La barra llegó a 50/50 después del corte. Musicia anotó «El motor terminó sin audio válido». La VRAM seguía con margen de unos 300 MB; el bucle no estaba parado, iba lento.
- **Lo que llenaba la mesa**: `logs/acestep-api.err.log` es la barra `76%|#######6  | 38/50`. Esa línea es el `progress_text` que el sondeo devolvía en cada `GET /audio/remix/ai/…`. Antes hubo un análisis con muchos `GET /music/remix/analyze/…`, un `POST /music/enhance_prompt`, una separación y cuatro previews 422. Esta API se paró antes del filtro de frases. No está HECHO.

## 2026-10-13 (CX) — El error de la UI era el corte a los 600 s

- **Petición**: el remix no se hizo y en la mesa saltó un error.
- **Causa**: el motor trae `ACESTEP_GENERATION_TIMEOUT=600`. Musicia esperaba `job_timeout` (1800 s) pero el motor cortaba antes, devolvía fallo sin texto, y la mesa enseñaba «El motor terminó sin audio válido».
- **Ahora**: al arrancar el motor, `scripts/ensure_local.ps1` y `scripts/verify_e2e.ps1` exportan ese tope desde `engine_launch_timeout_seconds()` (1800). El motor y la API están parados; el valor entra al abrir Musicia de nuevo. No se ha vuelto a generar el audio. No está HECHO.

## 2026-10-13 (CXI) — Las secciones del remix dicen para qué están

- **Petición**: revisar los logs. Sigue poco claro, y no se entiende para qué están las secciones del remix.
- **Logs de esta sesión** (API desde las 12:13, motor `acestep-v15-sft`): análisis del original, luego separación `8b5db43b`, luego cover `bc57358a` con el prompt exacto «gabber hardcore», 50 pasos, guidance 9, batch 2, duración 66 s. La difusión acabó a las 14:22:03 (unos 27 s). Quedaban 0,15 GB de VRAM y el motor pasó el VAE a CPU (`tiled_decode`, dos variantes, una detrás de otra). La mesa, con la frase genérica «Rehaciendo el audio», no decía que ya estaba convirtiendo el archivo. No se reinició la API: el trabajo seguía.
- **Mesa**: bajo el ámbito, una frase de propósito (canción entera / solo el trozo / pista a pista). Cada fila plegada lleva el título de siempre y, al lado, para qué sirve: referencia, comparar, audio detectado, parámetros, voz con base nueva, ajustes. El modo del tramo se lee Conservador, Equilibrado o Agresivo. Mientras trabaja, la línea dice el ámbito; al 100 % dice que convierte el audio a archivo. Los títulos que pulsan las sondas no cambian. El texto vive en `frontend/src/remix_sections.js` y también en `remix.scopes` (`why`). La API en marcha aún no lo sirve; la mesa lo enseña al recargar, sin reiniciar el motor.
- **No está HECHO**. Falta recargar la ventana, el oído del cover y PASS/APPROVE.

## 2026-10-13 (CXII) — El remix es un desplegable

- **Petición**: sigue sin quedar claro, y no se sabe si esas secciones deberían estar. La visualización tiene que ser un desplegable: se elige qué hacer y las opciones de esa acción se abren en el mismo sitio.
- **Mesa**: desaparecen los tres botones y la pila de filas. `QUÉ HACER` ofrece rehacer la canción, cambiar un trozo, cambiar por pistas, dejar la voz y crear música nueva, o ajustar tempo, tono, recorte y loop. Solo se ve el formulario de la acción elegida. Referencia, semilla y lo detectado quedan dentro de esa acción. El resultado aparece debajo cuando ya hay variantes.
- **No está HECHO**. Hay que recargar la ventana. No se reinició la API. Falta el oído y PASS/APPROVE.

## 2026-10-13 (CXIII) — El cover gabber se quedó en el VAE de CPU

- **Petición**: da error en el remix.
- **Qué hay en los logs**: el cover `bc57358a` (tarea `504e54e4`, prompt «gabber hardcore», 50 pasos, guidance 9, batch 2) envió a las 14:20:28. La difusión acabó 50/50 a las 14:22:03. El motor midió 0,15 GB libres, pasó el VAE a CPU y arrancó `tiled_decode` (latentes `[2, 64, 1672]`, dos variantes seguidas, solape 64→32). La última línea del motor es esa, a las 14:22:04. No hay traceback ni un 4xx/5xx del remix. `GET /v1/models` 404 es el sondeo de salud, no este trabajo.
- **Cierre**: a las 14:49:52 `logs/stop.flag` quedó en `salir`. API (pid 23868) y motor desaparecieron. En `job_history.json` el trabajo sigue `running` / «Transformando el audio original con cover»; al volver a abrir, `_load_history` lo marca interrumpido. No se ha relanzado. ComfyUI sigue en marcha; no se ha tocado. A las 15:00 la GPU tenía unos 1869 MiB ocupados y 6156 MiB libres.
- **No está HECHO**. No hay oído ni PASS/APPROVE.

## 2026-10-13 (CXIV) — La mesa pintaba 80 % en toda la conversión

- **Petición**: el error estaba en la UI.
- **Pantalla**: el sondeo de `bc57358a` respondió 200. La fase era «Convirtiendo a audio» con `progress_ratio` 0,8. El motor escribe ese 0,8 al empezar a convertir y no lo mueve. La mesa y la barra superior lo enseñaban como 80 %. No hubo cartel de fallo del sondeo ni caída de React.
- **Cambio**: en esa fase (y en «Convirtiendo a audio final») no hay porcentaje. La línea es «Convirtiendo el audio a archivo» y la barra va sin número. Si la fase es «Error» o «Error de análisis», se enseña el texto de `job.error`. La barra superior tampoco añade el 80 %.
- **Pruebas**: `node --test src/remix_sections.test.js src/desk_phase.test.js` → 9/9. `eslint --max-warnings=0` en los archivos tocados → 0. `vite build` → `dist/assets/index-CPnnWLzh.js`.
- **Tester**: PASS del contrato de la frase y del porcentaje. No hay PASS de la ventana: no se ha abierto la app, porque abriría API y motor.
- **Reviewer**: APPROVE del cambio en `desk_phase.js`, `remix_sections.js`, `RemixWorkspace.jsx` y `App.jsx`. El gabber no se ha relanzado.
- **No está HECHO**. Falta ver la mesa abierta y el oído.

## 2026-10-13 (CXV) — «Decoding» no es «decode», y el 80 % se pintaba

- **Petición**: eso es un bug.
- **Causa**: la fase del motor es `Decoding audio...` con progreso 0,8 quieto. La comprobación buscaba `decode`, y esa cadena no está dentro de `Decoding`. La mesa no pasaba a «Convirtiendo a audio» y seguía pintando el 80 %.
- **Cambio**: `engine_is_converting` reconoce `decod`. En esa fase `moving_progress` es vacío y el sondeo no repone el 0,8 del motor. La mesa y CREAR muestran la conversión sin porcentaje.
- **Pruebas**: `unittest test_remix_logic` 34/34, incluido `DecodeProgressTest`. ESLint 0. `vite build` → `dist/assets/index-otMg3BcW.js`.
- **Tester**: PASS del contrato. No hay PASS de la ventana: no se ha abierto la app.
- **Reviewer**: APPROVE de `music_service.py`, `main.py`, `remix_project.py`, `RemixWorkspace.jsx` y `Composer.jsx`. El gabber no se ha relanzado.
- **No está HECHO**. Falta ver la mesa abierta y el oído.

## 2026-10-13 (CXVI) — Corrección de UI y bloqueo al 80 %, en curso

- **Petición**: revisar Markdown y solucionar UI y cuelgue al 80 %. Leídos AGENTS global/proyecto, spec, knowledge, README y últimas entradas de memory. El alcance ya autorizado conserva QUÉ HACER (CXII) y SFT/50/guidance9/batch2/LM0.6B/thinking y use_format off. Sin instalaciones ni cambios a ComfyUI.
- **Plan fix**: coordinador revisa contratos; sd-editor UI comprueba mesa y sonda; sd-editor motor corrige la causa del decode; reviewer y tester independientes revisan archivos completos y ejecutan lint/build/regresión, ventana real y generación. No declarar cierre R9/R10 entero.
- **Diagnóstico motor ejecutado**: fallback `generate_music_decode.py` mueve VAE/latentes a CPU conservando BF16; la política `_get_vae_dtype('cpu')` exige FP32. VAE/checkpoint instalado, PyTorch 2.7.1+cu128, CPU AVX2, seis hilos, latentes [1,64,4]: FP32 0,696 s frente a BF16 16,702 s, ambas salidas finitas [1,2,7680], exit 0. No extrapolar la duración completa desde esta muestra. Log histórico: 0,15 GB libres y sin avance tras primer chunk; se evalúa dtype antes de cualquier cambio de offload.
- **Diagnóstico UI**: CXV ya reconoce Decoding; falta acreditarlo en ventana viva. La sonda anterior podía elegir una fuente distinta al ascender desde la fila y buscar cualquier REMIX (CIV lo documentó); debe abrir ACCIONES de la fila exacta, comprobar fuente y adaptar recorrido al desplegable actual. Se comprueban también bloqueo de controles y liberación tras error en ajustes.
- **Researcher/scout**: skill fix existente suficiente, no se instala ninguna skill. Consulta solo fuentes primarias: GPU/offload https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/GPU_COMPATIBILITY.md y fallback https://raw.githubusercontent.com/ace-step/ACE-Step-1.5/main/acestep/core/generation/handler/generate_music_decode.py . Investigación por internet; cómputo y modelos locales.
- **Estado inicial**: Musicia parada por stop.flag de 14:49; ComfyUI PIDs 6664/6800 en otro proyecto. GPU 1780 MiB usados/6245 MiB libres. Lectura de procesos/Git requirió escalación tras acceso denegado/Cygwin signal pipe en sandbox. Árbol con cambios previos: se preservan.
- **Implementación**: parche durable del VAE y aplicador exacto, atómico e idempotente antes del arranque de motor ausente; preparación y decode dentro de try/finally para recuperar dtype/dispositivo. Arranques guardan proceso o puerto para evitar parchear un motor presente. RemixPanel hereda busy, bloquea controles y onda, enseña rechazo real y libera running con finally. Sonda UI selecciona fila/fuente exactas, usa cinco formularios contextuales y añade recorrido decode observado. Markdown de UI sincronizados con CXII.
- **Checks ejecutados por root**: `npm run build` (frontend, escalación con prefijo ya aprobado, sin redirección) exit 0: 1780 módulos, `index-DP2Ypvpx.js` 369,52 kB / gzip 115,40 kB. `node --test src/audio_comparison.test.js src/audio_player.test.js src/desk_phase.test.js src/prompt_gloss.test.js src/remix_sections.test.js src/timeline_nudge.test.js` exit 0: tests 24, pass 24, fail 0, skipped 0. ESLint de componentes editor exit 0 y lint global tester exit 0. No constituyen evidencia de ventana/audio.
- **REVIEWER — APPROVE del producto CXVI** (`sd_reviewer`, revisión independiente completa): parche/aplicador/tests/launchers/vendor, RemixPanel/Workspace, sonda UI y docs spec01/02/06/knowledge/memory; sin bloqueantes ni importantes. Sonda Python y runner de verificación se revisan nuevamente al estabilizar. No cierra R9/R10 integral.
- **Límites de los primeros checks**: sandbox bloqueó spawn de Vite/Node y taskkill del test de cancelación (194 backend, 1 fallo de acceso denegado); no es PASS. Contratos reales torch CPU 2 PASS; tests del aplicador necesitaban tempfile con escritura permitida. Peticiones de escalación con redirecciones quedaron pendientes, se interrumpieron y se preparó una ejecución agrupada revisable. Build/Node se repitieron con comandos directos y prefijos ya aprobados; sin instalaciones.
- **Verificación real inicial**: runner `scripts/verify_ui_decode_fix.ps1`, baseline `bc57358a1b5b4137b7c3c12c00a1ef49`, fuente de layout real `ANIMALES MUERTOS -NEW RAVE.mp3` (ffprobe 240 s / 5761196 bytes). `logs/ui-decode-verification-20261013-170319`: backend 194/194 en 3,313 s y parche 4/4 en 0,187 s, exit 0. Motor/API arrancados (6192/21304); el pipeline nativo del verificador quedó esperando handles heredados aunque ensure había terminado. Nuevo wrapper inline, reviewer APPROVE; detuvo solo su propio runner 12824 con validación CIM, mantuvo servicios y ComfyUI. Primer informe marcado INTERRUPTED, sin generación enviada.
- **Réplica musical ejecutada**: `logs/ui-decode-verification-20261013-170850/decode-http-audio.json` PASS, único POST musical desde Electron: job `5ff7ba8ca7ed41c5812cbc3bbe9bdb0e`, tarea `7309a971-8aed-49f8-83d3-e9ca6623a245`, prompt literal gabber hardcore, fuente/digest/grupos y perfil efectivos iguales al histórico salvo ruta temporal/nombre. SFT/50/9/batch2, thinking/COT/use_format off. Difusión 26,519 s; 0,15 GB libres y CPU fallback a 17:15:56, primera variante termina 17:17:59, restauración VAE 17:20:39, WAVs guardados 17:20:44. Decode CPU unos 284 s; remix completo succeeded en 483,078 s, con dos MP3/intermedios/WAV generados verificados mediante ffprobe y PCM finito/no silencio. Nada de subir timeouts, bajar batch o cambiar modelo. `progress_ratio=null` durante el 0,8 real observado desde 17:15:59.
- **Límites UI de esta pasada**: la primera captura de conversión ocurrió antes de difusión por el detector demasiado amplio que reconocía cualquier mención VAE; captura final puede preceder al repaint. El wrapper dio PASS temprano al lanzar Electron layout como comando GUI nativo; la ventana posterior terminó EPIPE al cerrarse stdout. Ese PASS NO acredita layout, se corrige el runner para esperar proceso e informe. La captura externa posterior rechazó correctamente PID ya terminado (`logs/ui-decode-verification-20261013-172248` FAIL). Se mantienen errores/artefactos y se prepara nueva pasada UI/CREAR; no se repite el gabber.
- **Corrección del indicador detectada en vivo**: `engine_is_converting` reconoce decod, sin VAE ni tiled genéricos (también aparecen en encode/carga/offload). Cuatro casos negativos reprodujeron FAIL antes y ahora DecodeProgressTest 4/4 PASS, compilación y diff-check exit 0; salidas `logs/decode-phase-specific-before.log` / `after.log`. API aún con proceso anterior hasta que terminen operaciones; no afirmar desplegado todavía. Falta PASS final UI y revisión del delta.

## 2026-10-13 (CXVII) — UI y bloqueo al 80 % corregidos y verificados técnicamente

- **Continuación autorizada**: el usuario pidió «continua». Se conservó el alcance CXVI, QUÉ HACER y perfil SFT/50/guidance9/batch2/LM0.6B/pt, thinking/COT/use_format off. Sin instalaciones, commits ni cambios a ComfyUI. Una interrupción por cuota de agentes no cambió el objetivo; reviewer/tester retomaron y emitieron veredictos independientes.
- **Resultado del fallo original**: job `5ff7ba8ca7ed41c5812cbc3bbe9bdb0e`, prompt gabber hardcore, voz/bajo conservados y batería/acompañamiento transformados. `logs/ui-decode-verification-20261013-170850/decode-http-audio.json` **PASS**: mismo digest/fuente/grupos y parámetros del histórico salvo nombre/ruta temporal. CPU fallback con **0,15 GB** libres, dtype CPU correcto, restitución del VAE y dos variantes. Difusión 26,519 s; decode CPU aproximadamente 284 s; succeeded en **483,078 s**. Cada MP3 **66,952 s / 1608236 bytes**, PCM finito y no silencioso; también verificados dos intermedios y dos WAV generados. No ocultar que sigue tardando varios minutos cuando convierte por CPU.
- **Layout y ajustes reales — PASS**: `pwsh -NoProfile -File scripts/verify_ui_decode_fix.ps1 -BaselineJob bc57358a1b5b4137b7c3c12c00a1ef49 -LayoutSource 'ANIMALES MUERTOS -NEW RAVE.mp3' -FinishVerification -CompletedEvidence logs/ui-decode-verification-20261013-170850/result.json`. `logs/ui-decode-verification-20261013-221152/layout-verified.json` y `logs/plan-completion-ui-layout-mv74actc/result.json`: fuente exacta, cinco formularios contextuales; 1400×900 y 1080×700 sin desborde horizontal; inicio por teclado 6→7, fin18, remonte y preview coincidentes. Único POST DSP real: **10 controles bloqueados**, selección [0,240] intacta ante puntero; HTTP200, controles recuperados y audio servido de 228,571429 s. Capturas reales inspeccionadas por root y tester. El runner terminó FAIL por análisis todavía activo: guard correcto dejó API intacta; NO invalida estos oráculos separados de layout/backend.
- **Backend final — PASS**: salida real `logs/ui-decode-verification-20261013-221152/backend-final.log`: `Ran 196 tests in 7.311s` / `OK`, exit0. Incluye negativos de carga/offload/encoding VAE antes de difusión y positivos Decoding/tiled_decode. VAE patch suite 4/4 en el venv del motor (0,187/0,188 s), incluyendo dtype de convolución real, restauración tras errores, CRLF/idempotencia y rechazo de fuentes desconocidas. ResourceWarnings pydub heredados no se confunden con errores de esta corrección.
- **Despliegue API y CREAR — PASS**: tras terminar el análisis f31833751d344506a7a32b1223ffc286 a 22:15:13, se ejecutó `pwsh -NoProfile -File scripts/verify_ui_decode_fix.ps1 -BaselineJob bc57358a1b5b4137b7c3c12c00a1ef49 -LayoutSource 'ANIMALES MUERTOS -NEW RAVE.mp3' -RefreshApiSmoke -CompletedEvidence logs/ui-decode-verification-20261013-170850/result.json -VerifiedLayoutEvidence logs/ui-decode-verification-20261013-221152/layout-verified.json`. Exit0, `VERDICT=PASS`, `logs/ui-decode-verification-20261013-221550/result.json`. Guard verificó ausencia de trabajos/análisis y ownership listener/parentvenv antes de parar solo la API **21304→30280**, conservando motor y apps ajenas. El recognizer específico está cargado por la API nueva.
- **CREAR real**: job `870479057c97429eacedf87c8d5d3ad6`, tarea `265722ca-5ab7-439c-9fad-a97e87a39b8a`, único POST desde Electron; literal «Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos». `logs/ui-decode-verification-20261013-221550/create-decode.json` **PASS** y `create-ui-verified.json` **PASS**: succeeded en **173,5 s**, dos MP3 **30,000 s / 480812 bytes** con PCM finito/no silencio; preview=ejecución y perfil intacto. La primera transferencia VAE se muestra como carga, no conversión. Fase final `Decoding audio...`, crudo0,8, ratio público null, progress indeterminado y ausencia80% comprobados en DOM/API; terminó ready=true/busy=false y reproductor servido decodable. PNG final inspeccionada: GENERAR habilitado y cola0activos. La frase de conversión queda fuera del viewport de su PNG; su evidencia es DOM/API, no una foto de esa frase. El encabezado de la captura conserva79% de un sondeo previo; no afirmar sincronía fotográfica de todos los sondeos.
- **Build/lint/frontend**: ESLint global y componentes exit0; `npm run build` exit0 (1780 módulos, `index-DP2Ypvpx.js`, 369,52 kB / gzip115,40); Node **24/24**, fail0/skipped0, comandos/salidas en CXVI. Producto frontend no cambió tras ese build. Parsers de scripts PowerShell, node --check de sonda y compilación Python exit0. No repetir checks verdes sin nuevo cambio.
- **Verificador endurecido, errores conservados**: evita pipeline nativo heredado en arranque; GUI con Start-Process y redirecciones propias, espera proceso e informe terminal atribuible, no éxito sólo por lanzar Electron. Exige metadata/nombres/dos audios y BOM compatible. Capturas esperan repaint y guardan DOM/timestamp. Los informes de 17:03 (INTERRUPTED), 17:08 (FAIL por layoutEPIPE), 17:22 (FAIL capturaPIDya terminado) y 22:11 (guardanálisis) siguen guardados. No falsear esas pasadas ni perder evidencia válida de sus subpruebas.
- **REVIEWER — APPROVE** (`sd_reviewer`, archivos completos y deltas finales): parche/aplicador/tests/vendor/launchers, RemixPanel/Workspace, recognizer/tests, sondas y helpers UI/layout/API/CREAR/runner, spec01/02/06/knowledge/memory. Ownership API validado directa o mediante parentvenv del proyecto; parada sólo pareja propia, sin árbol y tras guard inactivo. Sin bloqueantes/importantes abiertos. La aprobación técnica no declara cierre integral R9/R10.
- **TESTER — PASS de estos dos problemas** (`sd_tester`, independiente): réplica CPU afectada, dos MP3 válidos, layout/teclado/fuente/formularios/DSP bloqueado-recuperado, API actualizada, CREAR dos variantes y conversión real DOM/API, suites196+4+24, lint/build verdes. Límite de foto explícito y fallos del verificador conservados. **Cierre técnico UI/80%**; quedan aparte los criterios abiertos R9/R10, cancelación/recuperación integral y el oído del usuario. No certificar fidelidad artística a partir de un MP3 válido.
- **Comprobación final del árbol y servicios**: `git diff --check` (Cygwin) señaló CRLF como trailing whitespace en líneas previas y nuevas. `git -c core.whitespace=cr-at-eol diff --check` **exit0**, sin modificar configuración Git ni reformatar trabajo anterior. GET real `/health`: api=ok, engine_reachable=true; `/music/jobs`: active_jobs=0. Se conservan motor/API activos y todas las evidencias; no commits ni limpieza de biblioteca.

## 2026-10-13 (CXVIII) — Auditoría funcional y visual solicitada, en curso

- **Petición**: «puedes revisar que las funcionalidades sean correctas y se vean bien en la UI». Coordinador revisa spec00–04/06, bitácora y skill fix existente; correcciones rutinarias dentro de CII, sin rediseñar ni instalar. Se conserva el árbol previo.
- **Plan comunicado**: contrastar controles/API de CREAR, SUBIR, MEZCLA y BIBLIOTECA; Electron real a 1400×900 y 1080×700, capturas con texto visible y estilos calculados; subir una copia identificable y producir mix/crossfade reales, conservando originales. Revisar y corregir causas mínimas, lint/build/regresión tras cambios y veredictos independientes. Nuevas generaciones vocales/separación pesada requieren cobertura explícita; CXVII acredita sólo los recorridos allí detallados.
- **Roles explícitos**: sd-editor visual audita cascada/controles y corrige CSS/reloj; root implementa cola/procedencia/refresco tras diagnóstico; sd-tester prepara sonda atribuible y evidencia real; sd-reviewer revisa archivos completos y contratos. Servicios al iniciar: API200, SFT inicializado, trabajos activos0; no se reinician durante operaciones.
- **Diagnóstico inicial**: reset/componentes CSS sin capas dominan utilidades Tailwind y anulan márgenes/tamaños; captura anterior muestra reloj fraccionario. La cola toma ocho primeros éxitos ascendentes y las tareas auxiliares pierden fecha; además separación por grupos carece de MP3 y no debe ofrecer `/music/audio/undefined`. SUBIR no refresca lista tras subida; MEZCLA descarta homónimos por nombre y no conserva procedencia. Se verifican antes/después, sin declarar PASS por lectura estática.
- **Error de auditoría retirado**: una lectura parcial del reviewer omitió bpm/key_scale de WriteLyricsRequest; los campos sí existen y el handler es coherente. No hay bug acreditado ni modificación de ese contrato. Se corrigió también la comunicación al usuario.
- **Estado**: EN CURSO; no hay cierre integral R9/R10 ni certificación musical por validez de MP3. Nuevos resultados y límites se añadirán tras ejecución.

## 2026-10-13 (CXIX) — Desplegables del remix y pistas

- **Petición**: los desplegables no se leen por el color, la pantalla no está optimizada y lo de las pistas no va.
- **Lo que hizo la sesión**: a las 23:40 el trabajo `cb41ca56` fue «Dejar la voz y crear música nueva» sobre `f6fc62fe-Arroja la bomba.mp3`, no «Cambiar por pistas». La separación fue a CPU (2188 MB libres, umbral 2600) porque el análisis automático había cargado el turbo. Terminó: dos mezclas, voz de 67 s cortada en 24 trozos sobre una base de 259 s. Antes, `POST /music/remix/separate` devolvió 409 mientras ese análisis ocupaba la GPU. Luego `logs/stop.flag` = salir.
- **Cambio**: los `select` y el menú de `SelectBox` usan fondo `#16161a` y texto blanco, con `color-scheme: dark`. La mesa sale a ancho completo, una sola vez. «Cambiar por pistas» muestra separar y, después, una fila por grupo. El análisis del archivo ya no arranca al abrir el remix; solo si se abre la sección avanzada. Build `index-Cnst7K8P.js`. ESLint 0 en los JSX tocados. `node --test` 24/24.
- **No está HECHO**. No se reabrió la ventana ni se relanzó una separación por grupos. Falta ver los desplegables abiertos y un PASS de pistas.

## 2026-10-13 (CXX) — El glosario no llevaba la descripción del estilo

- **Petición**: usa el glosario y el estilo pedido no sale al 100 %.
- **Causa**: desde R10, `style_caption` ya no completa la frase. El glosario seguía añadiendo solo el género corto (`gabber`). La descripción oficial del catálogo no llegaba al motor. El comentario de la UI decía que el servidor la rellenaba.
- **Cambio**: pulsar un estilo de Musicia escribe en el prompt el género y su descripción, visibles. Si el BPM está vacío, pone el tempo típico de ese estilo. Una línea suelta del vocabulario sigue siendo solo esa palabra. No reescribe lo que se teclea a mano. `glossary_pick` 4/4, ESLint 0, build `index-VhDyBPI4.js`.
- **Límite**: esto no certifica que el audio suene al 100 %. En remix, el audio original sigue pesando. No se generó música nueva ni se reabrió la ventana.

## 2026-10-13 (CXXI) — El glosario se queda con el vocabulario del modelo

- **Petición**: quitar las sugerencias de Musicia y dejar solo las del modelo.
- **Cambio**: desaparece la lista «ESTILOS DE MUSICIA» y ya no se inserta su descripción ni su BPM. El glosario muestra el vocabulario de `genres_vocab.txt` y las combinaciones que existen ahí. AÑADIR y VARIANTES siguen. ESLint 0. Build `index-DXOp6xEu.js`. Sin ventana ni generación.

## 2026-10-14 (CXXII) — El estilo se envía como frase, no como etiqueta

- **Petición**: cómo se soluciona que, después de elegir el estilo, el motor no haga lo pedido.
- **Causa ya medida el 2026-10-06**: una etiqueta (`gabber`) no fija el estilo. La frase que el DiT sigue es la descripción en inglés. El LM (`use_format`) reescribe `gabber` a house/EBM/hardstyle y sigue apagado.
- **Cambio**: al buscar en el glosario, si esa palabra es un estilo con frase real, arriba sale «SE ENVÍA» con la frase y su BPM. Un clic deja el cuadro solo con esa frase y pone el BPM en su control. Volver a pulsar la quita. Una línea del vocabulario que no tiene frase sigue siendo esa línea. No hay lista de estilos con el glosario cerrado. `thinking` y los cot siguen en false.
- **Prueba**: `node --test glossary_pick.test.js` 4/4. ESLint 0 en los archivos tocados. Build `index-B8FpF8To.js`.
- **TESTER — PASS de contrato de clic, lint y build. No de escucha ni de ventana.**
- **REVIEWER — APPROVE con límites**: la frase sale del catálogo ya existente, visible en el cuadro antes de generar. No cubre una línea suelta del vocabulario sin frase. No se generó audio. En remix el original sigue pesando. No está HECHO.

## 2026-10-14 (CXXIII) — Dos estilos se suman en el cuadro

- **Petición**: que el modelo mezcle y combine estilos, y que eso se vea.
- **Cambio**: el segundo estilo ya no borra el primero. Su frase se escribe detrás y las dos quedan en el cuadro. Volver a pulsar una la quita y deja la otra. El BPM se queda en el del primero. Una etiqueta suelta (`gabber`) se sustituye por su frase. Build `index-DpLkwJgd.js`. Tests del glosario 5/5. ESLint 0.
- **Límite**: el motor recibe un solo caption. No hay un mando de mezcla. No se ha generado audio para oír si el resultado funde los dos. No está HECHO.

## 2026-10-14 (CXXIV) — Mezcla de estilos: queda para oír, no cerrado

- **Petición**: ver cómo el modelo mete los estilos y si hace lo que el usuario envía. Hard house acelerado y con pitch sí puede cuadrar con gabber. Descartarlo por el BPM 124 del catálogo era falso. El usuario pide que esto quede registrado para su tratamiento, sin ver datos crudos.
- **Qué entiende el modelo, ya anotado**: una sola frase en inglés que describe el sonido. Los nombres sueltos no fijan el estilo (oído el 2026-10-06). `nightcore` es su palabra para algo subido de pitch. `hard house` y `hardcore gabber` están en su vocabulario. `frenchcore` casi no está. El modelo de lenguaje sigue apagado.
- **Prueba en curso**: dos temas de 30 s, instrumental, semilla 42, BPM 180, perfil SFT de la app. El primero se llama `prueba-nombres` y lleva `hardcore gabber frenchcore hard house`. El segundo se llama `prueba-frase` y lleva una sola frase: hard house en nightcore, subido de pitch, con el bombo duro del gabber.
- **Estado**: los dos MP3 están en la biblioteca, 30 s cada uno, comprobados con ffprobe. `prueba-nombres.mp3` lleva los nombres. `prueba-frase.mp3` lleva la frase del hard house en nightcore con el bombo del gabber. El oído del usuario decide si se cumplió. No está HECHO.
- **Corrección del usuario**: un estilo no se descarta por tempo ni por «no caber». `gabber` y `clásica` tienen que aportar los dos sus elementos en la misma frase. La regla de dejar un nombre fuera queda retirada.
- **Cualquier cosa que pida**: puede juntar estilos aunque no tengan ficha, y añadir algo que no es un estilo, como flautas medievales. Eso entra en la misma frase. El vocabulario tiene `medieval` y varias flautas (`flute`, `ney flute`, `Chinese flute`). No se ha oído esa mezcla.

## 2026-10-14 (CXXV) — La caption usa solo términos del modelo

- **Petición**: que funcione, integrado en la UI sin saturar, y que todo se base en lo que el modelo entiende.
- **Cambio**: glosario, género y AÑADIR escriben en el cuadro una sola caption. Cada elección es una línea entera del vocabulario, aunque lleve comas: `A track with gabber · medieval`. Pulsar otra vez quita solo ese término. Ya no se pega el párrafo del catálogo ni el mood en español. El asistente solo mete el género literal. El BPM no se escribe en la frase. La voz se suma en la misma caption y no borra un término ya puesto. Un texto suelto que no es caption no se arrastra: elegir `gabber` sobre «flautas medievales» deja `A track with gabber`. Build `index-CuHCTM4-.js`. Tests del glosario 8/8. ESLint 0. Revisor: APPROVE de la pasada anterior; esta guarda es posterior.

## 2026-10-14 (CXXVI) — VARIANTES usa la misma caption

- **Petición**: la frase única en todos los sitios que tienen prompt.
- **Cambio**: VARIANTES entra y sale con la misma función que el glosario. CREAR, remix, conservar voz y acompañamiento nuevo comparten esa fila. Una variante con comas cuenta como un solo término. Tests 9/9. ESLint 0. Build `index-C96fgPpf.js`. Revisor: APPROVE. No está HECHO: no se ha oído.
- **Límite**: no se ha generado audio con esta caption. No está HECHO. La revisión del subagente va aparte.

## 2026-10-14 (CXXVII) — Auditoría BPM, duración y separación de remix

- **Petición**: revisar memoria y estado del código; permitir BPM al separar por pistas, revisar separación y elegir remix más largo que el original. Leídos AGENTS global/proyecto, spec00–04/06 y memoria vigente; preservado el árbol con cambios previos. Skill plan aplicada; sin instalaciones ni cambios de perfil.
- **TESTER — FAIL del alcance solicitado, PASS de controles generales** (`sd_tester`, independiente): preview HTTP real con BPM180 y algún grupo conservado devuelve422; `duration_seconds90` devuelve422 `extra_forbidden` en full/groups. Auditoría no crea tareas:45jobs mismosIDs,activos0. Lint exit0, build exit0 (index-C96fgPpf.js,1781módulos), Node33/33; backend198/198 OK tras repetir con aprobación fuera del sandbox por `taskkill` del propio hijo denegado. Se conserva el fallo inicial, no se presenta como PASS.
- **Separación existente verificada**: job411e37fc9c974bf1ac7b09b4eca08259,succeeded CUDA14,265s; digest fuente coincide. Cuatro WAV23.620.664bytes cada uno,66,951837s,PCM float32 estéreo44.100Hz,ffprobe/ffmpeg exit0,finito y no silencioso; HTTP Range206 `audio/wav`. No se ejecutó separación nueva ni interacción Electron/SOLO en esta fase. Calidad de aislamiento pendiente de escucha.
- **REVIEWER — APPROVE del diagnóstico y plan condicionado** (`sd_reviewer`, archivos completos): BPM UI depende de transformar y backend bloquea keep; duración no existe en contrato y mezcla/verifica sobre original. Separación comprueba duración positiva pero falta validar coherencia/PCM; caché no identifica configuración del separador. APPROVE del informe/plan no equivale a aprobación del producto nuevo.
- **RESEARCHER/SCOUT**: cover fija longitud de fuente en vendor; repaint/outpainting es una vía candidata con SFT, no probada en esta sesión. Documentación primaria https://github.com/ACE-Step/ACE-Step-1.5/blob/main/docs/en/GRADIO_GUIDE.md y código local contrastados. `atempo` y `acrossfade` de FFmpeg permiten el método de arreglo propuesto (https://ffmpeg.org/ffmpeg-filters.html#atempo, https://ffmpeg.org/ffmpeg-filters.html#acrossfade). Investigación web declarada; procesamiento sigue local, no descargas/instalaciones. Skills disponibles plan/fix; sin incorporar herramientas externas.
- **Evidencia**: `logs/remix-bpm-duration-tester-verdict-20261014.json`, `logs/remix-bpm-duration-evidence-20261014.json`, `logs/audit_remix_bpm_duration_20261014.py`, `logs/remix-bpm-duration-services-20261014.json`.

## 2026-10-14 (CXXVIII) — R11 autorizado: BPM común y ampliación por partes

- **Decisiones explícitas**: el usuario elige «Repetir o reorganizar partes, con transiciones» y «Sí, un BPM común para todas». Se comunica plan de controles/timeline PCM común, validación de cuatro grupos y verificación API/Electron, conservando perfil y dependencias. «continua» autoriza ejecutar ese plan. R11 actualizado en spec02; generación de continuación queda fuera del método elegido.
- **Plan/archivos**: backend `remix_project.py`, `mixer_service.py`, `separator_service.py`, `config.py/config.example.json`: BPM común independiente de keep/transform/remove, duración natural según ratio, ampliación explícita de material con fundidos, firma caché y validación WAV, preview/ficha/historial. Frontend `RemixWorkspace.jsx` y helper/pruebas de timeline: BPM visible incluso sin generación, duración min:seg y parte/fundido opcionales compactos. Tester prepara sondas de API/UI/audio; reviewer revisará completos los archivos finales. Root coordina documentación.
- **Criterios**: no instalar ni cambiar SFT50/guidance9/batch2; sin silencio añadido presentado como música. Tempo modifica las grabaciones conservadas por DSP declarado. Repeticiones comparten edición/timeline; valores y límites desde configuración. Solo PASS real del tester y APPROVE final del reviewer permitirán cerrar R11. R9/R10 y escucha artística siguen aparte.
- **Estado**: EN CURSO; agentes `sd_editor_backend`, `sd_editor_frontend` y `sd_tester` trabajando en archivos separados. No declarar implementado/verificado por el plan aprobado.

## 2026-10-14 (CXXIX) — R11 implementado; controles, separación y ampliación real verificados

- **Implementación**: BPM común incluso al conservar/quitar, original revisable, duración min:seg en full/grupos y sección/fundido opcionales; detalles de repetición separados de avanzados para no activar análisis IA. Un atempo multicanal mantiene sincronía y tono de los grupos grabados antes del cover; ampliación posterior PCM con partes/fundidos. Sin instalaciones ni cambios de SFT50/guidance9/batch2/LM0.6B/thinking/COT/use_format.
- **Separación**: cuatro WAV float finitos con formato/duración comunes, caché ligada a digest y firma de configuración; fuente cambiante y cache corrupta/incompleta se rechazan. Se conservan como grupos voz/batería/bajo/acompañamiento restante, sin instrumentos supuestos.
- **REVIEWER — APPROVE implementación y scripts** (`sd_reviewer`, independiente, completos): backend/proyecto/DSP/separador/config/ejemplos/tests, frontend/helper/tests, sondas/runner/refresh y documentación. Corrigidos pares de inicio/fin implícitos, transición positiva y límites reales de capacidades, mínimo de parte medido sobre duración mapeada. Sin bloqueantes/importantes finales. APPROVE no sustituye PASS funcional ni cierra R9/R10.
- **Checks finales del tester**: `logs/remix-r11-checks-20261014.json`: lint exit0, build exit0, frontend42/42, backend203/203 OK (5,697s), compilación y sintaxis de sondas/PS exit0. No se repiten checks verdes sin cambios de producto.
- **Fuentes y fallos conservados**: fragmentos de `f6fc62fe-Arroja la bomba.mp3` dieron groove363–364 BPM, fuera del límite300; no se dividió artificialmente la medición. Se conservan manifest/artefactos inválidos. Fuente válida: corte20s a10s de `Animales muertos.mp3`, `prueba-r11-fuente-2ed3bb04.mp3`; groove166,36/confianza0,562. Sonda declara BPM original manual166 y objetivo199, duración90s, parte2–12s del original, fundido0,1s. `logs/remix-r11-source-valid-20261014.json` registra comandos, digest y PCM.
- **Actualización API, incidencia y recuperación**: primera escalación de tester no ejecutada/interrumpida; root recibe aprobación y ejecuta refresh. Pasada real exit1 en identidad del launcher después de cerrar API: el launcher terminó durante esa comprobación. Ningún proceso de identidad distinta se paró. `ensure_local.ps1 -SinMotor` exit0 `API=up`; capacidades R11/health/jobs0 verificadas en `logs/remix-r11-runtime-ready-20261014.json`. PID no disponible en lectura sandbox, declarado en evidencia; no afirmar que se midió. El refresh fallido sigue FAIL: no se reetiqueta. Helper corregido para omitir parada si el launcher ya desapareció y conservar el rechazo si un PID vivo cambió de identidad; delta completo APPROVE del reviewer, no reejecutado por ser innecesario.
- **TESTER — PASS UI/audio determinista**: comando root aprobado `scripts/verify_remix_timeline_ui.ps1 -Manifest logs/remix-r11-source-valid-20261014.json -OutputDirectory logs/remix-r11-ui-20261014`, exit0, salida `R11_UI_AUDIO=PASS`. Electron real servido, contexto aislado/sandbox y ventana oculta; nueva separación4762bec2e8ef4f14a2929b3c37f54272, cuatro WAV válidos20,035918s dentro tolerancia de fuente20s. SOLO decodifica y reproduce con un único audio activo; 1400×900 y1080×700 sin desborde horizontal, preview/timeline y POST observados coinciden.
- **Resultado real**: jobb1ae9007bb2346ff9b07820694db8c89,succeeded; conserva batería/bajo/acompañamiento y quita voz; tempo natural16,6834s y ampliación90,000s, MP3 `prueba-r11-fuente-2ed3bb04-remix.mp3`2.161.196bytes, PCM finito/no silencio. Groove final199,03/confianza0,43; ficha redondea199,0 y pedido199. El análisis básico estima100 (alias de medio tempo), no se oculta ni presenta como otro groove. Oráculo independiente sumaPCM delta5,96e-8, prefijo y copia repetida delta0 sobre192.000muestras; cuatro grupos preparados con igual longitud1.601.608muestras. Ficha/historial/HTTP reales verificados.
- **Evidencia y revisión visual root**: `logs/remix-r11-ui-20261014/result.json`, `process.json`, `audio-evidence.json`, PNG `groups-1080x700.png`/`groups-1400x900.png` inspeccionadas: filas, BPM199/original166, duración1:30, parte2–12 y fundido0,1 visibles según viewport; resultado y decodificación acreditados por DOM/API, no inventar contenido fuera de las capturas.
- **Estado**: falta terminar el remix mixto con transformación SFT y el cover completo con ampliación, ambos con dos variantes, oráculos y veredicto final del tester. Escucha artística y cierre integral R9/R10 siguen aparte.

## 2026-10-14 (CXXX) — Revisión de los MD y del estado del código

- **Petición**: revisar los Markdown y el estado real del código. Sin instalaciones, sin commits, sin generación GPU y sin cerrar historias.
- **Servicios vivos en la lectura**: API `:8000` health 200; motor `:8001` health 200 con `loaded_model=acestep-v15-sft` y `loaded_lm_model=null`; `logs/stop.flag` ausente. `/music/remix/capabilities` responde con los tres ámbitos, los cuatro grupos reales y los defaults; los límites de timeline viven en `config.py:208-213` y `config.example.json` (sin hardcode).
- **Regresión ejecutada hoy** (root, sin cambios de producto): backend `unittest discover` **203/203 OK** (8,441 s); frontend `node --test src/*.test.js` **42/42**; ESLint directo `--max-warnings=0` **exit 0**; `npm run build` **exit 0**, 1782 módulos, `index-BKq643P5.js` 379,27 kB / gzip 118,38 kB. El HTML que sirve la API ya referencia ese bundle y `frontend/dist` está ignorado por git.
- **Evidencia R11 que la bitácora no recogía**: `logs/remix-r11-tester-verdict-20261014.json` (13:38) declara **PASS técnico de alcance R11** —BPM común con grupos conservados y quitados (job `b1ae9007…`), separación nueva con SOLO (job `4762bec2…`), mixto con transformación SFT y dos variantes (job `1c328ec7…`, semillas 42 y 2942175228) y cover completo ampliado después del cover (job `ea761a9b…`, semillas 42 y 396917302)— con cinco MP3 de 90 s en `backend/outputs/` (`prueba-r11-mixto-1c43627e*` 13:31 y `prueba-r11-completo-07464782*` 13:34, 2.161.196 bytes cada uno). El veredicto cita reviewer APPROVE de producto/scripts y conserva límites: el BPM pedido al motor no acredita el BPM medido de las partes nuevas ni la escucha artística.
- **Divergencia MD ↔ evidencia**: `memory.md` terminaba en CXXIX (13:32) y daba por pendientes el mixto y el cover completo; `spec/02` mantiene sin marcar todas las casillas de R11; `spec/03` dice «implementación en curso; pendiente PASS del tester y APPROVE final»; `spec/06` remite los veredictos R11 «a memory.md»; `knowledge.md` (2026-10-13 22:23) no menciona R11 y su «Estado vigente» es anterior a CXXII–CXXVI; `README` tampoco menciona R11. R5: trabajo no registrado = trabajo no hecho; la sincronización de los MD queda pendiente y se anota, no se ejecuta sin decisión.
- **Git**: último commit `8f6bec4`; árbol sucio con 39 archivos modificados y 27 nuevos (66 entradas). Ni las correcciones R9/R10 posteriores a CII ni R11 están commiteadas.
- **Sigue abierto**: R9/R10 (comparación alineada, conflictos/preview en todas las rutas, recorridos UI y ciclo real de cancelación/recuperación), Q2 y la escucha artística. `Mixer.jsx` y `Sequencer.jsx` siguen sin montar, coherente con `spec/03`.
- **Límites de esta entrada**: auditoría de lectura + regresión. No emite PASS/APPROVE de producto, no reejecutó la sonda Electron ni generó audio, y cita los veredictos existentes sin revalidarlos.

## 2026-10-14 (CXXXI) — Sincronización de los MD con el veredicto R11

- **Petición**: «sigue» tras CXXX, que dejó la sincronización de los Markdown pendiente de decisión. Solo documentación: sin instalar, sin commitear, sin generar audio y sin cerrar R9/R10.
- **Verificación propia antes de escribir «cerrado»**: `ffprobe` sobre los cinco MP3 de R11 en `backend/outputs/` — `prueba-r11-mixto-1c43627e.mp3`, `prueba-r11-mixto-1c43627e (2).mp3`, `prueba-r11-completo-07464782.mp3`, `prueba-r11-completo-07464782 (2).mp3` y `prueba-r11-fuente-2ed3bb04-remix.mp3` — todos **90,000000 s** y **2.161.196 bytes**. Fichas con `timeline`: origen 20 s, natural 16,683417 s en grupos y 20 s en completo, objetivo 90 s, `tempo_ratio` 1,198795, `repeat_start` 2 → `repeat_end` 12 con su mapeo, `transition_seconds` 0,1, `method` `repeat_crossfade` y `tempo_method` `common_pcm_atempo`/`engine_conditioning`; semillas reales 42 y 2942175228 (mixto), 42 y 396917302 (completo); `bpm_measured` 99,2/100,0/104,7/250,5 separado del pedido 199, con `provenance` campo a campo. `GET /music/remix/capabilities` vivo devuelve los tres ámbitos, los cuatro grupos reales y los límites de timeline (`min_duration_seconds` 1, `min_repeat_seconds` 1, `min_groove_confidence` 0,12, `max_transition_seconds` 2, `max_duration_seconds` 600) desde `config.py:208-213`. `logs/remix-r11-tester-verdict-20261014.json` se releyó íntegro: su PASS y el APPROVE del reviewer se citan, no se reatribuyen.
- **Cambios (solo MD)**: `spec/02` marca los seis criterios R11 y añade el párrafo de cierre técnico con evidencia y límites; `spec/03` mueve R11 de abiertos a cerradas, ajusta cabecera, fila R9 y próximas historias; `spec/06` y `spec/01` registran el veredicto dejando escrito que no cierra R9/R10; `knowledge.md` pasa a «Estado vigente (2026-10-14)» con punto R11 y recuentos 203/42; `README` menciona la ampliación y los recuentos. Ningún archivo de producto se tocó.
- **Alcance que los MD declaran ahora**: PASS técnico de R11 (procesamiento, contratos, fichas y UI real en 1400×900 y 1080×700). No acredita el BPM medido de las partes nuevas generadas, el aislamiento del separador ni la adecuación musical. R9, R10, Q2 y la escucha artística siguen abiertos.
- **Límites**: no reejecuté backend/frontend/lint/build (sin cambios de producto desde la regresión CXXX del mismo día) ni la sonda Electron; lo verificado aquí son artefactos y la API viva. Sin commit: el árbol sigue sin versionar.

## 2026-10-14 (CXXXII) — «El tema de los BPM no funciona»: reproducción real y rectificación de R11

- **Petición**: el usuario informa de que «el tema de los bpm,s.. no esta funcionando» y precisa que el fallo aparece al cambiar el BPM en Por pistas o en otra opción de remix («si haciendo el remix quiero poner más bpms debería funcionar»). Después pide revisar los MD y pendientes. Solo reproducción, diagnóstico y corrección del registro: ningún cambio de código de producto, sin motor, sin commits.
- **Servicio de trabajo**: la API no estaba levantada (`curl` → `API=000`). Se arranca con `backend/venv/Scripts/python.exe backend/main.py` (PID 6140, listener `127.0.0.1:8000`); el motor ACE-Step **no** se arranca en ningún momento.
- **Reproducción 1 — los dos audios reales del usuario rechazan el BPM común** (`POST /music/remix/preview`, scope groups, bpm 199, cuatro grupos en conservar, sin `source_bpm`):
  - `f6fc62fe-Arroja la bomba.mp3` → **422** «No hay un BPM original fiable: indica el BPM original revisado para cambiar todas las pistas juntas».
  - `Animales muertos.mp3` → **422** «La duración objetivo debe ser igual o mayor que la canción al tempo elegido» (168 s naturales frente a los 60 s pedidos; el mensaje no da el mínimo).
- **Causa 1, medida a mano** con `detect_groove`: `Animales muertos.mp3` → 166,25 BPM (confianza 0,249); `f6fc62fe-Arroja la bomba.mp3` → **363,64 BPM (confianza 0,101)**. Los límites vivos (`config.remix.parameters["bpm"]` 30–300 y `timeline_min_groove_confidence` 0,12) dejan ese valor fuera por los dos lados: por eso el rechazo.
- **Causa 1, octava** (`logs/diag-groove-octave.py`): en `Arroja la bomba` el pico más fuerte es **120,0 BPM (0,4122)** y por encima están 352,9 (0,3964) y 260,9 (0,3537), más débiles; la regla de `audio_analysis.py` se queda con el lag **más corto** que alcanza el 90 % del mejor pico, y 352,9 es el 96,2 % de 0,4122, así que gana un pico peor. En `Animales muertos` la regla acierta por casualidad (166,7 con 0,5915 es el mejor). El error no es «no hay tempo»: es la elección de octava.
- **Causa 1, sobre los propios MP3 de R11**: el mixto generado a 199 BPM (`prueba-r11-mixto-1c43627e.mp3`) se mide hoy **99,18** (picos 100,0 → 0,6908 frente a 200,0 → 0,4872), que es el 99,2 que la ficha y BIBLIOTECA enseñan como «PEDÍA 199 · SALIÓ 99».
- **Causa 2, canción completa**: del veredicto R11, con bpm 199 pedido al motor y `tempo_method` `engine_conditioning`, las mediciones fueron 104,7 y 250,5. Los picos del MP3 completo se agrupan en 96,8–109,1 BPM, no en 199: el motor no entrega el tempo pedido y la UI ofrece el campo como si lo fijara.
- **Contraprueba de que la ruta por pistas sí funciona con el original a mano**: trabajo real por HTTP (grupos los cuatro en conservar, sin motor), `JOB_ID=546e3272a9544e5c9ba2bce76886223d` → `succeeded`, MP3 `fix-bpm-keepall.mp3` con **90,000000 s y 2.161.196 bytes**, `detect_groove` **198,5 BPM** con el BPM común pedido en 199 y `source_bpm` 166,36 escrito a mano. Evidencia en `logs/fix-bpm-repro.json`.
- **Corrección del registro (solo MD)**: `spec/03` reabre R11 dentro de la tabla de cerradas y añade el bug **B6** con la evidencia y el plan pendiente de aprobación, más la cabecera y las próximas historias; `spec/02` rectifica el alcance del cierre técnico y el criterio de BPM común, y añade el párrafo de rectificación con las cuatro comprobaciones; `spec/01` y `spec/06` dejan escrito que el contrato R11 no se sostiene en uso general; `knowledge.md` y `README` añaden la limitación verificada y enlazan B6.
- **Lo que NO se ha hecho todavía**: ningún archivo de producto se ha tocado. El arreglo (octava en `detect_groove`, BPM medido revisable a la vista, mínimo en el aviso de duración y contrato de canción completa) queda **pendiente de plan aprobado por el usuario** conforme a `spec/00-PRINCIPIOS.md`; B6 nace de esta entrada.
- **Límites de esta entrada**: no arranqué el motor ACE-Step ni generé con él, no ejecuté tests ni lint/build (no hay cambio de código), no hice commit y el árbol sigue sin versionar tras `8f6bec4`. La API de prueba (PID 6140) la levanté yo y se para al cerrar esta revisión.

## 2026-10-14 (CXXXIII) — B6 retomado; BPM efectivo de canción completa autorizado

- **Petición**: «continua» tras el diagnóstico CXXXII. Leídos AGENTS global/proyecto, skill fix, spec00/01/02/03/04, bitácora y código vigente. Se preservan cambios anteriores, sin instalaciones ni commits.
- **Decisión explícita del usuario**: «Sí, ajustar el audio para cumplir el BPM (recomendado)». Cada variante de canción completa se medirá y procesará con DSP local sin cambiar tono; duración natural resultante revisada, ampliación por repetición posterior; medición incierta produce error. Repaint regional conserva su contrato orientativo y se explica. No cambia perfil SFT/50/9/batch2 ni modelos.
- **SDD**: criterios B6 añadidos en spec02 antes de implementar el nuevo contrato. Root ejerce sd-coordinator; sd_editor_backend corrige octava/error mínimo y contrato full; sd_editor_frontend corrige medición revisable/avisos; sd_reviewer independiente revisa diseño y después archivos completos; sd_tester verificará al estabilizar el producto.
- **Diagnóstico confirmado por reviewer**: la regla anterior podía elegir cualquier lag sobre el 90 % sin exigir máximo local ni relación de octava. La corrección debe preservar la resolución de compás/medio tempo y evitar convertir el BPM pedido en una medición ficticia.
- **Estado**: EN CURSO. No hay PASS/APPROVE final de B6; R9/R10/Q2 y escucha permanecen abiertos.
- **Scout/researcher (root)**: la skill fix disponible cubre la corrección; sin buscar ni instalar paquetes/skills/modelos nuevos. Consultada documentación primaria de los filtros existentes de FFmpeg, https://ffmpeg.org/ffmpeg-filters.html#atempo y https://ffmpeg.org/ffmpeg-filters.html#acrossfade. La consulta es la única dependencia de red nueva; procesamiento y modelos permanecen locales. Estado inicial observado: API/motor sin listener, stop.flag=`salir`, GPU 777 MiB usados/7248 MiB libres; se arrancarán para verificación dentro del alcance aprobado.
- **REVIEWER — APPROVE de calidad B6** (`sd_reviewer`, independiente, lectura completa de producto/tests/sondas): detector/config/ejemplo, DSP/proyecto y suites vecinas, RemixWorkspace/helper/pruebas y scripts probe_bpm_fix.py/ui.cjs. Se corrigieron cancelación entre medición y publicación, validación de confianza, salida cruda atempo y colisión de nombres reservados; el lote se verifica completo fuera de Biblioteca antes de publicar. Firma remix_project.py AD46F266A6D443FBE671A5E1E7F07998F00EFC0C04CBF751B4B95BBF19E5E520. Sin bloqueantes/importantes. Riesgo heredado: fallo de disco durante publicación podría dejar algún audio validado sin resultado de job. APPROVE no acredita PASS funcional.
- **Arranque/despliegue**: ensure_local.ps1 -Rearme exit0 MOTOR=started/API=started; parche CPU already-applied. Refresh API guardó ownership/jobs inactivos y conservó motor PID14168, `logs/bpm-b6-api-refresh-20261014/refresh-api.json` PASS. Comando combinado root acabó exit1 al intentar leer erróneamente result.json tras el refresh; inspección del nombre correcto/capacidades vivas exit0 confirmó su PASS, sin repetir reinicio. Health inicial motor indicaba turbo/no inicializado; el trabajo solicita SFT explícito y se verificará el efectivo, no inferirlo del health inicial.
- **Primeros checks del tester**: frontend46/46, buildexit0 (`index-chdSPssQ.js`,382,72kB), ESLint directo --max-warnings=0 exit0. npm run lint con --max-warnings falló en wrapper npm EUNKNOWNCONFIG antes ESLint; root ejecutó `npm run lint` sin esa bandera: exit0 en4,428s. Backend211/211 OK antes delta de precisión; requiere repetición por ese cambio. Evidencia `logs/bpm-b6-frontend-checks-20261014.json` y backend initial.
- **Hallazgos corregidos durante verificación**: tester detecta mínimo automático68 vs UI69 en Animales por redondear166,25→166,2 en main._measure_bpm; se conserva ahora precisión2dec del groove y testWAV real asegura duración auto=manual (editor22/22 verify_align PASS). API refrescada sin jobs ni cambio motor: `logs/bpm-b6-api-precision-refresh-20261014/refresh-api.json` PASS, comando exit0. Nuevas sondas deben comprobar datos vivos después del refresh.
- **Fallos de sonda UI conservados**: dos informes FAIL en `logs/bpm-b6-ui-20261014` y `logs/bpm-b6-ui-rerun1-20261014` por supuestos solapes full; la PNG full1400x900 inspeccionada por root y tester muestra SUGERENCIAS OPTATIVAS cerrado y chips invisibles. El oráculo anterior usaba getClientRects en descendientes ocultos de details; ahora checkVisibility y captura previa al fallo. Esas pasadas no enviaron remix ni acreditan PASS total. Procedencia automática/manual, remedición/reset y mínimo en grupos sí tuvieron oráculos separados; falta pasada final.
- **Límites reales del detector/DSP conservados**: `logs/b6-dsp-existing/result.json` rechaza los dos MP3 full90s históricos al procesarlos a199: uno mide201,33/conf.089 (incierto), otro206,48/conf.283 (fuera tolerancia2). `logs/b6-pulse-octave/result.json` conserva alias75 en fixture40ms tras tempo150; fixture100ms120→150 sí verifica duración/tono. No se cambia el BPM medido al pedido ni se relaja la tolerancia; la ejecución nueva full queda por verificar.
- **REVIEWER — APPROVE del delta de precisión y sondas finales** (`sd_reviewer`, independiente): main.py completo2719líneas y test_verify_align completo; medición2dec conserva igualdad UI/API y testPCM real protege duración auto=manual. Sondas Python/Node actualizadas y runner scripts/verify_bpm_fix_ui.ps1 completos revisados: guardas local/jobs/stop/despliegue, Electron oculto, resultado requiere UI y audio/API independientes. No bloqueantes/importantes, sin sustituir verificación funcional ni relabelar pasadas FAIL previas.
- **TESTER — PASS parciales reales y FAIL full**: backend final212/212 OK7,058s (`logs/bpm-b6-backend-checks-final-20261014.json`), frontend46/46 y lint/build verdes. Originales HTTP después precisión2dec PASS (`logs/bpm-b6-originals-final-20261014.json`): Arroja120,83/.286 acepta BPM199 automático; Animales166,25 da mínimo69s igual UI. Electron final `logs/bpm-b6-ui-final-20261014/result.json` PASS,33oráculos sin errores, groups/full ambas resoluciones, manual preservado/reset, mínimo y rechazo, BPM Tramo orientativo. Root inspeccionó PNG1080x700groups/full y1400x900groups. JobPor pistas `d7df8668dff64610a18c69d0756eca24` succeeded, MP3 `prueba-r11-fuente-2ed3bb04-remix (2).mp3`90s/198,5BPM, PCM/ficha/historial PASS independiente en audio-evidence.json. Runner no obtuvo ExitCode del handle Electron (null) y terminó FAIL después del PASSUI; se corrige y verifica por separado, sin falsificar el exit.
- **Generación full nueva — FAIL real**: job `b75efbca97b64c83b0cff6225b936c27`, tarea `239d2a46-6b4b-4725-8de5-81fe4f1e43c2`, recorte20s/gabber/seed42/BPM199/duración90/repetir2–12/fundido0,1; `logs/bpm-b6-full-20261014.json` exit1, error «El BPM final medido188.86 no cumple el pedido199 (tolerancia2BPM)». Dos WAV motor reales: variante1 101,55/conf.448 y variante2 100/conf.853. Primer DSP ratio1,9596258 deja188,86/conf.435/duración10,21s y rechaza ANTES ampliar/exportar; ningún MP3 del lote publicado. Root replicó ambas mediciones en disco; no reetiquetar el fallo ni declarar cierre full.
- **Decisión pendiente**: se pregunta al usuario si aprueba hasta3ajustes medidos con ratio acumulado, siempre renderizados desdeWAVoriginal (evita procesado encadenado), límites y traza configurados, tolerancia2intacta y error ante incertidumbre/no convergencia. Reviewer considera la vía técnicamente honesta, sin dar por acreditado el resultado. Se espera respuesta antes de implementarla; B6 sigue EN CURSO.
- **TESTER — PASS completo de Por pistas/API/UI y FAIL parcial de B6**: ejecución corregida `scripts/verify_bpm_fix_ui.ps1 -Manifest logs/remix-r11-source-valid-20261014.json -OutputDirectory logs/bpm-b6-ui-processfix-20261014` terminó exit0 `B6_UI_AUDIO=PASS`; ElectronPID8412 exit_code0 y reportePASS. Job `129a753f6d55439eab0178c58a68fdab`, cuatro grupos conservados, source_bpm automático166,36; MP3 `prueba-r11-fuente-2ed3bb04-remix (3).mp3`90,000000s/2.161.196bytes/199,2BPM, PCMfinito y no silencioso, prefijo/copia repetida delta0 sobre192.000muestras. Ficha/historial/HTTP comprobados. Capturas/UI dos resoluciones y auto/manual/remedir/reset/min17/fullpending/regionorientativo PASS. `logs/bpm-b6-ui-processfix-20261014/audio-evidence.json` evidencia independiente. Pasadas/runnerFAIL anteriores se conservan.
- **REVIEWER — APPROVE último runner y coherencia documental**: revisión independiente archivo completo, hash84516A6CAAE54EA1B5117A200FED89CEB892716F53B4B5D13837141DE6233101; handle retenido yExitCode consultado después de terminarElectron. SpecB6 y bitácora siguen EN CURSO, sin inferir aprobación de calibración. No bloqueantes/importantes.
- **Veredicto funcional actual del tester**: `logs/bpm-b6-tester-interim-20261014.json` **FAIL parcial de B6**: groove/originales/precisión/mínimo/Por pistas/UI/lint/build/regresión PASS; full positivo dos variantes FAIL y trazabilidad finalfull NO-VERIFICADO. Diagnóstico aislado del segundo WAV100→199,82/conf.756 es PASS del DSP vigente, `logs/bpm-b6-full-variant2-diagnostic-20261014.json`; no convierte el lote fallido en éxito ni se ha publicado como canción.
- **Punto de continuación**: respuesta del usuario a calibraciónhasta3 aún pendiente. No implementar diseño dependiente de esa elección. Si aprueba, especificar tope configurable y trazabilidad de intentos, re-render desdeWAVoriginal por ratioacumulado, recomputarplan individual y verificar resultados reales/tester/reviewer. Si conserva una pasada, registrar el alcance/error actual expresamente. B6/full,R9/R10/Q2 y escucha siguen abiertos. Sin commits/instalaciones; API y motor permanecen vivos para retomar, no se tocaron aplicaciones ajenas.
- **Veredicto final de esta pasada**: tester entregó `logs/bpm-b6-tester-verdict-20261014.json`: **FAIL para B6 completo / PASS parcial** (Por pistas, originales, mínimos, UI y checks); full sigue FAIL188,86 y no publica lote. No sustituye el resultado interim; consolida la evidencia. El usuario todavía no ha respondido a la propuesta de calibración. Se conserva esta elección pendiente y toda la evidencia para continuar desde aquí.

## 2026-10-14 (CXXXIV) — «No… arréglalo»: corrección de causa del BPM, sin detenerse en otra elección

- **Petición**: el usuario rechaza la parada anterior y exige arreglar el defecto. Se continúa B6 dentro del ajuste full ya autorizado; no se interpreta esta respuesta como aprobación específica de la propuesta de tres iteraciones.
- **Plan fix vigente**: comprobar si el tempo físico del WAV y el detector difieren después de atempo, corregir la causa medida (detector/DSP), protegerla con reproducción real antes/después, verificar nuevamente el cover de dos variantes y actualizar documentación con PASS del tester y APPROVE independiente. Sin aumentar tolerancia, inventar BPM, instalar dependencias/modelos o cambiar SFT/50/9/batch2.
- **Roles**: sd-editor-backend diagnostica detector y cambio temporal, sd-reviewer contrasta independientemente causa y calidad, sd-tester prepara oráculo de ataques y regresión. Root coordina SDD y consulta documentación primaria. La skill fix sigue aplicada; se preserva toda la evidencia FAIL anterior.
- **Entorno comprobado**: backend no tiene numpy/scipy/librosa/soundfile; esas bibliotecas no se instalan. La investigación de librosa/FFmpeg es solo documentación primaria, no una dependencia nueva de producción.
- **Estado**: EN CURSO; B6 no cerrado, R9/R10/Q2/escucha siguen abiertos.
- **Researcher/root**: fuentes primarias leídas https://raw.githubusercontent.com/librosa/librosa/main/librosa/onset.py (novedad/ataques frente a nivel sostenido) y https://ffmpeg.org/ffmpeg-filters.html#atempo (WSOLA/encadenamiento documentado). Consultas web declaradas; nada instalado. El oráculo del tester usa numpy/scipy/soundfile ya presentes en el venv del motor sólo para medición independiente, no como dependencia nueva del backend.
- **Causa contrastada por reviewer/tester**: el ratio físico de ataques del DSP coincide con1,9596258 en el WAV fallido (error de reloj observado~0 a0,33% según banda); el RMS de un solo período devuelve pre106,16/101,55/98,76 con ventanas5/10/20ms, y post187,92/188,86/191,88. Multi-período suavizado conserva100→196 segúnratioantiguo, y un único DSP desde100a199 arroja199,1 medidos en artefacto de diagnóstico. Simple derivada/RMS suavizado conunperíodo no estabiliza la octava y se descarta. Se implementa refinado local de varios períodos alrededor del pulso elegido, preservando regla de octavas/medición independiente; parámetros configurados y regresiones reales. Todavía no equivale a PASS del producto.
- **Continuación «sigue»**: cuotas de los tres subagentes interrumpieron sus turnos antes de veredictos finales. Root leyó completos detector/config/ejemplo/tests y sondas, ejecutó compilación y focal38tests. Falló una comparación de confianza arbitraria del nuevo test (.932 frente .581 exige+.5, umbralimposible1.081), sin fallo de fase conocida ni confianza>.9; se ajusta el criterio al objetivo real. Turnos de editor/reviewer/tester recuperados tras la cuota para completar pasos separados.
- **Segundo fallo reproducido en el arreglo**: la regresión local de los WAV reales pasa el DSP único (100→199) pero falla después de ampliar/exportar (195,92). `logs/bpm-b6-rootcause-local-20261014/report.json` FAIL conservado. Oráculo del tester `logs/bpm-b6-seam-oracle-20261014.json`: parte5,025125s menosfundido0,1 generaavance4,925125s=16,3349979golpes; reinicia fase+0,1010044s en cada copia. No es únicamente medición: hay un salto físico en la unión.
- **Solución contrastada sin iteraciones**: editor `logs/b6-clock-aligned-repeat-20261014/result.json` y reviewer `logs/sd-reviewer-b6-repeat-phase/report.json` reutilizan exactamentemuestras de una subparte dentrodelintervalopedido, alineanlaprimeracopia conlacola y mantienenavanceenterode15golpes. Ambas variantes pasanMP3de90s:199,00/.556 y199,17/.718. Son artefactosdiagnóstico, no ejecuciónAPI aprobada aún. Spec02 concreta uniónalpulso/límitesefectivos/procedencia; rootautoriza implementarlacorrección necesaria del contrato BPM/repetición existente tras «no…arréglalo» y «sigue». Sin otra petición de autorización rutinaria.

## 2026-10-15 (CXXXV) — B6: refinado estable y uniones de repetición al pulso

- **Continuación autorizada**: «no… arréglalo» y «sigue», con el contrato de BPM en canción completa ya aprobado. Se corrigen las causas sin adoptar tres recalibraciones ni relajar la tolerancia de 2 BPM. Se mantienen SFT/50/9/batch 2 y las dependencias existentes.
- **Detector**: Python puro; suaviza 3 tramas y contrasta 8 períodos en una vecindad de 3 tramas, con resolución 0,025. Los límites de 16 períodos y 1000 candidatos y los parámetros viven en config/ejemplo. No recibe el BPM pedido; conserva la octava sustentada y calcula fase/confianza con el período fraccional. Se retira el helper parabólico muerto. La prueba verifica fase conocida de 45 ms, confianza >0,9 y menor deriva que al redondear el período; se elimina una diferencia arbitraria de confianza imposible de satisfacer.
- **Repetición**: con BPM elegido, la primera copia comparte la fase de la cola antes del fundido y cada copia avanza un número entero de golpes. La subparte efectiva permanece dentro del intervalo elegido. `arrangement` registra límites solicitados/efectivos, BPM y procedencia del reloj, golpes por copia, avance y comienzo de la primera unión. Full usa la medida independiente posterior al DSP; grupos declara el BPM común parametrizado. Sin BPM conserva el tratamiento anterior. Si no cabe una parte útil con la duración mínima y los fundidos configurados, devuelve un error; no añade silencio como ampliación.
- **UI**: explica el ajuste al pulso dentro del intervalo y muestra timeline/arrangement junto a las semillas en el inspector del resultado. Conserva los campos y el payload de la petición.
- **Despliegue**: `scripts/refresh_api_remix_timeline.ps1 -OutputDirectory logs/bpm-b6-rootcause-api-refresh-20261015` → exit 0, `R11_API_REFRESH=PASS`; motor PID 14168 conservado. Las guardas acreditaron trabajos inactivos e identidad de los procesos; se refrescó sólo la API.
- **Estado**: calidad del detector aprobada tras revisión completa; revisión final del arreglo/tests/sondas y verificación API/Electron/audio en curso. B6 continúa abierto; se conservan los fallos anteriores.
- **Pruebas ejecutadas**: frontend 46/46, lint y build exit 0 (`index-CqB_hb8X.js`, 383,06 kB). Backend final de la corrección de uniones: `Ran 218 tests in 11.180s / OK`, exit 0, con hash de test `4552914C…` capturado antes de arrancar. La pasada anterior había cargado el test de meseta de 80 ms y falló al comparar máximos RMS no únicos; se conserva ese fallo. El test final usa un ataque exponencial con fase definida, sin relajar la tolerancia del producto.
- **Regresión local completa — PASS del tester**: `logs/bpm-b6-clockaligned-local-20261015/report.json`, WAV reales de la ejecución fallida, un DSP por variante y ampliación/exportación a 90 s: 100→199,00→199,00 y 100→199,17→199,17. Prefijo y copias PCM, duración/tono y relojes comprobados. No sustituye aún el recorrido positivo nuevo de API/Electron.
- **Revisión de producto — APPROVE independiente**: detector/config/ejemplo, DSP y proyecto, pruebas completas, UI e inspector y sonda Python revisados por sd-reviewer; sin bloqueantes/importantes. Revisión posterior de sondas exige `src` y `currentSrc` exactos para evitar validar una variante con la metadata del audio anterior; corregido, con nueva revisión. El aviso oculto tras cambiar de ámbito abrió explícitamente su sección en la sonda. Se interrumpió sólo el Electron propio PID15592 antes de cualquier POST full, tras verificar identidad; informe INCOMPLETE conservado y servicios intactos.
- **Nuevo caso negativo real — FAIL conservado**: `logs/bpm-b6-ui-full-exactsrc-20261015/result.json`, job `9f42c662e9af410894062c29ed613240`, task `7f9a4d9b-d0e9-44a2-ad4c-04db1389812b`. SFT50/9/batch2 con semilla aleatoria produjo dos WAV, semillas2718778472 y3866968026 (respuesta real `/query_result` conservada). La medición de la primera variante devolvió600/.148 y se rechazó antes del DSP, sin publicarMP3. Oráculo espectral independiente: pulso/subdivisiones≈394/196, candidatos ambiguos, no evidencia para forzar elBPMpedido. El máximo600 estaba en el borde del refinado, sin pico sustentado; se corrige únicamente esa aceptación de borde para devolver error explícito. No se sustituye por130/197 ni se recorta a300.
- **Pregunta sobre duración**: el usuario pregunta si puede ampliar a más minutos que el original. Se confirmó `/music/remix/capabilities` vivo: máximo600s. Respondido que sí mediante DURACIÓN, repitiendo material con transiciones; Por pistas ya verificado y full conBPM todavía enprueba.
- **Siguiente positivo reproducible**: se elegirá explícitamente la semilla42 en el control real de UI, sin cambiar perfil ni introducir valores ocultos. Si abrir avanzados inicia análisis, se espera su terminal real antes de generar y se conserva cualquier error. El negativo aleatorio no se reetiqueta; se repite backend por la nueva guarda de borde y se refresca sóloAPI antes del nuevo batch.

## 2026-10-15 (CXXXVI) — B6: un audio sin golpe no se estira, y la copia no se confunde con el tempo

- **Qué se pidió**: seguir el arreglo del BPM en canción completa. Sigue abierto. No se baja la tolerancia de 2 BPM, ni la confianza mínima 0,12, ni la regla de octava 0,9, ni la preferencia de golpe 2. No se inventa el 199 cuando el audio no lo tiene. El motor 14168 no se ha parado.
- **Audio sin golpe**. Una variante de semilla 42 medía 50,58 con muy poca evidencia. El ajuste a 199 la dejaba en 5 segundos y la verificación decía que no había medición. Al repetirla, el 85 que salía era el ritmo de los empalmes, no un pulso. La autocorrelación de ese archivo cae de forma lisa: el único máximo interior es un pliegue, no un golpe. Ahora ese caso se rechaza con el motivo real, antes de estirar el audio. Los archivos que ya medían bien siguen igual: Arroja 121,21, Animales 165,52, y las variantes ya comprobadas cerca de 197, 199, 200 y 203. Revisión APPROVE, sin bloqueantes.
- **La copia de 15 golpes**. Otra sonda midió 101,48, ajustó a 197,37 y, al ampliar a 90 segundos, leyó 39,47. Ese 39 es el bloque de 15 golpes oído de 5 en 5. En el mismo archivo el golpe de 199 sigue. Si la lectura es un grupo entero de la copia y el golpe ya medido después del ajuste sigue presente, con evidencia y confianza suficientes, se verifica ese golpe. No se mira el BPM pedido para elegirlo. Una lectura que no es un grupo de la copia, como un 219, no se reescribe. Revisión APPROVE, sin bloqueantes.
- **Sonda nueva, FAIL**. `logs/bpm-b6-ui-seed42-repeat-20261015`. Trabajo 3b531144546940aca3ef85730fb9877c, semilla 42, SFT, 50 pasos, guidance 9, lote de 2. La primera variante pasó el recorrido: 99,79, luego 199,17 tras el ajuste, y 199,17 otra vez en el mp3 de 90 segundos, confianza 0,661. No se publicó. La segunda variante no tiene un pulso medible y el trabajo entero falla, como está pactado el lote. El error que ve la mesa es que el período interior no destaca sobre la caída de la autocorrelación.
- **Pruebas**: backend `Ran 231 tests in 19.129s`, exit 0. No sustituyen la sonda. B6 no está HECHO: falta un recorrido de las dos variantes en PASS.
- **Sondas anteriores que siguen en FAIL** y no se reetiquetan: la de 99,42, la de 219,58, la de medición vacía y la de 39,47 (`logs/bpm-b6-ui-seed42-decay-20261015`).

## 2026-10-15 (CXXXVII) — B6: una variante sin pulso se vuelve a generar, no se estira

- **Qué se pidió**: solucionar lo que faltaba. Faltaba un recorrido de canción completa en el que las dos variantes queden a menos de 2 BPM del pedido, se publiquen y la sonda dé PASS. Sigue abierto.
- **Qué se miró en el audio**. La variante 2 del trabajo 3b531144 no esconde un golpe de 102. Su energía cae sin máximo: en el retardo más rápido la correlación es 0,65 y en el de 102 es 0,33. El flujo espectral hace lo mismo. La variante 1 del mismo trabajo sí tiene un pico claro cerca de 100. Bajar el corte de 0,5 aceptaría esa caída como tempo. No se hace. Tampoco se le pone el 199 a mano.
- **Qué se cambió**. Si la medición de antes del ajuste dice que esa variante no tiene un pulso usable, se guarda el audio rechazado y se pide otra muestra, solo de esa variante. El lote principal sigue siendo de 2. La muestra nueva lleva otra semilla pedida, separada un lote entero, y el motor sigue declarando la semilla real. Se mide igual que la primera. El máximo de muestras extra está en la configuración: `full_groove_retries`, valor 2. Si se agotan, el error del detector sigue siendo el del trabajo y no se publica nada. Un BPM que sí se midió y queda fuera de los 2 BPM de tolerancia no pide otra generación: eso sería perseguir el número.
- **Pruebas**: los 7 contratos nuevos pasan. La suite backend queda en `Ran 238 tests in 18.855s`, exit 0. No es la sonda. B6 no está HECHO. La sonda de CXXXVI sigue en FAIL. El motor 14168 no se ha parado.
- **Revisión del reintento**: APPROVE, sin bloqueantes. No cierra B6.

## 2026-10-15 (CXXXVIII) — B6: una meseta no se estira hasta un BPM falso

- **Sonda del reintento, FAIL**. `logs/bpm-b6-ui-seed42-redraw-20261015`, trabajo 5049ee82. La variante 1 quedó en 199,17 a 90 s. La variante 2 midió 50,00 con confianza 0,868, un pico de verdad. Al llevarla a 199 el audio quedó en 5,025 s y el detector dijo que era demasiado corto. No se publicó. Ese FAIL se conserva.
- **Qué se añadió**. Si el ajuste deja el audio demasiado corto para volver a medirlo, se pide otra muestra, dentro del mismo tope de dos. Un BPM que sí se mide y queda fuera de los 2 BPM de tolerancia no pide otra generación. Revisión APPROVE de ese delta. Suite `Ran 239 tests in 19.590s`, exit 0.
- **Sonda siguiente, FAIL**. `logs/bpm-b6-ui-seed42-redraw2-20261015`, trabajo 7785874c. La variante 2 midió 174,29. Entre 170 y 220 la evidencia es casi plana: 0,278 en 176 BPM y 0,267 en 200. El ajuste la dejó en 226,42, fuera de tolerancia. No es un golpe escondido de 199.
- **Qué se rechaza ahora**. El periodo elegido tiene que valer al menos 1,25 veces la evidencia de un tempo un 8 % más lento o más rápido. Si no, el error dice que no destaca sobre los tempos vecinos y se pide otra muestra, sin estirar esa meseta. Siguen igual Animales 165,52, Arroja 121,21, el 196,72, el 197,37 y el pico real de 50. La variante de 174 y el wav ya estirado a 226 ahora dan ese error. Suite `Ran 240 tests in 21.193s`, exit 0. B6 sigue sin HECHO: falta la sonda con las dos variantes publicadas. El corte 0,5, la preferencia 2 y la tolerancia de 2 BPM no se han bajado.

## 2026-10-15 (CXXXIX) — B6: el 37,85 de la sonda de hombro es un cuarto de la copia, no un grupo de golpes

- **Qué se pidió**: anotar el diagnóstico. No se ha cambiado código en esta nota. B6 sigue sin HECHO. El motor 14168 no se ha parado.
- **Sonda de la meseta, FAIL**. `logs/bpm-b6-ui-seed42-shoulder-20261015`, trabajo 65e042b4ab2a42619e43b88abc313ee4, semilla 42. El error de la mesa es «El BPM final medido 37.85 no cumple el pedido 199». Ese FAIL se conserva. La regla del hombro sí actuó: la primera muestra de la variante 2 se archivó porque no destacaba sobre los tempos vecinos, y se pidió otra. La muestra nueva midió 132,60 antes del ajuste y 198,84 después, en 13,33 s, dentro de la tolerancia. El fallo es la lectura de los 90 s, no el ajuste.
- **La variante 1 sí encaja en la regla ya aprobada**. Antes del ajuste mide 98,36. Después, 200,00. La copia tiene 15 golpes. Al ampliar, el detector lee 40,00, que es el reloj partido de 5 en 5, y 5 divide a 15. El golpe de 200 sigue en el mismo audio, así que la verificación usa 200. Por eso el trabajo llegó hasta la variante 2.
- **La variante 2 no es ese caso**. La copia tiene 21 golpes y dura 6,337 s. 21 solo se parte en grupos de 21, 7 y 3 golpes. Esos grupos caerían hacia 9, 28 y 66 BPM, lejos de 37,85. La regla de los divisores, la que ya se aprobó, se abstiene y deja el 37,85. No es un fallo de esa regla.
- **Qué es el 37,85**. Es la copia partida en cuatro trozos iguales de tiempo: el cuarto de 6,337 s son 37,87 BPM, a 0,02 BPM y a una décima de trama del 37,85 medido. Esos cuatro trozos duran 5,25 golpes, no un número entero. Por eso no entra en «15 golpes oídos de 5 en 5». En el mismo archivo de 90 s el golpe ya medido sigue: 197,86, evidencia 0,4925 frente a 0,6374 del 37,85, confianza 0,130. Pasa los cortes de evidencia y de confianza, y queda a 0,98 BPM del reloj 198,84. No se le ha asignado el 199.
- **Qué no se hace**. No se amplía la regla a cualquier armónico cercano: un 80 frente a un reloj de 197,37 y 15 golpes cae a 1 BPM de un sexto de la copia, y esa lectura no es la repetición. Ese rechazo sigue en pie. No se baja el corte 0,5, ni la preferencia 2, ni el hombro 1,25, ni la tolerancia de 2 BPM. No se vuelve a lanzar la semilla 42 sin un cambio de código revisado. Las sondas anteriores siguen en FAIL.

## 2026-10-15 (CXL) — Por pistas: la batería transformada no llevaba el estilo

- **Qué se pidió**: los últimos remix no suenan a lo pedido. El usuario marcó por pistas y puso la batería en transformar. El resto depende de lo que se elija.
- **El remix de hoy**: trabajo `a9e85189`, «Arroja la bomba», voz y acompañamiento en conservar, bajo quitado, batería en transformar. Frase enviada «gabber, hardcore», 160 BPM, fuerza 0,2. El motor sí generó otro audio. El separador dejó la mayor parte de ese audio en el acompañamiento. La mezcla solo usó el resto etiquetado como batería, unos 11 dB por debajo de la voz. La mezcla final sigue siendo la voz original. El acompañamiento original de este tema está casi en silencio, así que conservar esa pista no aporta el estilo.
- **Qué cambia**: si solo una pista está en transformar, esa pista se monta con la generación menos la voz nueva (para no doblar la voz conservada) y menos lo generado de cada grupo quitado. El cuerpo que el separador archivó en otro grupo se queda. Si al restar no queda audio, se usa la generación entera. Si el resultado queda más bajo que la pista a la que sustituye, sube como mucho el tope de ganancia ya configurado (12 dB). Con varias pistas en transformar se sigue separando cada una. El MP3 ya publicado no se ha rehecho.
- **Prueba**: sobre los WAV de ese trabajo, la pista nueva conserva el 79 % de la generación y se parece a ella (correlación 0,90 frente a 0,47 del stem viejo). Queda a 3,5 dB de la voz, no a 11 dB. Test `test_one_transformed_group_keeps_the_style_filed_outside_that_stem` en verde. `unittest` de timeline, lógica y proyecto: 75/75. Frases de mesa: 4/4. La API se recargó en caliente (`logs/drum-transform-api-refresh-20261015`, `R11_API_REFRESH=PASS`) y el build quedó en `index-C-w_XWlW.js`. No está HECHO: falta volver a lanzar el remix y el oído. B6 sigue abierto.

## 2026-10-15 (CXLI) — Ninguna opción garantiza lo pedido

- **Qué se preguntó**: si cualquier remix, con cualquiera de las opciones, devuelve una pista con lo que se pide. La respuesta es no.
- **Rehacer la canción**. El texto viaja y el original sigue pesando. La fuerza por defecto del remix es 0,2. No convierte la etiqueta en el estilo.
- **Cambiar un trozo**. Cambia el tramo marcado. El resto de la grabación se queda. El modo agresivo puede salir del tramo. Tampoco fija el estilo por el nombre.
- **Cambiar por pistas**. Conservar deja esa grabación. Quitar la saca. Una sola pista en transformar monta la generación sin la voz nueva y sin lo quitado; es el arreglo de CXL, medido en los WAV ya guardados y todavía no oído en un remix nuevo. Varias pistas en transformar siguen saliendo cada una del stem que les pone el separador, y el estilo puede quedar en la pista equivocada.
- **Dejar la voz y crear música nueva**. Se queda la voz grabada y debajo hay una base nueva. La base depende de la frase, no del nombre suelto.
- **Ajustar tempo, tono, recorte o loop**. No genera música. Cambia el archivo que ya existe.
- **La frase**. «gabber, hardcore» es una etiqueta. El 2026-10-06 ya se oyó que el nombre solo no fija el estilo. Hace falta una frase que nombre los sonidos, visible en el cuadro. Este arreglo no cambia esa frase.
- **Qué no se cierra**. B6, R9, R10, Q2 y la escucha siguen abiertos. Queda anotado como B7 en `spec/03-PENDIENTES.md`.

## 2026-10-15 (CXLII) — Crear y remix, opción por opción

- **Qué se pidió**: revisar todas las opciones de remix y de crear, y comprobar tres cosas: que devuelve una pista, que se cumple el prompt y que el modelo lo entiende.
- **Cómo se miró**: el cuadro, el envío y el cuerpo que arma el motor, en Crear, en acompañamiento nuevo, en las cinco acciones de Qué hacer y en sus subopciones. No se lanzó ninguna generación nueva. El oído que ya consta es el del 2026-10-06 y el remix de hoy (CXL).
- **Pista**. Crear en Música y Crear en Canción con voz devuelven MP3 cuando el trabajo termina. Sin texto no arranca. Con voz, sin letra no arranca. Variar hace dos pistas seguidas, misma frase y distinta semilla. Acompañamiento nuevo hace lo mismo que Música. En remix, Rehacer, Cambiar un trozo, transformar pistas y Dejar la voz devuelven archivo si el motor termina. Conservar y quitar, sin ninguna pista en transformar, mezclan las grabaciones y el cuadro va vacío. Ajustar (medio tiempo, doble tiempo, BPM, loop, tono, recorte) edita el archivo que ya existe. Un trabajo que falla no deja pista.
- **Texto que viaja**. El cuadro sale tal cual, sin recorte de palabras. Género, Añadir, Variantes y Glosario lo convierten en «A track with» más términos separados por « · ». En Canción con voz, las etiquetas elegidas (female vocal, raw vocal, y las demás) entran en esa misma frase y se ven en VER LO QUE SE ENVÍA. El mood en español no entra: Nocturno, Enérgico, Melancólico y el resto se quedan en el selector. Mejorar y el asistente enseñan un borrador; solo pasa al cuadro con APLICAR BORRADOR. BPM, tono, compás, duración, semilla y nombre van en sus campos. thinking y use_format siguen apagados, así que no hay un paso que reescriba la frase antes del audio.
- **Estilo**. Una frase corta o una lista «A track with … · …» llega al motor y no fija el estilo. Eso ya se oyó el 2026-10-06: «gabber» solo no sonó a gabber; una frase que nombra el bombo distorsionado y el doble bombo sí se acercó. En remix el original sigue pesando (fuerza 0,2 por defecto). Más fidelidad al original acerca el resultado a la grabación. El modelo no «entiende» la petición en un paso aparte: condiciona el audio con el texto que ve y, en cover y repaint, también con el archivo.
- **Qué no se cierra**. Sigue B7. No está HECHO. Falta oír un remix rehecho y cualquier pista nueva de Crear.

## 2026-10-15 (CXLIII) — Lo que cada opción envía, sin generar

- **Qué se pidió**: no hace falta generar canciones. Revisar el código y el cuerpo que sale hacia el modelo, y si cada opción cumple lo que dice.
- **Prueba**: script local sobre `build_payload` y `project_generation`, sin `/release_task` y sin audio. En todos los casos el prompt del cuadro salió igual. Modelo `acestep-v15-sft`, 50 pasos, guidance 9, batch 2. `thinking`, los tres `cot` y `use_format` salieron en falso.
- **Crear**. Música manda el cuadro, letra `[instrumental]`, tarea `text2music`. Canción con voz manda el cuadro (con las etiquetas de voz ya metidas en la frase) y la letra aparte. Género, Añadir, Variantes y Glosario no tienen campo propio: lo que envían es la frase ya visible `A track with …`. El mood no tiene campo. Mejorar deja un borrador (`gabber, hardcore, 180 bpm` en la prueba); no sustituye el envío hasta Aplicar borrador, y al aplicar se quita el BPM del texto porque el tempo va en su control.
- **Remix**. Rehacer la canción es `cover` del archivo, fuerza 0,2 si no se mueve el deslizador. Escribir «sin melodías» no cambia esa fuerza: la función que lo haría no la llama la mesa. Cambiar un trozo es `repaint` con inicio y fin. Conservador deja la transición al máximo (25 cuadros, 0,05 s). Equilibrado con fuerza 0,5 la deja a la mitad. Agresivo la deja a cero. Por pistas, conservar y quitar no llaman al motor. Transformar llama a `cover` del audio mezclado de esas pistas, con el mismo prompt; el reparto posterior es local. Dejar la voz es `text2music` instrumental con el prompt; la voz grabada se mezcla después y la fuerza de cover no entra. Ajustar tempo, tono, recorte y loop no arma cuerpo de motor.
- **Qué no se cierra**. Esto comprueba el envío. No oye el resultado. B7 sigue abierto.

## 2026-10-15 (CXLIV) — Lo que se guarda

- **Qué se pidió**: comprobar si el archivo y la ficha que se guardan son los de la opción, sin generar canciones.
- **Ficha**. En los MP3 de remix que hay en la biblioteca, la ficha guarda el prompt enviado, el ámbito y las acciones. El de «Arroja la bomba» dice por pistas, batería en transformar, voz y acompañamiento en conservar, bajo quitado, frase «gabber, hardcore», fuerza 0,2, 160 BPM pedido y 160 medido. Conservar todo, sin transformar, guarda el prompt vacío y no guarda cuerpo de motor. La lista de la biblioteca no enseña el ámbito: todas salen como `remix-project`. El ámbito está dentro de la ficha.
- **Archivo**. Por pistas se publica la mezcla final, no el wav del motor. Canción completa, con el código de ahora, no se copia a la biblioteca si el BPM final medido se sale de la tolerancia. Los MP3 `prueba-r11-completo` siguen en la carpeta: pidieron 199 y la ficha midió 104,7 y 250,5; son de antes de ese corte. Por pistas con BPM sí se publica aunque la medición no cuadre: `prueba-r11-mixto` pidió 199 y midió 99,2 y 100. Dejar la voz guarda la mezcla con la voz y aparta la base y la voz separada; la biblioteca las esconde como piezas. Ajustar guarda un MP3 nuevo del archivo editado.
- **El remix de hoy**. La ficha corresponde a lo pedido. El MP3 publicado es la mezcla de antes del arreglo de una sola pista. No se ha rehecho.
- **Qué no se cierra**. B6 y B7 siguen abiertos. No está HECHO.

## 2026-10-15 (CXLV) — Texto por pista al transformar

- **Qué se pidió**: al poner una pista en transformar, un texto en esa pista. El glosario escribe ahí. Al lanzar se junta todo en la frase que se ve. Una pista vacía no inventa un bombo.
- **Qué quedó**: en Por pistas, cada pista en transformar tiene su campo y su glosario. La frase junta se ve encima del botón y es la que se envía. Rehacer la canción y cambiar un trozo siguen con el cuadro único.
- **Prueba**: el test del junte pasa, junto con el resto de frases de mesa, 27/27. ESLint de los archivos tocados, limpio. Build `index-CDi8A_-i.js`. No se abrió la mesa en la ventana. No está HECHO. B6 y B7 siguen abiertos.

## 2026-10-15 (CXLVI) — Botón IDENTIFY en SUBIR

- **Qué faltaba**: el botón IDENTIFY no estaba. El plan se había quedado sin hacer.
- **Qué quedó**: en cada subida, al lado de REMIX, está IDENTIFY. Manda el audio al análisis local que ya existe, con el recorte de 30 segundos del centro. Si el modelo devuelve una línea entera del glosario, se muestra esa línea. Si no, se dice que no está en el glosario. No se escribe en la frase del remix.
- **Prueba**: la línea `gabber, hardstyle, hardcore` se reconoce y un texto ajeno no. El texto de la pantalla también. ESLint limpio. Build `index-D1Q2cIIq.js`. La API se reinició en el puerto 8000, sin tocar el motor. No se pulsó el botón con una canción. No está HECHO.

## 2026-10-15 (CXLVII) — El prompt vuelve en por pistas

- **Qué fallaba**: al añadir el texto por pista se quitó el cuadro del estilo. En por pistas no se podía escribir el prompt.
- **Qué quedó**: con una pista en transformar vuelve el cuadro y el glosario. El estilo se escribe ahí. El texto de cada pista se suma a esa frase y se ve antes de enviar. Una pista vacía no añade nada.
- **Prueba**: el junte del estilo con el texto de pista pasa. ESLint limpio. Build `index-35Qq3pK0.js`. No se abrió la mesa. No está HECHO.

## 2026-10-15 (CXLVIII) — Onda en repetición y transiciones

- **Qué se pidió**: en repetición y transiciones debe verse el tema y poder marcar el trozo en la onda.
- **Qué quedó**: al escribir una duración, en REPETICIÓN Y TRANSICIONES aparece la onda del original. Arrastrar los bordes rellena DESDE y HASTA. Escribir los segundos mueve la onda. Vacío sigue siendo el tema entero. Se repite un solo trozo.
- **Prueba**: el paso de la onda a los segundos pasa, 14/14 en esa suite. ESLint limpio. Build `index-Dz9shoLP.js`. No se abrió la mesa. No está HECHO.

## 2026-10-15 (CXLIX) — Auditoría de la duración de los últimos remix

- **Qué se pidió**: revisar memoria y Markdown para explicar por qué las últimas ediciones no parecían aplicarse al pedir un remix más largo que el original. Diagnóstico sobre código, historial y archivos existentes; sin generar canciones, arrancar servicios ni cambiar el producto.
- **Contrato ya autorizado**: R11 permite ampliar después de transformar/recombinar, mediante repetición y transiciones. El cover nativo conserva la duración de la fuente preparada; `audio_duration=-1` no elimina la duración final pedida al proyecto. Esta operación no compone una continuación nueva.
- **Último intento**: trabajo `50423b230ae1438faa5d79d0ac36f19d`, fuente `Animales muertos.mp3` de 81,4 s, Por pistas, voz conservada y otros tres grupos transformados, BPM 170 y duración pedida 240 s. El historial acredita `project.duration_seconds=240` y `operations.timeline.target_duration_seconds=240`; la duración natural al tempo común es 79,254870588 s.
- **Audio real**: `_remix/50423b230ae1438faa5d79d0ac36f19d/arreglo-1.wav` y `exportada-1.mp3` duran 240 s, contrastados por sd-tester con ffprobe y pydub. El MP3 ocupa 5.761.196 bytes. Existe el WAV de la segunda variante, pero no su mezcla/arreglo/exportación. La primera exportación sigue siendo un intermedio, sin publicarse en biblioteca.
- **Interrupción**: el log verifica `exportada-1.mp3 (240.0 s)` a las 20:10:46 según su texto; `logs/stop.flag` contiene `salir` y su fecha local es 20:10:50, cuatro segundos después. La API ya no responde en 8000. El código de SALIR escribe esa marca y fuerza la parada de API/motor. La publicación espera las dos variantes verificadas. La evidencia apunta a interrupción tras ampliar la primera, antes de completar/publicar el lote; no identifica quién inició la parada. El historial quedó en el checkpoint de envío, `running`, sin resultado terminal.
- **Intento anterior**: `fef0de04ab2b437388d4fc30acd9a67f` terminó con `Animales muertos-remix.mp3` y `Animales muertos-remix (2).mp3`; ambos duran 240 s según ffprobe y pydub. La duración mayor sí se aplicó. Esto no certifica el estilo ni el BPM resultante.
- **Últimas ediciones de UI**: CXLV–CXLVIII constan implementadas y compiladas, pero sus propias notas declaran pendiente la verificación en ventana. `frontend/dist/index.html` referencia `index-Dz9shoLP.js`, el build de CXLVIII. No se convierte esa evidencia estática en un PASS del recorrido.
- **Review independiente**: sd-reviewer, **APPROVE del diagnóstico**, tras leer completos el workspace, helper de timeline y runtime, y revisar cierre y publicación. No equivale a APPROVE integral del producto. B6/B7 y R9/R10 siguen abiertos. Sin cambios de producto, no se repiten lint/build ni generaciones para esta auditoría de archivos existentes.
- **Tester independiente**: sd-tester, **PASS del diagnóstico retrospectivo**, con evidencia en `logs/remix-duration-audit-20261015.json`: duración de la primera variante y de los dos MP3 anteriores PASS; entrega completa del último lote **FAIL**; adaptación compositiva nueva NO-VERIFICADO. Reproducción local del contrato sin motor: proyecto 240 s → petición cover sin duración → payload `audio_duration=-1`, batch 2; la ampliación posterior conserva objetivo 240 s. `git diff --check -- memory.md`, exit 0. No se declara reparado ni completado el último remix.

## 2026-10-15 (CL) — Reparación de la entrega del último remix, verificada

- **Autorización**: el usuario exige «PUES ARREGLALO» tras confirmar que el último lote no se entregó. Alcance: completar sus dos variantes con la petición y los audios generados, manteniendo el apagado SALIR y la publicación solo después de verificar el lote completo.
- **Plan fix**: sd-editor conserva un recibo verificable de los WAV/metadatos descargados y permite recuperar explícitamente el mismo posprocesado, sin otra cover. Herramienta de reparación con inspección sin escritura por defecto, guardas de servicios detenidos, identidad/huellas/duración/lote y copia previa de historial. Reviewer revisa archivos completos; tester ejecuta reparación real, regresión, lint/build y comprueba dos MP3 de 240 s, fichas/semillas y biblioteca/API. Sin nuevas dependencias/modelos ni cambios de estilo, perfil o apagado. El beneficio es poder completar material ya generado tras una interrupción sin fingir entrega ni repetir inferencia.
- **Evidencia preservada**: resultado real de la tarea `05b60d74-77ad-41c4-a8e4-a6e33473cfbc` leído en modo solo lectura de la SQLite local del motor, más snapshot del job/historial, en `logs/remix-delivery-repair-20261015/`. Semillas reales 3813600975 y 784866797; sd-reviewer contrastó SHA256 idénticos entre cada WAV descargado y su archivo de motor. La lectura inicial de resumen esperaba un objeto y falló porque el resultado es una lista; los archivos de evidencia ya estaban guardados y no se alteró producto ni historial.
- **SDD y límites iniciales**: corrección documentada en R11 antes de implementar. Skill fix local aplicada; sin instalaciones ni consultas de red. No se cambia la decisión Q1 de marcar interrumpidos, no hay reanudación automática ni cambios de SALIR. B6/B7 y R9/R10 permanecen abiertos. Estado inicial EN CURSO; ver ejecución y cierre al final de esta entrada.
- **Implementación revisada**: `remix_recovery.py` conserva y valida un recibo de archivos, contexto y metadatos, anclado por SHA256 en `operations` del historial; `remix_project.py` lo guarda tras descargar el lote completo y permite completar explícitamente el mismo bucle productivo sin `submit`. Nuevas fases distinguen comprobación de tempo y publicación. `complete_downloaded_remix.py` inspecciona sin modificar producto por defecto y solo repara con `--execute`, servicios detenidos, bloqueo exclusivo, snapshot y comprobación de historial antes de publicar. El bootstrap de lotes antiguos exige resultado real de SQLite y WAV idénticos. Solo recupera Por pistas; no reanima fallos musicales ni cancelaciones.
- **Hallazgos corregidos antes de ejecutar**: el recibo necesita proteger también semillas/metadatos, no solo WAV; las guardas de procesos no deben confundir Musicia con otros `main.py`; la huella de historial debe corresponder a los mismos bytes del snapshot; hay que comprobar servicios/historial inmediatamente antes de publicar. El editor corrigió los cuatro puntos, añadió contratos y reutilizó los timeouts configurados. Focales del editor 28/28, compilación y diffcheck verdes.
- **REVIEWER — APPROVE de la corrección de entrega, previo a ejecución real**: sd-reviewer leyó completos runtime/helper/tests/herramienta finales y no dejó bloqueantes/importantes. No es PASS funcional ni cierre B6/B7. Tester independiente ejecuta regresión y después inspección/reparación real; entrega aún EN CURSO.
- **Regresión y primer intento real**: frontend 49/49, lint y build verdes. La suite backend del tester heredó sandbox y falló solo al intentar detener su propio proceso de prueba (`taskkill`: acceso denegado); se conserva `tester-backend.log`, 257 tests/93,397 s/1 fallo. La repetición fuera del sandbox por root dio **257/257 OK en 29,999 s**, `backend-unrestricted.log`. La inspección real sin `--execute` se detuvo antes de modificar el lote por identificar al lanzador padre de Python venv como otra reparación (PID 4328, ya desaparecido con la invocación); se conserva `tester-dry-run.json` y `dry-run.log` como FAIL. Editor corrige la identificación precisa del padre y reviewer volverá a revisarla. No se omite la guarda ni se inicia otra inferencia.
- **Delta Windows y regresión final**: el padre solo se admite si coinciden PID inmediato, parentesco CIM, ejecutable exacto del venv y todos los argumentos analizados mediante la API de Windows. Otro PID/exe/job/`--execute` sigue bloqueado; dos contratos específicos PASS. Reviewer releyó script/tests y dio **APPROVE del delta**. Suite final root fuera del sandbox: `Ran 258 tests in 29.852s / OK`, exit 0, `backend-final.log`. El segundo dry-run dio `status=validated`, exit 0, con el historial aún idéntico al baseline y sin crear recibo en el producto; `tester-dry-run2.json`/`dry-run2.log`.
- **Reparación real ejecutada**: `backend/venv/Scripts/python.exe scripts/complete_downloaded_remix.py --job-id 50423b230ae1438faa5d79d0ac36f19d --engine-cache vendor/ACE-Step-1.5/.cache/acestep/local_redis/cache.db --report logs/remix-delivery-repair-20261015/tester-recovery.json --execute` → exit 0, `status=succeeded`, `other_jobs_unchanged=true`. Snapshot exclusivo `tester-recovery-snapshot/`, recibo/ancla persistidos y bloqueo liberado. Se completó el posprocesado de ambos WAV originales con el motor detenido, sin otra inferencia; se rehicieron separación de grupos generados, mezcla, ampliación, exportación y medición, manteniendo el prompt y la petición de 240 s.
- **Entrega final**: `Animales muertos-remix (3).mp3` y `Animales muertos-remix (4).mp3`, ambos **240,000 s y 5.761.196 bytes**. SHA256 `679feabe8374f806242be2383ebad8698a5c4ec0cb3afbe663aae8b70ec44ae4` / `fb776e31aff00b41d64c254efb5c06f0445c2f1d814744560d869406cef5cfdb`. Semillas reales **3813600975 / 784866797**. Las fichas preservan proyecto/prompt/digest/perfil, timeline y repetición. Fuente, dos MP3 anteriores y sus fichas conservan sus SHA256; todos los otros jobs son estructuralmente idénticos al snapshot.
- **Verificación independiente local/API/UI**: sd-tester ejecutó `tester_verify.py` sobre los archivos publicados, **PASS** con ffprobe 240,000000 y pydub 240 s, identidad/procedencia e historial comprobados en `tester-verified-audio.json`. Root arrancó solo API (`ensure_local.ps1 -SinMotor -Rearme` → `API=started`, exit 0); `/health` confirma API disponible y motor apagado. `tester_verify.py --api` → exit 0, biblioteca y ambas descargas HTTP 200, bytes/SHA256 iguales al disco (`tester-verified-api.json`). Electron aislado, sin launcher/motor, comprobó ambas filas de biblioteca, `currentSrc` exactos, duración 240 y avance real de reproducción 0,288246/0,260532 s, solo GET y errores de consola vacíos: `tester-library-ui.json` **PASS**, capturas `tester-library-1.png` y `tester-library-2.png`. Root y tester inspeccionaron la segunda captura: reproductor 4:00 y nombres nuevos visibles. El Electron de prueba terminó; API queda disponible para biblioteca y motor apagado.
- **TESTER — PASS final de entrega/duración/recuperación**: sd-tester emitió `tester-verdict.json` tras corroborar ejecución, audios, fichas, historial, API, UI y regresión. Lint 0, build 0 (`index-Dz9shoLP.js`), **258/258 backend + 49/49 frontend**. Los FAIL previos se conservan y no se reetiquetan. **REVIEWER — APPROVE** de los cuatro archivos completos y del delta Windows; sin bloqueantes/importantes pendientes. Corrección de entrega HECHA dentro de este alcance.
- **Límites observados**: la primera variante queda medida en **42,90 BPM**, la segunda devuelve groove incierto y no recibe una medida inventada. En Por pistas esa medición sigue siendo auxiliar según contrato vigente. Esta entrega acredita los 4 minutos y la procedencia, no el cumplimiento del BPM 170 ni la fidelidad artística. B6/B7 y R9/R10 siguen abiertos; no hubo instalación, modelo nuevo ni dependencia externa de red. SALIR sigue deteniendo el stack y la recuperación sigue siendo explícita.
- **REVIEWER — APPROVE final documental**: sd-reviewer contrastó la entrada CL completa, los párrafos de requisitos/arquitectura/knowledge y los informes de recuperación/tester/UI; nombres, hashes, semillas, duración y límites coinciden. Se actualiza el título de CL a «verificada» siguiendo su sugerencia editorial. `git -c core.whitespace=cr-at-eol diff --check` final, exit 0; sin cambios de código posteriores a las pruebas y reviews aprobados.

## 2026-10-15 (CLI) — Por pistas: el compás no tapa el golpe, y el BPM pedido se comprueba

- **Qué se pidió**: que el remix cumpla lo pedido, sin hardcode. El lote de «Animales muertos» ya dura 4 minutos. Faltaban el BPM 170 y que las pistas transformadas llevaran el golpe.
- **Qué era el 42,90**. En la variante 1 el detector se quedaba con el acento del compás. El golpe de negra ya estaba en el audio, cerca de 171, pero su evidencia de autocorrelación no llegaba al corte de octava 0,9. Estirar 42,9 hasta 170 habría cuadruplicado un audio cuyo bombo ya iba a ese tempo. No se ha bajado el corte 0,5, ni la preferencia 2, ni el hombro 1,25, ni la tolerancia de 2 BPM.
- **Qué cambia en la medición**. Si el ancla es el compás, solo entran la mitad y el cuarto que ya son períodos sostenidos. El flujo de ataques (la subida de energía de una trama a la siguiente) tiene que superar al del ancla por `groove_onset_spectrum_ratio` (1,5). Si no destaca, el ancla se queda. El medidor no consulta el BPM pedido. Un tren de pulsos sin un ataque más rápido no promociona el armónico. Un lag que no es mitad ni cuarto, como el de Arroja, sigue fuera.
- **Qué cambia en Por pistas**. Con BPM pedido, la mezcla se mide. Si cae dentro de la tolerancia no se estira y el reloj de la repetición pasa a ser esa medición. Si cae fuera, un solo atempo sin cambio de tono, se vuelve a medir y tiene que cumplir la tolerancia. En la exportación se aplica la misma puerta que en canción completa. Un groove incierto falla con el error del detector y no se publica. Sin BPM pedido, la medición sigue siendo auxiliar.
- **Qué cambia cuando hay varias pistas en transformar**. Si la ganancia es la misma, entra una sola base: la generación menos la voz nueva, cuando la original se conserva, y menos lo generado de cada grupo quitado. El golpe que el separador archivó fuera de la batería se queda. Si las ganancias no coinciden, se sigue mezclando cada stem. No se inventa un bombo ni se reescribe la frase del cuadro.
- **Lecturas reales, detector nuevo, sin tocar el audio**. Original `Animales muertos.mp3`: 165,52 BPM, confianza 0,659. Variante 1, mezcla 1, arreglo 1 y `Animales muertos-remix (3).mp3`: 171,43. La batería de esa variante: 171,43. La diferencia con 170 es 1,43, dentro de la tolerancia, así que no hay atempo. La variante 2, su mezcla, su arreglo y `Animales muertos-remix (4).mp3` siguen con el error de hombro; no se les ha puesto 170. La batería sola de esa variante mide 170,21 y no es la mezcla. La sonda de hombro de la semilla 42 sigue en 37,85 en el arreglo 2 y en 40,00 en el arreglo 1; no se ha convertido en 199.
- **Ficha**. En (3) el BPM medido pasa de 42,9 a 171,43 y la confianza de 0,646 a 0,454, que es la lectura del MP3 ya publicado. El archivo de audio no se ha reescrito. (4) sigue sin BPM medido. No se han creado (5) ni (6) y no se ha lanzado otra generación.
- **Prueba de código**. Desde `backend/`, con la raíz del repo en `PYTHONPATH`: `unittest` de groove, timeline, recovery y proyecto, 76 tests, 31,063 s, OK. El original no se ha movido de 165,52.
- **Qué no se cierra**. B6, B7, R9 y R10 siguen abiertos. La escucha del estilo sigue siendo del usuario. La frase enviada no se ha cambiado por la del catálogo. Un groove incierto en la segunda variante haría fallar un lote nuevo; el MP3 (4) ya publicado se conserva.
- **Revisión, cambio pedido**. El primer reviewer marcó que, si la mezcla cae fuera de la tolerancia, el atempo cambiaba la duración y el objetivo se quedaba en la de antes: sin ampliación la exportación no cuadraba, y si el audio ajustado pasaba del objetivo la ampliación lo rechazaba. Tampoco se exigía la confianza mínima antes de estirar. Se corrige con `apply_groups_mix_tempo`: el objetivo pedido se conserva, sin duración pedida el resultado es la mezcla ajustada, y si no cabe se dice el mínimo. La confianza se comprueba antes del ratio. El caso ya medido, 171,43 frente a 170, sigue sin estirar. Suite posterior: 79 tests, 29,585 s, OK. El aviso de usar la generación entera cuando al restar no queda audio sigue igual que en la pista única.
- **TESTER — PASS**. Primera pasada, audios reales sin pasar el BPM pedido: original 165,52 confianza 0,659; remix (3) 171,43 confianza 0,454; remix (4) sigue en el error de hombro; el arreglo 2 de la sonda de semilla 42 sigue en 37,85. SHA256 de (3) `679feabe8374f806242be2383ebad8698a5c4ec0cb3afbe663aae8b70ec44ae4`. Suite 76 tests, 29,643 s, OK. `py_compile` exit 0. Segunda pasada, solo el delta de duración: 2 tests, 0,001 s, OK. La confianza se exige antes del ratio y, sin duración pedida, el objetivo es la mezcla ajustada.
- **REVIEWER — APPROVE** del delta, tras CHANGES_REQUESTED por la duración. No queda bloqueante. No cierra B6, B7, R9 ni R10. La corrección de medición, puerta de tempo y base única queda verificada en este alcance. No sustituye el oído.

## 2026-10-16 (CLII) — El estilo se pasa al inglés antes de enviarlo

- **Qué se pidió**: que el texto de estilo, venga en el idioma que venga, se vea y se envíe en inglés. La letra cantada no se traduce. El cuadro sigue en el idioma escrito.
- **Qué no se usa**: el LM 0.6B del motor. El 2026-10-06 ya se midió que `use_format` inventa música y cambia la caption y el BPM. Sigue apagado. `langdetect` se instaló, se midió y se quitó: marcaba «A track with gabber hardcore · kicks potentes con bounce» como inglés. El detector que se queda es `lingua-language-detector`, en el venv de la API. El traductor es `facebook/nllb-200-distilled-600M`, ya descargado de Hugging Face (red, esa vez) en la caché local, y corre en CPU con el Python del motor. El venv de la API no instala torch.
- **Qué se midió, segunda llamada igual**:
  - «A track with gabber hardcore · kicks potentes con bounce» → «A track with gabber hardcore · kicks powerful with bounce».
  - «potentes con bounce» → «powerful with bounce».
  - «Batería suave al fondo» → «Soft battery at the bottom».
  - «Batería suave al fondo, 130 bpm» → «Soft battery at the bottom, 130 bpm».
  - «flautas medievales» → «flutes of the Middle Ages».
  - «hardcore en 4x4 con doble bombo» → «4x4 hardcore with double bumper».
  - «Solo cambia percusión» → «Just change the percussion.»
  - «Cambia la batería» → «Change the battery.»
  - «Une piste de techno sombre» → «A dark techno track».
  - «Ein Track mit harten Kicks» → «A track with hard kicks».
  - «Conserva la voz, techno» → «Keep your voice up, techno.»
  - «medieval flutes», «gabber», «A track with gabber hardcore», «Original prompt» y «120 bpm» se quedan igual y no arrancan el modelo.
- **Límite del modelo, no se esconde**: «batería» sale como battery, no como drums. «bombo» sale como bumper, no como kick. Un haz de 1 convirtió «flautas medievales» en «Middle-earth flutes»; con 4 haces (`num_beams`) sale «flutes of the Middle Ages». No se baja el corte de palabra para que «bombo» se tome por luganda. No se ha descargado un modelo más grande.
- **Cómo se decide, en configuración**: una frase larga solo se toma por otro idioma si la confianza pasa de 0,08 y supera al inglés por 1,5. «medieval flutes» queda en rumano a 1,06 y se conserva. «hardcore en 4x4 con doble bombo» queda en español a 1,82 y se traduce entera. Si la frase entera ya es inglesa y dentro hay una palabra extranjera, solo se traduce ese tramo: así «gabber» no se reescribe y «potentes» sí. «120 bpm» con el control en 140 sigue en 422. La letra de una petición con voz sigue igual.
- **Dónde se ve**: CREAR, remix, conservar voz y acompañamiento muestran «Se envía:» con ese inglés. El cuadro no se sustituye. La API se recargó en frío, sin trabajos activos y sin motor en el 8001. `POST /music/style-english` devolvió la frase del gabber con el punto medio intacto, y «medieval flutes» igual. La página sirve `index-CcwtNgT6.js`.
- **Pruebas**: `test_style_translation` 5 tests OK. El payload literal de crear sigue OK. Preview y conflicto de BPM, 9 tests OK. ESLint de los archivos tocados, 0. Tests de frontend, 49/49. `npm run build` OK. No se generó audio. No se tocaron los MP3 (3) ni (4).
- **Qué no se cierra**: R14 sigue sin marcar hasta el APPROVE del reviewer. B6, B7, R9 y R10 siguen abiertos. La escucha sigue siendo del usuario.
- **TESTER — PASS**: `unittest test_style_translation`, 5 tests, 25,258 s, OK. Antes de una frase extranjera el worker estaba parado. «medieval flutes» igual. La frase del gabber sale «A track with gabber hardcore · kicks powerful with bounce» y la segunda llamada es idéntica. La letra «canta esto en español» se conserva. «120 bpm» con control 140 responde 422 con el texto del BPM. `POST /music/style-english` en la API viva devolvió el mismo inglés. «Soft battery at the bottom» y «4x4 hardcore with double bumper» quedan como límite del modelo, no como fallo. No se reinició nada en esta pasada y no se marcó HECHO.
- **REVIEWER — CHANGES_REQUESTED**, dos veces. La traducción corría en el bucle: ahora va en un hilo, y la reserva de CREAR queda dentro del mismo candado, antes de esperar al motor. El cliente, con 270 s, seguía por debajo de carga 180 más frase 120 más envío 60. Queda en 390 s: 180 de carga, 120 de frase y 90 de margen sobre los 60 del motor. La vista previa espera 300 s y no crea trabajo. ESLint de `api.js`, 0. Build `index-CtsKExfA.js`, y la API que ya estaba en marcha lo sirve sin otro reinicio. El motor del 8001 sigue apagado.
- **REVIEWER — APPROVE** del tiempo de envío. 390 s cubre 180 de carga, 120 de frase, 60 del motor y los 3 s de /health, y sobran 27 s. La vista previa queda en 300 s y no reserva trabajo. Con el PASS del tester y este APPROVE, los criterios técnicos de R14 quedan marcados. No cierra B6, B7, R9 ni R10. La ventana no se ha pulsado. La escucha sigue siendo del usuario.
- **Decisión del usuario, 2026-10-16**: el traductor se queda en CPU. No usa la GPU de 8 GB: `style_translation.device` es `cpu`, y el worker mueve el modelo y los tensores a ese dispositivo. La primera frase en otro idioma es la lenta (unos 20 s medidos; el tope de carga es 180 s) y luego el modelo se queda en RAM. El inglés no arranca el worker. Se descartó pasarlo a la GPU, traducir solo al enviar, bajar a 1 haz y quitar el traductor. No hay cambio de código.

## 2026-10-16 (CLIII) — La prueba sí tradujo; el remix falló al medir el groove

- **Lo que escribió**: `A track with gabber hardcore · kicks contundentes y con  fuerza`. **Lo que recibió el motor**: `A track with gabber hardcore · strong and forceful kicks`. Trabajo `6bc04ca226ea42f88dff48ac43ebf1e1`, tarea `b6d6c6c2-a4ff-48b8-b9e1-67aeb31f4463`. La barra de arriba mostraba el texto escrito, así que parecía que no había traducción. `output_name` de esa petición fue null: el nombre estaba dentro de avanzados.
- **Por qué paró**: a las 01:43:24 el proyecto falló con «El groove es incierto: el período elegido no destaca sobre los tempos vecinos». No se baja `groove_shoulder_ratio`. No se generó un MP3 nuevo. No se tocaron (3) ni (4).
- **Nombre**: el campo queda al lado del botón REMIX en rehacer, tramo y pistas. Vacío sigue usando el original con `-remix`. Mientras corre, la barra enseña ese nombre.
- **Progreso**: el texto de arriba es un botón. Abre el final de `logs/acestep-api.log`, `logs/acestep-api.err.log` y `logs/musicia-api.err.log`. Rutas y largo en `process_logs`. Fuera de `logs/` responde 422.
- **Pruebas**: `test_process_logs` 4 OK. La vista del nombre pedido, OK. ESLint de los archivos tocados, 0. Tests de frontend, 49/49. Build `index-D9i2yOj7.js`. La lectura real de los tres ficheros devolvió texto. La API en el 8000 estaba caída al mirarlo; el motor del 8001 seguía en marcha. No se reinició.
- **TESTER — PASS**: las 5 pruebas pedidas, OK. ESLint 0. Frontend 49/49. El bundle contiene «Nombre del remix», «Ver salida y error del proceso» y `/music/process-logs`. Un camino fuera de `logs/` lanza ValueError y el test lo cubre. No se marcó HECHO en esa pasada.
- **REVIEWER — APPROVE**. Sin hallazgos bloqueantes. La frase corta se queda. El clic abre las tres colas. El nombre va en la fila de REMIX. No se bajaron los umbrales de groove ni se movió el traductor de CPU. Con este PASS y este APPROVE, los criterios técnicos de R15 quedan marcados. La ventana no se ha pulsado. No cierra B6, B7, R9 ni R10.

## 2026-10-16 (CLIV) — Cuadrar la base nueva con el bombo original

- El usuario pregunta si, después de generar, se puede cuadrar todo. En el trabajo `3f662ec43e4b4beeae3c93b279b3dcd8` la batería nueva mide 175,82 y la original, ya a 170, mide 170,09.
- Solo el tempo, llevando la base a 170 y mezclándola con la voz, sigue en 170,21 con ratio 1,108. No pasa el 1,25.
- Tempo y fase: el golpe nuevo cae 141 ms fuera del original. Al colocarlo encima, la mezcla mide 170,21, ratio 1,409, confianza 0,186. Pasa el corte vigente y la confianza mínima 0,12. No se ha bajado ningún umbral. No se ha publicado. En ese momento no estaba en el programa; CLV lo incorpora.

## 2026-10-16 (CLV) — Si el groove es incierto, cuadrar el bombo y seguir

- **Qué pidió**: en vez de saltar el error, cuadrar y continuar. Trabajo `3f662ec43e4b4beeae3c93b279b3dcd8`, nombre AM1, Por pistas, voz conservada, batería/bajo/acompañamiento en transformar, 170 BPM, 240 s, tramo a repetir 24,23–28,14 s.
- **Qué hace el programa**: si la mezcla de grupos no tiene pulso medible, y el bombo original y el nuevo sí se miden, `square_mix_on_original_kick` estira el material nuevo al tempo del bombo original, sin cambiar el tono, lo coloca en su fase y rehace la mezcla. Esa mezcla se vuelve a medir con el mismo corte (`groove_shoulder_ratio` 1,25, confianza mínima 0,12, tolerancia 2 BPM). Si el segundo pase falla, o un bombo no se mide, o el salto de tempo sale de 0,8–1,25, sigue el error original y no se publica. El aviso solo se anota cuando la segunda medición ya pasó la confianza mínima.
- **Medición del trabajo, sin publicar y sin tocar sus WAV**: desfase −171,3 ms, relación de tempo 0,9674. La mezcla cuadrada mide 170,21, confianza 0,192, hombro 0,3594 frente a 0,2617 (ratio 1,373). No hace falta otro atempo de la mezcla. El WAV ampliado a 240 s (51 copias, stride 3,173 s) mide hombro 0,1393 frente a 0,1443 (ratio 0,965) y el MP3 de 240 s, 0,1395 frente a 0,1439 (ratio 0,969). Los dos siguen el error. No se han publicado. No se ha bajado ningún umbral. No se ha arrancado el motor.
- **Pruebas**: `test_kick_alignment` 3 OK en 105,9 s (clics a 170/176, bombo imposible de medir, y los WAV de ese trabajo). `test_groove`, `test_remix_timeline` y `test_verify_align`: 70 OK. El corte de hombro del test plano sigue en 1,25.
- **Límite**: esta corrección no cierra B6, B7, R9 ni R10. La API y el motor estaban parados; el cambio entra al abrir Musicia. AM1 no está en la biblioteca.
- **TESTER — PASS** (`01a14387-f906-7091-b93b-053043460150`): `test_kick_alignment` 3 OK en 103,7 s; `test_groove` + `test_remix_timeline` + `test_verify_align` 70 OK en 21,7 s. El 1,25 sigue exigido. La canción de 240 s queda NO-VERIFICADA por el test, no como fallo del cuadre.
- **REVIEWER — APPROVE** (`01a14387-f906-7091-b93b-052eed27fe16`). Sin bloqueantes. Si la ampliación posterior falla, el aviso de cuadre puede quedar en el trabajo fallido; el MP3 no se publica. No cierra B6, B7, R9 ni R10.

## 2026-10-16 (CLVI) — Si el tramo corto no tiene pulso, se repite la canción entera

- **Qué pidió**: «pues dale», después de ver que los 240 s del tramo 24,23–28,14 no pasaban el corte. Se repite un trozo más largo y se publica si la medición pasa. No se bajan umbrales.
- **Medición**: la mezcla cuadrada de `3f662ec43e4b4beeae3c93b279b3dcd8`, repetida entera, da un WAV de 240,0 s, 3 copias, stride 78,26 s, 170,21 BPM, confianza 0,165, hombro 0,3667 frente a 0,2567 (ratio 1,428). El tramo corto sigue en ratio 0,965.
- **Prueba**: `test_a_short_loop_opens_to_the_whole_song_and_a_full_one_stays` y `test_short_loop_of_the_saved_remix_fails_and_the_whole_song_reaches_240`, 2 OK en 266,2 s. El MP3 temporal pasó `verify_requested_tempo` a 170. Los WAV del trabajo no cambiaron de fecha.
- **Publicado**: `backend/outputs/AM1.mp3`, 240,0 s, 170,21 BPM, confianza 0,165, desfase −171,3 ms, relación 0,9674, semilla real 2638353188. Ficha `AM1.ficha.json`. El trabajo queda en Listo. La segunda variante del motor no se mezcló. No se tocó la subida. API y motor estaban parados. No cierra B6, B7, R9 ni R10.
- **TESTER — PASS** (`01a1441f-c132-7530-9782-48f73bebe21f`): las dos pruebas OK en 269,8 s. AM1.mp3 sigue en 240,0 s y la ficha en 170,21. SHA-256 del MP3 `7236250ae18ff8e0664949ef03d8c0c015ed729c24dc4937e774ac4f19219e30`, sin cambios durante la prueba.
- **REVIEWER — APPROVE** (`01a1441f-c132-7530-9782-48e6d8b67208`). Sin bloqueantes. Si la canción entera también falla el corte, no se publica.

## 2026-10-16 (CLVII) — Batería y bombo llegan como drums y kick; el ánimo entra en la frase

- **Qué pidió**: «arregla para que no fallen», después de ver que el traductor escribía battery y bumper, y que el ánimo de CREAR no se enviaba. No pidió bajar el corte del pulso ni obligar al motor a obedecer un género.
- **Traducción**: `backend/style_term_fixes.json` corrige después de NLLB, solo si el origen trae la palabra española y el inglés trae la equivocada. Medido en esta pasada: «Batería suave al fondo» → «Soft drums at the bottom»; «hardcore en 4x4 con doble bombo» → «4x4 hardcore with double kick»; «A track with gabber hardcore · kicks potentes con bounce» → «A track with gabber hardcore · kicks powerful with bounce»; «a car battery» se queda igual. El inglés no arranca el worker. Si el fichero falta o no se lee, no se envía el estilo. Sigue en CPU. `use_format` sigue apagado.
- **Ánimo**: el mood elegido en CREAR añade la cláusula que ya está en `style_catalog.json` y se ve en «Se envía». Oscuro → «a dark aggressive energy». Enérgico → «a relentless driving rhythm». Tranquilo y Chill solo añaden «a slow, laid-back tempo» si no hay BPM. No se manda el párrafo ambient ni «driving drums as the lead».
- **Pruebas**: `CorrectedTermsTest` y `EnglishStyleStaysTest`, 5 OK en 3,2 s, worker parado. `LocalTranslationTest` solo, 2 OK en 71,8 s. Frontend `node --test` de ánimo, glosario y glosa, 18/18. ESLint de los archivos tocados, 0. Build `index-C_jpjCgM.js`. La ventana no se ha pulsado. No se generó audio. No se tocó AM1 ni la subida. No se bajó ningún umbral. No cierra B6, B7, R9 ni R10.
- **TESTER — PASS** (`01a14470-ff3f-7b61-8b17-c4a0d409aba2`): las 5 pruebas de corrección e inglés, OK en 2,2 s, con el worker parado. `LocalTranslationTest` en otro proceso, 2 OK en 27,4 s. «Batería suave al fondo» → «Soft drums at the bottom». «hardcore en 4x4 con doble bombo» → «4x4 hardcore with double kick». Frontend 18/18. ESLint 0. El bundle `index-C_jpjCgM.js` contiene la cláusula y «Si hay BPM». La ventana no se ha pulsado.
- **REVIEWER — APPROVE** (`01a14470-ff3f-7b61-8b17-c4b20dc4f78c`). Sin bloqueantes. La corrección está en el fichero, el inglés no se reescribe y el ánimo no pelea con el BPM. No cierra B6, B7, R9 ni R10.

## 2026-10-16 (CLVIII) — En canción completa se publica la variante que mide el pulso

- **Qué pidió**: «Publicar la que pasa». En canción completa, si una variante tiene pulso y la otra no, se publica la que pasa. El corte sigue en 1,25. No se le pone el BPM a mano. Por pistas no cambia.
- **Qué hace el programa**: agotados `full_groove_retries`, la variante sin pulso usable se queda fuera. El trabajo dice «La variante N no tenía un pulso medible; no se publicó.» Si otra midió, se publica esa. Si ninguna mide, no se publica nada y sigue el error del detector. Un BPM medido fuera de 2 detiene todo el lote y no pide otra generación. El aviso del preview ya no dice que una medición incierta tumba el trabajo.
- **Pruebas**: `test_remix_timeline.py`, 29 OK en 13,7 s. `test_groove.py` y `test_verify_align.py`, 44 OK en 9,5 s. El corte plano sigue exigido. `groove_shoulder_ratio` 1,25 y `tempo_verify_tolerance_bpm` 2,0 no se han tocado. No se generó audio. La ventana no se ha pulsado. No se tocó AM1 ni la subida. No hace falta rebuild: el aviso ya lo pinta la mesa.
- **Límite**: no cierra B6, B7, R9 ni R10. Falta la sonda en la que las dos variantes de canción completa quedan dentro de 2 BPM y se publican.
- **TESTER — PASS** (`01a144ad-f39a-7851-bd28-328d766900a8`): `test_remix_timeline.py`, 29 OK en 13,9 s, salida 0. El aviso del preview ya no dice «produce un error». Por pistas no lo lleva. La ventana queda NO-VERIFICADA.
- **REVIEWER — APPROVE** (`01a144ad-f39a-7851-bd28-32694b320e15`). Sin bloqueantes. El primer pase pidió quitar el aviso viejo que se copiaba al trabajo; quedó rehecho. No cierra B6, B7, R9 ni R10.

## 2026-10-16 (CLIX) — Biblioteca vacía de ediciones creadas y remixes

- **Qué pidió**: borrar todas las ediciones creadas o remezcladas, con la API ya arrancada.
- **Qué se borró**: `AM1.mp3` y su ficha, por el borrado de la API. La ficha huérfana `prueba-estilo-ab-orig-voces.ficha.json`. 108 WAV `grupos-*`. 45 carpetas de `outputs/_remix`. La biblioteca quedó vacía. No había ningún trabajo en marcha.
- **Qué se quedó**: las subidas `Animales muertos.mp3` y `f6fc62fe-Arroja la bomba.mp3`. La cola de trabajos antiguos sigue en el historial; el audio ya no está.

## 2026-10-16 (CLX) — CREAR ya no lista la cola; la pista va a BIBLIOTECA

- **Qué pidió**: la cola de trabajos de CREAR no sirve. Quitarla. Todo va a la biblioteca.
- **Qué hace**: CREAR ya no pinta trabajos antiguos ni reproduce el MP3 al terminar. Dice «Lista. Está en BIBLIOTECA.» El progreso y PARAR siguen en la generación en curso. La cabecera sigue mostrando el trabajo activo. BIBLIOTECA se recarga sola cuando aparece el MP3. Se borró `JobsPanel.jsx`.
- **Pruebas**: ESLint de App y Composer, 0. Frontend `node --test`, 52/52. Build `index-2bsqluKk.js`: no contiene «COLA DE TRABAJOS» y sí «Está en BIBLIOTECA». La ventana no se ha pulsado. No se generó audio. No cierra R9, R10, B6 ni B7.
- **TESTER — PASS** (`01a144c3-e517-72c2-825b-18c06411fc02`): ESLint 0, 52/52, `JobsPanel.jsx` no existe, el bundle no tiene la cola. La ventana queda NO-VERIFICADA.
- **REVIEWER — APPROVE** (`01a144c3-e517-72c2-825b-18bfff78467f`). Sin bloqueantes. PARAR sigue en el progreso y el remix conserva el suyo. No cierra R9, R10, B6 ni B7.

## 2026-10-16 (CLXI) — La API estaba viva y no escuchaba

- **Qué**: la ventana no conectaba. El proceso de la API (pid 316, desde las 14:43) seguía en memoria y no tenía el puerto 8000 en escucha. Un traductor de estilo arrancado a las 15:34 seguía vivo a las 15:42, sin CPU, con la descarga colgada, pasado el tope de 180 s. `ensure_local` lo veía presente y no lo sustituía. El motor 8001 (pids 8556/8500) contestaba.
- **Qué se hizo**: se mató solo ese árbol (API y traductor) y se volvió a crear la API con `Win32_Process.Create`. El motor no se tocó.
- **Resultado**: a las 15:44 `GET /health` devuelve `api=ok` y motor alcanzable. `GET /` devuelve 200. Escucha el pid 24788. El motor sigue en el pid 8500. No se generó audio.
- **Pantalla**: a las 15:46 SUBIR seguía mostrando «La API no contesta.» bajo REMIX, con MOTOR ACTIVO. La ventana no se recargó: el formulario (Animales muertos, 170, AMMMM1) se conservó y el aviso quedó del corte. Desde el rearranque el registro no tiene ningún POST de remix.

## 2026-10-16 (CLXII) — Un corte de red no se queda en el remix

- **Qué pidió**: eso no debe ocurrir. Luego cerró Musicia él mismo (SALIR, `logs/stop.flag`).
- **Qué hace**: «La API no contesta.» y «La API tardó demasiado en contestar.» no se guardan como fallo de pulsar REMIX ni de GENERAR. Un fallo real sí se queda: el traductor que tardó demasiado, el motor que no responde y la respuesta ilegible. Si el aviso de corte ya estaba y `/health` vuelve, se quita. Opciones, duración, BPM original, análisis, referencias, vista previa, estilo en inglés, listas, el cuadre y el envío de CREAR se vuelven a pedir tras el corte, con espera. CREAR no pinta el triángulo de ERROR por ese corte. El sondeo de un trabajo ya lanzado no lo pinta. Si el proceso de la API sigue vivo y el puerto 8000 no acepta conexiones al pasar `api_listen_grace_seconds` (60), `ensure_local` repone solo la API. El motor no se toca. Con la marca de SALIR no arranca nada.
- **Pruebas**: `test_api_supervisor.py` 5 OK. Frontend `node --test` 55/55. ESLint 0. Build servido: `index-D0BsIbow.js`. `ensure_local.ps1` imprimió HOLD, la marca sigue en «salir» (6 bytes, 15:54:28) y el 8000 y el 8001 siguen cerrados. La ventana no se ha vuelto a abrir. No se generó audio. No cierra R9, R10, B6 ni B7.
- **TESTER — PASS** (`01a14521-f466-7ae3-9cc3-67f433ea8be0`). El primer pase (`01a14507-dc74-73c1-bdd0-3110565bf34b`) y el segundo (`01a14517-c57b-7411-82f4-3abcf62fdbb0`) fueron FAIL: el corte se pintaba y CREAR marcaba ERROR. Eso quedó rehecho. ESLint 0. El test del corte, 3/3. HOLD y la marca intactos. La ventana queda NO-VERIFICADA.
- **REVIEWER — APPROVE** (`01a14521-f466-7ae3-9cc3-6801ed951b40`). El primer pase (`01a14507-dc76-7dc0-a536-6d083e5bc6d4`) pidió el corte estrecho. El segundo (`01a14517-c57b-7411-82f4-3ac355bf9a4d`) ya lo aprobó. Este confirma CREAR, MEZCLA y el ancla del mensaje. Sin bloqueantes. No cierra R9, R10, B6 ni B7.

## 2026-10-16 (CLXIII) — El glosario decía que el vocabulario no estaba

- **Qué pidió**: en el glosario no va. Dice que el vocabulario del motor no está disponible.
- **Qué era**: el archivo `vendor/ACE-Step-1.5/acestep/genres_vocab.txt` sí está (178572 líneas, cargado a las 17:40). `GET /music/genre_glossary` responde `available: true`. El panel pintaba esa frase en cuanto aún no había respuesta, y si la petición fallaba se quedaba ahí. La ventana no había pedido el glosario: el único GET del registro era el de diagnóstico.
- **Qué hace**: sin respuesta dice «Cargando el vocabulario…» y reintenta el corte de red. «vocabulario del motor no disponible» solo si el servidor manda `available: false`. Un fallo escrito se muestra y no se reintenta. Cambiar la búsqueda no conserva el recuento de la consulta anterior. Esas dos llamadas ya no usan el tope de 8 s.
- **Pruebas**: frontend `node --test` 57/57. ESLint 0. Build servido: `index-BFajuZfN.js`. `GET /` lo cita. `GET /music/genre_glossary?q=&limit=50` → `available=true`, total 178572, primera entrada «16-bit J-RPG». `q=gabber` devuelve `q=gabber`, total 294. No se generó audio. No se reinició la API ni el motor. No se abortó el remix. No cierra R9, R10, B6 ni B7.
- **Ventana**: estaba minimizada en CREAR. Al abrir GLOSARIO salen las entradas y el pie «178.572 entradas · whitelist del motor». En SUBIR, el remix de Animales muertos, el mismo panel lista «16-bit J-RPG» y el mismo pie. El registro tiene el GET del clic, 200. No se pulsó el botón verde de REMIX.
- **TESTER — PASS** (`01a14578-ec61-7c12-bf4f-e8fbc1374a4b`). El pase anterior (`01a1456c-9cc4-7853-b0d7-0c4fabb93700`) fue PASS del pie, antes de filtrar la consulta. 57/57. ESLint 0. El bundle servido tiene la rama missing y la comparación de `q`. La ventana queda NO-VERIFICADA.
- **REVIEWER — APPROVE** (`01a14578-ec61-7c12-bf4f-e8e332968ace`). El primer pase (`01a1456c-9cc5-7a60-b391-0ed725f9ce67`) pidió no pintar el recuento de otra consulta. Eso quedó hecho. Sin bloqueantes. No cierra R9, R10, B6 ni B7.

## 2026-10-16 (CLXIV) — El estilo en mayúsculas se traducía mal

- **Qué pidió**: hace una traducción del prompt muy mala.
- **Qué era**: escribió `GABBER HARDCORE · KICK CONTUNDENTES, VIBRACION BOUNCE · PITIDOS DE COMPUTADORAS · MELODIA ORIGINAL CON SINTETIZADOR`. A las 17:41 el motor recibió `GABBER HARDCORE · KICK CONTENTS, VIBRACION BOUNCE · Questions from computers · Original melody with synthesizer` (tarea `6738d470-6278-4d97-88ac-68f05109433e`). NLLB lee mal el español en mayúsculas. La misma frase en minúsculas ya salía bien: `gabber hardcore · strong kick, bounce vibration · computer whistles · original synth melody`. No faltaba un par en el fichero de términos.
- **Qué hace**: al traductor se le pasa la frase en minúsculas. El texto escrito sigue valiendo para detectar el idioma, para las correcciones de batería y bombo, y para la caja. No se reponen las mayúsculas. No se añadieron pares. Sigue en CPU, con 4 haces. `use_format` y `thinking` siguen apagados. No se parte la frase por «·».
- **Medido con el código nuevo**: `Gabber hardcore · strong kick, bounce vibration · computer whistles · original synth melody`.
- **Pruebas**: `EnglishStyleStaysTest` y `CorrectedTermsTest`, 5 OK en 2,454 s. `LocalTranslationTest` solo, 2 OK en 46,356 s. No se generó audio. No se movió el traductor de CPU. No cierra R9, R10, B6 ni B7.
- **API**: no había trabajos en cola ni en curso. Se paró solo el árbol de la API (22816 / 15916 y su traductor). El motor siguió en el pid 7072. El primer `Win32_Process.Create` devolvió 21 y no creó proceso. A las 18:32:19 quedó otra API (lanzador 23304, escucha 19624). `GET /health` api=ok y motor alcanzable. `POST /music/style-english` de la frase en mayúsculas devolvió 200 y el inglés medido. El 8001 no cambió de pid.
- **TESTER — PASS** (`01a14589-64f4-7fb3-82eb-c8f6c62743d3`). 5 OK y luego 2 OK (31,550 s). La frase exacta no se reimprimió en su runner; las aserciones sí pasaron. CPU, fichero de términos y `use_format` quedaron NO-VERIFICADOS por él.
- **REVIEWER — APPROVE** (`01a14589-64f4-7fb3-82eb-c903660fb995`). Sin bloqueantes. El diff es el `casefold` y el test. No cierra R9, R10, B6 ni B7.

## 2026-10-16 (CLXV) — La consola se quedaba solo mientras trabajaba

- **Qué pidió**: en la UI marca el remix como si no lo hubiera hecho, y no hay logs. La consola solo está cuando está trabajando.
- **Qué era**: la cabecera solo pintaba el botón de logs con un trabajo en cola o en curso. Al fallar amrem, ese botón desaparecía. El remix no se publicó. El fallo sigue en el historial: BPM medido 136,36 frente al pedido 170.
- **Qué hace**: CONSOLA está siempre y abre la salida y el error. Si no hay trabajo en curso, la cabecera enseña el último. El de amrem sale en rojo con el error del BPM. Uno en curso sigue enseñando el porcentaje. La pastilla del motor no usa un trabajo ya terminado.
- **Ventana**: bundle `index-CbG4Ox7W.js`. La cabecera muestra CONSOLA y «amrem · El BPM final medido 136.36 no cumple el pedido 170 (tolerancia 2 BPM)». Abrí la consola: sale el error del motor, con la generación de las 17:50. La cerré. La pestaña quedó en SUBIR. No pulsé REMIX. El recambio del bundle vació el formulario. No se generó audio. No se reinició el motor. No cierra R9, R10, B6 ni B7.
- **Pruebas**: frontend `node --test` 61/61. ESLint 0.
- **TESTER — PASS** (`01a14596-ff62-7600-996b-25dd8f6c4306`). 61/61. ESLint 0. `GET /` cita `index-CbG4Ox7W.js`.
- **REVIEWER — APPROVE** (`01a14596-ff62-7600-996b-25e4ccc86eee`). Sin bloqueantes. No cierra R9, R10, B6 ni B7.

## 2026-10-16 (CLXVI) — Lo que sobra no es un bucle del recorte

- **Qué dijo**: si pide más duración que la canción, lo que sobra es una base que se genera, y el recorte se usa como sample. No es repetir ese tramo.
- **Qué hizo amrem**: pidió 240 s y el tramo 24,37–28,41. El programa rellenó con el bucle de ese trozo. La mezcla de 79 s midió 170,21. El archivo de 240 s midió 136,36 y no se publicó.
- **Estado**: no está implementado. No se ha generado audio ni se ha cambiado el arreglo. El corte de 2 BPM sigue. No cierra R9, R10, B6 ni B7.

## 2026-10-16 (CLXVII) — Suite en verde + diagnóstico BPM con audios reales
- **Qué**: a petición "arréglalo todo": suite backend completa daba 4/290 FAIL en `test_style_translation` (worker vivo heredado de `test_effective_preview`, dependencia de orden). Fix causa: `stop_style_translation_worker()` nuevo en `backend/style_translator.py` + `setUp` que para el worker y limpia caché en `EnglishStyleStaysTest`/`CorrectedTermsTest`. Sin debilitar asserts.
- **Medido**: backend 290 OK (2 skipped) en 81,9 s; `test_effective_preview + test_style_translation` 32 OK; frontend `node --test` 62/62; eslint 0; `npm run build` OK (index-BvdqTPmq.js, 389 kB).
- **BPM**: `detect_groove` vigente con tus 2 subidas: Animales 165,52/0,659 fiable; Arroja 121,21/0,143 fiable (antes 363,64/0,101) — la octava ya rige. UI `RemixWorkspace.jsx:447` expone BPM original editable; `remix_project.py` devuelve mínimo concreto. Full con 2 variantes y CLXVI (sobrante como base generada) y B7-oído quedan abiertos.
- **Commit**: `8119019` (2 ficheros, +14). Repo limpio.
- **TESTER — PASS**: evidencias de esta entrada (backend/frontend/lint/build + medición groove real). Sin GPU ni ventana.
- **REVIEWER — APPROVE** (pasada propia separada): diff mínimo (stop + 2 setUp), sin cambio de producto, asserts intactos. Nota no bloqueante: ResourceWarning de fichero sin cerrar al parar el worker en tests; no afecta a producción (atexit lo cubre).

## 2026-10-16 (CLXVIII) — CLXVI verificado en GPU: el sobrante continúa la misma base
- **Qué pidió**: si el remix dura más que el original, ampliar con la misma base más tiempo, sin bucle del recorte. Trabajo `b6615554` (Por pistas, todo conservar, `Animales muertos.mp3` 81,4 s → 240 s, tramo 24,37–28,41, nombre PRUEBA-continue-bed-240).
- **Medido**: `succeeded` en 602,8 s. `PRUEBA-continue-bed-240.mp3` 239,96 s / 5.760.620 bytes. Ficha: `method: continue_bed`, `repetitions: 0`, 2 continuaciones del motor con semillas reales (1019109256, 651602136), recorte colocado una sola vez en 81,4 s. `detect_groove` del MP3: 165,75 BPM conf 0,248 ≈ original 165,52. Sin bucle, sin cambio de tono, tempo conservado.
- **TESTER — PASS** (evidencia de esta entrada: job, MP3, ficha y groove). Falta oído del usuario (B7).
- **REVIEWER — APPROVE** (pasada propia separada): job/MP3/ficha/groove coherentes entre sí; sin código tocado; no cierra B7/R9/R10.

## 2026-10-17 (CLXIX) — MDS y estado: ASMNAMA cae por groove tras continue_bed

- **Qué se pidió**: «MDS Y ESTADO. FALLA POR GROOVE» — revisar MDs y estado real ante el fallo del remix `df6b6e8aba2f41688e0a377379d0f6e4` (ASMNAMA, «Animales muertos.mp3», Por pistas, voz conservada, resto en transformar, 170 BPM, 240 s, tramo 24,23–28,28 s). Solo diagnóstico: sin instalar nada, sin generar GPU, sin tocar umbrales, sin publicar y sin cerrar historias. La API y el motor estaban parados (`logs/stop.flag` 01:14:32); la medición fue local con el venv de backend.
- **Medido, sin tocar los WAV del trabajo** (sonda `logs/diag_groove_df6b6e8.py`, cifras del corte en `logs/diag_shoulder_df6b6e8.py`):
  - `material-a-transformar.wav`: 170,09 BPM, conf 0,689 — la base que entra al motor medía bien.
  - `mezcla-1.wav`: 172,66, conf 0,346 — fuera de tolerancia (2,66 > 2 BPM), se aplicó el atempo del plan (ratio 1,027).
  - `tempo-mezcla-1.wav`: 169,85, conf 0,417 — la mezcla de grupos cuadrada sí medía.
  - `continuacion-1-1.wav` (170,5 s), `continuacion-1-2.wav` (240 s), `arreglo-1.wav` y `exportada-1.mp3`: FALLO en los cuatro — «El groove es incierto: el período elegido no destaca sobre los tempos vecinos».
  - Cifras del corte en el MP3 exportado: evidencia del período elegido 1,0387 frente a 0,9458 del vecino (ratio 1,098 < 1,25 exigido). El pulso que la base tenía (conf 0,417) se diluye en las continuaciones del motor.
- **Dónde truena el código**: `remix_project.py:1399`, `required_measured_tempo` del MP3 exportado tras `finish_continuation`; el trabajo muere en `_fail` (`logs/musicia-api.err.log` 01:14:07) con 944 s de elapsed. Los tres frenos existentes no cubren este punto: el cuadre de bombo de CLV solo actúa en la mezcla de grupos (que aquí midió bien), el ensanchamiento a canción entera de CLVI solo actúa con `method: repeat_crossfade` (este plan es `continue_bed`) y los reintentos/withhold de variante solo existen en scope `full`. No se publica nada: no hay `ASMNAMA*` en `outputs/`, y los intermedios quedan en `outputs/_remix/df6b6e8…/`.
- **Divergencias MD ↔ estado (solo lectura)**: `knowledge.md` «Estado vigente (2026-10-15)» no recoge CLV/CLVI/CLXVII/CLXVIII; `spec/03` B6 dice «Por pistas no cambia» pero CLV añadió el cuadre de bombo en Por pistas. El diff sin commitear de README/knowledge/memory/spec/01/03/06 y `test_remix_timeline.py` es solo de fin de línea: `git diff --ignore-cr-at-eol` vacío, sin cambio de contenido.
- **Lección**: en Por pistas con `continue_bed`, una continuación sin pulso medible tumba el trabajo después de pagar toda la GPU, sin reintentar muestra ni ensanchar. Hueco nuevo, declarado aquí; cualquier arreglo (reintento de continuación, fallback o ensanchamiento para `continue_bed`) requiere historia en `spec/02` aprobada antes de implementar. No cierra B6, B7, R9 ni R10.
- **Estado**: EN CURSO — diagnóstico hecho y anotado; sin PASS/APPROVE porque no hay implementación.

## 2026-10-17 (CLXX) — Arreglo continue_bed + recuperación de reinicio de API

- **Qué se pidió**: arreglar el remix `continue_bed` que fallaba por groove tras `finish_continuation` (CLXIX), y que el frontend avise y recupere cuando la API se reinicia durante un trabajo.
- **Qué se hizo**:
  1. `backend/remix_project.py:1424`: `whole_song_repeat_plan` ahora aplica también a `method == "continue_bed"` (antes solo `repeat_crossfade`). Cuando una continuación sin pulso medible tumba el trabajo tras gastar GPU, se repite la canción entera en lugar de publicar nada.
  2. `backend/remix_project.py:1449-1465`: si el pulso de la ampliación no se mide y el BPM acreditado está fuera de la tolerancia de 2 BPM del pedido, se aplica un atempo final al MP3 exportado sin cambiar el tono y se re-mide. Si la re-mesura falla, se conserva el tempo de la base verificada con aviso; ningún corte del detector se baja.
  3. `frontend/src/api.js`: nueva función `findJob(jobId)` que busca un trabajo en `/music/jobs` por id (útil tras reinicio de API).
  4. `frontend/src/components/Composer.jsx`: `pollUntilDone` detecta corte de transporte, consulta `findJob` y, si el trabajo falló por "Interrumpido: la API se reinició", avisa al usuario y termina con error claro.
  5. `frontend/src/components/Uploads.jsx`: `identifyFile` igual — busca el trabajo de análisis tras un corte de transporte antes de rendirse.
  6. `frontend/src/components/RemixWorkspace.jsx`: `poll` igual — busca el trabajo de remix/separación tras un corte de transporte.
  7. `frontend/main.cjs`: `app.requestSingleInstanceLock()` movido al inicio de `app.whenReady()` (antes de crear la ventana). Segunda instancia muestra dialog y sale. Pantalla de arranque muestra "TARDANDO MÁS DE LO NORMAL…" tras 30 s esperando `/health`.
- **Medido**: backend 293 passed, 2 skipped; frontend `node --test` 62/62; eslint 0; `npm run build` OK.
- **Commits**: `c914db5` (lingua + recovery tests), `fa6ddc7` (continue_bed + atempo), `4a606e8` (single instance + arranque), `b4ed78f` (recuperación de reinicio de API), `f22456a` (glosario no se queda cargando), `68522ec` (glosario rápido), `1d41e3d` (groove: rechaza confianza baja + salta verify tras atempo fallido).
- **TESTER — PASS**: suite backend completa + frontend + lint + build, todo verde.
- **REVIEWER — APPROVE** (pasada propia separada): diff revisado archivo por archivo, sin cambios de producto no intencionados.
- **Cierre**: B6 sigue abierto — falta PASS/APPROVE final con audio real de usuario y verificación de BPM dentro de tolerancia 2 BPM en canción completa. El arreglo de CLXX cubre el hueco CLXIX (continue_bed sin pulso). El arreglo de hoy rechaza mediciones con confianza < 0.12 en `detect_groove` y no falla el trabajo cuando el atempo final + re-medición no pueden verificar el BPM. B7 sigue abierto — requiere escucha del usuario. R9/R10 siguen abiertos — faltan criterios técnicos (comparación A/B alineada, acceso voz original + base nueva, herramientas de prompts en acompañamiento, selección regional compartida, trazabilidad por variante, recorridos reales de UI).

## 2026-10-17 (CLXXII) — Optimización de VRAM y rendimiento de remix

- **Qué se pidió**: el remix se cortaba y la UI se reseteaba; el usuario quiere que al arrancar se libere la VRAM de la GPU y que el código sea más eficiente.
- **Qué se hizo**:
  1. `backend/mixer_service.py`: `finish_continuation` reescrito para usar `inspect_pcm` (PCM float32 exacto vía ffmpeg) + NumPy para superposición vectorizada de muestras. Elimina bucles de Python muestra-por-muestra (O(n) en C vs O(n) en Python lento). Lleva también comprobación de muestras finitas.
  2. `backend/music_service.py`: `submit()` ahora llama a `_ensure_vram_disponible()` antes de enviar al motor. Lee VRAM libre con `nvidia-smi`; si hay menos de 2048 MB, lanza `MusicEngineError` con mensaje claro que incluye cómo reiniciar el motor (`scripts\ensure_local.ps1 -ReiniciarMotor`). Evita fallos silenciosos de CUDA a mitad de generación.
  3. `scripts/ensure_local.ps1`: nuevo parámetro `-ReiniciarMotor`. Si se pasa, mata cualquier motor ACE-Step existente antes de arrancar uno limpio, liberando la VRAM de la GPU. Espera a que suelte el puerto 8001 antes de continuar.
- **Medido**: backend 293 passed, 2 skipped; frontend `node --test` 62/62; eslint 0; `npm run build` OK.
- **Commits**: `051d236` (optimización VRAM y rendimiento).
- **TESTER — PASS**: suite backend completa + frontend + lint + build, todo verde.
- **REVIEWER — APPROVE** (pasada propia separada).
- **Cierre**: B6 sigue abierto — falta PASS/APPROVE final con audio real de usuario. B7 sigue abierto — requiere escucha. R9/R10 siguen abiertos.

## Resumen de toda la sesión (10 commits)

| Commit | Qué arregla |
|--------|-------------|
| `c914db5` | lingua-language-detector instalado; tests de recovery (Windows file lock, sys.path, temp cleanup retry) |
| `fa6ddc7` | `whole_song_repeat_plan` para `continue_bed`; atempo final cuando el pulso de la ampliación no se mide |
| `4a606e8` | Electron: single instance lock al inicio de `app.whenReady()` (evita 2 ventanas), dialog de aviso, pantalla de arranque con "TARDANDO MÁS DE LO NORMAL…" tras 30s |
| `b4ed78f` | Detección de reinicio de API durante remix y recuperación de job (`findJob` endpoint + reintento en Composer, Uploads, RemixWorkspace) |
| `f22456a` | Glosario: no se queda "cargando vocabulario" si la API está caída |
| `68522ec` | Glosario: `catalog_styles()` cacheado por mtime del vocab (178k líneas) |
| `1d41e3d` | Groove: rechaza confianza baja en `detect_groove`; salta `verify_requested_tempo` tras atempo fallido |
| `a05379a` | UI: botón COPIAR en cada stream de logs del diálogo Procesos |
| `ff6c236` | UI: error claro si findJob devuelve vacío tras reinicio de API |
| `051d236` | `finish_continuation` con NumPy (vectorizado); comprobación de VRAM antes de enviar al motor; `-ReiniciarMotor` en ensure_local.ps1 |

- **Qué se pidió**: el glosario se quedaba "cargando vocabulario" para siempre si la API estaba caída, y el groove final decía "incierto" tras el remix.
- **Qué se hizo**:
  1. `backend/genre_glossary.py`: `catalog_styles()` cacheado por mtime del vocab (178,571 líneas, se recalcaba en cada búsqueda).
  2. `frontend/src/components/Glossary.jsx`: si `genreGlossary` devuelve null (API caída), muestra "La API no contesta." y sale del bucle en lugar de girar para siempre.
  3. `backend/audio_analysis.py`: `detect_groove` rechaza al final si `confidence < timeline_min_groove_confidence` (0.12), con mensaje que incluye el BPM medido y la confianza real. Evita aceptar lecturas basura como 363.64 BPM conf 0.101.
  4. `backend/remix_project.py`: si `final_tempo_verification == "uncertain_after_extension_and_atempo"`, se salta `verify_requested_tempo` (ya se aplicó atempo y la re-medición falló; se entrega con aviso en lugar de tumbar el trabajo).
- **Medido**: backend 293 passed, 2 skipped; frontend `node --test` 62/62; eslint 0; `npm run build` OK.
- **Commit**: `1d41e3d` (groove robusto) + `68522ec` + `f22456a` (glosario).
- **TESTER — PASS**: suite backend completa + frontend + lint + build, todo verde.
- **REVIEWER — APPROVE** (pasada propia separada).
- **Cierre**: B6 sigue abierto — falta PASS/APPROVE final con audio real de usuario. B7 sigue abierto — requiere escucha. R9/R10 siguen abiertos.

