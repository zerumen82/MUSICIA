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

### [M1] [P0] [medido 2026-10-05, falta el oído] Un modelo que pueda seguir el prompt
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

**Criterios de aceptación** (todos verificados el 2026-10-05; evidencia en
memory.md entrada XLVI)
- [x] El peso `acestep-v15-sft` está en `vendor/ACE-Step-1.5/checkpoints/` y su
      tamaño en disco es 4 787 825 604 bytes (verificado con `stat`, idéntico
      al del turbo)
- [x] VRAM en pico medida con `nvidia-smi` durante una generación real con sft:
      **6 607 MB de 8 025 MB** (mínimo 1 418 MB libres, sin OOM); muestreo cada
      3 s en `logs/vram-sft-remix.log`
- [x] Una generación real con sft: remix completo 2026-10-05 21:17–21:21,
      `prueba-sft-obediencia.mp3` (81,45 s, 1 956 140 bytes, -14 LUFS); log del
      motor con `50/50` pasos y **cero** líneas «overriding guidance», es decir
      guidance 7.0 efectiva
- [x] `generation.allowed_models` acepta el sft (config.py + config.example.json)
- [x] El motor arranca con el modelo decidido desde `scripts/ensure_local.ps1`
      (`ACESTEP_ON_DEMAND_MODEL_LOAD=true`), sin tocar el código a mano
- [x] Si el sft entra: los remixes y las versiones lo usan, y CREAR sigue con
      el turbo. Verificado ida (remix → sft, `loaded_model: acestep-v15-sft`)
      y vuelta (crear → turbo, `loaded_model: acestep-v15-turbo`)
- [x] La VRAM y el modelo se enseñan en el lateral (`App.jsx`: modelo cargado,
      VRAM libre y modelo de remix, refrescados cada 10 s con `/music/models`)
- [ ] **El oído del usuario**: el próximo remix con el sft dicta si la
      obediencia mejora de verdad. La fuerza 0,1/0,5 y la glosa también se
      juzgan oyendo.

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

### [M3] [P1] [parcial] Declarar si el resultado obedeció
**Como** usuario, **quiero** ver si lo que salió se parezca a lo que pedí,
**para** no creer que un 130 bpm era un 170.

- [x] Cableado manual 2026-10-06: botón TEMPO en el menú ACCIONES de
      BIBLIOTECA mide el tempo real (`GET /audio/groove`, DSP local, con
      `source_kind=output`) y, si la ficha trae BPM pedido con diferencia
      ≥3, enseña `PEDÍA 180 · SALE 170`. Sin medición automática por fila.
- [ ] Tras generar, `detect_groove` mide el BPM y la confianza del MP3
- [ ] La ficha guarda `bpm_requested` y `bpm_measured`
- [ ] BIBLIOTECA lo enseña solo: `pedía 170 · salió 130`, solo si hay diferencia
- [ ] Nunca se maquilla: si no se puede medir, no se enseña nada

### [Q1] [P1] [en código] La cola sobrevive al reinicio
**Como** usuario, **quiero** que el historial de trabajos no se pierda al
reiniciar la API, **para** saber qué terminó y qué se quedó a medias.

**Decisiones (2026-10-06, ask_user)**: historial + interrumpidos (los activos
al apagar se marcan «Interrumpido: la API se reinició»); solo terminados no,
olvidar todo no. Fichero `backend/job_history.json` (con gitignore), foto
atómica al terminar cada trabajo y al cancelar; al arrancar se carga.

**Criterios de aceptación**
- [x] Al terminar/cancelar se escribe el fichero; al arrancar se recupera
- [x] Lo que estaba activo aparece como fallido «Interrumpido», nunca como listo
- [x] Tope `job_history` (30): los activos no se podan nunca

### [Q2] [P1] [en código] PARAR un trabajo en curso
**Como** usuario, **quiero** parar un trabajo que no me convence, **para**
liberar la GPU sin esperar 30 min.

**Decisiones (2026-10-06, ask_user)**: soltar + matar motor (el motor no sabe
cancelar: se mata su proceso y `ensure_local` lo relanza; recargar el modelo
tarda minutos); botón PARAR por fila activa en JobsPanel.

