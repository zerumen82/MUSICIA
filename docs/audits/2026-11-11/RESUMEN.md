# Auditoría técnica de Musicia — 2026-11-11

**Resultado: PASS del tester y APPROVE del reviewer para las once correcciones y los recorridos documentados.** La aplicación quedó abierta desde su lanzador normal para las pruebas del usuario. No se certifica fidelidad artística ni se cierran por inferencia R9/R10/B6/B7/Q2/R18.

## Qué se corrigió

1. Solo las pistas en transformar aportan exclusiones al prompt; se conserva su texto al cambiar de acción.
2. CREAR vuelve a funcionar bajo StrictMode de desarrollo.
3. SIN CUADRAR permite mezclar aunque no se pueda medir el pulso.
4. La onda se recupera de cortes de transporte y reinicia su estado al cambiar de fuente.
5. Las subidas hechas por otro cliente aparecen sin refresco manual.
6. API y panel rechazan lotes/pasos no positivos y guidance negativo o no finito; sin máximos inventados ni cambio de defaults.
7. Electron activa sandbox, mantiene aislamiento y restringe navegación, apertura externa e IPC de salida.
8. Groove, plan de mezcla, análisis de subida y picos dejan libre el bucle de la API.
9. El arranque/parada reintenta exclusivamente BUSY dentro de un único plazo configurado, conservando los demás errores.
10. Pausar o cambiar A/B no muestra como fallo la cancelación normal de play; los errores de medios/permisos siguen visibles.
11. Lanzador, supervisor y parada dejan de atribuir cualquier backend/main.py a Musicia. La API se inicia con ruta absoluta y se revalida por ruta, PID, fecha, ejecutable y comando antes de actuar; una identidad dudosa impide parar o anunciar un reinicio exitoso.

## Evidencia final

| Comprobación | Resultado | Archivo |
|---|---|---|
| Backend completo sobre fuentes finales | 466 pruebas: 464 PASS, 2 omitidas, 0 fallos/errores; 310,038 s, exit 0 | backend-suite-validated.log; backend-validated-process.json |
| Frontend | 77/77, lint y build exit 0 | frontend-ab-final-process.json; frontend-node-ab-final.log |
| Revisión independiente | APPROVE; 20/20 SHA-256 coincidentes | reviewer-final.md; reviewer-source-sha256.json |
| Verificación independiente | PASS de criterios cubiertos, con límites explícitos | tester-final.md; tester-final.json |
| UI desde el Electron real y dos tamaños | 21 comprobaciones PASS; 1400×900 y 1080×700 | functional-05/result.json |
| Recuperación, subida externa, consola, DSP y A/B sin falso error | 5/5 PASS | recovery-03/result.json; recovery-03/ab-shared-interval.png |
| Parámetros inválidos | 28 peticiones reales rechazadas con HTTP 422 | advanced-http-after.json |
| Generación GPU enviada desde CREAR | Job 1a7bdbf4b1504a5ba764bba572f338e7 succeeded, SFT/50/9/batch2; dos MP3 de 20 s/321068 bytes, ffprobe y descarga HTTP verificados | production-generation-02/; production-delivery-validation/; tester-production-audio.json |
| StrictMode y PARAR | Envío real desde Vite, cancelación durante inicialización y retorno a reposo; no acredita todas las fases | strictmode-cancel-01/result.json |
| Ampliación y mezcla reales desde UI | MP3 de 35 s y 20 s, ffprobe exit 0 | tester-functional-audio.json |
| Disponibilidad durante groove | 57 respuestas de salud HTTP 200 durante 18,177 s de análisis; máximo 0,359 s en esta pasada | api-responsiveness-controlled.json |
| Identidad de API y PowerShell | 25 pruebas focales PASS; tres scripts sin errores de parser | api-identity-focal-final.log; api-identity-parser-final.json |
| Arranque frío y proceso ajeno de más de 60 s | API propia disponible; fixture ajena con identidad intacta, ya tenía 103 s al arrancar | guard-aged-cold-result.json; guard-aged-cold-analysis.json |
| Parada real y SALIR por botón/IPC | exit 0, sin API ni listeners 8000/8001; fixture ajena intacta | guard-stop-result.json; exit-01-result.json |
| Lanzador público | Ventana normal responde y API disponible; proceso ajeno preservado | public-launch-result.json |

Los informes originales de intentos fallidos se conservan. En particular, production-generation-02 terminó con error del driver al buscar extensiones .mp3 en filas que muestran el nombre sin extensión: el job y los audios sí terminaron correctamente. Se revalidó **ese mismo job**, sin repetir la generación, en production-delivery-validation. La cancelación comprobada ocurrió durante inicialización, no durante difusión/descarga.

La pasada completa anterior de 457 tests tuvo un rechazo de identidad al limpiar una fixture. No se afirmó si era reutilización real o metadatos CIM transitorios: se reforzó la preparación/espera de snapshots sin relajar la identidad ni señalar procesos dudosos. La nueva suite completa quedó verde. No se omitieron esos fallos ni se cambiaron umbrales musicales.

## Qué sigue abierto

- Escucha y aprobación musical; fidelidad de negaciones, estilo y aislamiento en el uso general.
- Cierres integrales R9/R10/B6/B7/Q2/R18. Las pruebas nuevas amplían evidencia, sin completar automáticamente todos sus criterios.
- No se generó en esta pasada un audio GPU nuevo para cada combinación individual de cover, repaint, voz original con base nueva y grupos transformados; formularios/contratos y recorridos ejecutados están diferenciados en spec/02.
- Otras rutas DSP de escritura siguen siendo síncronas; la mejora de disponibilidad no es una garantía para todas las operaciones.
- Criba B8 estéreo y aviso de letras pendientes, además del monitor global de procesos Electron del lanzador. Ver spec/03-PENDIENTES.md.
- Los procesos API antiguos con argumentos relativos o identidad incompleta se preservan. Solo se migró la API de esta sesión tras acreditar su identidad y ausencia de trabajos activos.

## Estado entregado

Musicia se abrió con scripts/open_musicia.ps1 y su entorno normal, sin los overrides temporales de separación CPU o modo offline de los verificadores. Se cerraron el Vite y las fixtures propias de la auditoría; se conservaron audios, capturas y logs de evidencia. No se instalaron paquetes, modelos ni skills, no se cambiaron los defaults SFT y no se hicieron commits ni push.

La primera generación tras reposo recarga los modelos locales. Las pruebas de audio se ejecutaron localmente; las únicas consultas web de investigación fueron documentación oficial de Electron/Chromium.
