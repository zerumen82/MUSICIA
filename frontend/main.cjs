const { app, BrowserWindow, shell, ipcMain, Tray, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, spawnSync } = require('child_process');

// El backend sirve el propio dist si existe; aquí solo abrimos la ventana.
const DIST_INDEX = path.join(__dirname, 'dist', 'index.html');
const DEV_URL = process.env.MUSICIA_DEV_URL || 'http://localhost:5173';
const API_URL = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const ICON_PATH = path.join(__dirname, 'build', 'icon.ico');
const PRELOAD_PATH = path.join(__dirname, 'preload.cjs');
const STOP_SCRIPT = path.join(__dirname, '..', 'scripts', 'stop_local.ps1');
const ENSURE_SCRIPT = path.join(__dirname, '..', 'scripts', 'ensure_local.ps1');
const STOP_FLAG = path.join(__dirname, '..', 'logs', 'stop.flag');
// Con la ventana viva, si el proceso del motor o de la API desaparece, se vuelve a arrancar.
const ENSURE_INTERVAL_MS = 20000;

let willQuit = false;
let mainWindow = null;
let tray = null;
let uiWatchTimer = null;
let ensureTimer = null;
let bootTimer = null;
let ensuring = false;

const BOOT_HTML = `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
<html><head><meta charset="utf-8"><title>Musicia</title>
<style>
  html,body{margin:0;height:100%;background:#0a0a0c;color:#b8ff29;
    font-family:ui-monospace,Consolas,monospace;display:flex;align-items:center;justify-content:center}
  p{letter-spacing:.16em;font-size:13px}
</style></head>
<body><p>ARRANCANDO EL MOTOR LOCAL…</p></body></html>`)}`;

function ensureServices(rearme) {
  if (willQuit) return;
  if (!rearme && fs.existsSync(STOP_FLAG)) return;
  if (ensuring) return;
  ensuring = true;
  const args = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ENSURE_SCRIPT];
  if (rearme) args.push('-Rearme');
  let child;
  try {
    child = spawn('powershell.exe', args, { windowsHide: true, stdio: 'ignore' });
  } catch {
    ensuring = false;
    return;
  }
  child.on('exit', () => { ensuring = false; });
  child.on('error', () => { ensuring = false; });
}

/**
 * Recarga la ventana cuando el bundle servido por la API cambia.
 *
 * Por qué: la ventana se queda abierta (la X no la cierra) y el
 * single-instance lock restaura la que ya existe, así que tras un
 * `npm run build` la app seguía mostrando la UI vieja. Con esto, tras el
 * build la ventana se recarga sola.
 */
function startUiWatch() {
  if (uiWatchTimer) return;
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
 * SALIR apaga motor y API y cierra el proceso.
 * No hay diálogo: uno colgado sobre la ventana escondida dejaba la app muerta.
 * app.exit no espera al renderer; app.quit sí, y ahí se quedaba.
 */
function exitApp() {
  if (willQuit) {
    app.exit(0);
    return true;
  }
  willQuit = true;
  if (ensureTimer) {
    clearInterval(ensureTimer);
    ensureTimer = null;
  }
  if (uiWatchTimer) {
    clearInterval(uiWatchTimer);
    uiWatchTimer = null;
  }
  if (bootTimer) {
    clearTimeout(bootTimer);
    bootTimer = null;
  }
  // La ventana se va ya. La parada puede tardar y no debe dejar la UI congelada.
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.removeAllListeners('close');
    mainWindow.destroy();
  }
  stopServices();
  if (tray) {
    try { tray.destroy(); } catch { /* la bandeja ya no está */ }
  }
  app.exit(0);
  return true;
}

function stopServices() {
  try {
    fs.mkdirSync(path.dirname(STOP_FLAG), { recursive: true });
    fs.writeFileSync(STOP_FLAG, 'salir\n');
  } catch {
    /* si no se puede marcar, el script de parada sigue */
  }
  try {
    // Tope: la parada no puede dejar el cierre esperando para siempre.
    spawnSync(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', STOP_SCRIPT],
      { windowsHide: true, timeout: 20000 },
    );
  } catch {
    /* si falla el script, se sale igual: la marca evita que ensure los levante */
  }
}

function scheduleBoot(delayMs) {
  if (bootTimer) clearTimeout(bootTimer);
  bootTimer = setTimeout(() => { void loadWhenReady(); }, delayMs);
}

async function loadWhenReady() {
  if (willQuit || !mainWindow || mainWindow.isDestroyed()) return;
  try {
    const res = await fetch(`${API_URL}/health`, { cache: 'no-store' });
    if (res.ok) {
      await mainWindow.webContents.session.clearCache().catch(() => {});
      if (willQuit || mainWindow.isDestroyed()) return;
      await mainWindow.loadURL(API_URL);
      startUiWatch();
      return;
    }
  } catch {
    /* La API todavía no escucha. */
  }
  if (willQuit || !mainWindow || mainWindow.isDestroyed()) return;
  const current = mainWindow.webContents.getURL() || '';
  if (!current.startsWith('data:text/html')) {
    mainWindow.loadURL(BOOT_HTML).catch(() => {});
  }
  scheduleBoot(1000);
}

ipcMain.handle('musica:exit', () => exitApp());

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1080,
    minHeight: 700,
    backgroundColor: '#0a0a0c',
    autoHideMenuBar: true,
    // La X no cierra ni esconde. Windows la deja gris. Solo SALIR apaga.
    closable: false,
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

  mainWindow.webContents.on('unhandledrejection', (_e, reason) => {
    console.error(`[UI:1] UNHANDLED_REJECTION ${(reason && reason.message) || reason}`)
    if (mainWindow && !mainWindow.isDestroyed()) {
      // El fallback en sí no debe dejar la ventana blanca: solo registrar.
      console.error('[UI:1] Stack:', reason && reason.stack)
      // Intentar recargar la vista de forma segura si lloja un error de RAM.
      const url = mainWindow.webContents.getURL ? mainWindow.webContents.getURL() : ''
      if (!url.startsWith('data:text/html')) {
        mainWindow.reload()
      }
    }
  });

  mainWindow.webContents.on('did-fail-load', (_e, code, desc, url, isMainFrame) => {
    console.log(`[CARGA FALLIDA] ${code} ${desc} main=${isMainFrame} ${url}`);
    if (willQuit || isMainFrame === false) return;
    // -3 es ERR_ABORTED: un loadURL nuevo cortó el anterior. No es un fallo.
    if (code === -3) return;
    // La página de error de Chromium («took too long to respond») no se queda.
    const current = mainWindow.webContents.getURL() || '';
    if (!current.startsWith('data:text/html')) {
      mainWindow.loadURL(BOOT_HTML).catch(() => {});
    }
    scheduleBoot(1000);
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
      ensureServices(false);
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
    // Si la API aún no está, se enseña el aviso y se reintenta. Una carga
    // fallida dejaba la ventana en blanco para siempre.
    scheduleBoot(0);
  }

  // Un cierre que no venga de SALIR se ignora. No esconde a la bandeja.
  mainWindow.on('close', (event) => {
    if (willQuit) return;
    event.preventDefault();
  });

  const showMain = () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  };
  // Clic en el icono de la bandeja: mostrar/restaurar la ventana
  tray = new Tray(ICON_PATH);
  tray.setToolTip('Musicia. Para cerrar todo, usa SALIR.');
  tray.on('click', () => {
    ensureServices(false);
    showMain();
  });
  // Clic derecho: atajo para recargar la UI y para salir de verdad.
  tray.on('right-click', () => {
    tray.popUpContextMenu(Menu.buildFromTemplate([
      { label: 'Mostrar', click: () => showMain() },
      {
        label: 'Recargar interfaz',
        click: () => {
          if (!mainWindow || mainWindow.isDestroyed()) return;
          mainWindow.reload();
        },
      },
      { type: 'separator' },
      {
        label: 'Salir',
        click: () => {
          console.log('[SALIDA] cerrada desde la bandeja');
          exitApp();
        },
      },
    ]));
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(() => {
  try { fs.unlinkSync(STOP_FLAG); } catch { /* no había una parada anterior */ }
  createWindow();
  ensureServices(true);
  ensureTimer = setInterval(() => ensureServices(false), ENSURE_INTERVAL_MS);
});

app.on('window-all-closed', () => {
  // La ventana no es cerrable. SALIR la destruye y sale con app.exit.
  // app.quit aquí dejaba el cierre a medias.
});

app.on('will-quit', () => {
  if (uiWatchTimer) clearInterval(uiWatchTimer);
  if (ensureTimer) clearInterval(ensureTimer);
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});