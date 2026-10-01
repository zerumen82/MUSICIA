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

### [A3] [P1] [propuesta] Generar canción con voz (letra + estilo)
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
