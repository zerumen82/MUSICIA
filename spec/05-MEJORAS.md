# 05 · Mejoras propuestas

Estado: el 2026-10-02 el usuario pidió quitar la locución y aplicar las
mejoras sustanciales. Esa parte está en código (ver `memory.md`, entrada XVI,
y [F3] en `spec/02`). No es HECHO: no hay un MP3 de cover ni de repaint.
No se instaló `acestep-v15-base`. No hay botón PARAR. La tabla de pantalla
de más abajo (chips de CREAR, ondas de 28 px, un solo anuncio de VRAM) no
está hecha.

El producto ya genera, canta, sube, mezcla, separa y remixa. Este documento
no propone otro programa. La primera parte es lo que cambia el oficio.
La tabla de más abajo es la capa de pantalla, sobre el mismo CONSOLE.

La ventana real es 1400×900, mínima 1080×700 (`frontend/main.cjs`).
Todo lo de abajo está medido contra esa ventana y contra el código actual.

## Mejoras sustanciales

Revisión de todas las funciones el 2026-10-02: generación, letra, subida,
remix DSP, remix IA, separación, mezcla, crossfade, locución, biblioteca
y el motor ACE-Step 1.5. El hueco grande no es un botón nuevo. Es que el
motor sabe editar una pista que ya existe y Musicia solo le pide canciones
desde cero.

### Lo que el motor hace y la app no le pide

`music_service.build_payload` fija `task_type` en `text2music`
(`config.py`). ACE-Step 1.5, en el turbo que ya cabe en 8 GB, admite
además dos tareas de edición (`vendor/ACE-Step-1.5/docs/en/API.md` y
`GRADIO_GUIDE.md`):

| Tarea | Qué hace con el audio que ya tienes | ¿Cabe en el turbo de 8 GB? |
|-------|--------------------------------------|----------------------------|
| `cover` | Mantiene melodía, ritmo y forma. Cambia el estilo según el prompt. La fuerza (`audio_cover_strength`) acerca o aleja del original. | Sí. No está en la lista «solo modelo base». |
| `repaint` | Regenera un tramo (inicio y fin en segundos). El resto de la pista se queda. Sirve para arreglar un trozo, cambiar una estrofa o alargar el final. | Sí. Igual que cover. |
| `extract` | Aísla un instrumento: voz, bajo, batería, guitarra, sintes… | No. Exige `acestep-v15-base`. |
| `lego` | Añade una pista (un bajo, una batería) sobre el audio existente. | No. Mismo modelo base. |
| `complete` | Completa un arreglo con varias pistas. | No. Mismo modelo base. |

El XL y el modelo base no se cargan en esta máquina sin medir VRAM antes.
El pico del turbo ya es 6,9 GB de 8. `lego` y `extract` son justo «saca la
voz y pon un bajo», y hoy no se pueden encender. El camino que sí cabe es
`cover` y `repaint` sobre el turbo, más la separación demucs que ya corre.

### Las cinco funciones que hoy no son lo que dicen

1. **Re-crear, extender y «crear base» son la misma generación.** En SUBIR,
   `recreate`, `extend` y `backing` abren `RemixIAPanel` y acaban en
   `POST /music/generate` con un prompt sacado del análisis. No entra el
   audio. «Extender» no alarga la pista: compone otra. El extendido real
   es `repaint` desde el segundo final hasta `-1`.
2. **El remix con voz ya está en el servidor y la pantalla lo dispara vacío.**
   `POST /audio/remix/ai` separa (demucs, solo voz y resto), genera una
   base instrumental y mezcla a −14 LUFS. `RemixActions` lanza la acción
   al pulsar el menú, así que el prompt no se escribe.
3. **Mezcla no deja elegir dos pistas del mismo sitio.** Si hay algo en la
   biblioteca y algo en subidas, BASE solo lista la biblioteca y VOZ solo
   lista las subidas (`MixLab.jsx`). No se pueden mezclar dos pistas de la
   biblioteca, ni dos subidas.
4. **Separar voces bloquea la API.** `POST /audio/separate` espera a demucs
   dentro de la petición. Un minuto o tres con la API congelada: el
   `/health`, la cola y el resto de botones no responden. El remix IA sí
   va en segundo plano. La separación tiene que ir igual.
