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

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});