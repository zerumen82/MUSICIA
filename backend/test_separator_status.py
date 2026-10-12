"""El estado del separador no puede congelar la API (bug 2026-10-08).

`GET /audio/separate/status` comprueba demucs lanzando un subproceso que
importa torch (segundos) y llama a nvidia-smi. Ese trabajo:

1. El positivo se cachea UNA vez por proceso; el NEGATIVO caduca cada
   `NEGATIVO_TTL_S` y se vuelve a comprobar (bug 2026-10-10: un chequeo en
   frío cacheó «no instalada» y mató dos remixes seguidos).
2. Corre en un hilo (`asyncio.to_thread`), nunca en el hilo del evento: ahí
   paraba TODA la API ~5 s y, en CREAR, el desplegable AÑADIR se quedaba en
   «AÑADIR · SIN DATOS DEL MOTOR» (el usuario lo reportó el 2026-10-08).
3. `separate()` no depende del cache: solo comprueba que exista el venv y
   lanza demucs, para que un falso negativo no bloquee un trabajo real.

Se ejecuta con el venv del backend:
    cd backend && ./venv/Scripts/python.exe -m unittest test_separator_status
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import main
import separator_service


class CacheDisponibilidad(unittest.TestCase):
    """La instalación no cambia mientras la app corre: se comprueba una vez."""

    def setUp(self) -> None:
        self._anterior = separator_service._DISPONIBLE
        self._anterior_ts = separator_service._DISPONIBLE_TS
        separator_service._DISPONIBLE = None
        separator_service._DISPONIBLE_TS = 0.0

    def tearDown(self) -> None:
        separator_service._DISPONIBLE = self._anterior
        separator_service._DISPONIBLE_TS = self._anterior_ts

    def test_no_vuelve_a_importar_torch_en_cada_llamada(self) -> None:
        """Dos consultas = UNA comprobación real (el import de torch cuesta
        segundos y en cada llamada congelaba el hilo de eventos)."""
        llamadas = {"n": 0}

        class _Proc:
            returncode = 0
            stdout = "ok\n"

        def _run(*args, **kwargs):
            llamadas["n"] += 1
            return _Proc()

        # El venv de demucs puede no existir en esta máquina: se parchea la
        # ruta por una que sí exista para que llegue al subproceso.
        with patch.object(separator_service, "DEMUCS_PYTHON", Path(__file__)), \
                patch.object(separator_service.subprocess, "run", side_effect=_run):
            self.assertTrue(separator_service.is_available())
            self.assertTrue(separator_service.is_available())
            self.assertEqual(llamadas["n"], 1, "la comprobación se repitió")

    def test_sin_demucs_la_respuesta_tambien_se_cachea(self) -> None:
        with patch.object(separator_service, "DEMUCS_PYTHON", Path("no_existe_ningun.exe")), \
                patch.object(separator_service.subprocess, "run") as run:
            self.assertFalse(separator_service.is_available())
            self.assertFalse(separator_service.is_available())
            run.assert_not_called()

    def test_un_fallo_cacheado_se_reintenta_tras_el_ttl(self) -> None:
        """Un chequeo que falla (frío, carga, timeout) NO deja la separación
        muerta toda la sesión: dentro del TTL no se repite, caducado sí."""
        llamadas = {"n": 0}

        class _Proc:
            returncode = 0
            stdout = "ok\n"

        def _run(*args, **kwargs):
            llamadas["n"] += 1
            return _Proc()

        with patch.object(separator_service, "DEMUCS_PYTHON", Path(__file__)), \
                patch.object(separator_service.subprocess, "run", side_effect=_run):
            # Negativo recién cacheado (por un fallo real): en vigor.
            separator_service._DISPONIBLE = False
            separator_service._DISPONIBLE_TS = time.monotonic()
            self.assertFalse(separator_service.is_available())
            self.assertEqual(llamadas["n"], 0, "recomprobó antes de caducar")

            # Caducado: vuelve a comprobar y se recupera.
            separator_service._DISPONIBLE_TS = (
                time.monotonic() - separator_service.NEGATIVO_TTL_S - 1
            )
            self.assertTrue(separator_service.is_available())
            self.assertEqual(llamadas["n"], 1, "no reintentó el chequeo")

            # El positivo ya no caduca.
            separator_service._DISPONIBLE_TS = 0.0
            self.assertTrue(separator_service.is_available())
            self.assertEqual(llamadas["n"], 1, "el positivo se volvió a comprobar")


class FueraDelHiloDeEventos(unittest.TestCase):
    """El subproceso corre en un hilo: el bucle sigue respondiendo."""

    def test_el_estado_se_calcula_fuera_del_hilo_del_evento(self) -> None:
        hilo_prueba = threading.get_ident()
        vistas: list[int] = []

        def _disponible() -> bool:
            vistas.append(threading.get_ident())
            return True

        def _dispositivo() -> str:
            vistas.append(threading.get_ident())
            return "cpu"

        with patch.object(main, "separator_available", side_effect=_disponible), \
                patch.object(main, "pick_device", side_effect=_dispositivo):
            res = asyncio.run(main.audio_separate_status())

        self.assertEqual(len(vistas), 2, "no se calcularon las dos partes del estado")
        self.assertNotIn(
            hilo_prueba, vistas,
            "el estado del separador se calculó en el hilo del evento: congelaría la API",
        )
        self.assertEqual(
            res,
            {"available": True, "device": "cpu", "message": "Separación de voces disponible."},
        )

    def test_mensajes_honestos_cuando_no_esta_instalado(self) -> None:
        with patch.object(main, "separator_available", return_value=False), \
                patch.object(main, "pick_device", return_value="cpu"):
            res = asyncio.run(main.audio_separate_status())
        self.assertFalse(res["available"])
        self.assertIn("Separación no instalada", res["message"])

    def test_el_bucle_sigue_mientras_se_comprueba(self) -> None:
        """Mientras el estado tarda, otras peticiones se atienden."""
        ticks: list[str] = []

        def _lento() -> tuple[bool, str]:
            for i in range(10):
                threading.Event().wait(0.02)
            return True, "cpu"

        async def _escenario() -> None:
            async def latido():
                for _ in range(10):
                    await asyncio.sleep(0.01)
                    ticks.append("tick")

            with patch.object(main, "_separator_estado", side_effect=_lento):
                await asyncio.gather(main.audio_separate_status(), latido())

        asyncio.run(_escenario())
        self.assertGreaterEqual(len(ticks), 5, "el bucle se quedó sin latir")


class SeparateSinDependerDelCache(unittest.TestCase):
    """`separate()` comprueba que exista el venv y lanza demucs: el cache de
    la UI (que puede tener un falso negativo) no manda sobre un trabajo real."""

    def test_sin_venv_dice_no_instalado_y_no_lanza_nada(self) -> None:
        with patch.object(separator_service, "DEMUCS_PYTHON", Path("no_existe_ningun.exe")), \
                patch.object(separator_service.subprocess, "run") as run:
            with self.assertRaises(RuntimeError) as ctx:
                separator_service.SeparatorService.separate(
                    Path(__file__), Path(tempfile.gettempdir()), "t"
                )
            self.assertIn("no está instalado", str(ctx.exception))
            run.assert_not_called()

    def test_un_negativo_cacheado_no_bloquea_la_separacion(self) -> None:
        """Bug 2026-10-10: el cache decía «no instalado» con el venv perfecto.
        Con el venv presente, el error debe ser el de demucs, no el del cache."""
        out_dir = Path(tempfile.mkdtemp(prefix="separacion-test-"))
        try:
            with patch.object(separator_service, "_DISPONIBLE", False), \
                    patch.object(separator_service, "DEMUCS_PYTHON", Path(__file__)), \
                    patch.object(separator_service, "pick_device", return_value="cpu"), \
                    patch.object(separator_service, "free_vram_mb", return_value=0), \
                    patch.object(separator_service, "is_available",
                                 side_effect=AssertionError("consultó el cache")), \
                    patch.object(separator_service.subprocess, "run") as run:
                run.returncode = 1
                run.stdout = ""
                run.stderr = "Traceback: torch no carga"
                with self.assertRaises(RuntimeError) as ctx:
                    separator_service.SeparatorService.separate(
                        Path(__file__), out_dir, "t"
                    )
            self.assertIn("demucs falló", str(ctx.exception))
            self.assertNotIn("no está instalado", str(ctx.exception))
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
