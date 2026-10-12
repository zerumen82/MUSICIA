"""B2: remix modo voz real contra el stack local y su historial persistido."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
EVIDENCE = ROOT / "logs" / "fix-20261012-voice-result.json"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as response:
        return json.loads(response.read())


def run():
    request_body = {
        "file_name": "Animales muertos.mp3", "source_kind": "upload", "mode": "voz",
        "prompt": "hardtek gabber a steady four-on-the-floor kick drum",
        "duration_seconds": 30, "bpm": 180,
        "output_name": "diagnostico-b2-" + datetime.now().strftime("%Y%m%d-%H%M%S"),
    }
    evidence = {"request": request_body, "started_at": datetime.now().astimezone().isoformat()}
    try:
        before = get("/music/config")
        evidence["config"] = before
        req = urllib.request.Request(BASE + "/audio/remix/ai", method="POST",
                                     data=json.dumps(request_body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            accepted = json.loads(response.read())
            evidence["accepted"] = accepted
        job_id = accepted["job_id"]
        print("JOB", job_id, flush=True)
        deadline = time.monotonic() + 1900
        while True:
            status = get("/audio/remix/ai/" + job_id)
            evidence["last_status"] = status
            EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            print(datetime.now().strftime("%H:%M:%S"), status["status"], status.get("phase"),
                  "elapsed", status.get("elapsed_seconds"), flush=True)
            if status["status"] not in ("queued", "running"):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Remix sigue activo tras 1900 s; no se cancela automáticamente")
            time.sleep(15)
        assert status["status"] == "succeeded", status
        variants = status["result"]["variants"]
        assert len(variants) == 2, variants
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise RuntimeError("ffprobe no disponible")
        probes = []
        for name in variants:
            path = ROOT / "backend" / "outputs" / name
            assert path.is_file() and path.stat().st_size > 0, path
            proc = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration,size",
                                   "-of", "json", str(path)], capture_output=True, text=True, check=True)
            probe = json.loads(proc.stdout)
            assert float(probe["format"]["duration"]) >= 24, probe
            probes.append({"name": name, "ffprobe_exit": proc.returncode, "probe": probe})
        evidence["audio"] = probes
        history = json.loads((ROOT / "backend" / "job_history.json").read_text(encoding="utf-8"))
        matching = [j for j in history["remix"] if j["job_id"] == job_id]
        assert len(matching) == 1 and matching[0]["status"] == "succeeded", matching
        assert matching[0]["result"]["variants"] == variants, matching
        evidence["persisted_job"] = matching[0]
        evidence["finished_at"] = datetime.now().astimezone().isoformat()
        evidence["verdict"] = "PASS"
        print("PASS: 2 MP3 verificados y job succeeded persistido", flush=True)
    finally:
        EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
