"""Independent live acceptance: conflicts, active GPU cancellation and restart recovery.

Only cancels a job created by this probe. Does not restart the API itself: the
coordinator restarts Musicia between `cancel` and `recovery` phases. No installs.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def http(api, method, route, body=None, expected=200):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(api + route, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            code, value = response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        code, value = exc.code, json.load(exc)
    assert code == expected, (method, route, code, value)
    return value

def pid(port):
    result = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, check=True)
    return next((int(row.split()[4]) for row in result.stdout.splitlines()
                 if len(row.split()) >= 5 and row.split()[0] == "TCP"
                 and row.split()[3] == "LISTENING" and row.split()[1].rsplit(":", 1)[-1] == str(port)), None)

def probe(path):
    assert path.is_file() and path.stat().st_size > 0, str(path)
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(path)]
    run = subprocess.run(command, capture_output=True, text=True, check=True)
    value = json.loads(run.stdout)
    assert float(value["format"]["duration"]) > 0
    return value

def until(label, callback, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = callback()
        if value:
            print(label, json.dumps(value, ensure_ascii=False)[:800], flush=True)
            return value
        time.sleep(0.5)
    raise TimeoutError(label)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["validation", "cancel", "recovery"])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--source", default="pista-sin-nombre (2).mp3")
    parser.add_argument("--state", default=str(ROOT / "logs" / "plan-completion-state.json"))
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    target = ROOT / "logs" / f"plan-completion-{args.phase}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    report = {"status": "RUNNING", "phase": args.phase, "artistic_quality": "NOT CERTIFIED"}
    try:
        if args.phase == "validation":
            report["cases"] = []
            cases = [
                {"prompt": "techno a 120 BPM", "bpm": 140, "instrumental": True},
                {"prompt": "canción sin voz", "instrumental": False, "lyrics": "[Verse]\nEsta canción"},
                {"prompt": "waltz in 3/4", "time_signature": "4/4", "instrumental": True},
            ]
            before = http(args.api, "GET", "/music/jobs")
            for body in cases:
                body["duration_seconds"] = 30
                for route in ("/music/preview", "/music/generate"):
                    response = http(args.api, "POST", route, body, expected=422)
                    report["cases"].append({"route": route, "request": body, "response": response})
            after = http(args.api, "GET", "/music/jobs")
            assert len(before["items"]) == len(after["items"]), "Conflicts admitted a new job"
            report["jobs_before_after"] = [len(before["items"]), len(after["items"])]
        elif args.phase == "cancel":
            existing = http(args.api, "GET", "/music/jobs")
            assert not any(row.get("status") in {"queued", "running"} for row in existing["items"]), "Other Musicia job active"
            body = {"source_name": args.source, "source_kind": "output", "scope": "full",
                    "prompt": "Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos",
                    "seed": 734219, "source_classification": "electronic", "classification_origin": "manual",
                    "output_name": "prueba-plan-cancel-" + time.strftime('%H%M%S')}
            report["request"] = body
            accepted = http(args.api, "POST", "/music/remix/project", body)
            own_id = accepted["job_id"]
            route = "/audio/remix/ai/" + own_id
            def active():
                job = http(args.api, "GET", route)
                if job["status"] in {"failed", "succeeded"}:
                    raise AssertionError(("Ended before active cancellation", job))
                return job if job.get("engine_active") and job.get("engine_task_id") else None
            report["active_job"] = until("Engine submitted real job", active, args.timeout)
            old_pid = pid(8001)
            assert old_pid, "No actual motor listener"
            report["motor_pid_before"] = old_pid
            report["cancellation"] = http(args.api, "POST", f"/music/jobs/{own_id}/cancel", {})
            dead = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}", "/FO", "CSV"], capture_output=True, text=True, check=True)
            assert f'"{old_pid}"' not in dead.stdout, dead.stdout
            report["old_process_check"] = dead.stdout
            def relaunched():
                try:
                    health = http("http://127.0.0.1:8001", "GET", "/health")
                    next_pid = pid(8001)
                    return {"pid": next_pid, "health": health} if next_pid and next_pid != old_pid else None
                except (OSError, AssertionError):
                    return None
            report["motor_relaunched"] = until("ensure_local relaunched motor", relaunched, args.timeout)
            report["cancelled_job"] = http(args.api, "GET", route)
            assert report["cancelled_job"]["cancelled"] and report["cancelled_job"]["status"] == "failed"
            body["output_name"] = "prueba-plan-recovery-" + time.strftime('%H%M%S')
            report["preview_after_restart"] = http(args.api, "POST", "/music/remix/preview", body)
            accepted = http(args.api, "POST", "/music/remix/project", body)
            def completed():
                job = http(args.api, "GET", "/audio/remix/ai/" + accepted["job_id"])
                if job["status"] == "failed":
                    raise AssertionError(job)
                return job if job["status"] == "succeeded" else None
            job = until("New real audio after motor cancellation", completed, args.timeout)
            report["recovered_generation"] = job
            report["audio"] = [probe(ROOT / "backend" / "outputs" / name) for name in job["result"]["variants"]]
            assert job["effective_parameters"] == report["preview_after_restart"]["effective_parameters"]
            assert job["result"]["classification_origin"] == "manual"
            assert all(meta.get("seed") is not None and meta.get("seed_origin") != "unknown" for meta in job["result"]["metadata"])
            state = {"job": job, "request": body, "cancelled_id": own_id, "api_pid": pid(8000)}
            Path(args.state).write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            state = json.loads(Path(args.state).read_text(encoding="utf-8"))
            assert pid(8000) != state["api_pid"], "API has not actually restarted"
            saved = state["job"]
            job = http(args.api, "GET", "/audio/remix/ai/" + saved["job_id"])
            for key in ("status", "project", "result", "effective_parameters", "source_analysis"):
                assert job.get(key) == saved.get(key), ("Persistence mismatch", key)
            report["job"] = job
            report["audio"] = [probe(ROOT / "backend" / "outputs" / name) for name in job["result"]["variants"]]
            cancelled = http(args.api, "GET", "/audio/remix/ai/" + state["cancelled_id"])
            assert cancelled["status"] == "failed" and "Cancelado" in cancelled["error"]
            report["cancelled_recovered"] = cancelled
        report["status"] = "PASS"
    except Exception as exc:
        report.update(status="FAIL", error=repr(exc))
        raise
    finally:
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"status": report["status"], "evidence": str(target)}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
