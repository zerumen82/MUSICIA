# 02 · Requisitos — Historias de usuario

Formato: **[ID] [prioridad] [estado]**. Estados: `propuesta | especificada |
en-curso | implementada | verificada`. Una historia solo pasa a `verificada`
con evidencia en `memory.md`.

Prioridad: `P0` = esenciales del producto · `P1` = importantes · `P2` = mejoras.

Estado vigente revisado 2026-10-13: las decisiones fechadas describen su contexto histórico. La decisión posterior SFT en toda la app y el cierre correctivo R9/R10 del final de este archivo sustituyen sus condiciones antiguas. Las comprobaciones históricas siguen siendo evidencia de su recorrido; no acreditan automáticamente una nueva interfaz ni aprobación musical.

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

### [A2] [P0] [sustituida por BIBLIOTECA] Historial de canciones
- [x] Cada generación se guarda (título, duración, fecha)
- [x] Clic en el historial → reproduce
- [x] Vaciar historial
- [x] Persiste entre sesiones (localStorage, máx. 30)

Este historial de SESIÓN era el comportamiento verificado inicial. La lista duplicada se retiró posteriormente por decisión del usuario; la biblioteca de archivos/fichas y Q1 conservan el historial vigente. No remontar la SESIÓN por estos criterios históricos.

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

### [A4] [P2] [implementada] Parámetros musicales en CREAR
- [x] BPM, tonalidad (key_scale) y semilla en `Composer.jsx` (chips, tono, campo SEMILLA)
- [x] Compás AUTO/4/4/3/4/6/8 expuesto en CREAR y transmitido como `time_signature` (memory XLIII); el cierre correctivo comprueba además conflictos con el texto.

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

Estas decisiones corresponden al 2026-10-02. Q2 autorizó después cancelación mediante reinicio real del proceso, y M1/decisión LXXXVII establecieron SFT en toda la app. Cover/repaint siguen soportados; tareas del modelo base no se habilitan.
- Si el mismo nombre está en biblioteca y en subidas, mezcla usa el de la biblioteca.

**Criterios de aceptación**
- [x] El menú de remix elige la acción. HACER la lanza. Un prompt vacío no llama al motor.
- [x] Versión manda `task_type=cover`, la ruta del audio y la fuerza de `generation.cover_strength` (0,6 si no se cambia).
- [x] Tramo manda `repaint`, inicio/fin en segundos, y fin vacío vale -1 (hasta el final).
- [x] Sin duración pedida, cover y repaint envían `audio_duration=-1` para que el motor use la del origen.
- [x] `lego`, `extract` y `complete` se rechazan antes de crear un job.
- [x] Cover real con MP3 y duración positiva: sondas full de XCIX y artefactos revalidados en CI; aprobación musical separada.
- [x] Repaint real con audio verificado: sonda region de XCIX; conservación de forma fuera del intervalo con normalización declarada.
- [x] Ajustar sigue siendo el panel DSP (tempo, tono, fundido, recorte).
- [x] `POST /audio/separate` responde al momento con `job_id`. `GET /audio/separate/status` sigue diciendo si demucs está instalado.
- [x] **`GET /audio/separate/status` no congela la API** (2026-10-08, «acabo de errar la api creo»; `memory.md LXXXIV`): el estado se calcula en `asyncio.to_thread` y se cachea una vez por proceso. Medido: 1ª llamada 2,790 s (fría), 2ª 0,091 s; con 6 llamadas en paralelo, `/music/style_options` responde 200 en 0,0077 s. Antes clavaba el hilo de eventos ~5 s y en CREAR el AÑADIR salía `SIN DATOS DEL MOTOR`. Regresión cubierta por `backend/test_separator_status.py` (5 tests).
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
- [x] Solo modelos locales permitidos por configuración; hoy SFT por decisión LXXXVII, sin descarga automática de base/XL. La restricción exclusiva a turbo era histórica.
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
- [x] Cover real con origen y archivo válido registrada en XCIX; la verificación de la nueva UI corresponde al cierre correctivo R9/R10.

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
- Capacidad contrastada del checkpoint instalado: SFT admite `text2music`, `cover`, `repaint`. `extract`, `lego` y `complete` no se habilitan por el listado de tareas del servidor: requieren checkpoint compatible del modelo base (investigación de R9/XCV).
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

La comprobación ida/vuelta fue histórica. Desde la decisión del usuario «siempre en toda la app sft» (memory LXXXVII), CREAR también usa SFT; el perfil vigente conserva 50 pasos, guidance 9 y batch 2.
- [x] La VRAM y el modelo se enseñan en el lateral (`App.jsx`: modelo cargado,
      VRAM libre y modelo de remix, refrescados cada 10 s con `/music/models`)
- [ ] **El oído del usuario**: el próximo remix con el sft dicta si la
      obediencia mejora de verdad. La fuerza 0,1/0,5 y la glosa también se
      juzgan oyendo.

### [M2] [P1] [implementada 2026-10-05, falta remix real de subida] El remix usa la pista que elegí
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
- [x] El origen viaja con la petición (`source_kind: upload | output`) y el
      backend lo respeta; sin él, el nombre se resuelve como hoy
      (hecho: campo en los 9 modelos pydantic; tests `test_remix_logic`
      16/16: orden por kind, recurso cruzado en ambos sentidos, 400 y 404)
- [x] La biblioteca manda `output` y las subidas mandan `upload`, en los
      caminos de remix/mezcla que usan un nombre
      (hecho: `sourceKind` en Library/Uploads → `RemixActions`/`RemixIAPanel`;
      24 usos de `source_kind` en `main.py`; `/audio/remix_prompt` y
      `/audio/remix` unificados en `_find_audio`, entrada XLI)
- [x] Regresión: una mezcla en `outputs/` con el nombre de una subida no puede
      ganar al remix de esa subida (tests `FindAudioTest`: upload→SUBIDA,
      output→MEZCLA, homónimos cruzados, kind inválido→400, ausente→404)
- [ ] Un remix real de la subida, con la duración de la fuente correcta
      (pendiente de ejecutar con GPU y una subida homónima)

### [M3] [P1] [implementada 2026-10-08] Declarar si el resultado obedeció
**Como** usuario, **quiero** ver si lo que salió se parezca a lo que pedí,
**para** no creer que un 130 bpm era un 170.

- [x] Cableado manual 2026-10-06: botón TEMPO en el menú ACCIONES de
      BIBLIOTECA mide el tempo real (`GET /audio/groove`, DSP local, con
      `source_kind=output`) y, si la ficha trae BPM pedido con diferencia
      ≥ tolerancia, enseña `PEDÍA 180 · SALE 170`. Sin medición automática
      por fila (N análisis seguidos); la medición manual sigue disponible
      para pistas antiguas.
- [x] Tras generar, `detect_groove` mide el BPM y la confianza del MP3
      (2026-10-08: `_measure_bpm` en `_finalize_generation`, cover de
      `_run_ai_remix` y mezcla final de conservar-voz; en hilo aparte;
      fallo de medición → sin campos, nunca se inventa; evento
      «Tempo medido: X bpm» en la cola del job).
