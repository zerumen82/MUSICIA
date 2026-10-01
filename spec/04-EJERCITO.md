# 04 · Ejército de agentes (SDD)

## Jerarquía

```
        ┌─────────────────────────────┐
        │   TÚ (usuario/orchestrator) │   ← palabra final sobre TODO
        └──────────────┬──────────────┘
                       │ aprueba / decide / veto
        ┌──────────────▼──────────────┐
        │       sd-coordinator        │   ← PREGUNTA antes de decidir
        │  (global, ~/.agents/)       │
        └───┬─────────┬─────────┬─────┘
            │         │         │
      ┌─────▼───┐ ┌──▼──────┐ ┌▼───────────┐
      │sd-editor│ │sd-      │ │sd-scout /  │
      │implement│ │reviewer │ │sd-researcher│
      └─────────┘ │calidad  │ └────────────┘
                  └─────────┘
      ┌─────────────┐
      │  sd-tester  │ ← verificación funcional (última palabra)
      └─────────────┘
```

## Los tres agentes (globales, en `~/.agents/` — sirven para todos tus proyectos)

| Agente | Rol | Modelo | Puede |
|--------|-----|--------|-------|
| **sd-coordinator** | Manda el flujo SDD, mantiene spec/, delega | gpt-5.2 | preguntarte (ask_user), delegar, editar spec/ y memory.md |
| **sd-editor** | Implementa historias aprobadas | glm-4.7 | leer/editar código, ejecutar lint/build |
| **sd-reviewer** | Revisa calidad: seguridad, reglas, mantenibilidad. APPROVE/CHANGES_REQUESTED | claude-sonnet-4.6 | leer, buscar patrones, lint/build |
| **sd-tester** | Verifica con evidencia real; su veredicto es la última palabra | qwen3-coder-plus | leer, ejecutar comandos de verificación |

Ninguno decide alcance solo. El coordinador te pregunta con `ask_user` antes de:
cambiar alcance, elegir tecnologías/dependencias, tocar la especificación,
priorizar cuando hay ambigüedad, o ante cualquier acción destructiva.

## Flujo SDD de una historia

```
1. Petición del usuario
2. coordinator lee spec/ y memory.md
3. ¿Está especificada? ──no──► redacta historia + criterios ──► PREGUNTA al usuario
        │ sí                                                          │
        ▼                                                             ▼
4. coordinator delega en sd-editor ◄────────────────────── usuario aprueba
        │
5. sd-editor implementa (reglas: NO HARDCODE, NO STUB, NO FAKE)
        │
6. sd-reviewer revisa calidad ──CHANGES_REQUESTED──► sd-editor corrige (vuelta a 6)
        │ APPROVE
        ▼
7. sd-tester verifica (criterios exactos, evidencia real)
        │
   ┌────▼─────┐  FAIL   diagnostico ──► ¿varias vías? ──► PREGUNTA al usuario
   │ sd-tester │ ◄────────────────────────────┐ │
   └────┬─────┘                               ▼ ▼
        │ PASS                        volver al paso 4
        ▼
8. coordinator: actualiza spec/02 (estado) + memory.md (evidencia)
9. HECHO — reporta al usuario
```

## Cómo usarlo desde Codebuff

- **"usa sd-coordinator para X"** → flujos completos con método.
- **"usa sd-editor para X"** → solo implementación (para cambios triviales).
- **"usa sd-tester para X"** → solo verificación independiente.

## Especificación (spec/, dentro de cada proyecto)

| Archivo | Contenido |
|---------|-----------|
| `00-PRINCIPIOS.md` | Constitución: reglas innegociables + Definición de Listo |
| `01-ARQUITECTURA.md` | Procesos, contratos, módulos, decisiones |
| `02-REQUISITOS.md` | Historias de usuario con criterios de aceptación y estado |
| `03-PENDIENTES.md` | Deudas técnicas declaradas, riesgos, orden sugerido |
| `04-EJERCITO.md` | Este documento |
