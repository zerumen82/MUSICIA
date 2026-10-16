"""La API colgada no se confunde con un arranque ni con el motor ocupado."""

import unittest

from api_supervisor import api_is_wedged
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


if __name__ == "__main__":
    unittest.main()
