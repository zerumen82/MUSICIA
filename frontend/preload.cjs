/**
 * Puente seguro entre la UI y Electron (contextIsolation activa).
 * Solo expone lo mínimo: pedir el cierre de la app con una acción concreta.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('musica', {
  /** action: 'stop-all' | 'keep' | 'ask' */
  exit: (action) => ipcRenderer.invoke('musica:exit', action),
});