5. **Los trabajos viven en un diccionario.** `jobs` y `remix_jobs` en
   `main.py` se borran al reiniciar la API. No hay cancelar. Una
   generación de varios minutos ocupa la GPU y no se puede parar. En 8 GB
   eso impide separar y generar a la vez.

La locución (`VoiceLab`, edge-tts) es otra herramienta: habla un texto, no
canta. La pestaña se llama VOZ y CREAR también tiene «canción con voz».
Conviene que la pestaña diga LOCUCIÓN, para no buscar ahí el canto.

### Qué haría, en este orden

1. **Una mesa de remix con tres operaciones reales**, no seis nombres para
   dos caminos.
   - Ajustar: los sliders que ya existen (tempo, tono, fundido, recorte).
   - Versión: `cover` con el MP3 de origen, el prompt y una fuerza.
   - Tramo: `repaint` con la selección de la onda (inicio y fin en
     segundos), que `Waveform` ya sabe marcar.
   El audio se pasa al motor por ruta absoluta en la misma máquina
   (`src_audio_path`). Si el motor no puede leerla, se dice el error real.
2. **Arreglar la mesa que ya mezcla**, antes de inventar otra.
   - El menú de remix no ejecuta hasta HACER, con el prompt visible.
   - BASE y VOZ listan biblioteca y subidas, con el origen escrito.
   - `POST /audio/separate` pasa a job con fase, como el remix IA.
   - Un botón PARAR sobre el job activo. El motor ya tiene tarea: se
     corta la espera en Musicia y se anota que la GPU queda libre cuando
     el proceso del motor lo permita. Si ACE-Step no expone cancelación,
     se dice y el botón solo deja de sondear, sin fingir que la GPU paró.
3. **Medir el modelo base antes de prometer bajo y batería por dentro del
   motor.** Una prueba, con el turbo descargado de la GPU, de si
   `acestep-v15-base` entra en 8 GB. Si entra, `lego` (añadir bajo) y
   `extract` (aislar voz, bajo o batería) pasan a la mesa de remix como
   cambio de modelo, con reinicio y confirmación. Si no entra, se queda
   demucs (voz y resto) más una base generada por el turbo. No se instala
   el base en esta propuesta: solo se decide tras la medida.
4. **Ficha y cola**, que son la condición de lo anterior. Sin el JSON al
   lado del MP3, cover y repaint no saben la letra ni el BPM. Sin una cola
   única, demucs y el DiT se pisan los 8 GB.

Lo demás de este archivo (pantalla, pestañas, nombres, VRAM en el lateral)
sigue valiendo y va después. No sustituye a estos cuatro puntos.

## Resumen de pantalla

| # | Mejora | Dónde se nota | Por qué vale |
|---|--------|----------------|--------------|
| 1 | CREAR en una consola corta | `Composer.jsx` | Género, mood, BPM y tono ocupan tres filas de chips siempre abiertas. La voz ya se resolvió con desplegables. El prompt acaba fuera de la vista. |
| 2 | Una sola barra de transporte | `App.jsx` + `Composer.jsx` | El motor se anuncia tres veces, y la pastilla de arriba dice siempre «MOTOR IA LOCAL». |
| 3 | El progreso viaja contigo | `JobsPanel.jsx` | Lanzar «otra versión» desde BIBLIOTECA dice «mira el progreso en CREAR». Si cambias de pestaña, la barra desaparece. |
| 4 | Un menú por pista | `Library.jsx` | Cinco iconos juntos. El remix DSP y el remix IA se parecen y, al abrir remix, salen dos paneles a la vez. |
| 5 | Menos chips repetidos | `RemixIAPanel.jsx`, `Uploads.jsx`, `QualityWizard.jsx` | Diez variantes siempre visibles, un asistente que vuelve a preguntar género y BPM, y una caja de subida enorme. |
| 6 | Nombre en mezcla y en locución | `MixLab.jsx`, `VoiceLab.jsx` | La mezcla se guarda como `mix-` + la hora. La locución, como `voz-` + la hora. En CREAR el nombre ya se pide. |
| 7 | Ficha al lado del MP3 | backend, al terminar el job | BIBLIOTECA no sabe el prompt, la semilla, la letra ni el modelo. «Otra versión» reanaliza a ciegas. |
| 8 | Modelo y VRAM en el lateral | `App.jsx`, `config.py` | Hoy solo dice si el motor responde. El turbo cabe (pico 6,9 GB de 8). El XL no. demucs pide 2,6 GB libres y no puede coincidir con una generación. |
| 9 | Persistencia entre pestañas | `App.jsx` | Cambiar de CREAR a BIBLIOTECA desmonta la pantalla. Se pierden el prompt, la letra, la voz elegida y el seguimiento del job. |
| 10 | Canción con voz, sin perder la letra | `Composer.jsx`, `vocal.js` | La letra se exige para cantar, el LM 0.6B a menudo no la escribe, y desde BIBLIOTECA «otra versión» ni siquiera enseña el campo de letra. |
| 11 | Remix de estudio: voz real + base nueva | `RemixActions.jsx`, `separator_service.py`, `main.py` | El servidor ya puede dejar la voz y generar una base desde un prompt. El menú lanza la acción al pulsarla, así que el prompt no da tiempo a escribirse. La separación solo parte en voz y «el resto», no en bajo, batería y armonía. |

