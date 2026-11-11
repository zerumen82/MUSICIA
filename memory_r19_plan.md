# Plan R19 — Por pistas alarga repitiendo material real (no generando música nueva)

**Fecha:** 2026-10-24
**Estado:** Aprobado por usuario ("sí"); correcciones técnicas verificadas el 2026-10-26, escucha `PENDING_USER`
**Historia registrada en:** `spec/02-REQUISITOS.md` — sección [R19]

**Seguimiento 2026-10-26:** implementación parcial revisada con CHANGES_REQUESTED + FAIL. El usuario autoriza corregir los hallazgos. Los fragmentos y números de línea de este plan son el diagnóstico original; el segundo ajuste DSP sí necesita volver a mapear el intervalo ya ajustado, y la transición positiva debe salir del plan inicial, no solo de `apply_groups_mix_tempo`. El fallback sin reloj conserva el BPM pedido como intención, sin fingir verificación. El cierre depende de evidencia nueva en `logs/fix-review-20261026/` y `memory.md`.

**Resultado de las correcciones:** tester PASS + reviewer APPROVE, 452 pruebas backend sin fallos (2 omitidas), 77 frontend, lint/build y recorridos reales UI/API. E2E GPU sobre extracto de «Animales muertos»: lote explícito 1, MP3 de 35,000000 s, cola PCM idéntica a la base repetida y coseno espectral MP3 0,9999979479. No se acredita la escucha ni el cierre integral R9/R10. Ver `tester-final.json` y `gpu-e2e.json` en la carpeta de evidencia anterior.

**Sincronización documental 2026-11-11:** este plan conserva el diagnóstico y los fragmentos originales como historia. El código vigente incluye las correcciones del 26/10; los fragmentos de abajo no deben copiarse para reemplazarlo. Auditoría técnica actual validada en su alcance: reviewer APPROVE de 11 correcciones + tester PASS, 466 backend (dos omitidos), 77 frontend/lint/build y 20 fuentes coincidentes. Evidencias `logs/audit-ui-20261111/`, matriz de cobertura en spec/02. La escucha no se convierte en PASS técnico ni se cierran historias musicales integrales.

**Nueva evidencia acotada 11/11:** `functional-05/result.json` ejecuta desde UI Por pistas sin prompt, conservación/quita y ampliación R19 mediante material real, con MP3 de 35 s verificado. Ese recorrido es CPU y no una nueva inferencia de grupos-transform. Los dos MP3 GPU de 20 s pertenecen a CREAR instrumental (`production-delivery-validation/`); no acreditan por sí solos R19 transformando grupos. La regresión final de 466 pruebas está verde. Escucha y criterios integrales R9/R10/B6/B7 conservan sus límites.

---

## Diagnóstico técnico (evidencia de código real)

### El problema diagnosticado el 24/10 (corregido; no describe el código vigente)
En **Por pistas** (`scope="groups"`), cuando la duración pedida supera la natural del original:
- `timeline_plan()` (línea 226) devuelve `"method": "continue_bed"`
- `run()` (línea 1700-1703) ejecuta `_continue_bed()` que **genera música NUEVA** con el motor (repaint de trozos máx. 90 s, solape 10 s, condicionado solo al prompt + BPM)
- El motor **no conoce la armonía/melodía/estructura** del original → el tramo extra "suena a otra cosa pegada"

### La solución existente (ya verificada)
`MixerService.extend_timeline()` (mixer_service.py:597) implementa **`repeat_crossfade`**:
- Repite material **REAL** del audio con fundidos lineales
- Con BPM verificado → costuras **alineadas al compás** (`seam_method="beat_clock_aligned"`)
- Sin BPM → crossfade simple (`seam_method="selected_interval_crossfade"`) + aviso honesto
- Configuración existente: `timeline_transition_seconds=0.1`, `timeline_min_repeat_seconds=1.0`, `timeline_max_repetitions=1200`
- **Determinista, sin GPU, sin sorteo aleatorio del LM**

---

## Cambios mínimos en `remix_project.py`