**Criterios de aceptación**
- [x] `POST /music/jobs/{id}/cancel`: inexistente→404, terminado→409, activo→failed «Cancelado» sin descargar nada
- [x] Si el motor trabajaba se reinicia; si no (cola, separación), solo se marca
- [x] Fila activa con PARAR + aviso del reinicio en el título
- [ ] Ciclo vivo con GPU (cancelar un remix real y ver volver el motor)

### [L1] [P1] [en código] BIBLIOTECA se actualiza sola al terminar un trabajo
**Como** usuario, **quiero** que la BIBLIOTECA se recargue cuando una
generación, remix o separación termina, **para** ver la pista nueva sin pulsar
ACTUALIZAR ni cambiar de pestaña.

**Decisiones (2026-10-06, ask_user)**: nada de sondeo periódico (tráfico y
parpadeos sin motivo); evento: la app ya sondea `/music/jobs` cada 3 s para la
barra, y al pasar de "hay trabajo activo" a "no hay" dispara la recarga.

**Criterios de aceptación**
- [ ] Con BIBLIOTECA abierta y un trabajo en curso, al terminar aparece la pista nueva sin tocar nada (necesita job real + ventana; verificado por construcción y bundle)
- [x] Sin trabajos en curso no hay peticiones extra a `/music/library` (el tick solo avisa en la transición activo→vacío)
- [x] La selección del modo SELECCIONAR y la reproducción en curso sobreviven a la recarga (la recarga poda, no vacía; el `<audio>` va por nombre)
- [x] El botón ACTUALIZAR sigue funcionando a mano (no se tocó)

### [L2] [P1] [en código] Borrar en bloque desde BIBLIOTECA
**Como** usuario, **quiero** borrar varias pistas de una vez, **para** limpiar
pruebas sin ir una por una.

**Decisiones (2026-10-06, ask_user)**: modo SELECCIONAR explícito (botón en la
cabecera; clic en la fila marca/desmarca); un solo SÍ/NO para todo el bloque;
un endpoint múltiple `POST /music/audio/delete_many` (una petición, reporte
por archivo) en vez de N llamadas.

**Criterios de aceptación**
- [x] SELECCIONAR muestra casilla por fila + barra (N seleccionadas, TODAS, NINGUNA, BORRAR, SALIR) — bundle `index-hi3xe_Ft.js` lo trae
- [x] BORRAR pide un solo SÍ/NO y borra el bloque con su ficha (`.ficha.json`) — TestClient: 2 MP3 + ficha fuera en un POST
- [x] Inexistente en el bloque → se reporta, no tumba el resto; tope 100 nombres por petición (400) — TestClient: `not_found`, `[]`→422, 101→422, `../evil`→`not_found` sin borrar nada
- [x] Tras borrar, la lista se recarga y la selección se limpia (código + `refresh()` tras el POST)

### [L3] [P1] [verificada] BIBLIOTECA: solo versiones finales; base y voz, aparte
**Como** usuario, **quiero** que BIBLIOTECA enseñe solo mis versiones finales
y que la voz/base separadas no mareen, **para** ver de un vistazo lo mío.

**Diagnóstico (2026-10-07)**: un solo remix de voz dejaba 6 ficheros en la
lista (mezclas + 2 bases + voz separada + base separada). La base generada
llevaba ficha `remix` (indistinguible de la mezcla final) y la base separada
por demucs en modo voz no llevaba ficha (task `None` → parecía final).

**Criterios de aceptación**
- [x] Por defecto solo se ven las versiones finales (crear, versión, tramo, remix/mezclas, tempo, loop, ajuste)
- [x] Voz/base separadas (`task vocals|instrumental` o nombre `-base/-voces`) van al final, atenuadas, detrás de un botón `VER BASE Y VOZ SEPARADAS · n` (no desaparecen: se pueden borrar y usar en MEZCLA)
- [x] Backend: base separada y base generada en modo voz llevan ficha `instrumental`
- [x] Cabecera: `N versiones finales · M base/voz aparte`; TODAS selecciona solo lo visible
- [x] Evidencia sobre outputs/ reales: 8 finales (con-voz, variantes) vs 8 piezas (bases, voces), 0 cruces; lint 0; build `index-dFl4Y9JR.js` 361.17 kB; 75/75 tests backend (memory.md LXIX)