Orden si se aprueba: 9 primero (si no, cada prueba de las demás se borra al
cambiar de pestaña), luego 11 (el remix que se quiere usar ya), luego 10,
luego 2 y 3, luego el resto de la pantalla (1, 4, 5, 6) y al final los datos
(7 y 8). Cada bloque se especifica en `spec/02-REQUISITOS.md` antes de codificar.

## 9. Persistencia entre pestañas

`App.jsx` pinta solo la pestaña activa:

```
{tab === 'composer' && <Composer />}
{tab === 'uploads' && <Uploads />}
…
```

Al salir de CREAR, React desmonta el componente. Muere el estado local:
prompt, género, mood, BPM, tono, nombre, modo voz, selectores, letra y el
bucle `pollUntilDone` (`aliveRef` pasa a falso en el cleanup). Lo mismo en
SUBIR (el análisis y la acción elegida), MEZCLA (base, voz, volúmenes),
VOZ (el texto de la locución) y BIBLIOTECA (el panel de remix abierto).

El job de música sigue en el servidor. El de remix también, en el
diccionario `remix_jobs` de `main.py`. La pantalla olvida el `job_id`, así
que al volver no hay barra, ni error, ni reproductor. Si el remix iba
sondeando dentro de `RemixActions`, ese sondeo muere con la pestaña y el
resultado queda en disco sin que nadie lo anuncie.

Cambio, en dos capas:

1. Las cinco pantallas siguen montadas. La que no está activa se oculta,
   no se destruye. El texto escrito y el sondeo en curso sobreviven al
   cambio de pestaña.
2. El `job_id` activo (música o remix) vive en `App`, que no se desmonta.
   La franja del punto 3 lee ese id en cualquier pestaña. Al volver a
   CREAR, la letra y el prompt siguen en su sitio.

La letra y el prompt de CREAR, además, se guardan en `localStorage` al
escribir. Cerrar la ventana a la bandeja no es cambiar de pestaña, pero
perder una letra escrita duele igual. El borrador se restaura al abrir.
No se guarda audio en el navegador: el MP3 ya está en `backend/outputs/`.

## 10. Creación con voz y letra

Lo que ya funciona en CREAR, modo CANCIÓN CON VOZ:

- Selectores en una línea: género de voz, timbre, estilo, emoción, idioma.
- Sin letra, GENERAR no sale: el motor haría un instrumental.
- La letra plana recibe marcas `[verso]` / `[estribillo]` en `structureLyric`.
- `POST /music/write_lyrics` pide un borrador al LM. Si el LM 0.6B no
  compone y el usuario dejó frases, se construye la estructura con esas
  frases y se enseña el aviso. No se inventa una letra.
- `vocal_language` sale del selector, no del default `en`.

Lo que falla en el uso:

- La letra desaparece al cambiar de pestaña (punto 9).
- No hay botones de sección. Quien no conoce las marcas depende del
  automático, que alterna verso y estribillo y no sabe dónde va el puente.
- Desde BIBLIOTECA, «otra versión» llama a `RemixIAPanel` con
  `kind="musica"`. El campo de letra solo se pinta si el tipo es `voz` o
  `mixta`. Una canción cantada, reabierta en la biblioteca, se regenera
  como instrumental y sin los selectores de voz.
- El aviso del LM es un párrafo pequeño bajo el cuadro. Si el motor
  devolvió solo estructura instrumental, tiene que leerse sin abrir
  «ver lo que se envía».

Cambio:

