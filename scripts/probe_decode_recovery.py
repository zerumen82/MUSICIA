"""Reproduce a recorded remix via the live API and retain decode/audio evidence.

No fake audio, mocks, model loading, service restarts or cancellations. Use
--job-id to observe a job submitted by the real Electron window instead.
"""
from __future__ import annotations

import argparse
from array import array
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from config import get_settings


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def http(api, route, timeout, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(api.rstrip("/") + route, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def audio_evidence(path):
    path = Path(path)
    assert path.is_file() and path.stat().st_size > 0, str(path)
    metadata = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size:stream=codec_name,sample_rate,channels", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    result = {"path": str(path), "ffprobe": json.loads(metadata.stdout)}
    assert float(result["ffprobe"]["format"]["duration"]) > 0, result
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le", "-"],
        capture_output=True, check=True)
    samples = array("f")
    samples.frombytes(decoded.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    assert samples and all(math.isfinite(value) for value in samples), str(path)
    peak = max(abs(value) for value in samples)
    assert peak > 0, "Silent audio: " + str(path)
    result["pcm"] = {"sample_values": len(samples), "finite": True, "peak_absolute": peak}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-job", required=True, help="Existing historical remix ID")
    parser.add_argument("--job-id", help="Observe only; do not submit another job")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--history", type=Path, default=ROOT / "backend" / "job_history.json")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output-name", help="Optional distinctive name for generated variants")
    parser.add_argument("--timeout", type=float, help="Default: configured motor timeout")
    parser.add_argument("--poll-interval", type=float, help="Default: configured motor polling")
    parser.add_argument("--request-timeout", type=float, default=60)
    args = parser.parse_args()
    settings = get_settings()
    timeout = settings.acestep.job_timeout if args.timeout is None else args.timeout
    interval = settings.acestep.poll_interval if args.poll_interval is None else args.poll_interval
    assert timeout > 0 and interval > 0 and args.request_timeout > 0
    history = json.loads(args.history.read_text(encoding="utf-8-sig"))
    baseline = next(job for job in history["remix"] if job["job_id"] == args.baseline_job)
    body = dict(baseline["project"])
    if args.output_name:
        body["output_name"] = args.output_name
    report_path = args.report or ROOT / "logs" / ("decode-recovery-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"status": "RUNNING", "started_at": timestamp(), "baseline": baseline,
              "request": body, "polling": [], "artistic_fidelity": "Requires user listening"}

    def save():
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    save()
    try:
        report["health"] = http(args.api, "/health", args.request_timeout)
        report["preview"] = http(args.api, "/music/remix/preview", args.request_timeout, body)
        if args.job_id:
            job_id = args.job_id
        else:
            existing = http(args.api, "/music/jobs", args.request_timeout)
            active = [job for job in existing["items"] if job["status"] in {"queued", "running"}]
            assert not active, ("Other Musicia jobs active; no generation submitted", active)
            report["accepted"] = http(args.api, "/music/remix/project", args.request_timeout, body)
            job_id = report["accepted"]["job_id"]
        report["job_id"] = job_id
        save()
        print(json.dumps({"job_id": job_id, "evidence": str(report_path)}, ensure_ascii=False), flush=True)
        deadline = time.monotonic() + timeout
        last_phase = None
        while time.monotonic() < deadline:
            job = http(args.api, "/audio/remix/ai/" + job_id, args.request_timeout)
            row = {"at": timestamp(), **{key: job.get(key) for key in (
                "status", "phase", "progress_ratio", "engine_progress", "engine_progress_text",
                "elapsed_seconds", "engine_task_id", "error")}}
            report["polling"].append(row)
            report["job"] = job
            save()
            if row["phase"] != last_phase:
                print(json.dumps(row, ensure_ascii=False), flush=True)
                last_phase = row["phase"]
            if job["status"] in {"succeeded", "failed"}:
                break
            time.sleep(interval)
        else:
            raise TimeoutError("Live job exceeded verification deadline; job left untouched")
        assert job["status"] == "succeeded", job.get("error")
        assert job["source_digest"] == baseline["source_digest"], "Different source audio"
        # Classification is advisory; explicit zero gains and omitted zero
        # gains have the same mixing contract. The payload comparison below
        # verifies effective defaults for strength, seed, lyrics and voice.
        advisory_or_effective = {"source_classification", "classification_origin", "gains_db",
                                 "cover_strength", "cover_noise_strength", "lyrics", "instrumental", "seed"}
        assert all(job["project"].get(key) == value for key, value in body.items()
                   if key not in advisory_or_effective), "Different project operation/source"
        expected_gains = {group: (body.get("gains_db") or {}).get(group, 0.0)
                          for group in (body.get("groups") or {})}
        actual_gains = {group: (job["project"].get("gains_db") or {}).get(group, 0.0)
                        for group in (body.get("groups") or {})}
        assert actual_gains == expected_gains, ("Different group gains", actual_gains, expected_gains)
        actual = {key: value for key, value in job["effective_parameters"].items() if key != "src_audio_path"}
        expected = {key: value for key, value in baseline["effective_parameters"].items() if key != "src_audio_path"}
        assert actual == expected, ("Profile differs from historical job", actual, expected)
        conversions = [row for row in report["polling"] if row["phase"] in {
            "Convirtiendo a audio", "Convirtiendo a audio final"}]
        report["conversion_observations"] = len(conversions)
        assert conversions, "Conversion was not observed live"
        assert all(row["progress_ratio"] is None for row in conversions), conversions
        variants = job["result"]["variants"]
        assert len(variants) == expected["batch_size"], variants
        metadata = job["result"]["metadata"]
        assert len(metadata) == len(variants), "Incomplete final variant metadata"
        assert {item["file_name"] for item in metadata} == set(variants), "Variant metadata mismatch"
        assert set(job["result"]["preserved_groups"]) == set(baseline["preserved_groups"])
        report["audio"] = []
        for variant in metadata:
            final = audio_evidence(settings.outputs_dir / variant["file_name"])
            intermediate = audio_evidence(variant["intermediate_path"])
            seconds = float(final["ffprobe"]["format"]["duration"])
            assert abs(seconds - baseline["duration_seconds"]) <= settings.remix.duration_tolerance_seconds
            report["audio"].append({"final": final, "intermediate": intermediate})
            save()
        # Check the raw generated float WAVs as well as recombined/exported audio.
        material = Path(job["effective_parameters"]["src_audio_path"]).parent
        report["generated_audio"] = [audio_evidence(material / f"variante-{index + 1}.wav")
                                     for index in range(len(variants))]
        report.update(status="PASS", completed_at=timestamp())
    except Exception as exc:
        report.update(status="FAIL", error=repr(exc), completed_at=timestamp())
        raise
    finally:
        save()
        print(json.dumps({"status": report["status"], "evidence": str(report_path)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
