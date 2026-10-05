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

### [A3] [P0] [verificada] CANCIÓN CON VOZ: letra + selector de voz
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
- [x] El usuario confirmó el 2026-10-02 que el flujo funciona

**Endpoint**: `POST /music/write_lyrics` → proxy a `/format_input` del motor
(caption, lyrics, bpm, key_scale, vocal_language). El modo con voz y el campo
de letra están cableados en CREAR, SUBIR y BIBLIOTECA.

### [A4] [P2] [parcial] Parámetros musicales en CREAR
- [x] BPM, tonalidad (key_scale) y semilla en `Composer.jsx` (chips, tono, campo SEMILLA)
- [ ] Compás (time signature) no está expuesto

## Épica B — Voz

### [B1] [P0] [retirada] Texto a locución
El usuario la quitó el 2026-10-02: esa pestaña leía un texto en voz alta y el producto es música.
La voz cantada sigue en [A3]. `VoiceLab.jsx` ya no está.
El 2026-10-05 se quitaron también `POST /tts/generate`, `GET /voices`, `tts_service.py` y `edge-tts` de requirements (era red: anti LOCAL-FIRST).

### [B2] [P2] [propuesta] Voz sobre música (voz + mezcla desde la UI)
- Depende de `/audio/mix` (existe) + orquestación UI

## Épica C — Herramientas de estudio

### [C1] [P1] [cerrada por F1] Mezclador visual
- La pestaña MEZCLA monta `MixLab` (ffmpeg real). `Mixer.jsx` no está importado.

### [C2] [P2] [propuesta] Secuenciador con samples locales
- Hoy descarga samples de tonejs.github.io (R4: dependencia de red declarada)
- [ ] Samples empaquetados localmente

## Épica D — Plataforma

### [D1] [P0] [verificada] App de ventana (no navegador)
- [x] Electron con contextIsolation + sandbox
- [x] La API sirve la UI; la ventana carga `http://127.0.0.1:8000`
- [x] Lanzador único: `scripts/open_musicia.ps1`

### [D2] [P1] [implementada] Estado del motor visible siempre
- [x] Indicador real: antes del primer chequeo el lateral dice MOTOR y la pastilla no sale. Luego MOTOR ACTIVO o MOTOR APAGADO. No hay estado CONECTANDO.
- [x] Si `/health` no contesta, o hay una canción en curso, no se pinta APAGADO.
- [x] Con la ventana abierta, si el proceso del motor o de la API no está, se vuelve a arrancar. Solo SALIR lo deja parado. Abrir la ventana otra vez lo arranca.
- [x] La X de la ventana no cierra ni esconde. `closable: false` y el evento `close` se ignora. SALIR (botón y bandeja) apaga motor y API. No se ha abierto la ventana.
- [x] Un corte de tiempo no enseña el texto inglés de axios. La lista de biblioteca, subidas y mezcla lo calla. Si la ventana no carga, se ve «ARRANCANDO EL MOTOR LOCAL…» y no la página de error de Chromium. El envío de una canción espera 90 s, por encima de los 60 s del motor.
- [x] No hay botón suelto de reintentar: el sondeo reconecta solo

### [D3] [P2] [propuesta] Empaquetado instalable
- [ ] electron-builder → instalador Windows con icono propio

## Épica F — Mezcla y remixes (bootlegs)

### [F2] [P1] [verificada] REMIXER con IA y acciones de bootleg
**Como** usuario, **quiero** remixir de verdad: poner música nueva con la IA
sobre mi voz, sacar instrumentales o acápelas, hacer loops, medio/doble tiempo y
fundir dos temas, **para** hacer bootlegs y remixes sin salir de la app.

**Criterios de aceptación**
- [x] Acciones de un clic: VOZ + MÚSICA DESDE PROMPT, SOLO BASE DESDE PROMPT,
      INSTRUMENTAL, ACAPELLA, LOOP DE 4 COMPASES, MEDIO/DOBLE TIEMPO,
      FORZAR TEMPO A y CROSSFADE
- [x] El remix con IA encadena pasos con progreso real (separar → generar →
      cuadrar → mezclar), nunca "colgado"
- [x] Nunca se cuadra si el tempo no es fiable: se avisa en vez de destrozar
- [x] UI compacta: un desplegable de acciones + una línea de estado
- [x] Verificación real: loop, forzado a 90 bpm (0,26 % de error), crossfade a
      -14,5 LUFS y remix IA completo en ~230 s (memory.md)
- [x] El usuario confirmó el 2026-10-02 que el flujo funciona

### [F3] [P1] [en código] Versión, tramo y ajuste sobre el audio que ya existe
**Como** usuario, **quiero** cambiar el estilo de una pista, rehacer un trozo o ajustar tempo y tono, **para** remixar de verdad sin componer otra canción desde cero.