- Encima de la letra, cuatro botones de una línea: VERSO, ESTRIBILLO,
  PUENTE, FINAL. Insertan la marca en el cursor. No escriben texto.
- El aviso del LM queda en la misma línea que ESCRIBIRLA POR MÍ, en
  ámbar, mientras el borrador no traiga estrofas cantables.
- En BIBLIOTECA, «otra versión» de una pista que tiene ficha con letra
  abre el mismo bloque de voz que CREAR: letra, idioma y los cuatro
  selectores, rellenos desde la ficha. Sin ficha (pistas viejas), el
  campo de letra se muestra igual, vacío, para poder pegarla.
- El modo CANCIÓN CON VOZ y el borrador sobreviven al cambio de pestaña.

## 11. Remix versátil: sacar la voz y crear el resto

Lo que ya hace el servidor, en `POST /audio/remix/ai`:

1. Separa la pista con demucs (`--two-stems=vocals`): un MP3 de voz y un
   MP3 con todo lo demás.
2. Pide a ACE-Step una base nueva, instrumental, con el prompt y el BPM
   de la original (o el que se envíe). Duración acotada a la de la fuente,
   máximo 4 minutos.
3. Cuadra la voz con esa base si el groove es fiable. Si no, mezcla sin
   tocarla y lo dice.
4. Normaliza a −14 LUFS. Devuelve la mezcla, la base y la voz por separado.

Eso es exactamente «extraer la voz y que cree un bajo, o lo que sea»,
siempre que el prompt describa ese bajo. El modelo genera una pieza
completa con esa descripción. No genera un stem de bajo aislado: la
separación actual no sabe partir bajo, batería y armonía. Solo voz y resto.

Lo que impide usarlo:

- En `RemixActions.jsx` el menú llama a `run(id)` al pulsar la fila.
  `run` vacía la acción al empezar. El campo de prompt solo existe cuando
  la acción es `voz_prompt` o `solo_base`. Resultado: la acción se dispara
  con el prompt vacío y responde «Escribe un prompt para la música nueva»,
  sin dejar el campo a la vista.
- No hay un destino claro. «VOZ + MÚSICA DESDE PROMPT» es una frase larga
  dentro de un desplegable, al lado de loop y medio tiempo.
- El usuario no elige qué conservar. O se queda toda la voz sobre una
  base nueva, o se tira la voz y solo queda la base.
- Los tres archivos (voz, base, mezcla) se guardan, pero la línea de
  estado solo nombra uno.

Cambio, en la misma línea del remixer, sin panel nuevo:

1. Elegir la acción no la ejecuta. Abre lo que esa acción necesita y
   espera a un botón HACER.
2. Para la voz sobre música nueva, una línea:
   CONSERVAR `VOZ` · CREAR `BAJO` / `BATERÍA` / `BASE ENTERA` / `LO QUE ESCRIBA`
   · prompt · BPM · NOMBRE · HACER.
   Los cuatro destinos son frases fijas que se anteponen al prompt
   (`solo bajo profundo de…`, `batería seca de…`, `instrumental completo de…`).
   Van en config de textos, no sueltas en el componente. El prompt del
   usuario se suma detrás y se puede editar entero antes de lanzar.
3. El paso a paso se ve en la franja global: separando, generando, cuadrando,
   mezclando. Al terminar, la biblioteca tiene la mezcla, y la línea de
   estado nombra también la voz y la base por si se quieren remezclar.
4. Segunda capacidad, cuando la primera ya mezcle de verdad: separación
   en cuatro stems con htdemucs (voz, batería, bajo, resto), sin
   `--two-stems`. Ahí sí se puede conservar la voz y la batería originales
   y sustituir solo el bajo por uno generado. Es más lenta y usa la misma
   regla de VRAM: si no hay 2,6 GB libres, va a CPU o espera. No se
   presenta como disponible hasta que los cuatro archivos existan.

Hasta que existan los cuatro stems, la interfaz dice «base nueva», no
«bajo extraído y sustituido». El prompt puede pedir un bajo. El archivo
que vuelve es una base generada, mezclada con la voz real.

## Cómo se ven CREAR, remix, mezcla y biblioteca

