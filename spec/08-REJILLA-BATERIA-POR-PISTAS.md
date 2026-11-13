# 08 · Rejilla de batería en «Cambiar por pistas» — plan pendiente de aprobación

> **Estado:** implementado en 1.3.8 (2026-11-13). Código en backend y frontend. El
> requisito está en `spec/02-REQUISITOS.md` como `[R28]`, con sus criterios sin
> marcar. La aprobación del usuario es condición para empezar.

## 1. Contexto

Hoy la rejilla de batería de `[R20.F]` solo existe en **Secuencia de pasos**:
16 pasos × bombo, caja, charles y platillo, oculta y desactivada por defecto,
traducida a una frase inglesa que se antepone al caption del paso. La acción
**Cambiar por pistas** no monta ninguna rejilla: solo ofrece los cuatro grupos
reales de Demucs (voz, batería, bajo, acompañamiento restante) con conservar,
transformar o quitar, volumen, BPM común y duración.

La petición es poder marcar golpes de batería sobre la fila **BATERÍA** cuando
esa fila está en *transformar*, sin cambiar la semántica del resto de filas ni
del modo Secuencia.

## 2. Cumplimiento de AGENTS.md

- **NO HARDCODE:** pasos (16), instrumentos, etiquetas y tolerancias salen de
  `config.py` / `/music/remix/capabilities`; React no inventa listas.
- **NO STUB / NO FAKE:** la rejilla no sonará ni prometerá condicionamiento
  temporal. Viaja como texto y solo el bombo se mide en la salida publicada,
  igual que `[R20.F]`. Si el motor no obedece, se declara sin éxito falso.
- **LOCAL-FIRST:** reutiliza demucs y ACE-Step instalados; sin servicios nuevos
  ni descargas.
- **Perfil aprobado:** SFT, 50 pasos, guidance 9, lote 2, thinking/use_format
  off. No se toca.
- **BITÁCORA + entrega:** entrada en `memory.md`, versión visible, `dist` y
  `Musicia.exe` recompilados, PASS del tester + APPROVE del reviewer.

## 3. Decisiones que debe aprobar el usuario

1. **Solo la fila Batería.** La rejilla no se ofrece en voz, bajo ni
   acompañamiento: sus filas (bombo, caja, charles, platillo) no tienen
   significado verificable en esos grupos. Si se pide otra fila, no hay rejilla.
2. **Solo con *transformar*.** En conservar o quitar la rejilla no se muestra y
   el backend rechaza un patrón para un grupo que no se transforma.
3. **Contrato propuesto:** `patterns: {"drums": {...}}` en la petición de
   `scope=groups`, con la misma forma y validación que `SequencePattern`. Un
   grupo desconocido o un patrón mal formado devuelve error explícito, no se
   ignora.
4. **El patrón es intención, no control rítmico.** Se compone con el mismo
   traductor de `[R20.F]` y se antepone al caption de la pista de batería. El
   preview y la ejecución usan el mismo constructor; el texto exacto se ve antes
   de enviar. No pasa por el traductor de estilo.
5. **Medición:** el bombo se mide sobre el **archivo final publicado**, en toda
   la pista (el patrón se repite en cada compás). Caja, charles y platillo son
   intención declarada. Si el paso no se puede medir, se declara sin medir.
6. **Reutilización de la separación:** si ya hay grupos válidos de esa fuente y
   firma, se reutilizan; el patrón entra en la firma de configuración para no
   reutilizar una separación como si el patrón no existiera.

## 4. Pasos de implementación (tras aprobación)

1. **Backend — contrato** (`backend/remix_project.py`): campo `patterns` en
   `RemixProjectRequest`, validación restringida a `drums` y a acción
   `transform`, y rechazo de patrones en otros ámbitos.
2. **Backend — caption** (`backend/remix_project.py`): componer el caption de la
   pista transformada con `step_caption(prompt, pattern)`; un solo constructor
   para preview y ejecución. Mantener el caption global del resto de pistas.
3. **Backend — capacidades** (`backend/remix_project.py`): declarar
   `groups_pattern: {"groups": ["drums"], "steps": 16, "instruments": [...]}` en
   `/music/remix/capabilities`; la UI no codifica nada.
4. **Backend — medición** (`backend/remix_project.py`): extender la medición de
   `[R20.F]` al archivo final de `scope=groups`, con `measurement_stage=
   final_output` y sin marcar aciertos cuando no se midió.
5. **UI** (`frontend/src/components/RemixWorkspace.jsx`,
   `frontend/src/components/SequencePattern.jsx`): reutilizar la rejilla como
   componente, montarla solo en la fila Batería en transformar, con el mismo
   estado oculto/desactivado y el mismo resumen. Nada de rejilla en las demás
   filas.
6. **Regresiones**: validación del contrato, caption idéntico preview/ejecución,
   payload sin patrón cuando está desactivado, y medición honesta.

## 5. Riesgos y límites

- **No hay condicionamiento por golpe.** El SFT instalado recibe prosa; la
  rejilla documenta la intención y mide el bombo, no ordena posiciones.
- **La batería nueva sigue saliendo de una canción nueva separada.** Es el mismo
  límite declarado de «Por pistas»: no es un stem generado en contexto.
- **Coste:** una separación (demucs) y una generación (cover) por variante; la
  rejilla no añade llamadas, pero el trabajo ya es caro.
- **No se toca** la rejilla de Secuencia, el perfil SFT, el master −14 LUFS ni
  las deudas T9–T12; no se instala nada.
- **Fuera de alcance:** rejillas para voz/bajo/acompañamiento, condicionamiento
  MIDI/audio real, y prometer que el motor obedecerá los golpes.

## 6. Impacto

- **Beneficio:** cierra la asimetría entre Secuencia y Por pistas para el único
  grupo con rejilla verificable, sin duplicar código: el mismo traductor, la
  misma validación y la misma medición.
- **No entorpece:** el campo es opcional; sin patrón, la petición y el audio se
  comportan exactamente como hoy. La UI oculta la rejilla salvo en Batería +
  transformar.
- **Deuda:** la calidad de la sustitución de batería y la obediencia del modelo
  siguen pendientes de escucha; se declaran.

## 7. Verificación prevista

- Unitarias: contrato (`patterns` solo drums/transform), caption (patrón delante,
  identidad de instrumentos), payload sin patrón vacío/desactivado, medición.
- Frontend: lint, pruebas Node y build; rejilla oculta por defecto y solo en la
  fila Batería.
- E2E real: una generación GPU de «Por pistas» con la batería en transformar y
  patrón marcado; archivo MP3 verificado con ffprobe, ficha con parámetros y
  `pattern_check` medido sobre la salida final. La escucha artística la hace el
  usuario.
- PASS del tester + APPROVE del reviewer sobre los archivos completos y entrada
  en `memory.md` antes de declarar nada HECHO.
