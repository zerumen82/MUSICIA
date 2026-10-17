# 🎵 Musicia

Estudio musical local para Windows: crea canciones instrumentales o con voz cantada, trabaja sobre tus audios y mezcla pistas con FastAPI, React/Vite y Electron. El canto lo genera ACE-Step; la locución edge-tts se retiró.

## Qué puede hacer

- **CREAR** — Prompt editable, letra e idioma opcionales; BPM, tono, compás, semilla y variantes. MEJORAR propone un borrador optativo.
- **SUBIR** — MP3/WAV, análisis DSP y análisis local revisable de la fuente. REMIX trabaja sobre el original mediante cover, repaint o separación de voz, batería, bajo y acompañamiento restante, con BPM común para las pistas y duración mayor por repetición de partes con transiciones.
- **MEZCLA** — Pistas de biblioteca y subidas, volúmenes, fundidos, cuadre cuando el tempo es fiable y normalización con ffmpeg.
- **BIBLIOTECA** — Audios, fichas de generación, renombrado, descarga y herramientas por pista. Los trabajos muestran fase y errores reales.

El plan R9/R10 está en corrección tras la auditoría del 2026-10-13. La implementación existente y las pruebas parciales no acreditan su cierre completo: consulta [pendientes](spec/03-PENDIENTES.md), [criterios del plan](spec/06-REMIX-INTEGRAL.md) y [bitácora](memory.md). La ampliación R11 (BPM común por pistas y duración mayor por repetición de partes) quedó cerrada a nivel técnico el 2026-10-14 con PASS del tester y APPROVE del reviewer, sin cerrar R9/R10. El 2026-10-14 se comprobó además, con los dos audios reales del usuario, que el BPM común todavía no es fiable en uso general (octava del BPM original y BPM no cumplido en canción completa): está abierto como [B6](spec/03-PENDIENTES.md). La adecuación musical requiere escucha del usuario.

## Arquitectura

| Componente | Tecnología | Puerto local |
|---|---|---|
| Ventana | Electron + React/Vite/Tailwind | — |
| API y UI de producción | FastAPI, `backend/venv` | 8000 |
| Motor musical | ACE-Step 1.5, venv propio en `vendor/` | 8001 |
| Separación | Demucs, `backend/demucs-venv` | invocado por la API |

El perfil aprobado usa **SFT en toda la app**, 50 pasos, guidance 9 y dos variantes por defecto; `thinking` y `use_format` apagados. Los valores efectivos proceden de configuración y de los controles explícitos. Generación y separación se serializan para la GPU NVIDIA de 8 GB verificada en este equipo. La documentación de módulos y contratos está en [arquitectura](spec/01-ARQUITECTURA.md).

## Puesta en marcha

Con las dependencias y pesos ya instalados:

```powershell
# Desde la raíz: motor + API + ventana Electron
powershell -ExecutionPolicy Bypass -File scripts/open_musicia.ps1

# Solo servicios
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1

# Parar servicios
powershell -ExecutionPolicy Bypass -File scripts/stop_local.ps1
```

Después de cambiar el frontend, ejecutar `npm run build` dentro de `frontend/`: la API sirve `frontend/dist` en `/`. Para desarrollo con HMR, usar `npm run dev` en ese directorio. La X se ignora: no cierra ni esconde la ventana. SALIR detiene los servicios y cierra la aplicación. PARAR actúa sobre un trabajo, con reinicio del motor cuando la operación lo requiere.

Requisitos del entorno: Windows, ffmpeg/ffprobe en PATH, los venv del backend y motor, Node compatible con el Vite instalado y GPU NVIDIA recomendada. La instalación de paquetes o modelos requiere aprobación explícita; la primera descarga de pesos del motor y de Demucs necesita red.

## Verificación

Hay suites backend `backend/test_*.py` (unittest) y frontend `frontend/src/*.test.js` (Node). La auditoría del 2026-10-13 registró lint/build verdes, 164 tests backend y 8 frontend, y la revisión del 2026-10-14, 203 backend y 42 frontend con lint/build verdes; son referencias fechadas, no el cierre de R9/R10.

```powershell
# Prueba oficial: genera música local y valida el MP3 con ffprobe
powershell -ExecutionPolicy Bypass -File scripts/verify_e2e.ps1 -Seconds 30
```

Un cierre exige ejecución real de los recorridos afectados, lint/build verdes, **PASS del tester + APPROVE del reviewer**, con evidencia en `memory.md`.

## Privacidad y estructura

La generación, análisis, separación y mezcla se ejecutan en la máquina del usuario. Las descargas iniciales y cualquier dependencia de red se declaran en la bitácora. No se instala ni se descarga nada por abrir estos documentos.

`backend/` contiene la API y servicios; `frontend/`, la UI y Electron; `scripts/`, lanzadores y sondas; `spec/`, especificaciones SDD; `vendor/`, el motor externo. El secuenciador permanece fuera de la navegación; no se reactivan sus samples remotos.
