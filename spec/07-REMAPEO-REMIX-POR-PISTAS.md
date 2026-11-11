# 07 · Mapeo de remix por pistas — Grupos y acciones

> **Propósito**: Documentar qué hay en cada grupo Demucs y cómo mapear las decisiones del usuario a configuraciones de grupos + acciones. Documenta el problema B7: "ninguna opción garantiza el estilo pedido".

**Estado documental 2026-11-11:** contratos sincronizados y auditoría técnica validada en el alcance de spec/02: 466 backend (dos omitidos), 77 frontend/lint/build, reviewer APPROVE + tester PASS y 20 fuentes coincidentes. Escenarios musicales A–D siguen provisionales: la nueva prueba Por pistas ejecutó conservar/quitar/ampliar R19 sin inferencia, con MP3 real de 35 s; los previews de grupos-transform no equivalen a una nueva inferencia GPU individual. La generación GPU nueva de dos MP3 de 20 s fue CREAR instrumental. Evidencias `logs/audit-ui-20261111/`; sin aprobación artística global ni cierre integral R9/R10/B6/B7.

## 1. Los 4 grupos reales de Demucs

| ID | Nombre común | Qué contiene | Notas |
|----|-------------|--------------|-------|
| `vocals` | Voz | Cantante principal, rap | Dominante en canciones con letra |
| `drums` | Batería | Bombo, platillos, percusión | "Corazón rítmico" de la pista |
| `bass` | Bajo | Línea de bajo armónica | Base armónica fundamental |
| `other` | Acompañamiento | Resto (guitarra, teclados, strings) | "Cesto de lo que no sea voz/batería/bajo" |

**Fuente**: `backend/source_understanding.py`, `backend/separator_service.py` (Demucs).
**Validación**: El frontend los recibe como `config.groups` con estos 4 IDs.

## 2. Las 3 acciones por grupo

Para cada grupo, el usuario elige una acción. En una ejecución solo una está activa por grupo:

| Acción | Qué hace | Cuándo usarla |
|--------|----------|---------------|
| `keep` | Conservar la grabación del grupo, sujeta a ganancia y al tempo común pedidos | "Quiero conservar este material" |
| `transform` | Generar una versión del material seleccionado con el prompt y seleccionar/recombinar los grupos del resultado | "Quiero que suene diferente, con ese estilo" |
| `remove` | Quitar el grupo del resultado | "Quiero quitar la batería/voz" |

**Contrato comprobado en código (2026-10-26)**: una operación con grupos en `transform` exige un prompt de estilo no vacío; la validación rechaza la petición si falta. El motor recibe un caption global compuesto con las instrucciones por pista y después se seleccionan los grupos transformados. Esto no garantiza aislamiento ni fidelidad musical. Conservar/quitar y ampliar por repetición R19 no requieren prompt ni inferencia musical nueva.

**Ampliación vigente (R19)**: después de crear la mezcla, una duración mayor repite material real de esa mezcla con transiciones. Sin recorte se repite la mezcla completa; con recorte se repite el intervalo mapeado al tempo efectivo. Con reloj acreditado las costuras se alinean al pulso; una mezcla incierta usa crossfade simple y aviso. `continue_bed` y sus reintentos B8/B8b quedan conservados como maquinaria histórica, sin activarse en esta ampliación Por pistas.

## 3. Mapeo de escenarios comunes (propuesto)

**ESTO NO ES definitivo** — guía inicial basada en usos típicos, sujeto a verificación (por eso B7/R9-R10 están pendientes).

### Escenario A: "Remix que mantiene la voz pero cambia el estilo"
| Grupo | Acción | Comentario |
|-------|--------|------------|
| `vocals` | `keep` | Conservar letra/melodía |
| `drums` | `transform` | Cambiar patrón rítmico al nuevo estilo |
| `bass` | `transform` | Cambiar línea de bajo |
| `other` | `transform` | Cambiar instrumentación |
| **Resultado** | Voz original + base nueva al estilo pedido |

### Escenario B: "Versión instrumental (quitar voz)"
| Grupo | Acción | Comentario |
|-------|--------|------------|
| `vocals` | `remove` | Sin voz |
| `drums` | `keep` | Mantener batería |
| `bass` | `keep` | Mantener bajo |
| `other` | `keep` | Mantener los demás instrumentos |
| **Resultado** | Pista instrumental completa |

### Escenario C: "Remix electrónico (batería y bajo destacados)"
| Grupo | Acción | Comentario |
|-------|--------|------------|
| `vocals` | `remove` | Quitar voz (electrónica a veces no tiene) |
| `drums` | `keep` | Patrón de batería original |
| `bass` | `transform` | Patrón de bajo al estilo electrónico |
| `other` | `transform` | Texturas a synths/arpegios |
| **Resultado** | Batería original + bajo + texturas transformadas |

### Escenario D: "Solo acompañamiento, quitar batería y bajo"
| Grupo | Acción | Comentario |
|-------|--------|------------|
| `vocals` | `keep` | Conservar si hay voz |
| `drums` | `remove` | Quitar batería |
| `bass` | `remove` | Quitar bajo |
| `other` | `keep` | Conservar guitarras/teclados |
| **Resultado** | Voz + texturas, sin ritmo batería/bajo originales |

## 4. Dudas e incertidumbres (por qué esto aún está pendiente)

| Dudas | Por qué importa |
|-------|----------------|
| Fidelidad de `transform` con prompt válido | La petición sin prompt se rechaza; queda verificar con audio el estilo y aislamiento del resultado aceptado |
| Aislamiento dentro de `other` | Contiene el acompañamiento restante; no permite seleccionar guitarra y teclado como stems independientes. La calidad audible al transformarlo sigue pendiente |
| Efecto acumulativo de acciones | ¿El motor entiende dos `transform` simultáneas? ¿Una anula a la otra? |
| BPM/tempo común | El control es global y prepara los cuatro grupos con tempo común; no existen cuatro controles de BPM independientes. Falta cerrar B6 contra todos los casos reales |
| BPM original en remix por pistas | La medición del original es revisable manualmente; su procedencia e incertidumbre deben conservarse. No se infiere que el BPM pedido al motor sea el BPM final medido |

**Por qué esto está pendiente**: el usuario no sabe qué poner porque el comportamiento real depende de implementaciones internas no documentadas claramente. El mapeo anterior es una **guía provisional**, no un contrato garantizado.

## 5. Próximos pasos para cerrar este conocimiento

Según spec/03-PENDIENTES.md y el flujo SDD, para pasar de "guía provisional" a "conocimiento verificado":

1. **[B6]**: Ejecutar pruebas de variantes con DSP local BPM, medir resultados reales
2. **[B7] cierre**: El usuario escucha los escenarios A–D con audio real y sentencia si cumplen lo pedido. Esa escucha corresponde a la aprobación musical.
3. **[R9/R10]**: Verificar explícitamente sus propios criterios de UI/API, preview/envío, selección, comparación y trazabilidad. Ni B6 ni la escucha B7 sustituyen esos recorridos ni producen un cierre integral automático.

**Este documento se queda como conocimiento registrado**. No implica comportamiento garantizado, pero documenta el estado actual para que futuras decisiones no reinventen la rueda.