### 1. `timeline_plan()` (línea 169-228)
```python
# ANTES (línea 226):
"method": "continue_bed" if expanding else "original",

# DESPUÉS:
"method": "repeat_crossfade" if expanding else "original",
```

### 2. `apply_groups_mix_tempo()` (línea 499-550)
```python
# ANTES (línea 542-543):
if float(requested_duration) > adjusted:
    updated["method"] = "continue_bed"

# DESPUÉS:
if float(requested_duration) > adjusted:
    updated["method"] = "repeat_crossfade"
    if marked:
        span = updated["mapped_repeat_end"] - updated["mapped_repeat_start"]
        if span < config.timeline_min_repeat_seconds:
            raise ValueError("El recorte es demasiado corto para usarlo como sample")
```

### 3. `run()` — rama de expansión (línea 1699-1710)
```python
# ANTES: variant_plan["method"] == "continue_bed" → _continue_bed()
# DESPUÉS: variant_plan["method"] == "repeat_crossfade" → MixerService.extend_timeline()
# (El código ya existe en línea 1705-1710, solo cambia la condición)
```

### 4. Avisos de preview (líneas 805, 1079)
```python
# ANTES: "el motor continúa el final de esa base..."
# DESPUÉS: "se repite material real de la canción con transiciones..."
```

### 5. `uncertain_extension_fallback()` (línea 385-404)
- **Ya no aplica** para `repeat_crossfade` (la medición final usa `tempo_after_repetition` que sí soporta `repeat_crossfade`)
- Se conserva el código para R17 (canción completa con `continue_bed`)

---

## Contratos de tempo que NO cambian

| Función | Comportamiento con `repeat_crossfade` |
|---------|----------------------------------------|
| `required_measured_tempo()` | Llama a `tempo_after_repetition()` si `arrangement.method == "repeat_crossfade"` ✓ |
| `tempo_after_repetition()` | Ya soporta `repeat_crossfade` (línea 269) — **no tocar** ✓ |
| `groups_tempo_ratio()` | Igual ✓ |
| `verify_requested_tempo()` | Igual ✓ |

---

## Tests a actualizar (contrato viejo `continue_bed` → `repeat_crossfade`)

### `test_remix_timeline.py`
- L82, 180, 353, 389, 453, 574, 589, 811

### `test_kick_alignment.py`
- L201: `plan["method"]` en fixture histórica

### `test_remix_recovery.py`
- L429, 436, 472: Fixtures de recuperación simulan `continue_bed` → actualizar a `repeat_crossfade`

---

## Criterios de aceptación R19 (de spec/02)

- [x] `timeline_plan`/`apply_groups_mix_tempo` con scope groups + expansión devuelven `method=repeat_crossfade`
- [x] `mapped_repeat_start/end`: 0..natural (sin recorte) o intervalo marcado
- [x] `extend_timeline` alcanza duración objetivo sin silencio, respeta config
- [x] Con BPM y reloj verificado: `seam_method=beat_clock_aligned`
- [x] Sin reloj: crossfade simple + aviso existente (no inventa reloj)
- [x] Recorte marcado se repite N veces; sin recorte → canción entera
- [x] Duración final ffprobe dentro de tolerancia
- [x] Regresiones: Por pistas sin expansión intacto; R17 intacto; suites verdes + lint/build
- [x] E2E real GPU: Por pistas ampliada sobre extracto de "Animales muertos.mp3" → cola = material real de la mezcla repetida (PCM y prueba espectral)
- [ ] Oído del usuario: `PENDING_USER`
- [x] tester PASS + reviewer APPROVE + memory.md

---

## Secuencia prevista (ejecutada; ver resultados del 2026-10-26 arriba)

1. **Escribir tests R19 nuevos** en `test_remix_timeline.py` (fallan primero)
2. **Implementar cambios** en `remix_project.py` (puntos 1-5 arriba)
3. **Actualizar tests de contrato viejo** (lista arriba)
4. **Suite completa** backend + frontend + lint/build
5. **E2E real GPU** con "Animales muertos.mp3"
6. **Cierre**: tester PASS + reviewer APPROVE + memory.md
