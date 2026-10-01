# 03 · Péndientes y deudas técnicas (backlog vivo)

> Lo que aquí aparece **declarado** no es un stub oculto: es deuda reconocida
> con plan. Lo peligroso es lo que NO está aquí y debería estar.

## Deudas técnicas (por prioridad)

| ID | Deuda | Impacto | Origen | Plan |
|----|-------|---------|--------|------|
| T1 | Mezclador (Mixer.jsx) 100% decorativo: faders que no suenan | R2 violada de forma visible; expectativa falsa en el usuario | UI heredada del template | [C1] conectar a `/audio/mix` + pistas del historial |
| T2 | Secuenciador depende de samples remotos (tonejs.github.io) | R4: sin internet no suena | Template Tone.js | [C2] empaquetar samples locales |
| T3 | Chunk de 624 kB en el build del frontend | primera carga lenta en la ventana | Vite sin code-split | manualChunks: react, tone, framer-motion |
| T4 | `backend/venv` con pip 22 (Python 3.10 sin actualizar pip) | avisos e instalaciones lentas | heredado | `python -m pip install -U pip` |
| T5 | pip global del usuario con índice NVIDIA roto (DNS falla) | ralentiza TODA instalación pip del sistema | config del sistema | quitar `extra-index-url` de la config global de pip |
| T6 | Sin tests automatizados | regresiones solo detectables a mano | proyecto joven |pytest para config/music_service (verificar_audio, build_payload, _download_target) |

## Bugs conocidos no resueltos

| ID | Bug | Estado |
|----|-----|--------|
| — | (ninguno abierto; los cerrados están en memory.md con su fix) | ✅ |

## Puntos de vigilancia (no son bugs, pero pueden romper)

| ID | Riesgo | Vigilancia |
|----|--------|-----------|
| W1 | VRAM: pico medido 6.9 GB de 8 GB → margen estrecho | si se añaden pistas más largas o batch > 1, medir VRAM con nvidia-smi ANTES de dar por bueno el cambio |
| W2 | Los procesos de motor/API son externos al script: si el usuario los mata a mano, la UI debe degradar con mensaje claro | comprobar el estado del panel "motor caído" |
| W3 | La primera ejecución descarga ~10 GB de pesos | documentado en open_musicia.ps1 y UI |

## Próximas historias candidatas (orden sugerido)

1. [A3] Generación con voz — el backend ya está; falta UI + verificación
2. [D2] Estado real del motor en la barra lateral — barato y evita confusión
3. [T1] Conectar el mezclador — elimina la mayor deuda R2 visible
4. [T6] Tests de music_service — protege el corazón del producto
5. [D3] Instalador — cuando el producto sea estable
