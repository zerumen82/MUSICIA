# 02 · Requisitos — Historias de usuario

Formato: **[ID] [prioridad] [estado]**. Estados: `propuesta | especificada |
en-curso | implementada | verificada`. Una historia solo pasa a `verificada`
con evidencia en `memory.md`.

Prioridad: `P0` = esenciales del producto · `P1` = importantes · `P2` = mejoras.

---

## Épica A — Crear música con IA (producto central)

### [A1] [P0] [verificada] Generar música instrumental desde una descripción
**Como** usuario, **quiero** escribir una idea ("techno oscuro, 130 bpm") y
obtener un MP3, **para** crear música sin saber producir.

**Criterios de aceptación**
- [x] La UI ofrece ideas rápidas clicables y duración 10 s–10 min en min:seg
- [x] El botón se deshabilita si no hay prompt o el motor está caído
- [x] Progreso visible durante la generación (estados reales del motor)
- [x] Al terminar: reproductor con autoplay + botón de descarga MP3
- [x] El archivo se verifica: existe, > 0 bytes, duración > 0
- [x] Evidencia: `e2e-lofi-20s.mp3` 20.0 s verificado con ffprobe (memory.md)

### [A2] [P0] [verificada] Historial de canciones
- [x] Cada generación se guarda (título, duración, fecha)
- [x] Clic en el historial → reproduce
- [x] Vaciar historial
- [x] Persiste entre sesiones (localStorage, máx. 30)

### [A3] [P0] [en-curso] CANCIÓN CON VOZ: letra + selector de voz
**Como** usuario, **quiero** que la canción con voz **cante mi letra** y poder
elegir cómo canta (mujer/hombre, timbre, estilo, emoción, idioma), **para**
que suene como la tengo en la cabeza y no como un instrumental.

**Bug raíz (2026-10-02)**: `GenerationDefaults.language = "en"` se mandaba
como `vocal_language` en TODAS las generaciones. El motor construye la
entrada `# Languages\n{lang}\n\n# Lyric\n{letra}`; con `"en"` y letra en
castellano la pista salía instrumental. Además el motor espera la letra con
marcas de estructura (`[Verse]`, `[Chorus]`…); un párrafo plano no canta bien.

**Decisiones del usuario (ask_user 2026-10-02)**
- Selector de: género de voz (mujer/hombre), timbre, estilo de canto y emoción.
- Letra: **híbrido** — botón "escribir la letra por mí" (LM local) que
  rellena el campo, y el usuario corrige o escribe la suya.

**Criterios de aceptación**
- [x] `vocal_language` viaja desde la UI (no el default "en")
- [x] Letra sin marcas → la app la estructura [verso]/[estribillo]/[puente]
- [x] Selector VOZ: género · timbre · estilo · emoción → se inyectan en el prompt
- [x] Selector IDIOMA que llega al motor (`vocal_language`)
- [x] Botón "ESCRIBIR LA LETRA POR MÍ" → `POST /format_input` del motor local,
      letra editable antes de generar (con aviso honesto si el LM no compone)
- [x] SUBIR/LIBRARY: si kind es voz/mixta, LETRA opcional → `instrumental=false`
- [x] Evidencia: generación con voz real (45 s) + letra estructurada (memory.md)
- [ ] Pendiente de oído humano: confirmar que la pista canta la letra
      (`Prueba Con Voz.mp3` en la biblioteca para escuchar)

**Endpoint nuevo**: `POST /music/write_lyrics` → proxy a `/format_input` del
motor (caption, lyrics, bpm, key_scale, vocal_language).
- [ ] La UI ofrece modo "con voz" con campo de letra (ya esbozado, falta cablear)
- [ ] Backend ya lo soporta (`instrumental=false` + `lyrics`)
- [ ] Verificación: el audio contiene voz (duración > 0 + revisión humana)

### [A4] [P2] [propuesta] Parámetros musicales avanzados
- [ ] BPM, tonalidad (key_scale), time signature expuestos en la UI
- [ ] Semilla reproducible (mostrar seed usada, permitir reutilizarla)

## Épica B — Voz

### [B1] [P0] [implementada*] Texto a locución
- [x] Selector de voces es-* reales de `/voices`
- [x] Genera y reproduce + descarga
- [*] Falta verificación de audio resultante (DoD punto 4) → pasa a `verificada` al probarla

### [B2] [P2] [propuesta] Voz sobre música (voz + mezcla desde la UI)
- Depende de `/audio/mix` (existe) + orquestación UI

## Épica C — Herramientas de estudio

### [C1] [P1] [propuesta] Conectar el mezclador visual al backend
- Los faders hoy son decorativos (R2: deuda declarada en 03)
- [ ] Cargar dos pistas (del historial), ajustar dB reales, exportar mezcla

### [C2] [P2] [propuesta] Secuenciador con samples locales
- Hoy descarga samples de tonejs.github.io (R4: dependencia de red declarada)
- [ ] Samples empaquetados localmente

## Épica D — Plataforma

### [D1] [P0] [verificada] App de ventana (no navegador)
- [x] Electron con contextIsolation + sandbox
- [x] La API sirve la UI; la ventana carga `http://127.0.0.1:8000`
- [x] Lanzador único: `scripts/open_musicia.ps1`

### [D2] [P1] [propuesta] Estado del motor visible siempre
- [ ] Indicador real (no decorativo) de motor activo/cargando en la barra lateral
- [ ] Botón "reintentar conexión"

### [D3] [P2] [propuesta] Empaquetado instalable
- [ ] electron-builder → instalador Windows con icono propio

## Épica E — Biblioteca y nomenclatura

### [E1] [P1] [verificada] Nombrar la música en todo el ciclo de vida
**Como** usuario, **quiero** poner nombre a mis canciones al crearlas, al
editar las ya creadas y al hacer remixes, **para** reconocerlas de un
vistazo y no ver `cd6809482...-synthwa.mp3`.

**Decisiones del usuario (2026-10-02, ask_user)**
- Sin nombre escrito → genérico numerado: `pista-sin-nombre`, `pista-sin-nombre-2`…
- Si el nombre ya existe → sufijo de numeración `(2)`, `(3)`; nunca se pisa nada.
- Renombrable en Biblioteca **y** en Subidas.

**Criterios de aceptación**
- [x] CREAR: campo de nombre opcional; si se rellena, el MP3 sale con ese nombre
- [x] Sin nombre → `pista-sin-nombre[-N].mp3` (nunca hash + prompt)
- [x] REMIX (IA) y RE-CREACIÓN: campo de nombre propio en el panel compartido
- [x] REMIX (DSP) y AJUSTES: heredan nombre de la fuente con sufijo, no `-remix-remix`
- [x] Biblioteca y Subidas: renombrado en línea (endpoint de rename) que no pisa
      ficheros ajenos (busca en outputs/ y uploads/)
- [x] Nombres seguros: sin rutas ni caracteres especiales (`_safe_name`)
- [x] Verificación real: crear, renombrar, remix y comprobar nombres en disco (memory.md)

**Endpoint nuevo**: `PATCH /music/audio/{name}` con `{ new_name }` →
resuelve outputs/ y uploads/, sanea, desambigua con sufijo y devuelve
`{ name, renamed_from }`.
