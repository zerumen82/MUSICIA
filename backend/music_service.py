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
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx
from loguru import logger
from pydub import AudioSegment

from config import AppSettings, GenerationDefaults, get_settings
from prompt_constraints import rules as constraint_rules, validate_explicit_constraints

# Códigos de estado que devuelve /query_result (STATUS_MAP del motor).
STATUS_PENDING = 0
STATUS_SUCCEEDED = 1
STATUS_FAILED = 2

TERMINAL_STATUSES = {STATUS_SUCCEEDED, STATUS_FAILED}


class MusicEngineError(RuntimeError):
    """Fallo real del motor o de la verificación del audio generado."""


def stage_source_audio(source: str) -> str:
    """Copia el audio a la carpeta temporal.

    El motor rechaza una ruta absoluta que no esté ahí (`absolute audio file
    paths are not allowed`). Cover y repaint leen esa copia.
    """
    src = Path(source)
    if not src.is_file():
        raise MusicEngineError(f"No existe el audio de origen: {source}")
    fd, dest = tempfile.mkstemp(prefix="musicia-src-", suffix=src.suffix or ".mp3")
    os.close(fd)
    try:
        shutil.copyfile(src, dest)
    except OSError:
        Path(dest).unlink(missing_ok=True)
        raise
    return dest


def lyrics_are_song(text: str | None) -> bool:
    """Una palabra suelta («BASE») no es una letra: si se envía, el motor la canta."""
    words = re.findall(r"[^\W\d_]{2,}", text or "", flags=re.UNICODE)
    return len(words) >= 8


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
    use_format: bool | None = None
    audio_format: str | None = None
    model: str | None = None
    task_type: str | None = None
    source_path: str | None = None
    repaint_start: float | None = None
    repaint_end: float | None = None
    cover_strength: float | None = None
    reference_path: str | None = None
    cover_noise_strength: float | None = None
    repaint_mode: str | None = None
    repaint_strength: float | None = None
    repaint_wav_crossfade_sec: float | None = None
    repaint_latent_crossfade_frames: int | None = None
    external_voice: bool = False
    # Texto del usuario para las contradicciones. No viaja al motor:
    # el prompt ya es el inglés del estilo.
    constraint_prompt: str | None = None


@dataclass
class GeneratedTrack:
    """Una pista devuelta por el motor, con sus metadatos reales."""

    file: str
    prompt: str = ""
    lyrics: str = ""
    metas: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    seed_origin: str = "unknown"


def engine_is_converting(stage: str = "", progress_text: str = "") -> bool:
    """True mientras el motor convierte a audio.

    «decod» cubre decode, Decoding y tiled_decode. Mencionar VAE o tiled
    también ocurre al cargar, descargar y codificar antes de la difusión.
    """
    blob = f"{stage}\n{progress_text}".lower()
    return "decod" in blob


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

    def moving_progress(self) -> float | None:
        """Porcentaje que se puede pintar. Al convertir, el motor deja el número quieto."""
        if engine_is_converting(self.stage, self.progress_text):
            return None
        return float(self.progress)