- [x] La ficha guarda `bpm` (pedido) y `bpm_measured`/`bpm_confidence`
      (medidos); `_carry_ficha` no arrastra la medición del origen salvo
      que traiga una fresca.
- [x] BIBLIOTECA lo enseña solo: `PEDÍA 170 · SALIÓ 130 BPM`, solo si hay
      ambos valores y la diferencia ≥ `generation.bpm_display_tolerance`
      (config, 3). Sin medición, la línea no existe.
- [x] Nunca se maquilla: si no se puede medir, no se enseña nada
      (`_measure_bpm` devuelve None → la ficha no lleva el campo; test
      `FichaMedidaTest`).
- [x] Verificación end-to-end con una generación real nueva (2026-10-08:
      job `bd8bf24e`, «prueba m3 tempo» pedido a 150 bpm → evento
      «Tempo medido: 149.8 bpm (seguridad 78%)», ficha con `bpm: 150` y
      `bpm_measured: 149.8`, `/music/library` expone ambos campos)

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
tarda minutos). Desde el 2026-10-16 la cola de CREAR no se muestra: PARAR está en el progreso de la generación en curso. La pista terminada está en BIBLIOTECA.

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
- [x] CREAR muestra el modelo configurado y propone comparar variantes; la nota antigua turbo/SFT se retiró al elegir SFT en toda la app. No certifica obediencia artística.
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
- [x] Selector GÉNERO de `Composer.jsx` con los 29 estilos oficiales del modelo, con etiquetas legibles en español y orden coherente (`frontend/src/genres.js`: 29 `id` = 29 `genre`).
- [x] Al seleccionar género, añade el término al prompt (`item.genre`, línea literal; nunca el `id` en español) y el backend compone la caption oficial en inglés (`style_caption`, vía MEJORAR).
- [x] Descriptores de voz en `frontend/src/vocal.js` 100% verificados contra el corpus de entrenamiento del modelo (sin palabras ausentes como `grit`).
- [x] `backend/test_realism.py` ampliado para auditar también `vocal.js` (`test_vocal_tags_use_only_vocabulary_the_model_uses`).
- [x] `QualityWizard.jsx` alineado con los géneros del modelo (lee `CATALOG_GENRES`; su `prompt` monta `g.genre` + `words`/`extra` que la glosa traduce al inglés).
- [x] Tests de backend pasan, tests de frontend/glosa pasan, ESLint 0 advertencias, build de Vite exitoso.

**2ª auditoría (2026-10-08, «en toda la app el glosario y los chips en unos sitios funcionan y en otros no» + «debes eliminar los términos que no entiende el modelo»; alcance Completo P0–P4)** — `memory.md LXXXIII`:
- [x] Ver ≠ enviar en remix: `RemixActions.jsx` mostraba `ENVÍA: glossPrompt(...)` pero mandaba `prompt.trim()`; hoy los 4 envíos (versión/tramo, reestilar, voz, MEJORAR) glosan con `promptEnviado()`. SUBIR/BIBLIOTECA ya glosaban en el padre.
- [x] `AÑADIR` nunca despliega vacío sin explicación en remix y OTRA VERSIÓN (`SIN DATOS DEL MOTOR` / `SIN SUGERENCIAS`), mismo criterio que CREAR.
- [x] Los 5 `genre` de `genres.js` que no eran línea literal pasan a `gabber`, `hard dance`, `hard house`, `folk`, `orchestral`; control en `test_realism.test_genres_js_only_offers_genres_the_model_can_write` y `test_genres_js_agrees_with_the_backend_catalog` (29 estilos ⇒ mismo género en selector y glosario).
- [x] `catalog_styles()` nunca devuelve `genre: None`: si ninguna clave es línea literal se usa la subfrase más larga del nombre que sí lo es (`uptempo hard dance` → `hard dance`); test `test_genre_glossary.test_ningun_estilo_se_queda_sin_genre`.
- [x] Glosa completa de todos los textos fijos de la UI: `evoluci[oó]n`, `cálido→warm`, `relajado→relaxed`, `textura→texture`, `clara→clear`, `íntimo→intimate`, `banda→full band`, `hard bounce→hard house`; control en `prompt_gloss.test.js` (11 tests) sobre moods de `Composer.jsx` y `words`/`extra` de `QualityWizard.jsx`.
- [x] Bases del prompt de remix (`/audio/remix_prompt`) en inglés y solo con palabras de los captions del modelo, como datos en `prompt_enhancer.py` (`REMIX_BASES` y asociados); el `basis` que se explica al usuario sigue en español. Test `test_realism.test_las_bases_del_remix_son_del_vocabulario_del_modelo`.
- [x] Evidencia: **117/117 backend** + **11/11 glosa** + ESLint 0 + build `index-BFgd1hNJ.js` + API reiniciada con endpoints en vivo (`genre_glossary`, `style_options`, `remix_prompt` con MP3 real). Sin clic en ventana (no hay browser tooling): TESTER PASS con ese límite declarado.

# Correcciones autorizadas 2026-10-12 — B1/B2 (diagnóstico XCIII)

El usuario solicita «hazlo» tras la revisión de memoria/logs y añade que los estilos no parecen lo pedido. B1/B2 corrigen los contratos existentes de biblioteca e historial; el tratamiento musical se diagnostica y se acuerda con el usuario antes de cambiar el diseño.

- **B1 — Borrado con archivo ocupado**: un MP3 ocupado por otro proceso devuelve un conflicto HTTP con explicación real en el borrado individual, sin excepción ASGI/500 ni éxito falso. El borrado múltiple continúa con los archivos disponibles y declara los ocupados por separado; conserva sus fichas y no anuncia que los borró. El reproductor de Musicia libera el archivo seleccionado antes de solicitar su borrado. Verificar con un bloqueo Windows real sobre un MP3 de prueba y una petición real a la API, además de las pruebas de regresión.
- **B2 — Historial del modo voz**: todo resultado terminal de remix (incluido el retorno anticipado del modo voz) se persiste por el camino común. Verificar que una ejecución real de voz termina y que su job existe con estado final en `job_history.json`; cubrir el retorno anticipado con una regresión automatizada. No cambiar SFT, batch ni duraciones elegidas.
- **Regresión encontrada durante la prueba real B2**: un nombre que alcanza `generation.max_slug_chars` no puede perder el ordinal de desambiguación al añadir ` (2)`, ` (3)`; debe reservar sitio dentro de ese límite, sin pisar archivos y sin repetir el mismo candidato hasta el error 409. El máximo de intentos se declara en configuración. Verificar nombres largos con archivos reales temporales y repetir el remix de dos variantes que falló.
- **Estilos/conservación**: contrastar el prompt original, las reglas del catálogo y el payload al motor. No presentar género sustituto como equivalente demostrado ni éxito técnico como fidelidad musical. La corrección del envío está verificada; la interpretación y transformación integral de la canción pertenece a R9, sin convertir ejemplos de voz/guitarra en alcance separado.
- **Corrección de fidelidad existente (recordatorio del usuario: NO HARDCODING y lenguaje del modelo)**: conservar los géneros literales pedidos y añadir descripciones sin introducir géneros vecinos. Las reglas lingüísticas y restricciones viven como datos del catálogo. Coincidencias negadas o contenidas en una frase más específica no añaden estilos/detalles positivos; una mezcla explícita con ocurrencias independientes sigue funcionando. La glosa no convierte frenchcore en hard dance ni jungle en breakbeat. Las descripciones que contradigan una exclusión explícita del usuario se omiten; no se inventa un reemplazo. Géneros añadidos y prosa siguen verificados con vocabulario/captions locales. La conservación específica de guitarra original queda pendiente de acordar un tratamiento posible con los modelos ya instalados.
- **Plan de verificación**: tests de regresión backend/frontend, lint y build, revisión independiente y verificación real con evidencia en `memory.md`. No instalar dependencias/modelos ni modificar programas ajenos.

