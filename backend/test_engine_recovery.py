"""Recuperación del motor: busy no reinicia; caído reinicia y reintenta.

Regresión del 2026-10-18: un chequeo /health antes de cada petición trataba
`busy` (estado normal generando) como motor muerto y lo reiniciaba sobre su
propia generación. Estos tests fijan el contrato corregido.
"""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import AppSettings  # noqa: E402
from music_service import MusicService  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class EngineRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.service = MusicService(AppSettings())
        self.client = Mock()
        self.client.request = AsyncMock(
            return_value=_Response({"code": 200, "data": {"ok": True}})
        )
        self.service._client = self.client

    def test_busy_engine_is_not_restarted(self):
        """Generando (busy) no es motor muerto: se continúa sin reiniciar."""
        async def scenario():
            salud = AsyncMock(return_value={"reachable": True, "busy": True})
            with patch.object(self.service, "health", new=salud), \
                    patch.object(MusicService, "_restart_engine", new=Mock()) as restart:
                result = await self.service._request("POST", "/release_task", json={})
            self.assertEqual(result, {"ok": True})
            restart.assert_not_called()
        run(scenario())

    def test_unreachable_engine_is_restarted_and_request_retried(self):
        async def scenario():
            salud = AsyncMock(return_value={"reachable": False, "error": "ConnectError"})
            with patch.object(self.service, "health", new=salud), \
                    patch.object(MusicService, "_restart_engine", new=Mock()) as restart, \
                    patch("music_service.asyncio.sleep", new=AsyncMock()):
                result = await self.service._request("POST", "/release_task", json={})
            self.assertEqual(result, {"ok": True})
            restart.assert_called_once()
        run(scenario())

    def test_status_poll_skips_the_alive_check(self):
        """El sondeo /query_result no pasa por el chequeo previo."""
        async def scenario():
            self.client.request = AsyncMock(return_value=_Response({"code": 200, "data": []}))
            salud = AsyncMock(return_value={"reachable": True, "busy": True})
            with patch.object(self.service, "health", new=salud) as health, \
                    patch.object(MusicService, "_restart_engine", new=Mock()) as restart:
                estado = await self.service.status("task-x")
            health.assert_not_called()
            restart.assert_not_called()
            self.assertTrue(estado.pending)
        run(scenario())

    def test_failing_alive_probe_does_not_block_nor_restart(self):
        """Si el propio /health revienta, se continúa: el error lo dirá la petición."""
        async def scenario():
            salud = AsyncMock(side_effect=RuntimeError("transporte raro"))
            with patch.object(self.service, "health", new=salud), \
                    patch.object(MusicService, "_restart_engine", new=Mock()) as restart:
                result = await self.service._request("POST", "/release_task", json={})
            self.assertEqual(result, {"ok": True})
            restart.assert_not_called()
        run(scenario())

    def test_connect_error_restarts_engine_once_and_retries(self):
        async def scenario():
            self.client.request = AsyncMock(side_effect=[
                httpx.ConnectError("connection refused"),
                _Response({"code": 200, "data": {"ok": True}}),
            ])
            salud = AsyncMock(return_value={"reachable": True, "error": "down"})
            with patch.object(self.service, "health", new=salud), \
                    patch.object(MusicService, "_restart_engine", new=Mock()) as restart, \
                    patch("music_service.asyncio.sleep", new=AsyncMock()):
                result = await self.service._request("POST", "/release_task", json={})
            self.assertEqual(result, {"ok": True})
            restart.assert_called_once()
        run(scenario())


if __name__ == "__main__":
    unittest.main()