**Decisiones (2026-10-02)**
- El usuario quitó la locución y pidió aplicar las mejoras.
- En el turbo de 8 GB solo `text2music`, `cover` y `repaint`. `lego`, `extract` y `complete` no se ofrecen: piden `acestep-v15-base` y no se ha medido la VRAM.
- No hay botón PARAR. La API de ACE-Step no cancela, y un botón que solo deje de mirar fingiría que la GPU queda libre.
- Si el mismo nombre está en biblioteca y en subidas, mezcla usa el de la biblioteca.

**Criterios de aceptación**
- [x] El menú de remix elige la acción. HACER la lanza. Un prompt vacío no llama al motor.
- [x] Versión manda `task_type=cover`, la ruta del audio y la fuerza de `generation.cover_strength` (0,6 si no se cambia).
- [x] Tramo manda `repaint`, inicio/fin en segundos, y fin vacío vale -1 (hasta el final).
- [x] Sin duración pedida, cover y repaint envían `audio_duration=-1` para que el motor use la del origen.
- [x] `lego`, `extract` y `complete` se rechazan antes de crear un job.
- [ ] Una versión cover real, con MP3 y duración > 0. No se lanzó: el turbo ya estaba cargado y una cover ocupa la GPU varios minutos.
- [ ] Un tramo repaint real, con la misma prueba de audio.
- [x] Ajustar sigue siendo el panel DSP (tempo, tono, fundido, recorte).
- [x] `POST /audio/separate` responde al momento con `job_id`. `GET /audio/separate/status` sigue diciendo si demucs está instalado.
- [x] MEZCLA lista biblioteca y subidas en BASE y en VOZ. El nombre vacío usa el stem de `mixer.default_output_name`.
- [x] Al acabar una generación se escribe `*.ficha.json` junto al MP3.
- [x] CREAR, SUBIR, MEZCLA y BIBLIOTECA siguen montadas al cambiar de pestaña.
- [x] En SUBIR, cada audio ya guardado tiene REMIX. Abre la misma mesa con ese nombre, sin un POST nuevo a `/audio/upload`.
- [x] La base nueva (voz real o solo base) acepta minutos (1 hasta `max_duration_seconds`) y una letra. La letra se adapta a esos minutos antes de generar. Sin letra sigue siendo instrumental.
- [x] El payload manda `use_cot_caption=false`. El caption que llega al motor es el prompt escrito, no una reescritura del LM. Versión y tramo siguen durando lo que dura el audio: el motor ignora otra duración en cover y repaint.
- [x] El payload manda `use_cot_metas=false` y el motor lo respeta desde la recarga del 2026-10-04. Sin BPM pedido, el meta sale `N/A`: el LM no escribe un tempo ni un tono. No se ha oído una canción nueva después de ese arreglo.

### [F4] [P1] [en código] Remix con la misma ficha que CREAR, y un solo modelo
**Como** usuario, **quiero** que una versión o un tramo se pidan como una canción (prompt, letra, BPM, tono, semilla, nombre) y que la GPU no cargue otro modelo, **para** afinar el remix y no quedarme sin VRAM.

**Criterios**
- [x] Versión y tramo aceptan letra (vacío = instrumental), tono, semilla y nombre. La semilla escrita apaga el azar.
- [x] MEJORAR PROMPT usa el mejorador local ya existente.
- [x] Si la biblioteca tiene ficha, el remix la enseña al abrir.
- [x] Al terminar cover o repaint, el MP3 pasa por el mismo master de −14 LUFS que la mezcla.
- [x] Un segundo trabajo pesado (generar, remix IA o separar) responde 409 mientras el primero sigue.
- [x] `model` distinto de `acestep-v15-turbo` se rechaza. No se llama a `/v1/init`. No se descargan pesos.
- [ ] Una cover real con letra, master medida y duración > 0. El master sí se midió sobre una copia de `am.mp3` (−13,66 LUFS). La cover en GPU no se lanzó.

### [F5] [P1] [en código] Cableado: la ficha, la barra y el doble tiempo
**Como** usuario, **quiero** que cada pista nueva recuerde de dónde sale y que la barra de arriba diga qué está haciendo la máquina, **para** no perder el hilo al cambiar de pestaña.

