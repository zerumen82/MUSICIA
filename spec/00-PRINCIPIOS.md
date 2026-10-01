# 00 · Principios — Constitución del proyecto (SDD)

> **Fuente de verdad suprema.** Todo el resto de la especificación y todo el
> trabajo de los agentes se subordina a este documento. Si hay conflicto, gana
> este archivo.

## 1. Las cinco reglas innegociables

| # | Regla | Significado operativo |
|---|-------|----------------------|
| R1 | **NO HARDCODE** | Cero valores mágicos en código. Todo parámetro vive en `backend/config.py` (overridable por `config.json` o vars `MUSICIA_*`). Los textos de UI viven en constantes junto al componente, no dispersos. |
| R2 | **NO STUB** | Prohibido entregar funciones vacías, `pass`, TODO sin plan fechado, endpoints que devuelven éxito sin trabajar, o UI que "parece" pero no funciona. Lo no implementado se declara, no se simula. |
| R3 | **NO FAKE** | Prohibidos mocks en producción, datos inventados, éxitos no verificados. Toda afirmación de "funciona" exige evidencia: comando ejecutado + salida real pegada en la bitácora. |
| R4 | **LOCAL-FIRST** | La generación de música/voz corre en la máquina del usuario. Cualquier dependencia de red (edge-tts, samples de Tone.js) debe estar declarada en `memory.md`. |
| R5 | **BITÁCORA** | Cada decisión, prueba y resultado se registra en `memory.md` con fecha y evidencia. Trabajo no registrado = trabajo no hecho. |

## 2. Definición de Listo (DoD) — una tarea NO está terminada sin TODO esto

1. ✅ **Código funciona**: ejecución real con salida verificada (no "debería funcionar").
2. ✅ **Lint en verde**: `npm run lint` sin errores.
3. ✅ **Build en verde**: `npm run build` (frontend) o `py_compile` (backend).
4. ✅ **Verificación de comportamiento**: para audio → archivo existe y duración > 0 (ffprobe/pydub). Para UI → montada y servida. Para API → endpoint responde con datos reales.
5. ✅ **Sin regressión**: lo que ya funcionaba sigue funcionando.
6. ✅ **Config, no hardcode**: nuevos parámetros en `config.py`/`config.json`.
7. ✅ **Bitácora actualizada** en `memory.md` con la evidencia.

> Un agente que declara "listo" sin estos 7 puntos está mintiendo. Cualquier
> otro agente tiene el deber de rechazar el trabajo y devolverlo.

## 3. Cadena de especificación (SDD)

```
spec/00-PRINCIPIOS.md      ← constitución (este archivo)
spec/01-ARQUITECTURA.md    ← sistema, módulos, contratos de datos
spec/02-REQUISITOS.md      ← historias de usuario priorizadas, criterios de aceptación
spec/03-PENDIENTES.md      ← backlog vivo y deudas técnicas
```

**Regla de oro SDD**: primero se especifica, luego se implementa. Si el código
y la especificación discrepan, se corrige el que esté mal — y se decide cuál es
en la bitácora, no en silencio.

## 4. Verificación como ciudadanía

- La **única** prueba válida de algo asíncrono (generación de música) es
  esperar el resultado real. No se acepta "el motor seguramente terminó".
- Los archivos de audio se validan SIEMPRE: existencia + tamaño > 0 + duración
  > 0 (ffprobe o pydub), nunca solo "no hubo error".
- Los fallos se propagan con su mensaje real. Prohibido tragar excepciones.

## 5. Estilo de trabajo

- Español en UI, bitácora y especificación; inglés en identificadores de código.
- Commits pequeños con intención clara (cuando el usuario pida commits).
- Antes de instalar cualquier dependencia nueva: justificarlo en la bitácora
  (peso, licencia, alternativa local).