**Estado de las correcciones**: PASS técnico del tester y APPROVE del reviewer, evidencia real en `memory.md XCIV`. B1/B2 y colisiones de nombres verificadas; cumplimiento musical de oído no verificado.

## [R10] Fidelidad del prompt en CREAR y REMIX — corrección autorizada

Autorización 2026-10-12: corregir el prompting e implementar R9 con autodetección de audio electrónico. Se retiran las recetas automáticas y las glosas parciales que desvirtúan el contexto. Sugerencias voluntarias conservadas; una adaptación semántica no verificada no se presenta como comprensión universal. La fuente se clasifica mediante análisis real, con desconocido/mixto y revisión manual disponibles; no se traduce la clasificación en órdenes musicales nuevas.

Petición 2026-10-12: antes de decidir el plan, revisar las cosas que la app añade sin pedirlas; el usuario aclara expresamente «no solo en remix, al crear también». Rige para todos los recorridos de generación, no para un ejemplo de instrumento concreto.

**Estado real**: las correcciones de XCIV evitaron determinadas sustituciones de género y coincidencias, pero no eliminaron la expansión musical automática. Ejecución local de `style_caption` documentada en `logs/prompt-audit-20261012.json`: «batería suave al fondo» añade batería protagonista; «bajo potente, sin voz» enviado directamente al backend añade voz principal potente y luego instrumental. En el recorrido con glosa de la UI este segundo caso sí filtra la voz potente: no confundir ambas entradas. El tester ejecutó Node y Python para el recorrido completo (`logs/prompt-audit-tester-20261012.json`): los cuatro previews cambian al pasar por backend y la batería al fondo sigue convertida en protagonista. CREAR y REMIX llaman esta función después de la glosa que muestra la UI. El vocabulario del modelo no demuestra equivalencia semántica ni aprobación del usuario.

**Contrato autorizado de R10** (la propuesta original fue aprobada en XCVIII; los criterios abiertos se completan en el cierre correctivo CII):
- Mantener texto original, intención y restricciones; adaptar al idioma/formato del motor sin introducir instrumentos, protagonismo, carácter, patrones rítmicos o estilos adicionales. La glosa de palabras actual no equivale a interpretar el prompt completo.
- Las sugerencias creativas son optativas y revisables; una selección explícita en la UI forma parte de la petición. Detectar un género o un adjetivo no autoriza a insertar una receta musical.
- Mostrar el prompt y los parámetros efectivos del motor en ambos modos, con procedencia de texto, selección y configuración; el servidor no añade otra expansión oculta después de la vista previa.
- Resolver contradicciones entre texto y controles de voz/BPM/estructura antes de generar; distinguir omisión de letra, deseo de instrumental y conservación de la voz original. No cambiar los valores SFT/batch/thinking/use_format aprobados para tratar de compensar el fallo.
- No vender regex, catálogos ni traducción como un planificador semántico universal. La vía concreta de adaptación fiel del idioma sigue pendiente de acordar y validar con el modelo local, sin instalar dependencias o modelos.
- Verificar el envío real de CREAR y REMIX, casos de contexto/negación y preview frente a payload; evaluar audio A/B por separado. Un MP3 válido o un término presente en el corpus no certifican cumplimiento artístico.

**Cerrado 2026-10-12 (nocturna)**: la corrección ya estaba en el código desde XCVIII (`style_caption` identidad, `glossPrompt` identidad, MEJORAR como borrador fiel con BPM explícito declarado) y esta sesión la **verificó con auditoría viva** en todas las rutas (CREAR/MEJORAR/remix/otra versión): `logs/prompt-fidelity-audit-20261012-213935.json` PASS, test de payload `test_payload_de_crear_conserva_el_prompt_literal`, suite 164/164. Contrato cumplido: texto literal, sugerencias optativas visibles (chips/glosario añaden solo texto mostrado), preview = payload, procedencia y conflictos (BPM) declarados. La obediencia artística final la decide el oído del usuario.

El cierre anterior del 2026-10-12 es una declaración histórica limitada por la auditoría CI: no probaba todos los conflictos ni preview React/envío real. R10 queda en corrección hasta el nuevo PASS integral del tester y APPROVE del reviewer; no basta con cambiar el estado escrito.

## [R9] REMIX integral y fidelidad general del prompt — implementada, cierre técnico reabierto por auditoría CI

El usuario aclara que conservar voz/guitarra era solo un ejemplo; quiere un remix real más versátil respecto al modelo y la calidad de las creaciones. Se retira la propuesta de convertir ese ejemplo en una función específica. No se aprobó ninguna descarga.

- Usar el audio original como material del remix y distinguir qué se conserva, transforma o rehace según la intención completa del prompt.
- Contrastar cada operación con capacidades efectivas del modelo local; no ofrecer éxito falso para operaciones incompatibles.
- Prompts y parámetros en lenguaje/contratos del modelo, sin sustituir géneros ni añadir decisiones musicales ajenas al usuario; valores como configuración/datos.
- Calidad verificable mediante archivos válidos, revisión de defectos técnicos, trazabilidad de petición/operación/resultado y escucha comparada del usuario.
- Criterios de aceptación y límites en `spec/06-REMIX-INTEGRAL.md` (aprobado por el usuario). **Estado 2026-10-12**: implementada; tester PASS con 8 sondas reales (cover/repaint/grupos/dsp/análisis/recuperación sobre GPU) y reviewer APPROVE; hallazgos corregidos (hashlib en Python 3.10, declaración de normalización del repaint). Evidencia `memory.md` XCIX. Falta el veredicto de oído del usuario.

## Cierre correctivo R9/R10 — autorizado 2026-10-13, en curso