Mismo sistema CONSOLE: fondo `#0a0a0c`, panel `#101013`, verde `#b8ff29`,
mono para los datos, un solo botón verde por acción. No hay tema nuevo.
Lo que cambia es que cada pantalla enseña el audio, no solo el nombre.
La onda ya existe (`Waveform.jsx`, picos reales de `GET /audio/peaks`) y
hoy solo sale en el remix DSP. El porcentaje ya existe (`.vu`, `.num`) y
hoy es una barra de 8 px escondida bajo el prompt.

### CREAR

Una sola columna, sin la SESIÓN de 360 px. El prompt es el texto grande
(17 px, ya está). Debajo, una línea de desplegables: modo, género, mood,
BPM, tono. Si el modo es CANCIÓN CON VOZ, el cuadro de letra ocupa el
ancho, con el borde verde que ya tiene, y cuatro marcas pequeñas
(VERSO, ESTRIBILLO, PUENTE, FINAL) en `btn-ghost`.

La barra de abajo es el único sitio verde de la acción: nombre, duración,
semilla y GENERAR (`btn-signal`). Cuando hay un trabajo, GENERAR se queda
y a su izquierda aparece el número grande del porcentaje (clase `.num`)
más la fase en una línea. La barra `.vu` pasa a la altura del fader (8 px
ahora, 18 px entonces) y cruza todo el ancho. El ecualizador animado (`.eq`)
solo se ve mientras el estado es CREANDO. Al terminar, la tarjeta que ya
existe («TU PISTA ESTÁ LISTA», fondo `--acc-dim`) ocupa esa barra, con el
reproductor y el MP3. No hay una segunda lista al lado.

### Remix

El remix de una pista, venga de BIBLIOTECA o de SUBIR, abre el mismo
escenario. Arriba, la onda de esa pista a todo el ancho (altura ~96 px,
picos verdes, selección en `--acc-dim`). Encima de la onda, el nombre.

Debajo, una sola línea de rack:

`CONSERVAR` voz · `CREAR` bajo / batería / base / lo que escriba · prompt · BPM · `HACER`

`HACER` es el único `btn-signal`. Elegir en el menú no lanza nada: deja
el prompt escrito sobre la línea y el botón encendido. Mientras corre,
la onda se queda y encima se lee la fase (separando, generando, cuadrando,
mezclando) con el mismo `.vu`. Al acabar, tres pastillas con nombre, no
una frase: VOZ, BASE, MEZCLA. Cada una con play. La mezcla es la que
arranca sola.

El remix de sliders (velocidad, tono, fundido) no se apila debajo. Es
otra entrada del mismo menú, `AJUSTAR`, y sustituye la línea de CONSERVAR
por los faders que ya tiene `RemixPanel`. La onda sigue siendo la de arriba.

### Mezcla

Dos columnas dentro de un `rack`, no una tira de selectores.

| Izquierda | Centro | Derecha |
|-----------|--------|---------|
| BASE, nombre, onda pequeña, fader de volumen (el thumb verde que ya existe) | La frase del plan: «se cuadra ×1,02» o «no se toca», en mono | VOZ, nombre, onda, fader |

Debajo, una línea: CUADRAR, −14 LUFS, NOMBRE, MEZCLAR. MEZCLAR es el
`btn-signal`. El resultado usa la misma tarjeta verde de CREAR, no una
fila pequeña distinta.

EXTRAER VOCES queda como acción de la columna BASE: al terminar, la
columna izquierda pasa a ser la base extraída y la derecha la voz, con
sus ondas. El crossfade deja de ser una nube de hasta 12 chips con el
nombre cortado a 22 letras. Es una tercera fila del rack: se marcan
pistas de la misma lista, con el nombre entero, y FUNDIR a la derecha.

### Biblioteca

Cada pista es una fila de rack, no una línea de iconos.

- Cuadrado de play, 44 px, verde cuando suena (ya está).
- El nombre en 14 px, sin la extensión `.mp3` en la lectura. La extensión
  queda en el tooltip.
- Debajo del nombre, una onda muda de 28 px de alto, los picos de esa
  pista. Al reproducir, el tramo recorrido se pinta en verde y el resto
  en `--line-strong`.
- A la derecha, una sola palabra: ACCIONES. El menú dice Otra versión,
  Remix, Ajustes, Descargar, Borrar. Remix abre el escenario del apartado
  anterior, debajo de esa fila, no un segundo panel de sliders al lado.

La fila que suena lleva el fondo `--acc-dim` que ya tiene, y el
reproductor dentro de la fila. Las demás siguen mostrando solo la onda
muda, para que la lista se lea de un vistazo.

