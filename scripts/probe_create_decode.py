"""Real serial CREAR regression after the API conversion recognizer correction."""
import argparse
import json
from pathlib import Path
import time

from probe_decode_recovery import audio_evidence, get_settings, http, timestamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--prompt", default="gabber hardcore")
    parser.add_argument("--job-id", help="Observe existing UI-submitted job; never submit another")
    parser.add_argument("--request-file", type=Path, help="Real UI submitted.json for observe mode")
    args = parser.parse_args()
    settings = get_settings()
    report = {"status": "RUNNING", "started_at": timestamp(), "polling": []}
    body = {"prompt": args.prompt, "instrumental": True, "duration_seconds": args.seconds,
            "output_name": "prueba-crear-decode-" + time.strftime("%Y%m%d-%H%M%S")}
    if args.request_file:
        assert args.job_id, "Existing job ID required for UI request file"
        body = json.loads(args.request_file.read_text(encoding="utf-8-sig"))["request"]
    report["request"] = body

    def save():
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        report["preview"] = http(args.api, "/music/preview", 60, body)
        if args.job_id:
            job_id = args.job_id
        else:
            existing = http(args.api, "/music/jobs", 60)
            assert not any(job["status"] in {"queued", "running"} for job in existing["items"]), "Other active Musicia jobs"
            report["accepted"] = http(args.api, "/music/generate", 60, body)
            job_id = report["accepted"]["job_id"]
        save()
        print(json.dumps({"create_job_id": job_id, "evidence": str(args.report)}), flush=True)
        deadline = time.monotonic() + settings.acestep.job_timeout
        last_phase = None
        while time.monotonic() < deadline:
            job = http(args.api, "/music/status/" + job_id, 60)
            row = {"at": timestamp(), **{key: job.get(key) for key in (
                "status", "phase", "stage", "progress_ratio", "engine_progress", "engine_progress_text", "error")}}
            report["polling"].append(row)
            report["job"] = job
            save()
            if row["phase"] != last_phase:
                print(json.dumps(row, ensure_ascii=False), flush=True)
                last_phase = row["phase"]
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(settings.acestep.poll_interval)
        else:
            raise TimeoutError("CREAR deadline exceeded; job left untouched")
        assert job["status"] == "succeeded", job.get("error")
        assert job["effective_parameters"] == report["preview"]["effective_parameters"], "Preview/execution mismatch"
        payload = job["effective_parameters"]
        defaults = settings.generation
        for key, expected in {"model": defaults.model, "inference_steps": defaults.steps_by_model.get(defaults.model, defaults.inference_steps),
                              "guidance_scale": defaults.guidance_by_model.get(defaults.model, defaults.guidance_scale), "batch_size": defaults.batch_size,
                              "thinking": defaults.thinking, "use_format": defaults.use_format,
                              "lm_model_path": defaults.lm_model, "lm_backend": defaults.lm_backend}.items():
            assert payload[key] == expected, (key, payload[key], expected)
        assert payload["prompt"] == body["prompt"]
        conversion = [row for row in report["polling"] if row["phase"] in {
            "Convirtiendo a audio", "Convirtiendo a audio final"}]
        assert any(row["engine_progress"] == 0.8 for row in conversion), "Final real decode not observed"
        assert all(row["progress_ratio"] is None for row in conversion), conversion
        assert not any("vae" in (row["engine_progress_text"] or "").lower()
                       and "decod" not in (row["engine_progress_text"] or "").lower()
                       and row["engine_progress"] != 0.8 for row in conversion), "Generic VAE transfer misclassified as final decode"
        variants, metadata = job["variants"], job["variant_metadata"]
        assert len(variants) == defaults.batch_size == len(metadata)
        assert set(variants) == {item["file_name"] for item in metadata}
        report["audio"] = [audio_evidence(settings.outputs_dir / name) for name in variants]
        for item in report["audio"]:
            assert abs(float(item["ffprobe"]["format"]["duration"]) - body["duration_seconds"]) <= settings.remix.duration_tolerance_seconds
        report.update(status="PASS", completed_at=timestamp(), artistic_fidelity="Requires user listening")
    except Exception as exc:
        report.update(status="FAIL", error=repr(exc), completed_at=timestamp())
        raise
    finally:
        save()
        print(json.dumps({"status": report["status"], "evidence": str(args.report)}), flush=True)


if __name__ == "__main__":
    main()