El usuario solicita «HAZLO» tras la auditoría CI. Autoriza completar sus criterios técnicos pendientes y actualizar los Markdown; no supone autorización para instalar dependencias/modelos ni cambiar SFT/50/9/batch2/thinking/use_format. El cierre anterior queda limitado por los hallazgos de `logs/auditoria-plan-20261013.md` hasta obtener nuevo PASS + APPROVE.

- [ ] Comparador original/variantes con posición e intervalo compartidos, conmutación A/B y teclado; nunca reproducción simultánea inadvertida.
- [ ] Selección regional única: onda, campos numéricos, remonte del ámbito y payload coinciden; límites y normalización/modo agresivo visibles.
- [ ] Conflictos explícitos de BPM/voz/estructura validados antes de llamar al motor, sin reescribir la intención; error que permite corregir texto o selección. No presentar esta comprobación como comprensión semántica universal.
- [ ] Vista previa calculada por el backend con los mismos contratos/defaults que la ejecución; mostrar parámetros efectivos registrados, procedencia y diferencias de operaciones deterministas.
- [ ] Acceso equivalente al flujo de voz original + base nueva, incluidos minutos; herramientas de prompt (glosario, AÑADIR, variantes y mejorador optativo) y controles efectivos también en acompañamiento nuevo.
- [ ] Procedencia de clasificación manual/análisis persistida y semillas reales de variantes trazables, sin inventar valores desconocidos.
- [ ] Sondas reales de UI SUBIR/BIBLIOTECA en 1400×900 y 1080×700, preview/envío, comparación/selección/solo/teclado, cancelación y recuperación; conservar evidencia y declarar límites musicales.
- [ ] Markdown vigentes sincronizados, historia preservada en memory; lint/build/regresión verdes, tester PASS y reviewer APPROVE de archivos completos.

### Corrección UI y bloqueo de conversión — petición 2026-10-13

Corrección del recorrido existente, autorizada por la petición actual y CII; conserva el desplegable QUÉ HACER solicitado en CXII y el perfil SFT/50/9/batch2, sin instalaciones.

- [x] La acción elegida muestra su formulario y opera sobre la fuente seleccionada; errores reales visibles y controles bloqueados durante una operación incompatible. Ventana servida y probada en 1400×900 y 1080×700, con capturas.
- [x] La fase Decoding se muestra como conversión sin presentar el 0,8 fijo del motor como progreso medido. No confundir carga/offload/encode VAE con decode. Comprobado en DOM/API durante una ejecución real, además del contrato automatizado.
- [x] El fallback del VAE a CPU usa la política de dtype CPU del motor y restaura dispositivo y dtype originales incluso si falla; corrección local reproducible del vendor ignorado en Git.
- [x] El recorrido afectado llega a estado terminal y produce dos variantes con tamaño y duración positivos, sin cambiar el perfil aprobado. Lint/build/regresión, PASS del tester y APPROVE del reviewer con evidencia en memory CXVII.

**Cerradas estas dos correcciones, 2026-10-13**: remix de grupos de 66,952 s, fallback CPU con 0,15 GB libres, dos MP3 válidos y finitos; CREAR tras actualizar solo API, dos MP3 de 30 s, preview=ejecución y conversión real sin porcentaje en DOM/API. La PNG de conversión de CREAR muestra el contexto del viewport, no la frase situada debajo; no usarla como evidencia fotográfica de esa frase. Los criterios abiertos del cierre integral R9/R10 anterior permanecen abiertos y la escucha artística corresponde al usuario.

### Auditoría funcional y visual de UI — petición 2026-10-13

El usuario solicita revisar que las funciones sean correctas y se vean bien. Dentro del cierre correctivo CII se corrigen defectos de la interfaz existente, conservando sus valores, tokens, formularios y perfil musical. El usuario autoriza explícitamente «Mostrar progreso y resultado antes de la cola (recomendado)»; el resto de decisiones de reorganización visual requiere acuerdo aparte.

- [ ] La cascada CSS respeta las utilidades de espaciado y tamaño ya declaradas: `px`/`py` de navegación, cabecera y contenido; botones `h-8`/`h-7`. Verificar estilos calculados y capturas antes/después en las dimensiones de Electron, sin desborde horizontal.
- [ ] El reloj de CREAR muestra minutos y dos dígitos enteros de segundos, sin fracciones, incluso cuando el sondeo devuelve `elapsed_seconds` decimal.
- [ ] En CREAR, el progreso aparece después del formulario. El 2026-10-16 el usuario quita la cola de trabajos y el reproductor del resultado: la pista terminada se escucha en BIBLIOTECA. Conservar el preview técnico como desplegable y los controles de generación.
- [x] La cola de CREAR no lista trabajos antiguos. Esos MP3, si existen, están en BIBLIOTECA. Decisión del usuario el 2026-10-16.
- [ ] Las subidas se actualizan en SUBIR y MEZCLA sin pulsar ACTUALIZAR. Las altas, borrados y renombrados invalidan las listas afectadas, incluso cuando cambia un fichero antiguo.
- [ ] MEZCLA distingue cada pista por origen y nombre; una mezcla alineada requiere el plan vigente de la pareja seleccionada, y durante su ejecución los controles de esa pareja quedan bloqueados.
- [ ] La subida se puede iniciar con teclado y los reproductores de la aplicación evitan reproducción simultánea inadvertida.
- [ ] Archivos completos revisados; lint/build verdes y evidencia independiente del tester y reviewer registrada en memory antes de declarar el cierre de esta auditoría.

## [R11] BPM por pistas, revisión de separación y remix más largo — propuesta 2026-10-14

**Corrección de entrega autorizada, 2026-10-15**: tras la auditoría CXLIX el usuario exige «PUES ARREGLALO». Completar el lote interrumpido usando sus dos WAV descargados y metadatos reales del motor, con la petición de 240 s intacta. El posprocesado y la publicación siguen el recorrido productivo existente; se conserva un recibo verificable del lote descargado para recuperarlo explícitamente sin otra inferencia. Se validan identidad de fuente/petición/tarea, parámetros, huellas, cantidad y duración de archivos; se rechazan material alterado, cancelaciones y trabajos ya publicados. La reparación operativa se ejecuta con los servicios detenidos y copia previa del historial, sin pisar trabajos ajenos. SALIR sigue apagando los servicios; Q1 sigue marcando los trabajos interrumpidos y no se reanudan automáticamente. Verificar dos MP3 finales de 240 s, sus fichas, semillas reales y exposición en biblioteca/API, regresión, lint/build, PASS del tester y APPROVE del reviewer antes de cerrar esta corrección. No cierra B6/B7 ni certifica el estilo musical.

**Corrección de entrega verificada, 2026-10-15 (memory CL)**: el trabajo `50423b230ae1438faa5d79d0ac36f19d` terminó sin otra inferencia y publicó `Animales muertos-remix (3).mp3` y `(4).mp3`, ambas de 240 s, con semillas reales 3813600975/784866797 y fichas fieles a la petición original. Fuente, archivos anteriores y otros trabajos conservados. ffprobe/pydub, biblioteca/descargas HTTP y reproducción real Electron PASS; lint/build verdes, 258/258 backend y 49/49 frontend. Tester PASS y reviewer APPROVE, evidencia en `logs/remix-delivery-repair-20261015/`. El cierre corresponde a recuperación, entrega y duración: B6/B7 y R9/R10 siguen abiertos; una variante mide 42,90 BPM y la otra carece de medida fiable, sin atribuirles el 170 pedido.

