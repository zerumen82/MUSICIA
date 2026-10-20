"""Los callbacks de producción del ciclo de vida deben ser corutinas reales.

Regresión del 2026-10-19: un `pause` que no era async rompía el cierre de toda
operación con `TypeError: object NoneType can't be used in 'await' expression`
y dejaba el estado del motor en error tras cada trabajo. La construcción de
`EngineLifecycle` no valida el tipo, así que el fallo solo aparecía en
producción, al terminar la primera operación.
"""

import asyncio
import unittest


class ProductionLifecycleCallbacksTest(unittest.TestCase):
    def test_wake_and_pause_are_real_coroutines(self):
        import main

        for name in ("_wake", "_pause"):
            with self.subTest(callback=name):
                callback = getattr(main.engine_lifecycle, name)
                self.assertTrue(
                    asyncio.iscoroutinefunction(callback),
                    f"{name} no es una corutina: {callback!r}",
                )
                # Crear la corutina sin ejecutarla: comprueba que devuelven una
                # corutina sin lanzar PowerShell ni tocar procesos.
                created = callback()
                self.assertTrue(asyncio.iscoroutine(created))
                created.close()

    def test_callbacks_delegate_to_the_supervisor_controls(self):
        # Un stub asíncrono (p. ej. `async def _noop_pause(): pass`) pasaría la
        # comprobación de corutina; este contrato exige que wake/pause manden
        # las acciones reales al supervisor local.
        import main

        actions: list[str] = []

        async def fake_engine_control(action: str) -> str:
            actions.append(action)
            return "MOTOR=test"

        original = main._engine_control
        main._engine_control = fake_engine_control
        try:
            asyncio.run(main.engine_lifecycle._wake())
            asyncio.run(main.engine_lifecycle._pause())
        finally:
            main._engine_control = original
        self.assertEqual(actions, ["WakeEngine", "IdleEngine"])


if __name__ == "__main__":
    unittest.main()
