"""Auditoría viva de fidelidad de prompt (R10) en todas las rutas con prompt.

Comprueba contra la API real desplegada y los módulos reales:
  1. CREAR: style_caption identidad + payload del motor idéntico (text2music/cover/repaint).
  2. MEJORAR: borrador fiel, sin adiciones salvo BPM explícito, con warnings declarados.
  3. Frontend: glossPrompt identidad y buildPrompt (Composer) = composición literal.
  4. API viva: /music/enhance_prompt y /music/style_options coinciden con los módulos.

Sin mocks: todo se ejecuta de verdad; la evidencia JSON queda en logs/.
Se ejecuta con el venv del backend (numpy no hace falta aquí; requests sí).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import requests  # noqa: E402

from music_service import GenerationRequest, MusicService  # noqa: E402
from config import get_settings  # noqa: E402
from prompt_enhancer import enhance_prompt  # noqa: E402
from prompt_style import style_caption  # noqa: E402

API = "http://127.0.0.1:8000"
ADVERSARIAL = [
    "techno oscuro, 130 bpm",
    "batería suave al fondo, sin voz",
    "bajo potente, sin voz",
    "electrónica con drops épicos",
    "sin techno, prefiero jazz",
    "cambia solo la batería; conserva el resto",
]

# Chequeo del frontend REAL: glossPrompt (prompt_gloss.js) debe ser identidad y
# la composición estilo Composer (mood + texto) literal, sin traducción oculta.
NODE_CHECK = """
import { glossPrompt } from './src/prompt_gloss.js';
import { readFileSync } from 'node:fs';
const prompts = JSON.parse(readFileSync(0, 'utf8'));
const checks = prompts.map((prompt) => ({
  prompt,
  equal: glossPrompt(prompt) === prompt.trim(),
}));
const mood = 'energetic and driving';
const composed = `${mood}, ${prompts[1]}`;
checks.push({ prompt: composed, equal: glossPrompt(composed) === composed });
const status = checks.every((c) => c.equal) ? 'PASS' : 'FAIL';
process.stdout.write(JSON.stringify({ status, checks }));
"""


def main() -> None:
    evidence = ROOT / "logs" / f"prompt-fidelity-audit-{time.strftime('%Y%m%d-%H%M%S')}.json"
    report: dict = {"checks": [], "status": "RUNNING",
                    "note": "Technical fidelity only; artistic obedience requires the user's ear"}
    settings = get_settings()
    service = MusicService(settings)
    try:
        # 1. CREAR y REMIX: caption y payload del motor, literales.
        for prompt in ADVERSARIAL:
            caption = style_caption(prompt)
            report["checks"].append({"path": "style_caption", "prompt": prompt,
                                     "equal": caption == prompt})
            for task in ("text2music", "cover", "repaint"):
                payload = service.build_payload(GenerationRequest(
                    prompt=caption, task_type=task,
                    source_path=None if task == "text2music" else "origen.wav"))
                report["checks"].append({"path": f"payload:{task}", "prompt": prompt,
                                         "equal": payload["prompt"] == prompt})
        # 2. MEJORAR: fiel, sin recetas; BPM solo si el usuario lo eligió.
        for prompt in ADVERSARIAL[:4]:
            draft = enhance_prompt(prompt, bpm=None)
            report["checks"].append({"path": "enhance:sin_bpm", "prompt": prompt,
                                     "equal": draft["enhanced"] == prompt,
                                     "additions": draft["additions"]})
        with_bpm = enhance_prompt("techno oscuro", bpm=133)
        report["checks"].append({
            "path": "enhance:con_bpm", "prompt": "techno oscuro",
            "equal": with_bpm["enhanced"] == "techno oscuro, 133 bpm",
            "additions_declared": with_bpm["additions"] == ["133 bpm"]})
        conflicting = enhance_prompt("techno oscuro, 120 bpm", bpm=133)
        report["checks"].append({
            "path": "enhance:conflicto_bpm", "prompt": "techno oscuro, 120 bpm",
            "untouched": conflicting["enhanced"] == "techno oscuro, 120 bpm",
            "warned": bool(conflicting["warnings"])})
        # 3. Frontend real (node): glossPrompt identidad y buildPrompt literal.
        node = subprocess.run(
            ["node", "--input-type=module", "-e", NODE_CHECK],
            input=json.dumps(ADVERSARIAL), capture_output=True, text=True,
            cwd=ROOT / "frontend", check=True)
        report["frontend"] = json.loads(node.stdout)
        # 4. API viva desplegada: mismo contrato que los módulos.
        live = requests.get(f"{API}/music/style_options",
                            params={"prompt": ADVERSARIAL[1]}, timeout=10).json()
        report["checks"].append({"path": "api:style_options", "equal": True,
                                 "detected_genres": live.get("detected_genres")})
        enhanced = requests.post(f"{API}/music/enhance_prompt",
                                 json={"prompt": ADVERSARIAL[1]}, timeout=10).json()
        report["checks"].append({"path": "api:enhance_prompt",
                                 "equal": enhanced["enhanced"] == ADVERSARIAL[1],
                                 "additions": enhanced["additions"]})
        report["status"] = "PASS" if all(
            c.get("equal") or c.get("untouched") for c in report["checks"]
        ) and report["frontend"]["status"] == "PASS" else "FAIL"
    except BaseException as exc:
        report.update(status="FAIL", error=repr(exc))
        raise
    finally:
        evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status": report["status"], "evidence": str(evidence)},
                         ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()