**Criterios**
- [x] «Otra versión» en BIBLIOTECA y re-crear en SUBIR envían `task_type=cover` y `source_name`, sin duración.
- [x] Re-crear en SUBIR no envía el BPM medido. Un prompt vacío no inventa una frase. Crear base manda la duración del audio, con tope `max_duration_seconds`, y tampoco ese BPM.
- [x] «Crear base» en SUBIR sigue siendo instrumental nuevo, con duración.
- [x] La ficha se mueve al renombrar, se borra con el audio y se copia en mezcla, tempo, loop, fundido, edición, remix DSP, separación y remix IA.
- [x] DOBLE TIEMPO envía `mode=double`. Un modo distinto de `half`, `double` o `bpm` responde 400 y no escribe MP3.
- [x] `GET /music/jobs` incluye el remix IA y la separación. La barra muestra la fase del trabajo activo.
- [ ] Una cover real. Sigue sin lanzarse.

### [F6] [P1] [en código] Arreglo automático de la voz sobre una base más larga
**Como** usuario, **quiero** que la voz de una canción se corte en trozos y se reparta sola cuando la base nueva dura más, **para** llenar el tema sin estirar la voz.

**Decisiones (2026-10-04)**
- El cover no puede alargarse: el motor fija la duración a la onda de origen.
- SOLO BASE NUEVA sí puede durar más minutos. La voz real se coloca después, en MEZCLA.
- El sistema lo hace solo. No hay que marcar cada trozo.
- Si las dos pistas duran parecido (la voz pasa de `arrange_shorter_than`, 0,85 de la base), se mezcla como hasta ahora.

**Criterios**
- [x] Con una voz claramente más corta, MEZCLAR corta frases y las coloca en los golpes de la base, sin atempo. Probado con 12 s sobre 40 s del tema subido: 9 trozos, el primero a 0,04 s y el último a 39 s.
- [ ] Antes de mezclar, la pantalla dice cuántos trozos y dónde entra el primero y el último. El texto está en la mezcla; no se ha abierto la ventana.
- [x] Con dos pistas de duración parecida no se parte la voz. El mismo tema contra sí mismo no arregla.
- [x] El MP3 dura lo que la base (40,000 s), −13,96 LUFS y pico −1,0. El original no se tocó y el archivo de prueba se borró.
- [x] VOZ REAL con minutos: 300 s sobre una canción de 240 s pide base nueva y trozos. 120 s o sin minutos se queda en el cover. No se lanzó esa generación en la GPU.
- [x] MEJORAR PROMPT solo añade el BPM. «rotterdam hardcore… techno oscuro» más 175 bpm no trae otro estilo.
- [x] FUNDIR no estira un tempo fuera de 0,8–1,25. Un metrónomo de 160 contra uno de 100 no se estiró. Uno de 120 sí se igualó.


### [F1] [P0] [implementada] Mezcla que "cuadra las baterías" y suena profesional
**Como** usuario, **quiero** que al mezclar se alineen las pistas entre sí
(tempo y fase de la batería) y que el volumen quede igualado, **para** que
suene a canción y no a capas pegadas.

**Decisiones del usuario (ask_user 2026-10-02)**
- Alineación: **mostrar lo que se va a hacer y pedir confirmación** (nunca
  aplicarla a ciegas).
- Acabado activado por defecto: **normalización a -14 LUFS** (con margen para
  no saturar). Ducking y filtro de graves: NO se activan.
- Separación de voces: **profesional** (modelo de separación real en local,
  instalación de ~2,5 GB, 1-3 min por pista).

**Capacidad real del entorno (verificado)**
- ffmpeg 9.0.2 tiene `atempo`, `loudnorm` y `sidechaincompress` → alineación
  de tempo sin cambiar tono y loudness profesional, sin dependencias nuevas.
- ACE-Step 1.5 **NO tiene** separación de voces (revisadas todas sus rutas):
  hace falta un motor aparte (venv dedicado + pesos).

**Criterios de aceptación**
- [x] Análisis en pareja: BPM + fase de golpe de cada pista y ajuste propuesto
      (ratio de tempo + desfase en ms) antes de mezclar
- [x] `atempo` (ratio en cadena si sale de rango) + `adelay` para cuadrar la
      batería; el tono NO cambia
- [x] `loudnorm` a -14 LUFS con `true peak` limitado (nunca satura)
- [x] `POST /audio/separate`: extrae voces (y base) a ficheros reales; se puede
      remezclar la voz extraída con otra base
- [x] Si el motor de separación no está instalado, la UI lo dice; nunca simula
- [x] UI compacta: controles en una línea con desplegables (`SelectBox`)
- [x] Verificación real: mezcla de dos pistas con tempos distintos, nombres y
      loudness medidos (memory.md)


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

## Épica M — El motor obedece al prompt

### [M1] [P0] [medición en curso] Un modelo que pueda seguir el prompt
**Como** usuario, **quiero** que lo que escribo se oiga, **para** no tener que
aceptar que un «hardcore de Rotterdam» suene a otra cosa.

