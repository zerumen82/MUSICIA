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