**Corrección de tempo y golpe en Por pistas, autorizada el 2026-10-15**: el usuario exige que el remix cumpla lo pedido, sin hardcode. Por pistas con BPM pedido mide la mezcla y exige la confianza mínima antes de estirar. Si la lectura cae fuera de `tempo_verify_tolerance_bpm`, un solo atempo local, sin cambio de tono, recalcula la duración natural y el objetivo, y se vuelve a medir antes de ampliar. Sin duración pedida, el resultado es la mezcla ajustada. Si la mezcla ajustada supera la duración pedida, se dice el mínimo y no se recorta. Si ya cae dentro, no se estira. En la exportación se vuelve a medir y se aplica la misma tolerancia que en canción completa. Un groove incierto no se publica tal cual ni recibe el BPM pedido. Si el bombo nuevo y el original se pueden medir, se cuadran en tempo y en fase y la mezcla se vuelve a medir con el mismo corte; si sigue incierta, no se publica. Si al repetir el tramo elegido la canción larga vuelve a quedar incierta, se repite la canción entera, se vuelve a medir con el mismo corte y, si sigue incierta, no se publica. El detector no consulta ese BPM: si el ancla es el compás, solo puede sustituirlo un período sostenido de la mitad o del cuarto, y solo cuando la potencia del flujo de ataques supera a la del ancla por `groove_onset_spectrum_ratio`. Una meseta y un tren de pulsos sin ataque más rápido se quedan. Si varias pistas se transforman con la misma ganancia, la mezcla usa una sola base (la generación menos la voz nueva, si se conserva, y menos lo quitado) para no perder el golpe que el separador archivó fuera de su grupo. Ganancias distintas siguen por stem. No se reescribe la frase visible ni se sintetiza un bombo. No cierra B6/B7 ni R9/R10.

**Petición del usuario**: revisar memoria y estado del código; poder modificar BPM en remix al separar por pistas, revisar esa separación y poder elegir una canción más larga que la original. **Plan autorizado**: el usuario elige BPM común para todas las pistas y repetir/reorganizar partes con transiciones; «continua» autoriza ejecutar el plan comunicado. Estado: **implementación verificada técnicamente** el 2026-10-14 (PASS del tester + APPROVE del reviewer, memory CXXXI); **alcance rectificado el 2026-10-14 (memory CXXXII)**: esa verificación usó un recorte preparado y no cubre el uso general. No sustituye los criterios abiertos R9/R10 ni la escucha artística del usuario.

- [x] El control de BPM común funciona en Por pistas también cuando se conservan o quitan grupos. Aplica un cambio de tempo sincronizado sin cambiar el tono y declara el procesamiento de las grabaciones conservadas; medición original revisable cuando sea incierta. No basta con retirar el rechazo actual: comprobar alineación, duración resultante y tempo medido, sin afirmar que el BPM pedido al motor demuestra el BPM del audio. *(Rectificado el 2026-10-14, memory CXXXII: la comprobación se hizo con un recorte y el BPM original a mano. En uso general el control queda condicionado a que la medición automática acierte la octava, y en canción completa el BPM pedido no se cumple; ver **B6**.)*
- [x] Revisar los cuatro grupos reales de Demucs: voz, batería, bajo y acompañamiento restante; archivos válidos, muestras finitas, duración/frecuencia coherentes con la fuente, preescucha SOLO y recombinación. La calidad de aislamiento requiere escucha; no presentar instrumentos adicionales como pistas separadas. Considerar identidad de fuente y parámetros de separación al reutilizar material.
- [x] Ofrecer duración objetivo en minutos y segundos para canción completa y Por pistas mediante repetición de material con fundidos y una timeline verificable. Se reutiliza el tema o la parte elegida con la misma edición para todas las pistas. Cover conserva la longitud de su fuente: la ampliación es una operación posterior explícita, sin silencio añadido como música. La generación de continuación mediante repaint queda fuera del método elegido.
- [x] Los grupos conservados se reutilizan con el mismo cambio común de tempo y arreglo por repetición; declarar estas operaciones, sin atribuir voz nueva ni continuación generada a «conservar».
- [x] Preview, ejecución, ficha e historial distinguen duración original/final, tempo original/objetivo/medido y operaciones realizadas. Límites y transiciones proceden de configuración; no modificar el perfil SFT/50/9/batch2 ni instalar dependencias/modelos.
- [x] Verificación real del recorrido aprobado en API y Electron, lint/build/regresión, PASS del tester y APPROVE del reviewer de archivos completos, con evidencia en memory.md. La auditoría previa del código y de artefactos existentes no acredita una separación nueva ni la nueva funcionalidad.

**Cierre técnico R11, 2026-10-14 (memory CXXXI)**: PASS del tester y APPROVE del reviewer registrados en `logs/remix-r11-tester-verdict-20261014.json`, con lint 0, build 0, 203/203 backend y 42/42 frontend. Comprobado en primera mano contra los artefactos: cinco MP3 de 90,000 s y 2.161.196 bytes (`prueba-r11-mixto-1c43627e*`, `prueba-r11-completo-07464782*`, `prueba-r11-fuente-2ed3bb04-remix.mp3`), fichas con `timeline` (duración original/natural/final, `tempo_ratio`, `method: repeat_crossfade`, `tempo_method` `common_pcm_atempo`/`engine_conditioning`), semillas reales 42/2942175228 (mixto) y 42/396917302 (completo) y `bpm_measured` medido aparte del pedido. Límites vigentes: el BPM pedido al motor no acredita el BPM de sus partes nuevas, la calidad de aislamiento y la adecuación musical requieren escucha del usuario, y R9/R10, Q2 y la cancelación integral siguen abiertos.

**Rectificación del alcance R11, 2026-10-14 (memory CXXXII)**: la reproducción directa del recorrido por el agente principal, con los **dos audios reales del usuario y sin tocar código**, corrige lo anterior: (1) `f6fc62fe-Arroja la bomba.mp3` mide 363,64 BPM con confianza 0,101 y el BPM común se rechaza con 422 «No hay un BPM original fiable»; el pico más fuerte de esa pista es 120 BPM (0,4122) y la regla de octava elige un pico más débil (352,9 con 0,3964); (2) `Animales muertos.mp3` (81,4 s, 166,25 BPM) con BPM común 199 y 60 s se rechaza con «La duración objetivo debe ser igual o mayor que la canción al tempo elegido», sin decir que el mínimo son 68 s; (3) un MP3 generado a 199 BPM se mide como 99,2 (PEDÍA 199 · SALIÓ 99); (4) en canción completa el BPM pedido 199 salió medido 104,7 y 250,5, es decir no se cumple. Sí funciona cuando el BPM original se escribe a mano: trabajo real de «Por pistas» con todo en conservar y BPM común 199 → MP3 de 90,000 s y 198,5 BPM medidos. El defecto queda abierto como **B6** en `spec/03-PENDIENTES.md`; su arreglo requiere plan aprobado.