Vacía: el mismo texto de ahora, centrado, y un botón verde IR A CREAR.
Sin ilustración nueva.

## Lo que se queda como está

- Sistema visual CONSOLE: fondo neutro, un verde de señal, datos en mono. Ya se eligió así tras rechazar dos interfaces.
- Pestañas: CREAR, SUBIR, MEZCLA, VOZ, BIBLIOTECA.
- La X minimiza a la bandeja. SALIR apaga motor y API sin preguntar. Es una decisión ya tomada.
- MEZCLA en una línea: base, voz, volumen, cuadrar, −14 LUFS.
- El remixer de bootlegs (`RemixActions.jsx`): un desplegable y una línea de estado.
- Selectores de voz cantada en una línea, con el resumen ELIGIDO.
- ACE-Step 1.5 turbo y el LM 0.6B. El XL 4B no entra en esta máquina.
- El secuenciador sigue fuera de la navegación.

## 1. CREAR cabe en la ventana

Archivo: `frontend/src/components/Composer.jsx`.

Hoy, de arriba a abajo:

1. MÚSICA / CANCIÓN CON VOZ / ASISTENTE / MEJORAR PROMPT / estado del motor.
2. Fila de 6 géneros.
3. Fila de 5 moods.
4. Fila de 6 BPM y 6 tonos.
5. El prompt.
6. Si hay voz: otra caja con letra.
7. Nombre, duración, semilla, GENERAR, VARIAR.
8. Cola de trabajos.
9. Progreso.
10. Reproductor.
11. A la derecha, una columna SESIÓN de 360 px (`localStorage`, máximo 30).

En 1080 px de ancho, la consola se queda con unos 700 px y el prompt
hace scroll. SESIÓN repite pistas que ya están en BIBLIOTECA, y un renombre
en disco no actualiza ese `localStorage`.

Cambio:

- Género, mood, BPM y tono pasan al mismo patrón que la voz (`VocalSelect`):
  una línea y el valor elegido siempre visible. Los chips de esas cuatro
  filas desaparecen. Las listas (Techno, 128, Do M…) se conservan: son las
  que el backend ya acepta.
- ASISTENTE y MEJORAR PROMPT se quedan, en esa misma primera línea.
  El asistente (`QualityWizard.jsx`) deja de ser un segundo camino con
  otras listas de género y de BPM. Rellena los cuatro desplegables y el
  prompt, y se cierra.
- La columna SESIÓN sale de CREAR. La lista de verdad es BIBLIOTECA.
- Abajo, fija, una barra: nombre, duración, semilla, GENERAR. Si hay un
  job, la barra de porcentaje real ocupa esa misma franja. El prompt no
  se va al hacer scroll.

## 2. Un solo anuncio del motor

Hoy hay tres:

| Sitio | Qué dice |
|-------|----------|
| Lateral (`App.jsx`) | CONECTANDO / MOTOR ACTIVO / MOTOR APAGADO. Sondeo real a `/health` cada 10 s. |
| Cabecera (`App.jsx`) | El texto es siempre «MOTOR IA LOCAL». Solo cambia el color del borde. |
| CREAR | «MOTOR ACTIVO» otra vez. |

Se queda el lateral, que ya es el dato real. La pastilla de la cabecera
pasa a decir ACTIVO o APAGADO, el mismo estado. CREAR no lo repite.
«100% LOCAL · SIN NUBE» se queda: es la frase del producto, no un estado.

## 3. El progreso no depende de la pestaña

`JobsPanel.jsx` solo está montado dentro de CREAR. Desde BIBLIOTECA,
`runIAFromLibrary` lanza el job y escribe: «Mira el progreso en CREAR».
La barra de porcentaje (`job.progress_ratio`, `job.phase`) vive en el
componente de CREAR. Al cambiar de pestaña, ese componente se desmonta.

Cambio: la franja de progreso pasa al `header` de `App.jsx`. Se ve en
SUBIR, MEZCLA, VOZ y BIBLIOTECA. Muestra fase, porcentaje y el nombre de
la pista. Un fallo muestra `job.error`, no la frase genérica «revisa el
prompt» que hoy pone la cola cuando hay trabajos en `failed`.

