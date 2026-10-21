"""Run explicit B9b A/B requests through the real local API and ffprobe outputs.

The manifest contains the exact two payloads; no engine configuration is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if urllib.parse.urlsplit(args.api).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Local API required")
    args.output.mkdir(parents=True, exist_ok=True)
    result_file = args.output / "audio-result.json"
    if result_file.exists():
        raise ValueError("Use a fresh output directory")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    report = {"status": "RUNNING", "started_at": time.time(), "manifest": manifest, "cases": []}

    def save() -> None:
        result_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def request(route: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(args.api.rstrip("/") + route, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=manifest["submit_timeout_seconds"]) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{route} HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc

    try:
        save()
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise ValueError("Installed ffprobe is required")
        report["health"] = request("/health")
        jobs = request("/music/jobs")
        if any(job["status"] in {"running", "queued"} for job in jobs["items"]):
            raise ValueError("Another real job is active; no audio submitted")
        for case in manifest["cases"]:
            payload = dict(case["request"])
            entry = {"label": case["label"], "request": payload, "polls": []}
            report["cases"].append(entry)
            if case.get("preparation"):
                entry["preparation_request"] = case["preparation"]
                entry["preparation_response"] = request("/music/enhance_prompt", case["preparation"])
                payload["prompt"] = entry["preparation_response"]["enhanced"]
            entry["preview"] = request("/music/preview", payload)
            save()
            entry["submitted"] = request("/music/generate", payload)
            save()
            deadline = time.monotonic() + manifest["job_timeout_seconds"]
            while time.monotonic() < deadline:
                status = request("/music/status/" + entry["submitted"]["job_id"])
                entry["polls"].append({"at": time.time(), "status": status["status"],
                                       "phase": status.get("phase"), "error": status.get("error")})
                save()
                if status["status"] in {"succeeded", "failed", "cancelled"}:
                    entry["job"] = status
                    break
                time.sleep(manifest["poll_interval_seconds"])
            else:
                raise TimeoutError(f"Actual job timeout: {entry['submitted']['job_id']}")
            if status["status"] != "succeeded":
                raise RuntimeError(f"Actual generation {status['status']}: {status.get('error')}")
            if status["effective_parameters"] != entry["preview"]["effective_parameters"]:
                raise AssertionError("Preview and executed effective parameters differ")
            names = [item["file_name"] for item in status.get("variant_metadata", [])]
            if not names:
                names = status.get("variants") or [status["output_name"]]
            entry["files"] = []
            for name in names:
                if not isinstance(name, str):
                    raise AssertionError(f"Unexpected actual variant descriptor: {name!r}")
                audio = (Path(manifest["outputs_directory"]) / name).resolve()
                if audio.parent != Path(manifest["outputs_directory"]).resolve():
                    raise AssertionError("Variant path escaped outputs")
                if not audio.is_file() or audio.stat().st_size == 0:
                    raise AssertionError(f"Actual output missing/empty: {audio}")
                probe = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                                        "format=duration:stream=codec_name,sample_rate,channels", "-of", "json", str(audio)],
                                       capture_output=True, text=True, check=True)
                decoded = json.loads(probe.stdout)
                if float(decoded["format"]["duration"]) <= 0:
                    raise AssertionError(f"Actual output duration is zero: {audio}")
                entry["files"].append({"path": str(audio), "bytes": audio.stat().st_size,
                                       "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
                                       "ffprobe": decoded, "ffprobe_exit_code": probe.returncode})
            print(f"{case['label']}: actual job {status['job_id']} succeeded; {len(entry['files'])} nonempty decoded outputs", flush=True)
            save()
        report["status"] = "PASS"
        report["listening_verdict"] = "PENDING_USER: technical audio validity does not establish artistic fidelity"
        return 0
    except Exception:
        report["status"] = "FAIL"
        report["error"] = traceback.format_exc()
        print(report["error"], flush=True)
        return 1
    finally:
        report["completed_at"] = time.time()
        save()
        print(f"AUDIO={report['status']} EVIDENCE={result_file}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