class MusicService:
    """Cliente del motor ACE-Step con espera activa y verificación del audio."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.engine = self.settings.acestep
        self.defaults: GenerationDefaults = self.settings.generation
        self._client: httpx.AsyncClient | None = None
        self._staged: dict[str, list[str]] = {}

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

    # -- comprobación de VRAM --------------------------------------------------

    @staticmethod
    def _vram_free_mb() -> int | None:
        """Devuelve la VRAM libre de la GPU en MB, o None si no se puede leer."""
        try:
            resultado = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if resultado.returncode == 0 and resultado.stdout.strip():
                return int(resultado.stdout.strip().splitlines()[0])
        except Exception:
            pass
        return None

    @staticmethod
    def _ensure_vram_disponible(minimo_mb: int = 2048) -> None:
        """Verifica que haya suficiente VRAM libre antes de enviar al motor.

        Lanza MusicEngineError con un mensaje claro si no, en lugar de
        fallar a mitad de la generación con un error críptico de CUDA.
        """
        libre = MusicService._vram_free_mb()
        if libre is None:
            return  # No se pudo leer; deja que el motor intente y falle por su cuenta
        if libre < minimo_mb:
            raise MusicEngineError(
                f"VRAM insuficiente: solo {libre} MB libres, se necesitan al menos "
                f"{minimo_mb} MB. Cierra otras aplicaciones que usen la GPU o reinicia el "
                f"motor (scripts\\ensure_local.ps1).")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise MusicEngineError("MusicService no inicializado: llama a start() primero")
        return self._client

    # -- reinicio automático del motor --------------------------------------

    @staticmethod
    def _restart_engine() -> None:
        """Mata el motor ACE-Step existente y arranca uno limpio para liberar VRAM.

        Espera hasta 60 s a que el nuevo motor responda /health antes de
        retornar, para que el llamador no se encuentre con él todavía caído.
        """
        import subprocess as _subprocess
        import time as _time
        raiz = str(Path(__file__).resolve().parents[1])
        # Arrancar ensure_local.ps1 sin bloquear este hilo.
        _subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-Command", f"& '{raiz}\\scripts\\ensure_local.ps1'"],
            stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL,
        )
        logger.warning("Motor reiniciado automáticamente (ensure_local.ps1 lanzado en segundo plano)")
        # Esperar a que el motor vuelva a escuchar en /health.
        for _intento in range(12):
            try:
                resultado = _subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command",
                     "Invoke-WebRequest -Uri 'http://127.0.0.1:8001/health' -TimeoutSec 3 -UseBasicParsing | Out-Null"],
                    capture_output=True, text=True, timeout=5,
                )
                if resultado.returncode == 0:
                    logger.warning("Motor ACE-Step reiniciado y responde en /health")
                    return
            except Exception:
                pass
            _time.sleep(5)
        logger.warning("Motor ACE-Step no confirmó /health tras 60 s de reinicio")

    # -- transporte ----------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Petición HTTP al motor, validando su envoltorio {data, code, error}.

        Antes de cada petición comprueba que el motor esté vivo; si no, lo
        reinicia y espera a que esté listo. Ante ConnectError, reintenta una
        vez tras reiniciar.
        """
        # Asegurar que el motor esté vivo antes de enviar.
        try:
            salud = await self.health()
            if not salud.get("reachable") or salud.get("busy"):
                logger.warning(f"Motor no reachable o ocupado antes de {path}; reiniciando")
                self._restart_engine()
                await asyncio.sleep(2)
        except Exception:
            self._restart_engine()
            await asyncio.sleep(2)

        ultimo_error = None
        for intento in range(2):
            try:
                response = await self.client.request(method, path, **kwargs)
                response.raise_for_status()
                payload = response.json()
                if payload.get("code") != 200 or payload.get("error"):
                    raise MusicEngineError(str(payload.get("error") or f"Error del motor en {path}"))
                return payload.get("data")
            except httpx.HTTPStatusError as exc:
                body = ""
                code = "?"
                if exc.response is not None:
                    code = exc.response.status_code
                    body = (exc.response.text or "").strip().replace("\n", " ")[:400]
                if "absolute audio file paths are not allowed" in body:
                    body = "No acepta la ruta del audio de origen."
                elif "path traversal" in body:
                    body = "No acepta esa ruta de audio."
                ultimo_error = MusicEngineError(
                    f"El motor ACE-Step rechazó {path} (HTTP {code}): {body or exc}"
                )
                raise ultimo_error from exc
            except httpx.ConnectError as exc:
                ultimo_error = exc
                # Motor caído: reiniciar y reintentar una vez.
                if intento == 0:
                    logger.warning(f"ConnectError en {path}; reiniciando motor y reintentando")
                    self._restart_engine()
                    await asyncio.sleep(3)
                    continue
                raise MusicEngineError(
                    f"El motor ACE-Step no responde ({path}): ConnectError tras reinicio"
                ) from exc
            except httpx.HTTPError as exc:
                detalle = str(exc).strip() or repr(exc)
                raise MusicEngineError(
                    f"El motor ACE-Step no responde ({path}): {type(exc).__name__}: {detalle}"
                ) from exc
            except json.JSONDecodeError as exc:
                raise MusicEngineError(f"Respuesta ilegible del motor ({path}): {exc}") from exc
        raise MusicEngineError(
            f"El motor ACE-Step no responde ({path}): {ultimo_error}"
        ) from ultimo_error

    # -- API del motor -------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Comprueba que el motor está vivo, con un tope corto.

        Una generación usa ``request_timeout``. Esta consulta no: si el motor
        no abre el puerto, la pastilla lo sabe en unos segundos y la API sigue
        respondiendo.
        """
        try:
            response = await self.client.get(
                self.engine.health_path,
                timeout=self.engine.health_timeout,
            )
            response.raise_for_status()
            return {
                "reachable": True,
                "status_code": response.status_code,
                "detail": response.text[:200],
            }
        except httpx.TimeoutException as exc:
            # El puerto sigue abierto y no contestó a tiempo: está ocupado
            # (letra o síntesis). Pintarlo apagado desactiva GENERAR.
            return {"reachable": True, "busy": True, "error": type(exc).__name__}
        except httpx.HTTPError as exc:
            detail = str(exc).strip() or type(exc).__name__
            return {"reachable": False, "error": detail}

    async def list_models(self) -> Any:
        """Modelos que anuncia el motor. Acepta el listado OpenAI y el envoltorio {code, data}."""
        response = await self.client.get(
            self.engine.models_path, timeout=self.engine.health_timeout
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "code" in payload:
            if payload.get("code") != 200 or payload.get("error"):
                raise MusicEngineError(str(payload.get("error") or "El motor no listó modelos"))
            return payload.get("data")
        return payload

    async def engine_info(self) -> dict[str, Any]:
        """Modelo y LM que el motor dice tener cargados ahora."""
        response = await self.client.get(
            self.engine.health_path, timeout=self.engine.health_timeout
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return {}
        return {
            "loaded_model": data.get("loaded_model"),
            "loaded_lm_model": data.get("loaded_lm_model"),
        }

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
        task = request.task_type or defaults.task_type
        # En cover/repaint una letra vacía no ordena eliminar la voz del audio.
        instrumental = (
            defaults.instrumental if task == "text2music" and request.instrumental is None
            else request.instrumental is True
        )
        try:
            validate_explicit_constraints(
                request.constraint_prompt or request.prompt,
                bpm=defaults.bpm if request.bpm is None else request.bpm,
                time_signature=defaults.time_signature if request.time_signature is None else request.time_signature,
                instrumental=(False if request.external_voice else instrumental if task == "text2music" else request.instrumental),
                lyrics=request.lyrics, marker=defaults.instrumental_marker,
                external_voice=request.external_voice,
            )
        except ValueError as exc:
            raise MusicEngineError(str(exc)) from exc
        duration = defaults.duration_seconds if request.duration_seconds is None else request.duration_seconds
        if duration <= 0 or duration > defaults.max_duration_seconds:
            raise MusicEngineError(
                f"La duración debe estar entre 0 y {defaults.max_duration_seconds:g} s (recibido: {duration})"
            )

        lyrics = request.lyrics
        if instrumental:
            # El motor trata estos marcadores como "sin voz" (server_utils.is_instrumental).
            lyrics = defaults.instrumental_marker
        elif task == "text2music" and (lyrics is None or not lyrics.strip()):
            raise MusicEngineError(
                "Para una pieza con voz debes enviar 'lyrics' o marcar instrumental=true "
                "(con la letra vacía el motor genera un instrumental)"
            )

        # Tarea y modelo primero: los pasos y el guidance dependen del modelo.
        model = defaults.model_for(task, request.model)
        inference_steps = (
            request.inference_steps
            if request.inference_steps is not None
            else defaults.steps_by_model.get(model, defaults.inference_steps)
        )
        guidance_scale = (
            request.guidance_scale
            if request.guidance_scale is not None
            else defaults.guidance_by_model.get(model, defaults.guidance_scale)
        )

        payload = {
            "prompt": request.prompt,
            "lyrics": lyrics or "",
            "audio_duration": duration,
            "bpm": defaults.bpm if request.bpm is None else request.bpm,
            "key_scale": defaults.key_scale if request.key_scale is None else request.key_scale,
            "time_signature": defaults.time_signature
            if request.time_signature is None
            else request.time_signature,
            "vocal_language": defaults.language if request.language is None else request.language,
            "inference_steps": inference_steps,
            "guidance_scale": guidance_scale,
            "seed": defaults.seed if request.seed is None else request.seed,
            # Una semilla escrita tiene que repetir el resultado. Si no, el
            # motor ignora el número y la comparación A/B no es real.
            "use_random_seed": (
                defaults.use_random_seed
                if request.use_random_seed is None and request.seed is None
                else False
                if request.use_random_seed is None
                else request.use_random_seed
            ),
            "batch_size": defaults.batch_size if request.batch_size is None else request.batch_size,
            "audio_format": defaults.audio_format
            if request.audio_format is None
            else request.audio_format,
            "model": model,
            # thinking genera códigos de audio y el DiT los sigue. El 2026-10-03
            # a las 23:27 el caption era el del usuario y aun así sonó otra cosa:
            # 1200 códigos mandaban más que la frase. Los tres cot en false
            # evitan que el servidor encienda el LM por su cuenta.
            "thinking": False,
            "use_cot_caption": False,
            "use_cot_language": False,
            "use_cot_metas": False,
            # use_format SÍ usa el LM, pero solo para reescribir caption y
            # letra al formato de entrenamiento (spec/02 [R3]): no genera
            # códigos de audio. Lo pedido manda; si no, la config.
            "use_format": (
                defaults.use_format if request.use_format is None else request.use_format
            ),
            "task_type": task,
            "infer_method": defaults.infer_method,
        }
        if defaults.use_lm:
            payload["lm_model_path"] = defaults.lm_model
            payload["lm_backend"] = defaults.lm_backend

        if task not in defaults.allowed_tasks:
            raise MusicEngineError(
                f"Tarea no disponible en esta GPU de 8 GB: {task}. "
                f"Usa una de: {', '.join(defaults.allowed_tasks)}"
            )
        if model not in defaults.allowed_models:
            raise MusicEngineError(
                f"Modelo no residente en esta GPU de 8 GB: {model}. "
                f"El que permanece cargado es: {', '.join(defaults.allowed_models)}"
            )
        if task in {"cover", "repaint"}:
            if not request.source_path:
                raise MusicEngineError("Esta tarea necesita el audio de origen")
            payload["src_audio_path"] = request.source_path
            # El LM no planifica cover ni repaint: el audio manda.
            payload["thinking"] = False
        if task == "cover":
            strength = defaults.cover_strength if request.cover_strength is None else request.cover_strength
            if not 0.0 <= float(strength) <= 1.0:
                raise MusicEngineError("La fuerza de la versión tiene que estar entre 0 y 1")
            payload["audio_cover_strength"] = float(strength)
        if task == "repaint":
            start = 0.0 if request.repaint_start is None else float(request.repaint_start)
            end = -1.0 if request.repaint_end is None else float(request.repaint_end)
            if start < 0 or end < -1 or (end != -1.0 and end <= start):
                raise MusicEngineError(
                    "El tramo tiene que empezar en cero o más y acabar después del inicio "
                    "(o -1 para llegar hasta el final)"
                )
            payload["repainting_start"] = start
            payload["repainting_end"] = end
            payload["chunk_mask_mode"] = "explicit"
        if request.reference_path:
            payload["reference_audio_path"] = request.reference_path
        for name in (
            "cover_noise_strength", "repaint_mode", "repaint_strength",
            "repaint_wav_crossfade_sec", "repaint_latent_crossfade_frames",
        ):
            value = getattr(request, name)
            if value is not None and (not name.startswith("repaint_") or task == "repaint"):
                payload[name] = value
        if task == "repaint":
            config = self.settings.remix
            mode = request.repaint_mode or config.repaint_mode
            strength = config.repaint_strength if request.repaint_strength is None else request.repaint_strength
            if mode not in config.repaint_modes or not 0.0 <= strength <= 1.0:
                raise MusicEngineError("Modo o fuerza de repaint fuera del contrato del motor")
            # ACE-Step deriva estas transiciones del modo/fuerza; ignora
            # los dos campos crossfade enviados. Registrar el valor real.
            preservation = 0.0 if mode == "aggressive" else 1.0 if mode == "conservative" else 1.0 - strength
            payload["repaint_mode"] = mode
            payload["repaint_strength"] = strength
            payload["repaint_latent_crossfade_frames"] = round(config.repaint_resolution_max_frames * preservation)
            payload["repaint_wav_crossfade_sec"] = config.repaint_resolution_max_wav_seconds * preservation
        if task in {"cover", "repaint"} and request.duration_seconds is None:
            # Cero o negativo: el motor toma la duración del audio de origen.
            payload["audio_duration"] = -1
        return payload

    def preview(self, request: GenerationRequest) -> dict[str, Any]:
        """La misma preparación que submit, sin HTTP, copias ni generación."""
        payload = self.build_payload(request)
        aliases = {
            "audio_duration": "duration_seconds", "vocal_language": "language",
            "audio_cover_strength": "cover_strength", "src_audio_path": "source_path",
            "reference_audio_path": "reference_path", "repainting_start": "repaint_start",
            "repainting_end": "repaint_end",
        }
        provenance = {}
        for key in payload:
            field_name = aliases.get(key, key)
            value = getattr(request, field_name, None)
            provenance[key] = "request" if value is not None else "configuration"
        for key in ("thinking", "use_cot_caption", "use_cot_language", "use_cot_metas", "chunk_mask_mode"):
            if key in payload:
                provenance[key] = "operation_contract"
        if payload.get("lyrics") == self.defaults.instrumental_marker:
            provenance["lyrics"] = "instrumental_control"
        if payload.get("audio_duration") == -1:
            provenance["audio_duration"] = "source_duration"
        warnings = [constraint_rules()["limitation"]]
        if any(payload.get(key) for key in ("src_audio_path", "reference_audio_path")):
            warnings.append("Al enviar, el mismo archivo se copia a una ruta temporal admitida por el motor; esa ruta de transporte no cambia el material ni los parámetros.")
        if request.external_voice:
            warnings.append("El motor genera solo la base instrumental; la voz procede del audio original y se mezcla después.")
        if payload["task_type"] == "repaint":
            for key in ("repaint_latent_crossfade_frames", "repaint_wav_crossfade_sec"):
                provenance[key] = "engine_mode_strength_contract"
            warnings.append("Las transiciones WAV y latentes se derivan del modo y la fuerza por el motor instalado; los valores crossfade directos del request no tienen efecto independiente.")
            if payload["repaint_mode"] != "balanced":
                provenance["repaint_strength"] = "ignored_by_engine_mode"
                warnings.append("La fuerza de repaint solo tiene efecto en modo equilibrado.")
        return {"effective_parameters": payload, "provenance": provenance, "warnings": warnings}

    async def submit(self, request: GenerationRequest) -> tuple[str, str]:
        """Envía la generación al motor y devuelve (task_id, estado inicial)."""
        self._ensure_vram_disponible()
        payload = self.build_payload(request)
        staged: list[str] = []
        try:
            for key in ("src_audio_path", "reference_audio_path"):
                if payload.get(key):
                    path = stage_source_audio(payload[key])
                    staged.append(path)
                    payload[key] = path
            data = await self._request("POST", self.engine.submit_path, json=payload)
        except Exception:
            for path in staged:
                Path(path).unlink(missing_ok=True)
            raise
        task_id = data.get("task_id")
        if not task_id:
            for path in staged:
                Path(path).unlink(missing_ok=True)
            raise MusicEngineError(f"El motor no devolvió task_id: {data}")
        if staged:
            self._staged[task_id] = staged
        logger.info(
            f"Tarea enviada al motor: {task_id} | modelo={payload.get('model')} "
            f"| pasos={payload.get('inference_steps')} guidance={payload.get('guidance_scale')} | "
            f"dur={payload.get('audio_duration')}s | "
            f"thinking={payload.get('thinking')} cot_caption={payload.get('use_cot_caption')} "
            f"cot_metas={payload.get('use_cot_metas')} use_format={payload.get('use_format')} "
            f"batch={payload.get('batch_size')} | prompt={request.prompt[:180]!r}"
        )
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
        for index, entry in enumerate(raw_result):
            if not isinstance(entry, dict):
                continue
            # La API real devuelve seed_value (lista ordenada) fuera de metas.
            # No derivar seed+n ni usar la semilla solicitada como si fuera real.
            raw_seed = entry.get("seed")
            seed_origin = "engine.seed"
            if raw_seed is None and isinstance(entry.get("metas"), dict):
                raw_seed = entry["metas"].get("seed")
                seed_origin = "engine.metas.seed"
            if raw_seed is None:
                raw_values = str(entry.get("seed_value") or "").split(",")
                if len(raw_values) == len(raw_result):
                    raw_seed = raw_values[index].strip()
                    seed_origin = "engine.seed_value"
            try:
                real_seed = int(raw_seed) if raw_seed is not None else None
                if real_seed is not None and real_seed < 0:
                    real_seed = None
            except (TypeError, ValueError):
                real_seed = None
            tracks.append(
                {
                    "file": str(entry.get("file") or ""),
                    "prompt": str(entry.get("prompt") or ""),
                    "lyrics": str(entry.get("lyrics") or ""),
                    "metas": entry.get("metas") or {},
                    "seed": real_seed,
                    "seed_origin": seed_origin if real_seed is not None else "unknown",
                    "error": entry.get("error"),
                    "progress": entry.get("progress"),
                    "stage": entry.get("stage"),
                }
            )
        return tracks

    async def _reconnect(self) -> None:
        """Abre de nuevo el cliente. Una conexión keep-alive caída no se reutiliza."""
        await self.aclose()
        await self.start()

    async def wait(
        self, task_id: str, on_update: Callable[[EngineStatus], None] | None = None
    ) -> EngineStatus:
        """Consulta periódicamente hasta que la tarea termine o agote el timeout.

        Un corte suelto de /query_result no mata el trabajo: el motor puede
        seguir generando (el LM ocupa la GPU un minuto) y el siguiente sondeo
        recoge el audio.
        """
        try:
            return await self._wait_loop(task_id, on_update)
        finally:
            self._drop_staged(task_id)

    async def _wait_loop(
        self, task_id: str, on_update: Callable[[EngineStatus], None] | None
    ) -> EngineStatus:
        deadline = time.monotonic() + self.engine.job_timeout
        misses = 0
        max_misses = self.engine.poll_max_misses
        while True:
            if time.monotonic() > deadline:
                raise MusicEngineError(
                    f"Tiempo agotado esperando la tarea {task_id} "
                    f"({self.engine.job_timeout:g} s)."
                )
            try:
                current = await self.status(task_id)
            except MusicEngineError as exc:
                cause = exc.__cause__
                if isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code not in {
                    408, 429, 500, 502, 503, 504,
                }:
                    raise
                if not isinstance(cause, (httpx.HTTPError, json.JSONDecodeError)):
                    raise
                misses += 1
                logger.warning(f"Sondeo {task_id[:8]} falló ({misses}): {exc}")
                try:
                    await self._reconnect()
                except Exception as rec:  # noqa: BLE001 - el siguiente sondeo lo reintenta
                    logger.warning(f"No se pudo reabrir el cliente del motor: {rec}")
                if misses >= max_misses:
                    # Un corte no es un fallo del remix. Si el proceso sigue
                    # vivo, se espera. Si no, el tope es job_timeout, no este aviso.
                    health = await self.health()
                    misses = 0
                    if health.get("reachable"):
                        logger.warning("El motor sigue vivo; el sondeo continúa")
                    else:
                        logger.warning("El motor no contestó el chequeo; el sondeo continúa")
                await asyncio.sleep(self.engine.poll_interval)
                continue
            misses = 0
            if on_update is not None:
                on_update(current)
            if current.status in TERMINAL_STATUSES:
                return current
            await asyncio.sleep(self.engine.poll_interval)

    def _drop_staged(self, task_id: str) -> None:
        """Borra la copia temporal cuando el motor ya terminó de leerla."""
        for path in self._staged.pop(task_id, []):
            try:
                Path(path).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(f"No se pudo borrar el audio temporal del motor: {exc}")

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