## [B6] BPM efectivo en remix — corrección autorizada 2026-10-14

El usuario pide «continua» tras CXXXII y aprueba explícitamente «Sí, ajustar el audio para cumplir el BPM»: en **Canción completa**, medir cada variante y ajustar después su tempo con DSP local sin cambiar el tono. La duración natural cambia y una duración mayor se completa con las repeticiones ya autorizadas. Agotadas las muestras, una variante sin pulso no se publica; si otra midió, se publica esa. Si ninguna mide, el error del detector para el trabajo. Un BPM medido fuera de tolerancia detiene el lote. Se conservan SFT/50/guidance9/batch2, dependencias y métodos de ampliación. No se amplía esta decisión al repaint regional: su BPM sigue siendo condicionamiento del motor y se indica como orientativo.

Plan: corregir la elección de octava sin escoger picos no armónicos por ser más rápidos; precargar la medición revisable en Por pistas respetando ediciones manuales; informar del mínimo de duración; medir y ajustar cada variante full antes de ampliar/exportar; ejecutar regresión y recorridos API/Electron/audio con reviewer y tester independientes.

**Continuación correctiva CXXXIV**: el usuario exige «no… arréglalo» tras el FAIL full de CXXXIII. La comprobación independiente de ataques acredita que atempo aplica su relación temporal; el detector RMS de un solo período cambia su estimación al procesar la textura. Se corrige la medición contrastando varios períodos alrededor del pulso previamente elegido, con parámetros en configuración y medición sin conocer el BPM pedido. Se conserva la selección de octava sustentada, la tolerancia y el ajuste único desde el WAV original. La propuesta de tres recalibraciones no se interpreta como aprobada ni se implementa.

**Corrección de unión de partes, continuación «sigue»**: el oráculo PCM demuestra que el solape restaba 0,1 s a cada parte y desplazaba el pulso un tercio de golpe en cada repetición. Al ampliar con BPM elegido, las copias deben compartir la fase de la cola y avanzar un número entero de golpes; se usa una subparte dentro del intervalo elegido, sin añadir material de fuera. El BPM de ese reloj procede de la medición independiente después del DSP en full y del tempo común parametrizado en groups. Se registran intervalo solicitado/efectivo, BPM y procedencia del reloj, fundido y golpes por copia; la UI explica el ajuste al pulso. Si no cabe una parte útil según configuración, se muestra el error. Esta corrección concreta el contrato existente de BPM común y repetición con transiciones; no cambia el texto ni los límites elegidos por el usuario, y no introduce iteraciones de tempo.

- [ ] Detectar groove sobre los dos originales reales sin priorizar un lag no armónico más corto; conservar pruebas de tempo/fase/alineación. No usar el BPM objetivo para convertir una medición fallida en éxito.
- [ ] Por pistas muestra el BPM original medido editable, su incertidumbre y los errores. La medición automática no pisa una edición manual ni datos de otra fuente; preview/envío distinguen la procedencia. El cambio común sigue sincronizado y sin cambio de tono.
- [ ] La duración solicitada inferior a la natural devuelve el mínimo concreto. UI muestra el mínimo calculable; full con BPM declara que su duración natural y ajuste solo se conocen tras generar.
- [ ] Cada variante full con BPM se mide antes del ajuste, se procesa por DSP sin cambio de tono y se mide después. Si antes del ajuste esa variante no tiene un pulso usable, se pide otra muestra, acotada por `full_groove_retries`; el lote principal sigue en 2. Agotadas las muestras, esa variante no se publica. Si otra variante de la canción completa tiene un pulso medible, se publica esa y el trabajo dice cuál quedó fuera. Si ninguna se puede medir, el trabajo falla con el error del detector y no se publica nada. Un BPM medido fuera de tolerancia sigue parando todo el lote y no pide otra generación. Repeticiones y transiciones se mapean a la timeline efectiva de esa variante; no se recorta o rellena con silencio una salida que exceda la duración solicitada.
- [ ] Preview, trabajo, fichas e historial declaran condicionamiento del motor y DSP posterior, valores pendientes, mediciones originales/resultantes, relación aplicada y duración por variante. Las semillas y parámetros efectivos del motor mantienen su trazabilidad.
- [ ] Lint/build/regresión verdes, recorrido real Por pistas y full con dos variantes, audios existentes/positivos/finitos, UI servida en las dos resoluciones y veredictos PASS del tester + APPROVE del reviewer con evidencia en memory. El BPM detectado sigue siendo una estimación revisable; la escucha artística no se sustituye por el PASS técnico.

**Muestra sin pulso, continuación «soluciona lo que falte»**: la segunda variante del trabajo 3b531144 no tiene un máximo de autocorrelación. La energía y el flujo caen de forma lisa, y el retardo más rápido queda por encima de cualquier retardo interior. No se baja el corte 0,5 ni se le asigna el BPM pedido. Antes del ajuste, si la medición dice que no hay pulso usable, se archiva ese audio y se pide una sola muestra nueva de esa variante. Una meseta de autocorrelación, en la que el máximo no destaca sobre el tempo de al lado, cuenta como pulso no usable: estirarla no cumple el BPM. Si el ajuste deja el audio demasiado corto para volver a medirlo, tampoco se publica: se pide otra muestra. El máximo son las generaciones extra de `full_groove_retries`. Cada muestra se mide sola. Agotadas las muestras de una variante de canción completa, esa variante queda fuera. Si otra variante sí tiene pulso, se publica y el trabajo dice que la otra no se publicó. Si ninguna se puede comprobar, el trabajo falla con el error del detector y no se publica nada. Un BPM medido fuera de la tolerancia de 2 detiene el lote entero y no pide otra generación. Por pistas no entra en esta regla.

Estado: **EN CURSO**, sin veredicto final todavía. El 2026-10-15 la sonda de semilla 42 sigue en FAIL: la primera variante de un trabajo llegó a 199,17 BPM en 90 s y no se publicó porque la segunda no tiene un pulso medible. Ver memory CXXXVI. La generación extra de una variante sin pulso está en el código y en las pruebas de contrato; todavía no hay una sonda nueva que publique las dos variantes. El mismo día, Por pistas con BPM pedido pasa a medirse y a comprobarse con la misma tolerancia (memory CLI). Eso no cierra esta historia: falta la sonda full con las dos variantes publicadas. El 2026-10-16 el usuario aprueba, solo en canción completa, publicar la variante que mide el pulso y dejar fuera la que no, con el mismo corte de 1,25. Si ninguna mide, no se publica nada. Un BPM medido fuera de 2 sigue parando el lote. Eso tampoco cierra la historia: falta la sonda en la que las dos variantes quedan dentro de 2 BPM y se publican.

