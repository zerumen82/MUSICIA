"""La API colgada no se confunde con un arranque ni con el motor ocupado.

Tampoco se conserva una API que responde pero corre código anterior al
último cambio de backend/*.py: eso dejaba el servidor vivo con el bug
de turno aunque el proceso respondiera /health.
"""

import os
import tempfile
import unittest
from pathlib import Path

from api_supervisor import api_is_stale, api_is_wedged, newest_backend_source_write
from config import AppSettings


class ApiSupervisorTest(unittest.TestCase):
    def test_a_fresh_process_is_still_starting(self):
        self.assertFalse(api_is_wedged(
            health_ok=False, port_accepts=False, age_seconds=5, grace_seconds=60,
        ))

    def test_a_process_that_stopped_listening_is_wedged(self):
        self.assertTrue(api_is_wedged(
            health_ok=False, port_accepts=False, age_seconds=60, grace_seconds=60,
        ))
        self.assertTrue(api_is_wedged(
            health_ok=False, port_accepts=False, age_seconds=3600, grace_seconds=60,
        ))

    def test_health_or_an_open_port_is_not_wedged(self):
        self.assertFalse(api_is_wedged(
            health_ok=True, port_accepts=False, age_seconds=3600, grace_seconds=60,
        ))
        self.assertFalse(api_is_wedged(
            health_ok=False, port_accepts=True, age_seconds=3600, grace_seconds=60,
        ))

    def test_the_wait_comes_from_settings(self):
        self.assertEqual(AppSettings().api_listen_grace_seconds, 60.0)

    def test_grace_and_age_must_make_sense(self):
        with self.assertRaises(ValueError):
            api_is_wedged(health_ok=False, port_accepts=False, age_seconds=10, grace_seconds=0)
        with self.assertRaises(ValueError):
            api_is_wedged(health_ok=False, port_accepts=False, age_seconds=-1, grace_seconds=60)


class ApiStaleTest(unittest.TestCase):
    def test_newer_code_than_the_process_marks_it_stale(self):
        # Código escrito hace 10 s, proceso arrancado hace 3600 s: sirve lo viejo.
        self.assertTrue(api_is_stale(source_write_age_seconds=10.0, process_age_seconds=3600.0))

    def test_code_older_or_equal_to_the_process_is_current(self):
        self.assertFalse(api_is_stale(source_write_age_seconds=3600.0, process_age_seconds=10.0))
        # Empate = misma resolución de segundos: sin reinicios gratuitos.
        self.assertFalse(api_is_stale(source_write_age_seconds=60.0, process_age_seconds=60.0))

    def test_negative_ages_are_a_wiring_bug(self):
        with self.assertRaises(ValueError):
            api_is_stale(source_write_age_seconds=-1.0, process_age_seconds=10.0)
        with self.assertRaises(ValueError):
            api_is_stale(source_write_age_seconds=10.0, process_age_seconds=-1.0)

    def test_the_newest_write_comes_from_first_level_python_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = Path(tmp)
            (backend / "old.py").write_text("x = 1\n", encoding="utf-8")
            os.utime(backend / "old.py", (100.0, 100.0))
            (backend / "new.py").write_text("x = 2\n", encoding="utf-8")
            os.utime(backend / "new.py", (300.0, 300.0))
            # venv y __pycache__ no son código que la API cargue.
            venv = backend / "venv"
            venv.mkdir()
            (venv / "site.py").write_text("x = 3\n", encoding="utf-8")
            os.utime(venv / "site.py", (900.0, 900.0))
            cache = backend / "__pycache__"
            cache.mkdir()
            (cache / "new.cpython-310.pyc").write_bytes(b"\x00")
            os.utime(cache / "new.cpython-310.pyc", (900.0, 900.0))

            self.assertEqual(newest_backend_source_write(backend), 300.0)

    def test_a_backend_without_python_files_is_not_comparable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                newest_backend_source_write(tmp)

    def test_a_missing_backend_directory_is_not_comparable(self):
        with self.assertRaises(ValueError):
            newest_backend_source_write(Path(tempfile.gettempdir()) / "musicia-no-existe")


if __name__ == "__main__":
    unittest.main()