---

## Épica R — Que el prompt se cumpla (2026-10-06)

Auditoría contra la doc del modelo (`vendor/ACE-Step-1.5/docs/en/`:
`ace_step_musicians_guide.md` — Remix = cover con el audio de origen +
`audio_cover_strength` 0.3-0.5 para cambios grandes; captions de
entrenamiento en inglés ~312 caracteres (`examples/text2music/`); batch 2-4
(`API.md` default 2); `guidance_scale` 7.0 solo efectiva en base/SFT (el
motor fuerza 1.0 en turbo); `use_format=true` = el LM reescribe caption y
letra al formato de entrenamiento **sin** códigos de audio (no es
`thinking`, que sigue apagado por decisión 2026-10-03).

**Decisiones (2026-10-06, ask_user)**: REMIX IA = cover nativo (reestilar,
el motor oye la pista); batch 2; probar `use_format`; banco de pruebas =
casos de memory.md (hardstyle/gabber, «Animales muertos», A/B 59de2282).

### [R1] [P1] [especificada] BIBLIOTECA se actualiza sola (robusto)
**Como** usuario, **quiero** que la BIBLIOTECA se recargue siempre que
aparezca o desaparezca audio, **para** no pulsar ACTUALIZAR nunca.

**Raíz**: el tick actual (`App.jsx:80`) solo salta en la transición de cola
activa→vacía. Fallos reales: trabajos encadenados (A→B sin hueco) y
endpoints síncronos que crean MP3 sin job (`/audio/mix`, `/audio/remix` DSP,
`/audio/process`, `/audio/tempo`, `/audio/loop`, `/audio/crossfade`).

**Criterios de aceptación**
- [x] `/music/jobs` devuelve `library_version` = máx. mtime de `outputs/*.mp3`
- [x] App refresca BIBLIOTECA cuando `library_version` cambia (cubre encadenados, DSP síncrono y borrados)
- [x] La condición vieja (activa→vacía) se retira (la huella la subsume: todo fin con MP3 cambia la huella)

### [R2] [P1] [especificada] REMIX IA = cover nativo (reestilar)
**Como** usuario, **quiero** que el remix oiga mi pista y la reestile,
**para** que el resultado tenga algo que ver con lo que pedí.

**Raíz**: `_run_ai_remix` nunca mandó `task_type=cover` (el motor nunca oyó
el original) y `AiRemixRequest.cover_strength` (`main.py:172`) era un campo
muerto. La UI mostraba un slider de fuerza sin efecto.

**Criterios de aceptación**
- [x] El remix envía `task_type=cover` + `src_audio_path` + `audio_cover_strength` real (manual o `remix_cover_strength_for`)
- [x] Duración `None` → `-1` (la del tema) salvo petición explícita; BPM solo si se pide (si no, el del tema)
- [x] Retirado de la UI de remix el camino «base nueva + voz pegada» (un solo modo REESTILAR; `keep_vocals`, minutos y `solo_base` fuera; CREAR cubre generar desde cero)
- [x] El slider de fuerza hace lo que dice (0.3-0.5 cambios grandes, 0.7-0.9 sutiles, con la escala de la doc)

### [R3] [P1] [especificada] Obediencia del caption (batch + formato)
**Como** usuario, **quiero** que el prompt pese en el resultado, **para**
que las tiradas cumplan más a menudo.

**Criterios de aceptación**
- [x] `batch_size: 2` en config; las 2 variantes se descargan a BIBLIOTECA (el usuario elige, no la app) — también en CREAR (`_finalize_generation` guarda `-v2`)
- [x] Flag `use_format` en config (default **false** desde 2026-10-06: medido en vivo que con caption en español el LM inventa otra cosa —piano a 300 bpm— y el servidor SUSTITUYE caption y BPM; con caption inglés sí pule bien); override por petición para futuros A/B
- [ ] A/B real del banco: mismo prompt antes/después; si no mejora, se apaga y queda anotado

### [R4] [P2] [especificada] UI honesta sobre obediencia
**Como** usuario, **quiero** saber qué puede y qué no puede cada modo,
**para** no pedir imposibles.

**Criterios de aceptación**
- [x] CREAR avisa: «Rápido (turbo) no obedece detalles — para obediencia, REESTILAR (SFT)» (nota bajo GENERAR)
- [x] «VER LO QUE SE ENVÍA» enseña caption final + modelo + `use_format` + batch

### [R5] [P1] [especificada] Conservar la voz y cambiar la música
**Como** usuario, **quiero** quedarme con mi voz y ponerle música nueva
debajo, **para** que la canción siga siendo la mía con otro estilo.

**Decisiones (2026-10-06, a petición directa)**: segundo modo del remix IA
junto a REESTILAR (el cover no conserva timbres: reescribe la voz). La base
nueva la genera el SFT (obedece el prompt) al tempo medido del tema salvo
petición, y dura lo que el tema salvo petición. La base sale siempre
instrumental (la voz la pone el original); la letra no se usa en este modo.

**Criterios de aceptación**
- [x] `mode: reestilar | voz` en `AiRemixRequest` (otro valor → 422)
- [x] Modo voz: separa la voz (demucs), genera base SFT instrumental al tempo del tema, la cuadra (`plan_vocal_arrangement`, reserva `mix_tracks`) y mezcla
- [x] Se guardan mezcla(s) + base(s) + voz; el usuario elige en BIBLIOTECA (las 2 variantes del batch se mezclan las 2)
- [x] La mesa ofrece VOZ + BASE NUEVA sin letra y sin fuerza (no aplican)
- [x] Piloto real 2026-10-06 (job `15d06c4b`): «Animales muertos» + hardcore 4x4 doble bombo → 2 mezclas 81.4 s, tempo 166.7 bpm (origen 166.25). Oído del usuario pendiente.
- [x] MINUTOS en modo voz (restaurado 2026-10-07, se perdió en el refactor): vacío = dura el tema; elegido (1…`max_duration_seconds` de config) → `duration_seconds` al backend, que pide la base más larga. Aviso honesto: la voz se reparte en trozos, no se estira.

### [R6] [P1] [en código] Glosario documental (lo que el fabricante avala)
**Como** usuario, **quiero** que mis palabras se traduzcan con el vocabulario
del fabricante, **para** que el motor las reconozca.

**Medición 2026-10-06**: guía oficial de captions (5 capas: género,
instrumentos, mood, estilo vocal, tempo feel — cubríamos 3); 400 textos
minados (pop 28, rock 34, hip-hop 17, trap 16…; hardstyle/gabber 0);
encoder Qwen3-Embedding (sin vocabulario cerrado); `use_format=false`
por defecto (el LM inventa en español, pule bien en inglés).

**Criterios de aceptación**
- [x] Catálogo en `backend/style_catalog.json` (NO HARDCODE; test de esquema)
- [x] Capa documental: 17 modificadores nuevos (estilo vocal ×7, tempo feel ×4, épica ×4, instrumentos ×3) con la redacción del fabricante
- [x] 6 agujeros de género cerrados (hardcore, tecno, rap con regex, trap, dembow, chill) + detalles sin género + idempotencia real
- [x] Glosa ES→EN ampliada (susurrada, falsete, lenta, himno, riffs…) con tests
- [x] Auditoría UI 2026-10-06 [R7]: cada chip/mood/género de CREAR, asistente, SUBIR y remix dispara estilo o modificador (test `test_variantes_del_remix_disparan_regla` + `test_moods_de_crear_caen_en_regla`); lo-fi gana a hip hop; tags de voz con vocabulario minado (200 captions), sin coletilla inventada

### [R7] [P0] [verificada] SUBIR no se queda en negro + vocabulario de la UI que el motor reconoce
**Como** usuario, **quiero** pulsar REMIX en SUBIR sin que la pantalla se ponga
en negro, y que cada chip/acción ofrezca palabras que el motor entiende,
**para** no pedir imposibles.

**Raíz del negro (2026-10-06)**: `RemixActions.jsx` perdió su cabecera de
imports en un refactor (sin `React/useState/api/lucide…` → `ReferenceError` al
montar → toda la pestaña SUBIR en negro). Además el menú se montaba siempre
(`open &&` + `box ?? oculto`: `box` nulo reventaba el `style`) y ofrecía
LEGO/EXTRACT/COMPLETE, que exigen `acestep-v15-base` (no instalado).

**Auditoría de vocabulario (2026-10-06, 200 captions del fabricante minados)**:
5 variantes del remix + moods (Melancólico, Luminoso) + textos de género no
disparaban ninguna regla; 16 tags de voz cantada no existían en su
vocabulario (`husky`, `sung vocals`, `brooding`, `happy`… con 0 apariciones).

**Criterios de aceptación**
- [x] Imports restaurados + menú solo cuando `open && box` + LEGO/EXTRACT/COMPLETE ocultos (exigen modelo base)
- [x] 10 VARIANTS reescritas con palabras del catálogo; géneros/moods de CREAR y asistente alineados
- [x] Tags de voz con frecuencias minadas (`female/male vocal`, `whispered`, `rapped`, `choir…ad-libs`); Melancólico + Luminoso en catálogo
- [x] Panel compacto (2026-10-07, «chips falsos y tamaño grande»): los chips viven en UN desplegable AÑADIR (direcciones + catálogo, cada uno con su texto en el tooltip), el consejo es plegable (CONSEJO) y la glosa cabe en una línea; el estilo detectado va inline
- [x] AÑADIR sin filtros (2026-10-07, «has vuelto a eliminar los chips… cuando los chips son reales del modelo son geniales»): se revierten los tres filtros que escondían chips (gate por prompt vacío, los 7 de voz en VOZ + BASE NUEVA y los 7 de voz en CREAR instrumental). El dato `voice` sigue en el catálogo y solo se filtra si el usuario lo pide (memory.md LXXIV)
- [x] Ofertas realistas para el modelo (2026-10-07, «que sea realista lo que me ofrece la app con lo que entiende el modelo»): toda la prosa de chips, captions de estilo y glosa sale del vocabulario del propio modelo (400 captions del fabricante para prosa + `genres_vocab.txt` para géneros); 9 chips, 15 captions y 6 términos de glosa llevaban vocabulario inventado y quedan en 0. Regla hecha test en `backend/test_realism.py`
- [x] Chips de CREAR más pequeños (2026-10-07, «los chips de CREAR deben ser más pequeños»): `h-3.5 px-1.5 text-[8px] leading-none` (antes `h-4 px-2 text-[9px]`) y huecos `gap-1.5`, para que no compitan con el prompt
- [x] Glosario del modelo (2026-10-07, «glosario directo del modelo de estilos y subestilos que entiende el modelo» + «combinar estilos como techno hardcore»): botón GLOSARIO en CREAR, VERSIÓN·CAMBIAR EL ESTILO, TRAMO, REESTILAR, VOZ + BASE y OTRA VERSIÓN (todas las opciones con prompt). Pinta los 29 estilos de Musicia y busca en `genres_vocab.txt` (178.572 entradas), que es la whitelist con la que el motor restringe el campo `genres` (`acestep/constrained_logits_processor.py`); COMBINAR con dos elegidos devuelve solo combinaciones que existen en ese archivo (techno + hardcore → «hardcore techno»; si no existe, no se ofrece). Endpoints `/music/genre_glossary` y `/music/genre_glossary/combine`, regla NO FAKE testada en `backend/test_genre_glossary.py` (todo resultado es una línea literal del archivo)
- [x] Ver y enviar el mismo idioma (2026-10-07, «al revés, los chips deberían ser en inglés también»): los chips muestran y añaden `clause`, la cláusula en inglés literal del catálogo, en CREAR (botones), remix y OTRA VERSIÓN (desplegable AÑADIR); el glosario añade la caption en inglés del estilo. `analyze_prompt` expone `clause` en cada chip; control en `test_prompt_style.test_chip_lleva_su_clausula_en_ingles`
- [x] Estado ELEGIDO (2026-10-07, «que se vea como elegido»): en el glosario, lo que ya está en tu frase se marca ELEGIDO y volver a pulsarlo lo quita (`removeTexto`); el componente recibe `prompt`/`setPrompt`, igual que `VariantChips`
- [x] Variantes en todos los prompts (2026-10-07, «presentes en todos los prompts»): `frontend/src/variants.js` + `components/VariantChips.jsx` se pintan en CREAR, VERSIÓN/TRAMO/REESTILAR/VOZ y OTRA VERSIÓN (antes solo en esta, en español). Los 10 textos están en inglés y pasan `test_realism.test_variantes_del_modelo`: 10/10 en el corpus y 10/10 disparando estilo o modificador. Correcciones del minado: `calm` y `few` no estaban en el corpus; `powerful` disparaba **Voz potente** y `double bass` **Doble bombo**
- [x] AÑADIR de CREAR en lista (2026-10-07, «los chips deben ser pequeños o en una lista»): CREAR usa el mismo `SelectBox AÑADIR` de remix (los botones en línea con cláusulas inglesas largas desbordaban la fila); GLOSARIO al lado y VARIANTES debajo. `memory.md LXXVII`
- [x] El glosario añade el género, no la definición (2026-10-07, «yo solo quiero el género»): cada estilo de Musicia muestra y añade `genre` (una línea literal de `genres_vocab.txt`), nunca la caption completa; el buscador filtra también el catálogo (antes solo se veía con consulta vacía). `catalog_styles` pasa de 26/29 a **28/29** al comprobar la frase completa en vez de palabra a palabra (`hard techno`, `hard house`); solo `uptempo hard dance` cae a su nombre. `memory.md LXXVIII`
- [x] AÑADIR nunca despliega vacío sin explicación (2026-10-07, «en AÑADIR no despliega nada»): si `styleOptions` falla pinta `AÑADIR · SIN DATOS DEL MOTOR` y si no hay sugerencias, `SIN SUGERENCIAS`; el desplegable solo se pinta con opciones reales (19 con prompt vacío, 21 con «techno oscuro en 4x4», 116 ms)
- [x] AÑADIR en español, añade en inglés (2026-10-07, «en el desplegable en español, más sintético, pero que al seleccionar se ponga en inglés»): la opción muestra la etiqueta corta del catálogo (`A toda velocidad`) y el tooltip `Se añade: «a fast tempo with relentless, driving energy»`; al pulsar se añade la cláusula inglesa, que es lo que viaja. Los tres AÑADIR (CREAR, remix, otra versión). `memory.md LXXIX`
- [x] Evidencia: 91/91 unittest backend, 9/9 glosa, lint 0, build `index-B0ijN-oY.js` 367.52 kB (memory.md LXXVI-LXXIX)

### [R8] [P1] [implementada] Géneros, chips y opciones al 100% con el modelo en toda la app
**Como** usuario, **quiero** que los selectores de género, chips y demás opciones de toda la app ofrezcan exactamente lo que el modelo ACE-Step 1.5 entiende, **para** tener disponible en la UI todo el catálogo musical real sin opciones inventadas ni recortes artificiales.

**Decisiones del usuario (2026-10-08, ask_user)**:
- El selector de GÉNERO en CREAR se amplía a los **29 estilos oficiales** del catálogo (`style_catalog.json`), en lugar de los 9 antiguos.
- Al seleccionar un género en CREAR, se añade el nombre directo al prompt para que el backend le componga la caption oficial en inglés que el modelo espera.
- Limpieza de términos fuera de vocabulario en `vocal.js` (`grit` y `belting` fuera; vocabulario 100% verificado contra el corpus).
- Sincronización del asistente `QualityWizard.jsx` con el catálogo real del modelo.

**Criterios de aceptación**
- [ ] Selector GÉNERO de `Composer.jsx` con los 29 estilos oficiales del modelo, con etiquetas legibles en español y orden coherente.
- [ ] Al seleccionar género, añade el término al prompt y el backend compone la caption oficial en inglés (`style_caption`).
- [ ] Descriptores de voz en `frontend/src/vocal.js` 100% verificados contra el corpus de entrenamiento del modelo (sin palabras ausentes como `grit`).
- [ ] `backend/test_realism.py` ampliado para auditar también `vocal.js`.
- [ ] `QualityWizard.jsx` alineado con los géneros del modelo.
- [ ] Tests de backend pasan (92/92), tests de frontend/glosa pasan, ESLint 0 advertencias, build de Vite exitoso.

