"""Entrada Demucs local: nunca descarga pesos al separar un proyecto."""
from __future__ import annotations

import os
import runpy

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch  # El script se ejecuta con demucs-venv, no con el venv de la API.


def reject_download(*args, **kwargs):
    raise RuntimeError(
        "Faltan pesos locales de Demucs. La separación no descarga modelos; "
        "se requiere autorización explícita para instalarlos."
    )


torch.hub.download_url_to_file = reject_download
runpy.run_module("demucs.separate", run_name="__main__")
