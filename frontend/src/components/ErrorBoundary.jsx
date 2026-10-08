import React from 'react'

/**
 * ErrorBoundary: captura errores del árbol de React que deja la ventana
 * completamente negra ("no se ve nada"), tal y como pasó en 2026-10-01
 * (TDZ en Composer.jsx). Sin esto, cualquier error no controlado en un
 * panel (remix, biblioteca, música) ensancha el navegador y el usuario
 * ve toda la app en negro.
 *
 * Regla: no dejar la UI en blanco. Si falla, pintamos un panel recuperable
 * y el usuario puede reiniciar la vista sin perder los datos del trabajo.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    // Registro central: igual que los listeners de main.cjs ([UI:n] y
    // render-process-gone). Aquí queda la traza en la consola y en la UI.
    console.error('[UI:ERROR] ErrorBoundary capturó:', error, errorInfo?.componentStack)
    this.setState({ error, errorInfo })
  }

  reload = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    // Si el origen es un bundle obsoleto, forzamos una recarga a la API.
    if (typeof window !== 'undefined' && window.location.protocol !== 'file:') {
      window.location.reload()
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-container flex h-full flex-col items-center justify-center bg-[var(--bg)] text-[var(--text)] p-6">
          <div className="max-w-md text-center">
            <div className="h-10 w-10 rounded-full bg-[var(--err)] flex items-center justify-center mx-auto mb-4 animate-pulse">
              <span className="text-white text-sm font-bold">!</span>
            </div>
            <h1 className="text-xl font-semibold tracking-tight">Se cayó la interfaz</h1>
            <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">
              {this.state.error?.message ?? 'Algo ha fallado en un panel (remix, biblioteca o música).'}
              <br />
              Verás el error en la consola del navegador. No pierdes tu trabajo: la aplicación
              seguirá disponible y puedes volver a cargarla.
            </p>
            <pre className="mt-3 mono text-left text-[11px] bg-[var(--surface-1)] rounded p-3 overflow-auto max-h-[120px] text-[var(--faint)]">
              {this.state.error?.stack ?? 'sin stack'}
            </pre>
            <button
              onClick={this.reload}
              className="btn btn-signal mt-5 h-10 px-6"
            >
              RECARGAR INTERFAZ
            </button>
            <p className="mono text-[10px] text-[var(--faint)] mt-3">
              Mantén presionada la tecla Ctrl + clic para recargar forzando la caché de Electron
              (si el problema es un bundle obsoleto).
            </p>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
