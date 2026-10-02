const { app, BrowserWindow, shell, dialog, ipcMain, Tray, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// El backend sirve el propio dist si existe; aquí solo abrimos la ventana.
const DIST_INDEX = path.join(__dirname, 'dist', 'index.html');
const DEV_URL = process.env.MUSICIA_DEV_URL || 'http://localhost:5173';
const API_URL = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const ICON_PATH = path.join(__dirname, 'build', 'icon.ico');
const PRELOAD_PATH = path.join(__dirname, 'preload.cjs');
const STOP_SCRIPT = path.join(__dirname, '..', 'scripts', 'stop_local.ps1');

let willQuit = false;
let mainWindow = null;
let tray = null;
let uiWatchTimer = null;

/**
 * Recarga la ventana cuando el bundle servido por la API cambia.
 *
 * Por qué: la X minimiza a la bandeja y el single-instance lock restaura la
 * ventana existente, así que tras un `npm run build` la app seguía mostrando
 * la UI vieja y parecía que el cambio no se aplicaba. Con esto, tras el build
 * la ventana se recarga sola.
 */
function startUiWatch() {
  const intervalMs = 4000;
  const fingerprint = (html) => {
    const m = /assets\/index-[A-Za-z0-9_-]+\.(js|css)/g;
    return (html.match(m) || []).join('|');
  };
  let last = null;

  const poll = async () => {
    if (willQuit || !mainWindow || mainWindow.isDestroyed()) return;
    try {
      const res = await fetch(API_URL, { cache: 'no-store' });
      const html = await res.text();
      const current = fingerprint(html);
      if (last === null) { last = current; return; }
      if (current && current !== last) {
        last = current;
        console.log(`[UI:RECARGA] bundle nuevo detectado (${current}), recargando`);
        mainWindow.reload();
      }
    } catch {
      // La API puede estar apagándose: silencioso, el siguiente ciclo reintenta.
    }
  };

  uiWatchTimer = setInterval(poll, intervalMs);
  poll();
}

/**
 * Salida segura con elección del usuario. `action`: 'ask' | 'stop-all' | 'keep'.
 * El botón SALIR de la UI manda 'stop-all' o 'keep' tras preguntar en la propia
 * app; el aspa de la ventana siempre pregunta con diálogo nativo.
 */
async function exitApp(action = 'ask') {
  const win = mainWindow;
  if (action === 'ask') {
    const { response } = await dialog.showMessageBox(win, {
      type: 'question',
      buttons: ['Cerrar todo (apaga el motor)', 'Dejar servicios activos', 'Cancelar'],
      defaultId: 0,
      cancelId: 2,
      title: 'Salir de Musicia',
      message: '¿Qué hacemos con el motor y la API al salir?',
      detail:
        'Apagar todo libera la GPU/VRAM. Dejarlos activos hace que la próxima ' +
        'apertura sea instantánea (el motor ya está cargado).',
    });
    if (response === 2) return false;
    if (response === 0) stopServices();
  } else if (action === 'stop-all') {
    stopServices();
  } // 'keep': no tocar servicios
  willQuit = true;
  if (tray) tray.destroy();
  app.quit();
  return true;
}

function stopServices() {
  try {
    spawn(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', STOP_SCRIPT],
      { detached: true, stdio: 'ignore', windowsHide: true },
    ).unref();
  } catch {
    /* si falla el script, los servicios siguen: no bloqueamos la salida */
  }
}

ipcMain.handle('musica:exit', (_event, action) => exitApp(action));

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1080,
    minHeight: 700,
    backgroundColor: '#0a0a0c',
    autoHideMenuBar: true,
    title: 'Musicia',
    show: false, // se muestra cuando está lista (evita ventana en blanco)
    icon: fs.existsSync(ICON_PATH) ? ICON_PATH : undefined,
    webPreferences: {
      contextIsolation: true, // seguro por defecto; sin nodeIntegration
      sandbox: false, // el preload necesita require('electron') para el puente
      preload: fs.existsSync(PRELOAD_PATH) ? PRELOAD_PATH : undefined,
    },
  });

  // Los enlaces externos se abren en el navegador del sistema, no dentro de la app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Diagnóstico: registrar errores de la página y fallos de carga en consola/log
  mainWindow.webContents.on('console-message', (_e, level, message, line, sourceId) => {
    if (level >= 2) console.log(`[UI:${level}] ${message} (${sourceId}:${line})`);
  });
  mainWindow.webContents.on('did-fail-load', (_e, code, desc, url) => {
    console.log(`[CARGA FALLIDA] ${code} ${desc} ${url}`);
  });
  mainWindow.webContents.on('render-process-gone', (_e, details) => {
    console.log(`[RENDER MUERTO] ${details.reason}`);
  });

  // Mostrar solo cuando el contenido esté pintado: nunca una ventana en blanco
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });
  // Fallback: si ready-to-show no llega (p.ej. API caída), mostrar a los 4 s
  setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
      mainWindow.show();
    }
  }, 4000);

  // Segunda instancia: en vez de duplicar, restaurar y enfocar la existente
  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
  } else {
    app.on('second-instance', () => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      }
    });
  }

  if (app.isPackaged === false && fs.existsSync(DIST_INDEX) === false) {
    mainWindow.loadURL(DEV_URL);
  } else {
    // Limpiar caché HTTP: tras cada build los assets cambian de nombre;
    // sin esto, Electron puede servir un bundle viejo y la UI rompe.
    mainWindow.webContents.session.clearCache().then(() => {
      mainWindow.loadURL(API_URL);
      startUiWatch();
    });
  }

  // La X NO cierra: minimiza a la bandeja. La única salida es el botón SALIR
  // de la UI (que apaga motor+API sin preguntar) o el icono de bandeja.
  mainWindow.on('close', (event) => {
    if (willQuit) return;
    event.preventDefault();
    mainWindow.hide();
  });

  // Clic en el icono de la bandeja: mostrar/restaurar la ventana
  tray = new Tray(ICON_PATH);
  tray.setToolTip('Musicia - minimizada. Usa SALIR en la app para cerrar todo.');
  tray.on('click', () => {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });
  // Clic derecho: atajo para recargar la UI y para salir de verdad.
  tray.on('right-click', () => {
    tray.popUpContextMenu(Menu.buildFromTemplate([
      { label: 'Mostrar', click: () => { mainWindow.show(); mainWindow.focus(); } },
      { label: 'Recargar interfaz', click: () => mainWindow.reload() },
      { type: 'separator' },
      {
        label: 'Salir',
        click: async () => {
          const ok = await exitApp('ask');
          if (ok) console.log('[SALIDA] cerrada desde la bandeja');
        },
      },
    ]));
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  if (uiWatchTimer) clearInterval(uiWatchTimer);
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});