## [R12] Texto por pista al transformar — aprobado 2026-10-15

**Como** usuario, **quiero** que al poner una pista en transformar aparezca su texto y el glosario escriba ahí, **para** juntar esos textos en la frase que se envía.

**Decisión**: un campo por pista en transformar. El glosario de esa pista escribe en su campo. Al lanzar, los textos no vacíos se juntan en una caption `A track with … · …`. Una pista vacía no añade términos y no se inventa un bombo. Rehacer la canción y cambiar un trozo siguen con el cuadro único.

- [ ] Cada pista en transformar muestra su campo y su glosario. La frase junta se ve antes de REMIX y es la que viaja en el prompt.
- [ ] Una pista vacía no aporta texto. El mismo término en dos pistas queda una vez.
- [ ] Rehacer la canción y cambiar un trozo no cambian su cuadro.

## [R13] IDENTIFY en SUBIR — pedido 2026-10-15

**Como** usuario, **quiero** un botón IDENTIFY al lado de REMIX en cada subida, **para** que el modelo escuche el audio y devuelva el género si es una línea de su glosario.

**Decisión**: 30 segundos del centro, el recorte ya configurado. El resultado solo se muestra. No entra en la frase del remix. Si el texto del modelo no es una línea entera del glosario, se dice y no se inventa otro.

- [ ] En cada fila de SUBIR, IDENTIFY está al lado de REMIX.
- [ ] La llamada es el análisis local ya existente. El género mostrado es `glossary_genre`, una línea literal.
- [ ] Un texto ajeno se enseña como fuera del glosario. El botón no escribe el prompt.

## [R14] El estilo se envía en inglés — pedido 2026-10-16

**Como** usuario, **quiero** que el texto de estilo, venga en el idioma que venga, se vea y se envíe en inglés, **para** que el motor reciba una caption que pueda seguir.

**Decisión**: solo el estilo. La letra cantada se queda como está escrita. El modelo local es `facebook/nllb-200-distilled-600M`, en CPU, en el Python del motor. No se usa el LM 0.6B ni se enciende `use_format`. El cuadro sigue en el idioma escrito. «Se envía» y el payload usan la misma función. Si el idioma no está en el mapa o el traductor falla, no sale el texto sin traducir. Una caption ya inglesa no se reescribe. Esto no cierra R9, R10, B6 ni B7, ni sustituye la escucha.

- [x] «Batería suave al fondo» y «A track with gabber hardcore · kicks potentes con bounce» salen en inglés, sin «potentes», y una segunda llamada devuelve lo mismo. Medido antes de la corrección, el 2026-10-16: «Soft battery at the bottom» y «A track with gabber hardcore · kicks powerful with bounce».
- [x] Si el origen dice «batería» o «baterías» y el inglés dice battery o batteries, queda drums. Si dice «bombo», «bombos» o «doble bombo» y el inglés dice bumper, bumpers o double bumper, queda kick, kicks o double kick. El fichero es `backend/style_term_fixes.json`. Una caption ya inglesa, incluida «a car battery», no se toca y no carga el modelo. Si el fichero falta o no se lee, no se envía el estilo. Medido 2026-10-16: «Soft drums at the bottom» y «4x4 hardcore with double kick». Tester PASS y reviewer APPROVE en memory.md CLVII.
- [x] En CREAR, el ánimo elegido añade su cláusula de `style_catalog.json` a la misma caption y se ve en «Se envía». Tranquilo y Chill no añaden «a slow, laid-back tempo» si el BPM está puesto. No se envía el párrafo ambient ni «driving drums as the lead». Esto no cierra B7. Bundle `index-C_jpjCgM.js`. La ventana no se ha pulsado.
- [x] «gabber», «A track with gabber hardcore», «Original prompt», «120 bpm» y «medieval flutes» se quedan igual y no cargan el modelo.
- [x] La letra de una petición con voz sigue igual. El preview y el payload llevan el mismo inglés. «120 bpm» con el control en 140 sigue en 422.
- [x] CREAR, remix, conservar voz y acompañamiento muestran esa frase antes de enviar. El bundle servido es `index-CtsKExfA.js`. La ventana no se ha pulsado en esta sesión.

## [R15] El progreso abre la salida real — pedido 2026-10-16

**Como** usuario, **quiero** pulsar el progreso de arriba y ver la salida y el error reales, **para** saber qué está haciendo el proceso.

**Decisión**: la frase corta del progreso se queda. El clic abre un panel con el final de `logs/acestep-api.log`, `logs/acestep-api.err.log` y `logs/musicia-api.err.log`. El largo y las rutas salen de `process_logs`. Un camino fuera de `logs/` no se lee. El nombre del remix queda en la fila del botón REMIX, no solo dentro de avanzados.

- [x] Con un trabajo en curso, el progreso de arriba es un botón. El panel muestra el texto de esos tres ficheros y se actualiza mientras sigue abierto. El bundle es `index-D9i2yOj7.js`. La ventana no se ha pulsado.
- [x] Un fichero ausente se dice. No se inventan líneas. Una ruta fuera de `logs/` lanza el error que la ruta convierte en 422. `test_process_logs`, 4 OK.
- [x] Un reinicio no borra lo que el panel enseñaba: cada stream lleva también la copia rotada (`<fichero>.bak`, la que `ensure_local.ps1` escribe al arrancar un proceso) debajo del vivo, con su propio COPIAR. `test_process_logs` cubre vivo + copia y el rechazo de un sufijo con separadores. Bundle `index-DNWC9fKU.js`. La ventana no se ha pulsado.
- [x] En rehacer, tramo y pistas, el nombre se escribe al lado de REMIX y viaja en `output_name`. Vacío sigue usando el nombre del original con `-remix`. La vista del nombre pedido, OK.

## [R16] Lo que sobra continúa la base y el recorte entra una vez — pedido 2026-10-16

**Como** usuario, **quiero** que una duración mayor que la canción continúe el final de la base que el remix ya creó, y que el recorte marcado entre una vez al empezar esa parte, **para** no rellenar el tiempo sobrante con un bucle de ese trozo.

**Decisión**: el motor instalado es SFT. La continuación es repaint del final, en trozos de `continuation_min_seconds` a `continuation_max_seconds` (3–90 s). El lote de cada trozo es `continuation_batch_size` 1. El lote 2, los 50 pasos, guidance 9, thinking, use_cot y use_format siguen como están. No se activan complete, lego ni extract, y no se descarga el modelo base. El recorte, si se marca, se toma de la base ya creada y se superpone una vez donde empieza lo que sobra, sin estirarlo y sin repetirlo. Sin recorte, solo continúa la base. El corte de 2 BPM se mide en el audio final. Un BPM fuera de tolerancia detiene el trabajo. Esto no cierra R9, R10, B6 ni B7. No se genera audio hasta que el usuario pida el remix.

