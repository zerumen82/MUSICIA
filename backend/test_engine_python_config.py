"""Engine runtime configuration remains compatible with older config files."""

import unittest

from config import AppSettings, _merge_tree, engine_launch_config


class EnginePythonConfigTest(unittest.TestCase):
    def test_default_engine_and_style_worker_share_python_environment(self):
        settings = AppSettings()
        expected = "vendor/ACE-Step-1.5/.venv311/Scripts/python.exe"

        self.assertEqual(settings.acestep.python_path, expected)
        self.assertEqual(settings.style_translation.python_path, expected)

    def test_legacy_config_without_engine_python_uses_dataclass_default(self):
        settings = AppSettings()
        _merge_tree(settings, {"acestep": {"base_url": "http://127.0.0.1:8001"}})

        self.assertEqual(
            settings.acestep.python_path,
            "vendor/ACE-Step-1.5/.venv311/Scripts/python.exe",
        )

    def test_launch_uses_configured_primary_model_and_explicit_offload(self):
        settings = AppSettings()

        launch = engine_launch_config(settings)

        self.assertEqual(launch["python_path"], settings.acestep.python_path)
        self.assertEqual(launch["lifecycle"], {
            "start_timeout_seconds": 300,
            "stop_timeout_seconds": 15,
        })
        self.assertEqual(launch["environment"], {
            "ACESTEP_CONFIG_PATH": settings.generation.model,
            "ACESTEP_LM_MODEL_PATH": settings.generation.lm_model,
            "ACESTEP_LM_BACKEND": settings.generation.lm_backend,
            "ACESTEP_GENERATION_TIMEOUT": "1800",
            "ACESTEP_ON_DEMAND_MODEL_LOAD": "true",
            "ACESTEP_OFFLOAD_TO_CPU": "true",
            "ACESTEP_OFFLOAD_DIT_TO_CPU": "false",
            "ACESTEP_LM_OFFLOAD_TO_CPU": "true",
        })

    def test_launch_respects_custom_models_timeout_python_and_disabled_offload(self):
        settings = AppSettings()
        _merge_tree(settings, {
            "acestep": {
                "python_path": "custom/python.exe", "job_timeout": 2345.9,
                "lifecycle_start_timeout_seconds": 420,
                "lifecycle_stop_timeout_seconds": 22,
                "offload_to_cpu": False, "offload_dit_to_cpu": False,
                "lm_offload_to_cpu": False,
            },
            "generation": {"model": "configured-main", "lm_model": "configured-lm",
                           "lm_backend": "configured-backend"},
        })

        self.assertEqual(engine_launch_config(settings), {
            "python_path": "custom/python.exe",
            "lifecycle": {
                "start_timeout_seconds": 420,
                "stop_timeout_seconds": 22,
            },
            "environment": {
                "ACESTEP_CONFIG_PATH": "configured-main",
                "ACESTEP_LM_MODEL_PATH": "configured-lm",
                "ACESTEP_LM_BACKEND": "configured-backend",
                "ACESTEP_GENERATION_TIMEOUT": "2345",
                "ACESTEP_ON_DEMAND_MODEL_LOAD": "true",
                "ACESTEP_OFFLOAD_TO_CPU": "false",
                "ACESTEP_OFFLOAD_DIT_TO_CPU": "false",
                "ACESTEP_LM_OFFLOAD_TO_CPU": "false",
            },
        })

    def test_legacy_config_keeps_offload_defaults_and_its_generation_profile(self):
        settings = AppSettings()
        _merge_tree(settings, {
            "acestep": {"base_url": "http://127.0.0.1:8001", "job_timeout": 900},
            "generation": {"model": "legacy-main", "lm_model": "legacy-lm"},
        })

        environment = engine_launch_config(settings)["environment"]

        self.assertEqual(environment["ACESTEP_CONFIG_PATH"], "legacy-main")
        self.assertEqual(environment["ACESTEP_LM_MODEL_PATH"], "legacy-lm")
        self.assertEqual(environment["ACESTEP_GENERATION_TIMEOUT"], "900")
        for name in ("ACESTEP_OFFLOAD_TO_CPU", "ACESTEP_LM_OFFLOAD_TO_CPU"):
            self.assertEqual(environment[name], "true")
        self.assertEqual(environment["ACESTEP_OFFLOAD_DIT_TO_CPU"], "false")


if __name__ == "__main__":
    unittest.main()
