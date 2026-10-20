"""Cola final de la salida y el error de los procesos locales.

El progreso enseña una frase corta. Estas colas son el texto de los
ficheros, sin reescribirlo. Las rutas y el largo viven en la configuración.
"""
from __future__ import annotations

from pathlib import Path

from config import ProcessLogSettings

_STREAMS = (
    ("engine_stdout", "engine_stdout"),
    ("engine_stderr", "engine_stderr"),
    ("api_stderr", "api_stderr"),
)


def collect_process_logs(logs: ProcessLogSettings, root: Path) -> list[dict]:
    """Lee el final de cada fichero declarado. Un camino fuera de logs/ falla.

    Cada stream lleva además su copia rotada (``<fichero><backup_suffix>``,
    la que ensure_local.ps1 escribe al arrancar un proceso): un reinicio
    trunca el vivo, y sin esa copia el panel se quedaba vacío.
    """
    if logs.tail_lines < 1 or logs.tail_lines > logs.max_tail_lines:
        raise ValueError("process_logs.tail_lines está fuera del límite configurado")
    if logs.line_char_budget < 1:
        raise ValueError("process_logs.line_char_budget debe ser positivo")
    if not logs.backup_suffix or any(sep in logs.backup_suffix for sep in ("/", "\\")):
        raise ValueError("process_logs.backup_suffix no puede estar vacío ni contener separadores")
    base = root.resolve()
    allowed = (base / "logs").resolve()
    budget = logs.tail_lines * logs.line_char_budget
    streams = []
    for stream_id, field_name in _STREAMS:
        relative = getattr(logs, field_name)
        path = _inside_logs(relative, base, allowed)
        present = path.is_file()
        text = _tail(path, logs.tail_lines, budget) if present else ""
        backup = path.with_name(path.name + logs.backup_suffix)
        backup_present = backup.is_file()
        backup_text = _tail(backup, logs.tail_lines, budget) if backup_present else ""
        streams.append({
            "id": stream_id,
            "present": present,
            "text": text,
            "backup_present": backup_present,
            "backup_text": backup_text,
        })
    return streams


def _inside_logs(relative: str, base: Path, allowed: Path) -> Path:
    raw = Path(relative)
    if raw.is_absolute():
        path = raw.resolve()
    else:
        path = (base / raw).resolve()
    if path != allowed and allowed not in path.parents:
        raise ValueError("La ruta de log queda fuera de logs/")
    return path


def _tail(path: Path, lines: int, byte_budget: int) -> str:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > byte_budget:
            handle.seek(size - byte_budget)
            blob = handle.read()
            cut = blob.find(b"\n")
            if cut != -1:
                blob = blob[cut + 1:]
        else:
            blob = handle.read()
    rows = blob.decode("utf-8", errors="replace").splitlines()
    return "\n".join(rows[-lines:])