- [ ] Si la duración pedida supera la de la base, el plan es `continue_bed` y los trozos respetan el mínimo y el máximo de la configuración.
- [ ] El payload del trozo es repaint, con el inicio en el final de la base, el final por delante, lote 1, `thinking` y `use_format` apagados, y el mismo BPM y la misma caption.
- [ ] El recorte entra una sola vez al empezar lo que sobra. La base anterior queda igual. No hay una segunda copia.
- [ ] La mesa dice continuación y recorte. Vacío no envía un sample. El fundido de repetición no se envía.
- [ ] El corte de 2 BPM no se baja. No se publica un audio de esta historia en esta entrega.

## [R17] La ampliación continúa la misma música y se entrega — pedido 2026-10-17

**Como** usuario, **quiero** que un remix por pistas con duración mayor siga la misma música y meta el recorte, y que el trabajo lo entregue en vez de morir por una medición final incierta, **para** no perder toda la GPU pagada después de que la base ya se midió y verificó.

**Decisión**: en Por pistas, antes de continuar la base, la mezcla ya exige pulso medible (`require_measured_tempo`, confianza mínima 0,12) y ya cumple el BPM pedido (un solo atempo si estaba fuera de los 2 BPM; `verify_requested_tempo` tras el ajuste). La continuación es repaint de esa misma base, con el mismo estilo y el mismo BPM. Si después de ampliar y exportar la medición del archivo final vuelve a ser incierta (los mismos cortes del detector, sin bajar ningún umbral), el trabajo se entrega con la medida de la base —ya verificada— como tempo acreditado y un aviso honesto de que el pulso de la ampliación no se pudo re-medir. Un BPM final medido y concluyente fuera de tolerancia sigue deteniendo el trabajo; un groove incierto ya no tumba una ampliación cuya base se verificó. Sin PASS/APPROVE esta historia no queda cerrada; esto no cierra B6, B7, R9 ni R10.

- [ ] Si la medición del archivo ampliado (`continue_bed`) es incierta y la mezcla base se verificó antes, el trabajo termina con `succeeded`, el tempo acreditado es el de la base y el aviso dice que el pulso de la ampliación no se pudo re-medir.
- [ ] La ficha conserva la medición de la base con su procedencia y el aviso; no se inventa una medición del archivo final.
- [ ] Si la medición final es concluyente y cumple tolerancia, se publica como hoy. Si es concluyente y no la cumple, el trabajo falla como hoy.
- [ ] El recorte sigue entrando una sola vez. Los cortes del detector (hombro 1,25, confianza 0,12) no se bajan.
- [ ] `repeat_crossfade` y el scope full conservan su comportamiento actual (ensanchamiento y reintentos).
- [ ] Pruebas nuevas de la rama incierta y de la rama concluyente; suite verde.

## Corrección de estabilidad con GPU compartida — autorizada 2026-10-18

El usuario autoriza corregir los tres hallazgos de la revisión actual y optimizar estabilidad, instalar NumPy exclusivamente en `backend/venv` y ejecutar una generación real de Musicia compartiendo la GPU ocupada. No amplía esta entrega a los criterios técnicos anteriores R9/R10/B6/Q2. ComfyUI y sus procesos se preservan. Continúa el perfil SFT/50 pasos/guidance 9/lote 2 y la traducción en CPU.

- [x] El supervisor periódico preserva un motor con proceso presente o puerto abierto aunque `/health` tarde; solo arranca uno ausente. Se mantienen HOLD, exclusión entre supervisores y rearme explícito. Prueba CPU con HTTP retardado y PID propio estable, sin tocar procesos ajenos.
- [x] El arranque usa el modelo SFT y LM configurados desde el principio: no carga Turbo para cambiar después. La política de offload del perfil de 8 GB se configura explícitamente para evitar que el servidor REST mantenga el DiT en GPU por su default; no cambia pasos/guidance/lote.
- [x] NumPy figura en requirements y se importa realmente con el Python de la API. La continuación usa vistas PCM y validación vectorizada para reducir copias y trabajo Python, preservando muestras, canales, duración y rechazo de NaN/Inf. Medición CPU antes/después sobre el mismo audio real.
- [x] R17 conserva continuación y recorte ante pulso final incierto usando únicamente la medición previa verificada con procedencia y aviso; un BPM final concluyente fuera de tolerancia falla. Regresión del flujo completo con recorte menor que la canción.
- [x] Suites backend/frontend, lint/build y reviewer/tester explícitos (PASS CPU 312/0/2, frontend 62/62, build/lint 0). Generación real ejecutada con perfil aprobado: PID 17108 estable ante 3 sondeos de ensure_local; la difusión completó los 50 pasos a las 11:47:11 (402,4 s), pero el trabajo falló por timeout a las 12:05:18 (1800 s) durante la decodificación VAE (tiled_decode) por contención con ComfyUI (~11 GB RAM/GPU activa). Registrado el fallo real en job-final.json y e2e.log sin cerrar aplicaciones ajenas. Procesos del motor propio terminados y VRAM liberada a las 12:07:41.

## [R18] Musicia libera su GPU al acabar — autorizado 2026-10-18, en implementación

**Petición y aprobación**: al terminar su trabajo, Musicia debe liberar la GPU; el usuario aprueba «Sí, liberar por completo al terminar». **Plan autorizado**: detener exclusivamente el proceso del motor propio cuando terminen todas las operaciones de Musicia que lo necesitan (éxito, fallo o cancelación); mantener API y ventana disponibles. La siguiente petición arranca el motor bajo exclusión y espera su disponibilidad real. El supervisor respeta la pausa de reposo y no lo relanza periódicamente. Separación termina su proceso propio como hasta ahora; otros programas GPU se preservan.

**Implementación prevista**: coordinación del ciclo del motor en backend, señal de reposo y PID propio en scripts de arranque/supervisión, estado de reposo visible y envío permitido desde frontend. Configuración central para política/tiempos; sin endpoints ficticios de descarga ni cambios al perfil SFT. La pausa de reposo no sustituye a SALIR ni borra su marca. Se comprueban operaciones solapadas y carreras inicio/fin antes de parar un motor.

- [ ] El último trabajo que usó el motor deja su proceso detenido y su VRAM liberada, incluida terminación con error/cancelación; no interrumpe otra operación ni confunde una separación con una generación.
- [ ] El watchdog respeta reposo. Nueva petición vuelve a arrancar exactamente un motor; UI distingue reposo de error y conserva uso normal. API y biblioteca siguen disponibles.
- [ ] Solo se actúa sobre PID identificado como motor de este proyecto; ComfyUI permanece vivo. Medir VRAM/procesos antes, durante y después, sin atribuir a Musicia memoria de otros procesos.
- [ ] Regresiones de concurrencia y reposo, lint/build, tester PASS/reviewer APPROVE y recorrido real de generación → liberación → nueva disponibilidad. La recarga del modelo añade latencia al siguiente trabajo y debe declararse.

