"""Decide si el proceso de la API está vivo pero ya no escucha, o si sirve
código antiguo.

No mata procesos. El script de arranque usa estas respuestas para reponer
solo la API de Musicia. El motor no entra aquí.
"""

from __future__ import annotations

from pathlib import Path


def api_is_wedged(*, health_ok: bool, port_accepts: bool, age_seconds: float, grace_seconds: float) -> bool:
    """True cuando el proceso ya debería escuchar y ni el puerto ni /health responden."""
    if grace_seconds <= 0:
        raise ValueError("La espera antes de reponer la API tiene que ser positiva.")
    if age_seconds < 0:
        raise ValueError("La edad del proceso de la API no puede ser negativa.")
    if health_ok or port_accepts:
        return False
    return age_seconds >= grace_seconds


def newest_backend_source_write(backend_dir: str | Path) -> float:
    """Epoch (mtime) del .py de backend más reciente.

    Solo el primer nivel de backend/: venv y __pycache__ no son código que
    la API cargue al arrancar. Cualquier .py de primer nivel cuenta, tests
    incluidos: no hay reglas de nombre mágicas y comparar de más es solo un
    reinicio en el arranque de la app, nunca un corte en caliente.
    """
    directory = Path(backend_dir)
    if not directory.is_dir():
        raise ValueError(f"No existe el directorio del backend: {directory}")
    writes = [item.stat().st_mtime for item in directory.glob("*.py") if item.is_file()]
    if not writes:
        raise ValueError(f"No hay archivos .py en {directory}: no hay código que comparar.")
    return max(writes)


def api_is_stale(*, source_write_age_seconds: float, process_age_seconds: float) -> bool:
    """True cuando el último cambio de backend/*.py es más reciente que el
    proceso de la API.

    Ese proceso responde, pero sirve el código que había al arrancar: el
    relanzado de la app no puede conservarlo. Un empate no cuenta como
    obsoleto (misma resolución de segundos, sin reinicios gratuitos). El
    fallo de comparación (edades negativas por relojes rotos) es un error,
    y el script trata el error como «no obsoleto»: ante la duda se conserva
    el proceso en vez de matarlo.
    """
    if source_write_age_seconds < 0 or process_age_seconds < 0:
        raise ValueError("Las edades de código y proceso no pueden ser negativas.")
    return source_write_age_seconds < process_age_seconds
