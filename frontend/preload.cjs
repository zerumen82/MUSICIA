/**
 * Puente seguro entre la UI y Electron (contextIsolation activa).
 * Solo expone el cierre. Cualquier llamada apaga motor y API: no hay
 * diálogo ni opción de dejarlos encendidos.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('musica', {
  exit: (action) => ipcRenderer.invoke('musica:exit', action),
});
