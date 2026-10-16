"""Decide si el proceso de la API está vivo pero ya no escucha.

No mata procesos. El script de arranque usa esta respuesta para reponer
solo la API de Musicia. El motor no entra aquí.
"""

from __future__ import annotations


def api_is_wedged(*, health_ok: bool, port_accepts: bool, age_seconds: float, grace_seconds: float) -> bool:
    """True cuando el proceso ya debería escuchar y ni el puerto ni /health responden."""
    if grace_seconds <= 0:
        raise ValueError("La espera antes de reponer la API tiene que ser positiva.")
    if age_seconds < 0:
        raise ValueError("La edad del proceso de la API no puede ser negativa.")
    if health_ok or port_accepts:
        return False
    return age_seconds >= grace_seconds
