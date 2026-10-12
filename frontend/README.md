# Frontend de Musicia

React 19, Vite, Tailwind y Electron. La navegación activa ofrece CREAR, SUBIR, MEZCLA y BIBLIOTECA. El cliente HTTP común está en `src/api.js`; los límites y defaults proceden de la API local.

## Desarrollo y build

Con las dependencias aprobadas e instaladas, desde `frontend/`:

```powershell
npm run dev
npm run lint
npm run build
node --test src/prompt_gloss.test.js src/audio_player.test.js src/audio_comparison.test.js
```

`dev` abre el servidor HMR para desarrollo. En producción, FastAPI sirve `dist/` en `http://127.0.0.1:8000`; cada cambio de UI requiere build. `main.cjs` es el proceso principal de Electron y usa `contextIsolation` y sandbox. La ventana se inicia desde la raíz mediante `scripts/open_musicia.ps1`; `start_local.ps1` inicia solo servicios. La X se ignora y SALIR cierra la aplicación y detiene API y motor.

## Componentes y criterios

- `Composer.jsx`: prompt, controles de canción y letra; no añade recetas musicales automáticamente.
- `Uploads.jsx` y `Library.jsx`: fuentes y acceso a REMIX; `RemixActions.jsx` abre `RemixWorkspace.jsx` para canción completa, tramo y grupos reales.
- `Waveform.jsx`: onda y selección regional; `MixLab.jsx`: mezcla real mediante ffmpeg.
- `JobsPanel.jsx` y `App.jsx`: trabajos, fase, errores, PARAR y estado local del motor.

`Mixer.jsx` no se monta y `Sequencer.jsx` sigue retirado de la navegación. La locución fue eliminada; el canto se genera con ACE-Step en CREAR.

El cierre de R9/R10 está en corrección tras la auditoría del 2026-10-13. Las pruebas de contrato no sustituyen los recorridos reales en Electron a 1400×900 y 1080×700, la comparación alineada, la cancelación ni la escucha musical. Estado y evidencia: [pendientes](../spec/03-PENDIENTES.md), [plan](../spec/06-REMIX-INTEGRAL.md) y [memory.md](../memory.md). HECHO requiere PASS del tester y APPROVE del reviewer.
