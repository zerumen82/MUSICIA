# 04 · Ejército de agentes (SDD)

Hay dos capas. No se sustituyen.

1. **Ejército global** (`~/.agents/`, seis agentes): cualquier cambio de software, en este proyecto y en los demás. Fuente de reglas: `~/.agents/AGENTS.md`.
2. **Agentes musicales** (`.agents/` de Musicia, tres): una pieza concreta. Generan con ACE-Step 1.5. No deciden el producto.

El usuario es el orchestrator supremo en las dos capas.

## Jerarquía del software

```
        ┌─────────────────────────────┐
        │   TÚ (usuario/orchestrator) │   ← palabra final sobre TODO
        └──────────────┬──────────────┘
                       │ aprueba / decide / veto
        ┌──────────────▼──────────────┐
        │       sd-coordinator        │   ← PREGUNTA antes de decidir
        └───┬─────────┬─────────┬─────┘
            │         │         │
      ┌─────▼───┐ ┌──▼──────┐ ┌▼───────────┐
      │sd-editor│ │sd-      │ │sd-scout /  │
      │implement│ │reviewer │ │sd-researcher│
      └─────────┘ └─────────┘ └────────────┘
      ┌─────────────┐
      │  sd-tester  │ ← verificación funcional (última palabra de "funciona")
      └─────────────┘
```

## Los seis agentes globales

| Agente | Rol | Modelo | Herramienta clave |
|--------|-----|--------|-------------------|
| **sd-coordinator** | Flujo SDD, spec/, delega, pregunta | gpt-5.2 | `ask_user` |
| **sd-editor** | Implementa la historia aprobada | glm-4.7 | editar + lint/build |
| **sd-reviewer** | Calidad, seguridad, reglas. APPROVE o CHANGES_REQUESTED | claude-sonnet-4.6 | leer y buscar |
| **sd-tester** | Criterios con evidencia. PASS o FAIL | qwen3-coder-plus | ejecutar |
| **sd-scout** | Busca skills. Instala solo tras `ask_user` | gemini-2.5-flash | `ask_user` + `npx skills find` |
| **sd-researcher** | Docs, versiones, licencias, con URL leída | gemini-2.5-flash | web + lectura de la fuente |

`sd-scout` tiene `ask_user` en sus herramientas desde el 2026-10-02 (antes el prompt lo exigía y la lista no lo incluía).

## Flujo SDD de una historia

```
1. Petición del usuario
2. coordinator lee spec/ y memory.md
3. ¿Está especificada? ──no──► redacta historia + criterios ──► PREGUNTA al usuario
        │ sí                                                          │
        ▼                                                             ▼
4. sd-scout (¿hay skill?) y sd-researcher (¿qué hay que saber?)
        │
5. coordinator delega en sd-editor ◄────────────────────── usuario aprueba
        │
6. sd-editor implementa (NO HARDCODE, NO STUB, NO FAKE, LOCAL-FIRST, BITÁCORA)
        │
7. sd-reviewer ──CHANGES_REQUESTED──► sd-editor corrige (vuelta a 7)
        │ APPROVE
        ▼
8. sd-tester verifica con evidencia real
        │
   FAIL y hay varias vías ──► PREGUNTA al usuario ──► vuelta al paso 5
        │ PASS
        ▼
9. coordinator: spec/02 (estado) + memory.md (evidencia)
10. HECHO — solo con PASS y APPROVE
```

## Agentes musicales (este repo)

| Agente | Rol | Modelo |
|--------|-----|--------|
| **music-orchestrator** | Pregunta, reparte, verifica el audio | gpt-5.2 |
| **music-composer** | Spec JSON de la pieza (no genera audio) | claude-sonnet-4.6 |
| **audio-engineer** | ACE-Step, ffmpeg, demucs, y comprueba el archivo | qwen3-coder-plus |

```
petición musical
  → music-orchestrator (ask_user si el alcance no está cerrado)
      → music-composer  (JSON: bpm, key_scale, estructura, letra, nombre)
      → audio-engineer  (archivo real, duración > 0)
      → memory.md
```

Motor: ACE-Step 1.5 (Apache 2.0). MusicGen / audiocraft quedan fuera (CC-BY-NC).

En Codebuff se invocan por id (`sd-coordinator`, `music-orchestrator`, …). En un CLI sin ese spawn, el mismo prompt se usa como encargo del rol. El veredicto del tester y del reviewer se escribe igual en `memory.md`.

## Especificación (spec/, dentro de cada proyecto)

| Archivo | Contenido |
|---------|-----------|
| `00-PRINCIPIOS.md` | Constitución: reglas innegociables + Definición de Listo |
| `01-ARQUITECTURA.md` | Procesos, contratos, módulos, decisiones |
| `02-REQUISITOS.md` | Historias con criterios de aceptación y estado |
| `03-PENDIENTES.md` | Deudas declaradas, riesgos, orden sugerido |
| `04-EJERCITO.md` | Este documento |
