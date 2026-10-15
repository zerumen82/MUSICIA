"""Regression tests for the exact vendor patch and real torch CPU conversions.

Run with vendor/ACE-Step-1.5/.venv/Scripts/python.exe -m unittest
scripts.test_acestep_vae_patch. No checkpoints or CUDA contexts are loaded.
"""

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from scripts import apply_acestep_patches as patcher


ENGINE_ROOT = patcher.PROJECT_ROOT / "vendor" / "ACE-Step-1.5"
sys.path.insert(0, str(ENGINE_ROOT))
spec = importlib.util.spec_from_file_location("musicia_vae_decode", ENGINE_ROOT / patcher.TARGET_FILE)
decode_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decode_module)


class SmallVae(torch.nn.Module):
    """A real convolution catches dtype mismatches and records executed dtype."""

    def __init__(self):
        super().__init__()
        self.conv = torch.nn.Conv1d(3, 2, 1).to(dtype=torch.bfloat16)
        self.executed = []
        self.fail_decode = False
        self.fail_prepare = False

    @property
    def dtype(self):
        return next(self.parameters()).dtype

    def to(self, *args, **kwargs):
        result = super().to(*args, **kwargs)
        if self.fail_prepare and kwargs.get("dtype") == torch.float32:
            raise RuntimeError("CPU preparation failed after conversion")
        return result

    def decode(self, latents):
        self.executed.append((latents.device.type, latents.dtype, self.dtype))
        if self.fail_decode:
            raise RuntimeError("decode failed")
        return SimpleNamespace(sample=self.conv(latents))


class SmallHost(decode_module.GenerateMusicDecodeMixin):
    def __init__(self):
        self.vae = SmallVae()
        self.device = "cpu"
        self.use_mlx_vae = False
        self.mlx_vae = None
        self.current_offload_cost = 0

    @contextmanager
    def _load_model_context(self, _name):
        yield

    def _get_vae_dtype(self, device):
        self.assert_cpu_device = device
        return torch.float32

    def _empty_cache(self):
        return None

    def _memory_allocated(self):
        return 0

    def _max_memory_allocated(self):
        return 0

    def tiled_decode(self, latents):
        return self.vae.decode(latents).sample

    def run_decode(self, tiled=False):
        return self._decode_generate_music_pred_latents(
            torch.ones(1, 4, 3, dtype=torch.bfloat16), None, tiled, {"total_time_cost": 0},
        )


class CpuVaeContractTests(unittest.TestCase):
    def test_cpu_dtype_and_original_dtype_restored_for_forced_and_auto_decode(self):
        for forced in ("0", "1"):
            for tiled in (False, True):
                with self.subTest(forced=forced, tiled=tiled):
                    host = SmallHost()
                    with patch.dict(decode_module.os.environ, {"ACESTEP_VAE_ON_CPU": forced}), patch.object(
                        decode_module, "get_effective_free_vram_gb", return_value=0.15,
                    ):
                        audio, latents, _costs = host.run_decode(tiled)
                    self.assertEqual(host.vae.executed, [("cpu", torch.float32, torch.float32)])
                    self.assertEqual(host.vae.dtype, torch.bfloat16)
                    self.assertEqual(next(host.vae.parameters()).device.type, "cpu")
                    self.assertEqual(host.assert_cpu_device, "cpu")
                    self.assertEqual(audio.dtype, torch.float32)
                    self.assertEqual(tuple(audio.shape), (1, 2, 4))
                    self.assertTrue(torch.isfinite(audio).all())
                    self.assertEqual(latents.device.type, "cpu")

    def test_restore_after_decode_or_cpu_preparation_failure(self):
        for failure in ("fail_decode", "fail_prepare"):
            with self.subTest(failure=failure):
                host = SmallHost()
                setattr(host.vae, failure, True)
                with patch.dict(decode_module.os.environ, {"ACESTEP_VAE_ON_CPU": "1"}):
                    with self.assertRaisesRegex(RuntimeError, "failed"):
                        host.run_decode()
                self.assertEqual(host.vae.dtype, torch.bfloat16)
                self.assertEqual(next(host.vae.parameters()).device.type, "cpu")


class PatchApplicationTests(unittest.TestCase):
    def test_apply_once_original_crlf_and_leave_already_applied_untouched(self):
        source = (ENGINE_ROOT / patcher.TARGET_FILE).read_text(encoding="utf-8")
        for before, after in patcher.patch_hunks(patcher.PATCH_FILE.read_text(encoding="utf-8")):
            if after in source:
                source = source.replace(after, before, 1)
        with tempfile.TemporaryDirectory() as folder:
            engine_root = Path(folder)
            target = engine_root / patcher.TARGET_FILE
            target.parent.mkdir(parents=True)
            target.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
            self.assertEqual(patcher.apply_patch(engine_root), "applied")
            patched = target.read_bytes()
            self.assertIn(b"\r\n", patched)
            self.assertNotIn(b"\n", patched.replace(b"\r\n", b""))
            modified = target.stat().st_mtime_ns
            self.assertEqual(patcher.apply_patch(engine_root), "already-applied")
            self.assertEqual(target.read_bytes(), patched)
            self.assertEqual(target.stat().st_mtime_ns, modified)

    def test_unknown_source_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            engine_root = Path(folder)
            target = engine_root / patcher.TARGET_FILE
            target.parent.mkdir(parents=True)
            source = b"# unexpected upstream change\n"
            target.write_bytes(source)
            with self.assertRaisesRegex(ValueError, "Unknown ACE-Step"):
                patcher.apply_patch(engine_root)
            self.assertEqual(target.read_bytes(), source)


if __name__ == "__main__":
    unittest.main()
