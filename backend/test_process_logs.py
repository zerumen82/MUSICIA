"""Colas reales de salida y error, sin motor ni ventana."""
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import ProcessLogSettings  # noqa: E402
from process_logs import collect_process_logs  # noqa: E402


class ProcessLogTailTest(unittest.TestCase):
    def test_tail_keeps_the_end_and_reports_a_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "logs"
            logs.mkdir()
            stdout = logs / "acestep-api.log"
            stdout.write_text("uno\ndos\ntres\ncuatro\n", encoding="utf-8")
            (logs / "acestep-api.err.log").write_bytes(b"error real\n")
            settings = ProcessLogSettings(
                engine_stdout="logs/acestep-api.log",
                engine_stderr="logs/acestep-api.err.log",
                api_stderr="logs/musicia-api.err.log",
                tail_lines=2,
                max_tail_lines=10,
                line_char_budget=20,
            )
            streams = {item["id"]: item for item in collect_process_logs(settings, root)}
            self.assertEqual(streams["engine_stdout"]["text"], "tres\ncuatro")
            self.assertTrue(streams["engine_stdout"]["present"])
            self.assertEqual(streams["engine_stderr"]["text"], "error real")
            self.assertFalse(streams["api_stderr"]["present"])
            self.assertEqual(streams["api_stderr"]["text"], "")

    def test_a_long_file_drops_the_beginning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "logs"
            logs.mkdir()
            text = "\n".join(f"linea-{index:04d}" for index in range(50)) + "\n"
            (logs / "acestep-api.log").write_text(text, encoding="utf-8")
            (logs / "acestep-api.err.log").write_text("e", encoding="utf-8")
            settings = ProcessLogSettings(tail_lines=3, max_tail_lines=10, line_char_budget=8)
            streams = {item["id"]: item for item in collect_process_logs(settings, root)}
            shown = streams["engine_stdout"]["text"]
            self.assertNotIn("linea-0000", shown)
            self.assertIn("linea-0049", shown)

    def test_a_path_outside_logs_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "logs").mkdir()
            settings = ProcessLogSettings(engine_stdout="backend/main.py")
            with self.assertRaises(ValueError):
                collect_process_logs(settings, root)

    def test_tail_lines_outside_the_configured_limit_fail(self):
        settings = ProcessLogSettings(tail_lines=0, max_tail_lines=10)
        with self.assertRaises(ValueError):
            collect_process_logs(settings, Path("."))


if __name__ == "__main__":
    unittest.main()