El comparador A/B de la cola marca dos letras y abre dos `<audio>`
separados. La etiqueta dice «A/B LISTO PARA COMPARAR» y no hay un play
conjunto. Hasta que exista ese play, la etiqueta no promete una
comparación. Dos reproductores seguidos bastan, con el texto «A» y «B».

## 4. BIBLIOTECA: una fila, un menú

Archivo: `frontend/src/components/Library.jsx`.

Cada pista tiene play, lápiz, tamaño, fecha y cinco botones de icono:
remix (Shuffle), otra versión (Sparkles), ajustes, descarga y borrar.
Shuffle y Sparkles no se distinguen sin pasar el ratón. Abrir remix
monta a la vez `RemixPanel` (onda, tempo, tono, fundidos) y
`RemixActions` (el desplegable de bootlegs). Son dos herramientas
distintas en el mismo hueco.

Cambio:

- La fila queda en play, nombre, duración y un botón ACCIONES.
- El menú dice las acciones con palabra: Otra versión, Bootleg, Ajustes
  de volumen y fundido, Descargar, Borrar.
- Bootleg abre solo `RemixActions`. Ajustes abre el recorte y el fundido
  (`RemixPanel` o el formulario que ya existe, uno de los dos, no los dos).
- Otra versión abre `RemixIAPanel` como ahora, debajo de esa pista.

## 5. SUBIR y el panel de «otra versión»

`Uploads.jsx`: la zona de arrastre usa `py-14` aunque el análisis ya
está en pantalla. Debajo hay seis cifras, una hipótesis con chips, la
pregunta «¿qué es?» con más botones y «¿qué hacemos?» con tarjetas.

`RemixIAPanel.jsx`: diez chips (MÁS ENERGÍA, OSCURA, LO-FI…) siempre
visibles, y reescriben el prompt por concatenación.

Cambio:

- Con un archivo ya analizado, la caja de arrastre pasa a una línea:
  nombre, BPM, duración, y un botón para soltar otro archivo.
- Las seis cifras se quedan en esa línea. La hipótesis y las dos
  preguntas se quedan: son la decisión. Los chips de «señales» salen
  si no caben; el texto de la hipótesis basta.
- Las diez variantes del prompt pasan a un desplegable VARIANTE, una
  cada vez, con la frase añadida visible en el propio prompt. El
  textarea sigue siempre visible, que es lo que ya se pidió.

## 6. Nombre también al mezclar y al locutar

| Pantalla | Nombre hoy | Cambio |
|----------|------------|--------|
| CREAR | Campo. Vacío → `pista-sin-nombre`. | Se queda. |
| MEZCLA | `mix-${Date.now()}` en `doMix`. | Campo NOMBRE en la misma línea. Vacío → `pista-sin-nombre`. |
| VOZ | `voz-${Date.now()}.mp3` en `VoiceLab.jsx`. | Campo NOMBRE junto a ESCUCHAR. |
| Crossfade | El backend pone el nombre. | La línea de crossfade muestra el nombre que devolverá, antes de fundir. |

VOZ además usa un `<select>` nativo y llama a axios por su cuenta, y se
queda con las 8 primeras voces `es-`. Pasa al `SelectBox` del resto de
la app y al cliente `api.js`. Siguen siendo solo voces en español: es
lo que la pantalla es.

## 7. Ficha de la pista

Sin esto, las mejoras 4 y 5 rellenan «otra versión» a ciegas.

Al terminar con éxito `POST /music/generate` (y el remix con IA), el
backend escribe un JSON junto al MP3:

- nombre, prompt, BPM, tono, semilla, duración
- letra y etiquetas de voz, si las hubo
- modelo (`acestep-v15-turbo`) y LM (`acestep-5Hz-lm-0.6B`)
- día

BIBLIOTECA enseña bajo el nombre una segunda línea mono:
`128 · La m · semilla 4412`, solo si el JSON existe.
Las pistas viejas no tienen ficha: se ven como ahora y el remix sigue
usando el análisis DSP.

«Otra versión» arranca el prompt, la letra y la voz desde esa ficha
cuando existe.

## 8. Modelo y VRAM, en una línea

No es una pantalla nueva. Es la línea del lateral que hoy dice
MOTOR ACTIVO.

Pasa a: `TURBO · LM 0.6B · 6,9/8 GB`.

Al pulsar, un panel corto:

