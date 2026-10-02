"""Cliente del motor local de música ACE-Step 1.5.

El motor corre como proceso separado (``uv run acestep-api``, puerto 8001) y
expone su API real:

* ``POST /release_task``  -> crea la tarea y devuelve ``task_id``
* ``POST /query_result``  -> estado y rutas de audio de una tarea
* ``GET  /v1/audio``      -> descarga del audio generado
* ``GET  /health``        -> salud del motor

Todo se resuelve contra el motor de verdad: si falla, se propaga el error real.
No hay datos simulados ni rutas inventadas.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx
from loguru import logger
from pydub import AudioSegment

from config import AppSettings, GenerationDefaults, get_settings

# Códigos de estado que devuelve /query_result (STATUS_MAP del motor).
STATUS_PENDING = 0
STATUS_SUCCEEDED = 1
STATUS_FAILED = 2

TERMINAL_STATUSES = {STATUS_SUCCEEDED, STATUS_FAILED}


class MusicEngineError(RuntimeError):
    """Fallo real del motor o de la verificación del audio generado."""


@dataclass
class GenerationRequest:
    """Petición de generación con valores opcionales (los completa la config)."""

    prompt: str
    lyrics: str | None = None
    instrumental: bool | None = None
    duration_seconds: float | None = None
    bpm: int | None = None
    key_scale: str | None = None
    time_signature: str | None = None
    language: str | None = None
    inference_steps: int | None = None
    guidance_scale: float | None = None
    seed: int | None = None
    use_random_seed: bool | None = None
    batch_size: int | None = None
    audio_format: str | None = None
    model: str | None = None


@dataclass
class GeneratedTrack:
    """Una pista devuelta por el motor, con sus metadatos reales."""

    file: str
    prompt: str = ""
    lyrics: str = ""
    metas: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineStatus:
    """Estado de una tarea según el motor."""

    task_id: str
    status: int
    progress_text: str = ""
    progress: float = 0.0      # 0.0-1.0, campo real del motor
    stage: str = ""            # 'queued' | 'start' | ... (campo real del motor)
    tracks: list[GeneratedTrack] = field(default_factory=list)
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == STATUS_SUCCEEDED

    @property
    def failed(self) -> bool:
        return self.status == STATUS_FAILED

    @property
    def pending(self) -> bool:
        return self.status == STATUS_PENDING


class MusicService:
    """Cliente del motor ACE-Step con espera activa y verificación del audio."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.engine = self.settings.acestep
        self.defaults: GenerationDefaults = self.settings.generation
        self._client: httpx.AsyncClient | None = None

    # -- ciclo de vida -------------------------------------------------------

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.engine.base_url,
            timeout=self.engine.request_timeout,
            headers=self._auth_headers(),
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.engine.api_key}"} if self.engine.api_key else {}

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise MusicEngineError("MusicService no inicializado: llama a start() primero")
        return self._client

    # -- transporte ----------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Petición HTTP al motor, validando su envoltorio {data, code, error}."""
        try:
            response = await self.client.request(method, path, **kwargs)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MusicEngineError(f"El motor ACE-Step no responde ({path}): {exc}") from exc
        except json.JSONDecodeError as exc:
            raise MusicEngineError(f"Respuesta ilegible del motor ({path}): {exc}") from exc

        if payload.get("code") != 200 or payload.get("error"):
            raise MusicEngineError(str(payload.get("error") or f"Error del motor en {path}"))
        return payload.get("data")

    # -- API del motor -------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Comprueba que el motor está vivo (no simulado)."""
        try:
            response = await self.client.get(self.engine.health_path)
            response.raise_for_status()
            return {
                "reachable": True,
                "status_code": response.status_code,
                "detail": response.text[:200],
            }
        except httpx.HTTPError as exc:
            return {"reachable": False, "error": str(exc)}

    async def list_models(self) -> Any:
        """Modelos DiT disponibles en el motor."""
        return await self._request("GET", self.engine.models_path)

    async def write_lyrics(
        self,
        caption: str,
        lyrics: str = "",
        language: str | None = None,
        duration_seconds: float | None = None,
        bpm: int | None = None,
        key_scale: str | None = None,
    ) -> dict[str, Any]:
        """Pide al LM local del motor una letra con estructura de canción.

        Es el "escribir la letra por mí" de la UI: el usuario recibe un
        borrador editable (spec A3). Nunca sale a la nube, es el mismo motor.
        """
        param_obj: dict[str, Any] = {}
        if duration_seconds:
            param_obj["duration"] = int(duration_seconds)
        if bpm:
            param_obj["bpm"] = bpm
        if key_scale:
            param_obj["key"] = key_scale
        if language:
            param_obj["language"] = language
        data = await self._request(
            "POST",
            self.engine.format_input_path,
            json={"prompt": caption, "lyrics": lyrics, "param_obj": param_obj},
        )
        return data if isinstance(data, dict) else {}

    def build_payload(self, request: GenerationRequest) -> dict[str, Any]:
        """Construye el cuerpo de /release_task a partir de config + petición."""
        defaults = self.defaults
        instrumental = defaults.instrumental if request.instrumental is None else request.instrumental
        duration = defaults.duration_seconds if request.duration_seconds is None else request.duration_seconds
        if duration <= 0 or duration > defaults.max_duration_seconds:
            raise MusicEngineError(
                f"La duración debe estar entre 0 y {defaults.max_duration_seconds:g} s (recibido: {duration})"
            )

        lyrics = request.lyrics
        if instrumental:
            # El motor trata estos marcadores como "sin voz" (server_utils.is_instrumental).
            lyrics = defaults.instrumental_marker
        elif lyrics is None or not lyrics.strip():
            raise MusicEngineError(
                "Para una pieza con voz debes enviar 'lyrics' o marcar instrumental=true "
                "(con la letra vacía el motor genera un instrumental)"
            )

        payload = {
            "prompt": request.prompt,
            "lyrics": lyrics,
            "audio_duration": duration,
            "bpm": defaults.bpm if request.bpm is None else request.bpm,
            "key_scale": defaults.key_scale if request.key_scale is None else request.key_scale,
            "time_signature": defaults.time_signature
            if request.time_signature is None
            else request.time_signature,
            "vocal_language": defaults.language if request.language is None else request.language,
            "inference_steps": defaults.inference_steps
            if request.inference_steps is None
            else request.inference_steps,
            "guidance_scale": defaults.guidance_scale
            if request.guidance_scale is None
            else request.guidance_scale,
            "seed": defaults.seed if request.seed is None else request.seed,
            "use_random_seed": defaults.use_random_seed
            if request.use_random_seed is None
            else request.use_random_seed,
            "batch_size": defaults.batch_size if request.batch_size is None else request.batch_size,
            "audio_format": defaults.audio_format
            if request.audio_format is None
            else request.audio_format,
            "model": defaults.model if request.model is None else request.model,
            "thinking": defaults.thinking and defaults.use_lm,
            "task_type": defaults.task_type,
            "infer_method": defaults.infer_method,
        }
        if defaults.use_lm:
            payload["lm_model_path"] = defaults.lm_model
            payload["lm_backend"] = defaults.lm_backend
        return payload

    async def submit(self, request: GenerationRequest) -> tuple[str, str]:
        """Envía la generación al motor y devuelve (task_id, estado inicial)."""
        payload = self.build_payload(request)
        data = await self._request("POST", self.engine.submit_path, json=payload)
        task_id = data.get("task_id")
        if not task_id:
            raise MusicEngineError(f"El motor no devolvió task_id: {data}")
        logger.info(f"Tarea enviada al motor: {task_id} | prompt={request.prompt[:60]!r}")
        return task_id, str(data.get("status", "queued"))

    async def status(self, task_id: str) -> EngineStatus:
        """Consulta el estado real de una tarea y parsea sus pistas."""
        data = await self._request(
            "POST", self.engine.result_path, json={"task_id_list": [task_id]}
        )
        if not data:
            return EngineStatus(task_id=task_id, status=STATUS_PENDING)

        item = data[0] if isinstance(data, list) else data
        status = int(item.get("status", STATUS_FAILED))
        tracks = self._parse_tracks(item.get("result"))
        error = None
        progress = 0.0
        stage = ""
        for track in tracks:
            if track.get("error"):
                error = str(track["error"])
            # El motor reporta progreso real por pista (0.0-1.0) y stage
            try:
                p = float(track.get("progress") or 0.0)
                if p > progress:
                    progress = p
            except (TypeError, ValueError):
                pass
            s = str(track.get("stage") or "")
            if s and not stage:
                stage = s
        return EngineStatus(
            task_id=task_id,
            status=status,
            progress_text=str(item.get("progress_text") or ""),
            progress=progress,
            stage=stage,
            # GeneratedTrack solo acepta sus campos; lo demás (progress/stage)
            # ya fue consumido arriba.
            tracks=[
                GeneratedTrack(**{k: v for k, v in t.items() if k in GeneratedTrack.__dataclass_fields__})
                for t in tracks
            ],
            error=error,
        )

    @staticmethod
    def _parse_tracks(raw_result: Any) -> list[dict[str, Any]]:
        """El motor devuelve 'result' como texto JSON con la lista de pistas."""
        if not raw_result:
            return []
        if isinstance(raw_result, str):
            try:
                raw_result = json.loads(raw_result)
            except json.JSONDecodeError:
                logger.warning("No se pudo parsear 'result' del motor")
                return []
        if not isinstance(raw_result, list):
            return []
        tracks = []
        for entry in raw_result:
            if not isinstance(entry, dict):
                continue
            tracks.append(
                {
                    "file": str(entry.get("file") or ""),
                    "prompt": str(entry.get("prompt") or ""),
                    "lyrics": str(entry.get("lyrics") or ""),
                    "metas": entry.get("metas") or {},
                    "progress": entry.get("progress"),
                    "stage": entry.get("stage"),
                }
            )
        return tracks

    async def wait(
        self, task_id: str, on_update: Callable[[EngineStatus], None] | None = None
    ) -> EngineStatus:
        """Consulta periódicamente hasta que la tarea termine o agote el timeout."""
        deadline = time.monotonic() + self.engine.job_timeout
        while True:
            current = await self.status(task_id)
            if on_update is not None:
                on_update(current)
            if current.status in TERMINAL_STATUSES:
                return current
            if time.monotonic() > deadline:
                raise MusicEngineError(
                    f"Tiempo agotado esperando la tarea {task_id} "
                    f"({self.engine.job_timeout:g} s). Estado: {current.progress_text or 'en curso'}"
                )
            await asyncio.sleep(self.engine.poll_interval)

    def _download_target(self, remote: str) -> tuple[str, dict[str, str] | None]:
        """Normaliza la referencia de una pista a (ruta_http, query).

        El motor devuelve la pista ya como URL relativa (``/v1/audio?path=...``)
        cuando la resuelve en su lado, o como ruta local del sistema de ficheros.
        Hay que respetar esa forma: si se reenvía una URL como valor de ``path`` se
        codifica dos veces y el motor responde 403.
        """
        if remote.startswith(("http://", "https://")):
            return remote, None
        if remote.startswith("/"):
            return remote, None
        return self.engine.audio_path, {"path": remote}

    async def download(self, remote_path: str, destination: Path) -> Path:
        """Descarga el audio generado por el motor a un fichero local."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        target, params = self._download_target(remote_path)
        try:
            async with self.client.stream("GET", target, params=params) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        handle.write(chunk)
        except httpx.HTTPError as exc:
            raise MusicEngineError(f"No se pudo descargar {remote_path}: {exc}") from exc
        logger.info(f"Audio descargado del motor: {destination.name} ({destination.stat().st_size} bytes)")
        return destination

    @staticmethod
    async def verify_audio(path: Path, min_duration_ms: float = 1.0) -> float:
        """Verifica que el audio existe y no está vacío. Devuelve su duración."""
        if not path.exists():
            raise MusicEngineError(f"El motor no dejó el archivo esperado: {path}")
        duration_ms = await asyncio.to_thread(
            lambda: len(AudioSegment.from_file(path)) if path.stat().st_size > 0 else 0
        )
        if duration_ms <= min_duration_ms:
            raise MusicEngineError(f"El audio generado está vacío o corrupto: {path}")
        logger.info(f"Audio verificado: {path.name} ({duration_ms / 1000:.1f} s)")
        return float(duration_ms)