**Hecho medido en el motor (no es de Musicia)**
- El DiT turbo está **destilado con CFG horneado**: `guidance_scale` se fuerza a
  1.0 y no hay pasada incondicional
  (`vendor/ACE-Step-1.5/acestep/models/turbo/modeling_acestep_v15_turbo.py:1833-1849`
  y `:1907`). `inference.py:80`: «Only support for non-turbo model».
- El modelo lo declara: turbo `CFG ✗ · 8 pasos`; `acestep-v15-sft` y
  `-base` `CFG ✓ · 50 pasos` (`checkpoints/README.md`, tabla Model Zoo).
- `acestep-v15-sft/model.safetensors` mide **4 787 825 604 bytes: los mismos
  exactos que el turbo** (2B, misma arquitectura). El pico medido del turbo es
  6,9 GB de 8 GB, así que **cabe** — falta medirlo de verdad.
- No turbo → solo `text2music`, `cover`, `repaint`: lo decide `is_turbo` en
  `config.json` (`api/http/model_service_routes.py:33-46`). SFT desbloquea
  `extract`, `lego` y `complete`.
- El motor sabe descargar y cambiar de modelo en caliente
  (`api/job_model_selection.py:77`, `api/http/model_init_service.py:109`).
  El resident es `ACESTEP_CONFIG_PATH`; hay dos huecos más
  (`ACESTEP_CONFIG_PATH2/3`), y `ACESTEP_OFFLOAD_TO_CPU` existe.

**Decisiones del usuario (2026-10-04, ask_user)**
- **Medir el sft y, si cabe en 8 GB, usarlo en los remixes.**
- Si no cabe: no se cambia el modelo, y se dice con la medida. No se maquilla.
- No es obligatorio que el prompt se cumpla al 100 %: se busca lo más posible,
  y lo que no se cumple se declara.

**Criterios de aceptación**
- [ ] El peso `acestep-v15-sft` está en `vendor/ACE-Step-1.5/checkpoints/` y su
      tamaño en disco es 4 787 825 604 bytes (verificado con `Get-Item`)
- [ ] VRAM en pico medida con `nvidia-smi` durante una generación real con sft,
      con el número pegado en `memory.md`. Si supera el total de la GPU, el
      proyecto vuelve al turbo y se documenta
- [ ] Una generación real con sft, MP3 de duración > 0, con el log del motor
      pegado (guidance efectiva, pasos, metas)
- [ ] `generation.allowed_models` acepta el sft; el resto de allowlists, igual
- [ ] El motor arranca con el modelo decidido desde `scripts/ensure_local.ps1`,
      sin tocar el código a mano
- [ ] Si el sft entra: los remixes y las versiones lo usan, y CREAR puede
      seguir con el turbo. Si no entra: esto no se implementa y se dice
- [ ] La VRAM y el modelo se enseñan en el lateral (`spec/05-MEJORAS.md`, punto 8)

### [M2] [P0] [pendiente] El remix usa la pista que elegí
**Como** usuario, **quiero** que el remix use **mi** audio, **para** que no
remixee una mezcla vieja que se llama igual.

**Causa medida (2026-10-04)**
- `_find_audio` (`backend/main.py:298`) prueba `_resolve_output` **antes** que
  `_resolve_upload`. Si una mezcla en `outputs/` se llama como la subida de
  `uploads/`, gana la mezcla. Pasó el 2026-10-03 23:03: el remix 2 separó una
  mezcla de 180 s en vez de la subida de 81,4 s; por eso no oyó el tema, no
  alargó y el cover oyó la melodía de la mezcla anterior («SIN MELODÍAS» fue
  solo el caption).
- La UI sabe de dónde viene cada pista. La info se pierde al mandar el nombre.

**Criterios de aceptación**
- [ ] El origen viaja con la petición (`source_kind: upload | output`) y el
      backend lo respeta; sin él, el nombre se resuelve como hoy
- [ ] La biblioteca manda `output` y las subidas mandan `upload`, en los 11
      caminos de remix/mezcla que usan un nombre
- [ ] Regresión: una mezcla en `outputs/` con el nombre de una subida no puede
     ganar al remix de esa subida
- [ ] Un remix real de la subida, con la duración de la fuente correcta

### [M3] [P1] [pendiente] Declarar si el resultado obedeció
**Como** usuario, **quiero** ver si lo que salió se parezca a lo que pedí,
**para** no creer que un 130 bpm era un 170.

- [ ] Tras generar, `detect_groove` mide el BPM y la confianza del MP3
- [ ] La ficha guarda `bpm_requested` y `bpm_measured`
- [ ] BIBLIOTECA lo enseña: `pedía 170 · salió 130`, solo si hay diferencia
- [ ] Nunca se maquilla: si no se puede medir, no se enseña nada