- Modelo de música y LM cargados, leídos de la config y de `/health`.
- VRAM libre, leída con nvidia-smi.
- demucs: listo en GPU, listo en CPU, o no instalado. Si la VRAM libre
  es menor de 2,6 GB, el texto dice que la separación espera a que
  termine la generación.
- El XL 4B se muestra bloqueado, con el motivo (no cabe). No se puede
  elegir.
- Apagar el LM (`use_lm`) es un interruptor de esa línea. El aviso de
  que a veces no compone letra se mantiene.

Cambiar de modelo reinicia solo el proceso del motor, con confirmación,
y solo si no hay un job en curso. Este documento no instala pesos nuevos.

La allowlist vive en `backend/config.py`, no en la interfaz.
`generation.language` pasa de `en` a `es` para que una llamada sin
idioma deje de forzar inglés. La UI ya manda el idioma cuando hay letra.

## Orden de implementación, cuando se apruebe

1. Persistencia entre pestañas y borrador de letra (punto 9).
   Archivo: `App.jsx`. Las pantallas se ocultan, no se desmontan. El
   `job_id` vive en `App`. El borrador de CREAR va a `localStorage`.
2. Remix de voz + base nueva, usable (punto 11, pasos 1 a 3).
   Archivos: `RemixActions.jsx`, textos de destino en config, el job que
   ya existe en `main.py`. La separación de cuatro stems queda para cuando
   este camino mezcle y se oiga.
3. Letra y voz que no se pierden, también en BIBLIOTECA (punto 10).
   Archivos: `Composer.jsx`, `vocal.js`, `Library.jsx`, `RemixIAPanel.jsx`.
4. Pastilla de la cabecera y progreso global (puntos 2 y 3).
   Archivos: `App.jsx`, `Composer.jsx`, `JobsPanel.jsx`.
5. CREAR en una línea y sin columna SESIÓN (punto 1).
   Archivo: `Composer.jsx`. El asistente solo rellena.
6. Menú de BIBLIOTECA y un solo panel de remix (punto 4).
   Archivo: `Library.jsx`.
7. SUBIR compacto y variantes en un desplegable (punto 5).
   Archivos: `Uploads.jsx`, `RemixIAPanel.jsx`.
8. Campo NOMBRE en MEZCLA y en VOZ (punto 6).
   Archivos: `MixLab.jsx`, `VoiceLab.jsx`.
9. Ficha JSON (punto 7). Archivos: `backend/main.py`, `music_service.py`,
   lectura en `Library.jsx` y `RemixIAPanel.jsx`.
10. Línea de modelo y VRAM, y separación en cuatro stems (puntos 8 y 11.4).
    Archivos: `config.py`, `separator_service.py`, `GET /music/models`,
    el lateral de `App.jsx`.

Cada paso: historia en `spec/02-REQUISITOS.md`, lint, build, y una
pasada real por la ventana. La ficha y el modelo se comprueban con el
archivo en disco y con la salida de nvidia-smi. Nada se da por hecho
sin PASS y APPROVE en `memory.md`.

## Fuera de esta propuesta

- Instalar el XL u otro DiT.
- Traer el secuenciador. Si vuelve, antes van samples locales (deuda T2).
- Compás (time signature). Sigue en [A4], aparte.
- Instalador de Windows.
- Borrar `Mixer.jsx` y `Sequencer.jsx`. No están montados. Sacarlos es
  limpieza, no una mejora de uso.
- Un tema visual distinto.
- Mover los umbrales de mezcla (−14 LUFS, confianza 0,12, ratio 0,8–1,25)
  en este paquete. El sonido se queda. Si más adelante se quieren en
  config, es otro cambio y se pregunta.

## Cómo se sabrá que quedó bien

En la ventana a 1400×900 y a 1080×700:

- CREAR muestra el prompt, el nombre y GENERAR sin scroll para llegar al botón.
- Tras escribir una letra, cambiar a BIBLIOTECA y volver, la letra sigue.
- Con una generación o un remix en curso, el porcentaje se lee desde cualquier pestaña.
- Una pista de BIBLIOTECA abre un menú con palabras, y un solo panel.
- Un remix «voz + bajo» no arranca hasta pulsar HACER, con el prompt visible. Al terminar existen la mezcla, la voz y la base, con duración mayor que 0.
- Una mezcla nueva tiene el nombre escrito, o `pista-sin-nombre`.
- El lateral dice el modelo y la VRAM, y el XL no se puede pulsar.
