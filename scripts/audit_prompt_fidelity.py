"""Auditoría viva de fidelidad de prompt (R10) en todas las rutas con prompt.

Comprueba contra la API real desplegada y los módulos reales:
  1. CREAR: style_caption identidad + payload del motor idéntico (text2music/cover/repaint).
  2. MEJORAR: borrador fiel, sin adiciones salvo BPM explícito, con warnings declarados.
  3. Módulo frontend: glossPrompt identidad (no sustituye la prueba de React).
  4. API viva: previews del motor y endpoints de sugerencias coherentes.

Sin mocks: todo se ejecuta de verdad; la evidencia JSON queda en logs/.
Se ejecuta con el venv del backend; HTTP usa urllib de la biblioteca estándar.
La captura UI/envío de generación pertenece a la sonda Electron separada.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import argparse
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from music_service import GenerationRequest, MusicService  # noqa: E402
from config import get_settings  # noqa: E402
from prompt_enhancer import enhance_prompt  # noqa: E402
from prompt_style import analyze_prompt, style_caption  # noqa: E402

ADVERSARIAL = [
    "techno oscuro, 130 bpm",
    "batería suave al fondo, sin voz",
    "bajo potente, sin voz",
    "electrónica con drops épicos",
    "sin techno, prefiero jazz",
    "cambia solo la batería; conserva el resto",
]

# Solo comprueba el módulo importado; no recrea el componente para fingir probarlo.
NODE_CHECK = """
import { glossPrompt } from './src/prompt_gloss.js';
import { readFileSync } from 'node:fs';
const prompts = JSON.parse(readFileSync(0, 'utf8'));
const checks = prompts.map((prompt) => ({
  prompt,
  equal: glossPrompt(prompt) === prompt.trim(),
}));
const status = checks.every((c) => c.equal) ? 'PASS' : 'FAIL';
process.stdout.write(JSON.stringify({ status, checks }));
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--api')
    parser.add_argument('--source')
    args = parser.parse_args()
    evidence = ROOT / "logs" / f"prompt-fidelity-audit-{time.strftime('%Y%m%d-%H%M%S')}.json"
    report: dict = {"checks": [], "status": "RUNNING",
                    "note": "Modules and live previews only; UI/send capture and artistic listening are separate"}
    settings = get_settings()
    api = args.api or f'http://{settings.host}:{settings.port}'
    service = MusicService(settings)
    def http(route, body=None):
        data = None if body is None else json.dumps(body).encode('utf-8')
        req = urllib.request.Request(api + route, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=settings.acestep.request_timeout) as response:
            return json.load(response)
    try:
        library = http('/music/library')['items']
        source = args.source or (library[0]['name'] if library else None)
        if not source:
            raise RuntimeError('La auditoría necesita un audio real existente para cover/repaint')
        # 1. CREAR y REMIX: caption y payload del motor, literales.
        for prompt in ADVERSARIAL:
            caption = style_caption(prompt)
            report["checks"].append({"path": "style_caption", "prompt": prompt,
                                     "equal": caption == prompt})
            for task in ("text2music", "cover", "repaint"):
                payload = service.build_payload(GenerationRequest(
                    prompt=caption, task_type=task,
                    source_path=None if task == "text2music" else str(settings.outputs_dir / source)))
                report["checks"].append({"path": f"payload:{task}", "prompt": prompt,
                                         "equal": payload["prompt"] == prompt})
                request = {'prompt': caption, 'task_type': task}
                if task != 'text2music':
                    request.update(source_name=source, source_kind='output')
                live_payload = http('/music/preview', request)['effective_parameters']
                report['checks'].append({'path': f'api:preview:{task}', 'prompt': prompt,
                                         'equal': live_payload == payload})
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
        # 3. Módulo de texto importado mediante Node.
        node = subprocess.run(
            ["node", "--input-type=module", "-e", NODE_CHECK],
            input=json.dumps(ADVERSARIAL), capture_output=True, text=True,
            cwd=ROOT / "frontend", check=True)
        report["frontend"] = json.loads(node.stdout)
        # 4. API viva desplegada: mismo contrato que los módulos.
        live = http('/music/style_options?' + urllib.parse.urlencode({'prompt': ADVERSARIAL[1]}))
        report["checks"].append({"path": "api:style_options", "equal": live == analyze_prompt(ADVERSARIAL[1]),
                                 "detected_genres": live.get("detected_genres")})
        enhanced = http('/music/enhance_prompt', {'prompt': ADVERSARIAL[1]})
        report["checks"].append({"path": "api:enhance_prompt",
                                 "equal": enhanced["enhanced"] == ADVERSARIAL[1],
                                 "additions": enhanced["additions"]})
        report["status"] = "PASS" if all(
            (c.get('equal') is True or c.get('untouched') is True)
            and c.get('warned', True) is True and c.get('additions_declared', True) is True
            for c in report['checks']
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
