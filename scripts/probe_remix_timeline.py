"""R11 live evidence; real source excerpts, requests and audio, no mocked engine."""
from __future__ import annotations

import argparse
from array import array
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import httpx
from audio_analysis import analyze_audio, detect_groove
from config import get_settings


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def pcm(path, sample_rate=None):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path)]
    if sample_rate is not None:
        cmd += ["-ar", str(sample_rate), "-ac", "2"]
    cmd += ["-f", "f32le", "-c:a", "pcm_f32le", "pipe:1"]
    result = subprocess.run(cmd, capture_output=True, check=True)
    samples = array("f")
    samples.frombytes(result.stdout)
    return samples, cmd


def audio_evidence(path, client=None):
    path = Path(path)
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=sample_rate,channels,codec_name", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    probe = json.loads(result.stdout)
    samples, decode = pcm(path)
    rate = int(probe["streams"][0]["sample_rate"])
    channels = int(probe["streams"][0]["channels"])
    chunks = [samples[i:i + rate * channels] for i in range(0, len(samples), rate * channels)]
    evidence = {"path": str(path), "bytes": path.stat().st_size, "ffprobe": probe,
                "ffprobe_command": command, "ffprobe_exit": result.returncode, "decode_command": decode,
                "finite": all(math.isfinite(s) for s in samples), "max_abs": max(abs(s) for s in samples),
                "rms": math.sqrt(math.fsum(s * s for s in samples) / len(samples)),
                "per_second_rms": [math.sqrt(math.fsum(s * s for s in block) / len(block)) for block in chunks]}
    assert evidence["bytes"] > 0 and evidence["finite"] and evidence["rms"] > 0, evidence
    if client:
        response = client.get("/music/audio/" + path.name, headers={"Range": "bytes=0-127"})
        evidence["http"] = {"status": response.status_code, "headers": dict(response.headers), "bytes": len(response.content)}
        assert response.status_code in {200, 206}, evidence["http"]
    return evidence


def idle(client):
    result = client.get("/music/jobs").raise_for_status().json()
    active = [job for job in result["items"] if job["status"] in {"queued", "running"}]
    assert not active, "Active jobs; probe will not submit new work"
    return result


def prepare(args):
    settings = get_settings()
    source = Path(args.original).resolve()
    assert source.is_file()
    name = f"prueba-r11-fuente-{uuid.uuid4().hex[:8]}.mp3"
    target = settings.outputs_dir / name
    command = ["ffmpeg", "-v", "error", "-n", "-ss", str(args.offset), "-i", str(source), "-t", str(args.seconds),
               "-c:a", "libmp3lame", "-b:a", settings.remix.export_bitrate, str(target)]
    subprocess.run(command, capture_output=True, check=True)
    analysis = analyze_audio(target)
    groove = detect_groove(target)
    measured = groove.get("bpm")
    if not measured:
        raise AssertionError(f"No reliable source BPM: {analysis}")
    source_bpm = int(round(float(measured)))
    limits = settings.remix.parameters["bpm"]
    if not limits["min"] <= source_bpm <= limits["max"]:
        raise AssertionError(f"Measured source BPM outside supported limits; excerpt preserved at {target}: {groove}")
    target_bpm = min(int(settings.remix.parameters["bpm"]["max"]), int(round(source_bpm * args.tempo_ratio)))
    duration = float(analysis["duration_seconds"])
    manifest = {"source_name": name, "source_kind": "output", "path": str(target), "original": str(source),
                "original_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "excerpt_offset": args.offset,
                "command": command, "analysis": analysis, "groove": groove, "source_bpm": source_bpm, "bpm": target_bpm,
                "duration_seconds": args.target_seconds, "repeat_start": 2.0, "repeat_end": min(12.0, duration),
                "transition_seconds": args.transition, "evidence": audio_evidence(target)}
    save(target.with_suffix(".ficha.json"), {"name": target.stem, "duration_seconds": duration,
          "bpm_measured": measured, "source": "tester_excerpt", "original": source.name,
          "original_offset_seconds": args.offset})
    save(args.report, manifest)
    print(json.dumps({"status": "PASS", "manifest": args.report, "source_name": name, "source_bpm": source_bpm, "target_bpm": target_bpm}))


def independent_pcm_checks(job, request):
    work = get_settings().outputs_dir / "_remix" / job["job_id"]
    plan = job["operations"]["timeline"]
    prepared = job["operations"].get("prepared_groups", {})
    originals = {key: pcm(path)[0] for key, path in prepared.items()}
    if originals:
        assert len({len(samples) for samples in originals.values()}) == 1, "Prepared groups lose shared sample length"
    checks = []
    for index, metadata in enumerate(job["result"]["metadata"], start=1):
        parts = []
        for key, action in request.get("groups", {}).items():
            if action == "remove":
                continue
            if action == "keep":
                samples = originals[key]
            elif len([name for name, chosen in request.get("groups", {}).items() if chosen == "transform"]) == 1:
                samples = pcm(work / f"pista-transformada-{index}.wav", get_settings().remix.sample_rate)[0]
            else:
                samples = pcm(work / f"transformada-{index}-{key}.wav", get_settings().remix.sample_rate)[0]
            gain = 10 ** (request.get("gains_db", {}).get(key, 0.0) / 20)
            parts.append((samples, gain))
        mixture, _ = pcm(work / (f"mezcla-{index}.wav" if parts else f"variante-{index}.wav"))
        max_mix_difference = None
        if parts:
            differences = [abs(actual - sum((samples[i] if i < len(samples) else 0.0) * gain for samples, gain in parts)) for i, actual in enumerate(mixture)]
            max_mix_difference = max(differences)
            assert max_mix_difference < 0.000002, max_mix_difference
        extended, _ = pcm(metadata["intermediate_path"])
        rate = get_settings().remix.sample_rate
        channels = 2
        fade = round(plan["transition_seconds"] * rate) * channels
        base_stop = len(mixture) - fade
        prefix_difference = max(abs(a - b) for a, b in zip(mixture[:base_stop], extended[:base_stop]))
        assert prefix_difference == 0, prefix_difference
        section_start = round(plan["mapped_repeat_start"] * rate) * channels + fade
        section_end = round(plan["mapped_repeat_end"] * rate) * channels
        # Interior of first copy, away from the next fade: independently verify actual material is repeated.
        count = min(section_end - section_start - fade, len(extended) - len(mixture), rate * channels * 2)
        assert count > 0
        copied_difference = max(abs(a - b) for a, b in zip(mixture[section_start:section_start + count], extended[len(mixture):len(mixture) + count]))
        assert copied_difference == 0, copied_difference
        checks.append({"variant": index, "mixture_max_abs_delta_vs_independent_sum": max_mix_difference,
                       "preserved_prefix_max_abs_delta": prefix_difference,
                       "repeated_copy_interior_max_abs_delta": copied_difference,
                       "repeated_samples_compared": count, "prepared_group_sample_lengths": {k: len(v) for k, v in originals.items()}})
    return checks


def validate_job(client, job, request):
    assert job["status"] == "succeeded", job
    settings = get_settings()
    outputs = job.get("result", {}).get("variants") or job.get("outputs") or job.get("result", {}).get("outputs") or []
    if not outputs:
        outputs = [job["output_name"]] if job.get("output_name") else []
    outputs = [item["file_name"] if isinstance(item, dict) else item for item in outputs]
    evidence = []
    for name in outputs:
        path = settings.outputs_dir / name
        audio = audio_evidence(path, client)
        actual = float(audio["ffprobe"]["format"]["duration"])
        assert abs(actual - request["duration_seconds"]) <= settings.remix.duration_tolerance_seconds + 0.1, (actual, request)
        assert actual > float(job["operations"]["timeline"]["source_duration_seconds"]), actual
        ficha_path = path.with_suffix(".ficha.json")
        audio["ficha"] = json.loads(ficha_path.read_text(encoding="utf-8-sig"))
        audio["measured_analysis"] = analyze_audio(path)
        audio["measured_groove"] = detect_groove(path)
        evidence.append(audio)
    assert evidence, job
    history = json.loads((ROOT / "backend/job_history.json").read_text(encoding="utf-8-sig"))
    persisted = next(j for j in history["remix"] if j["job_id"] == job["job_id"])
    assert persisted["status"] == "succeeded", persisted
    return {"job": job, "outputs": evidence, "persisted_job": persisted,
            "independent_pcm_checks": independent_pcm_checks(job, request)}


def verify_ui(args):
    result = json.loads(Path(args.ui_result).read_text(encoding="utf-8-sig"))
    assert result["status"] == "PASS", result.get("error")
    with httpx.Client(base_url=args.api, timeout=60) as client:
        request = result["project_request"]
        job = client.get("/audio/remix/ai/" + result["job_id"]).raise_for_status().json()
        report = validate_job(client, job, request)
        report.update(status="PASS", ui_result=args.ui_result)
        assert result["preview_operations"]["timeline"] == job["operations"]["timeline"], "Preview timeline differs from execution"
        report["preview_equals_execution_timeline"] = True
        separation = client.get("/audio/separate/" + result["separation_id"]).raise_for_status().json()
        report["separation_job"] = separation
        report["separation_audio"] = [audio_evidence(get_settings().outputs_dir / g["file_name"], client) for g in separation["result"]["groups"]]
        streams = [g["ffprobe"]["streams"][0] for g in report["separation_audio"]]
        assert len(streams) == 4 and len({(s["sample_rate"], s["channels"]) for s in streams}) == 1
        save(args.report, report)
        print(json.dumps({"status": "PASS", "report": args.report, "job_id": result["job_id"], "outputs": len(report["outputs"])}))


def mixed(args):
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
    request = {key: manifest[key] for key in ("source_name", "source_kind", "source_bpm", "bpm", "duration_seconds", "repeat_start", "repeat_end", "transition_seconds")}
    request.update(scope="groups", prompt="A track with gabber", seed=42,
                   groups={"vocals": "keep", "drums": "transform", "bass": "keep", "other": "remove"},
                   output_name=f"prueba-r11-mixto-{uuid.uuid4().hex[:8]}")
    if args.mode == "full":
        request.update(scope="full", output_name=f"prueba-r11-completo-{uuid.uuid4().hex[:8]}")
        request.pop("groups")
        request.pop("source_bpm")
    report = {"status": "RUNNING", "request": request, "at": datetime.now(timezone.utc).isoformat()}
    gpu_command = ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"]
    gpu = subprocess.run(gpu_command, capture_output=True, text=True, check=True)
    report["gpu_before"] = {"command": gpu_command, "exit_code": gpu.returncode, "output": gpu.stdout.strip()}
    save(args.report, report)
    with httpx.Client(base_url=args.api, timeout=60) as client:
        idle(client)
        report["preview"] = client.post("/music/remix/preview", json=request).raise_for_status().json()
        parameters = report["preview"]["effective_parameters"]
        assert parameters["model"] == "acestep-v15-sft" and parameters["inference_steps"] == 50 and parameters["guidance_scale"] == 9
        assert parameters["batch_size"] == 2 and not parameters["thinking"] and not parameters["use_format"]
        accepted = client.post("/music/remix/project", json=request).raise_for_status().json()
        report["job_id"] = accepted["job_id"]
        save(args.report, report)
        print(f"JOB_ID={accepted['job_id']}", flush=True)
        deadline = time.monotonic() + float(get_settings().acestep.job_timeout)
        while time.monotonic() < deadline:
            job = client.get("/audio/remix/ai/" + accepted["job_id"]).raise_for_status().json()
            if job["status"] in {"failed", "succeeded"}:
                break
            time.sleep(2)
        report.update(validate_job(client, job, request))
        assert report["preview"]["operations"]["timeline"] == job["operations"]["timeline"]
        actual_parameters = job["effective_parameters"]
        comparable = {key: value for key, value in parameters.items() if key != "src_audio_path"}
        assert comparable == {key: value for key, value in actual_parameters.items() if key != "src_audio_path"}, "Effective preview differs from execution"
        report["status"] = "PASS"
        assert len(report["outputs"]) == get_settings().generation.batch_size
        save(args.report, report)
        print(json.dumps({"status": "PASS", "report": args.report, "job_id": accepted["job_id"], "outputs": len(report["outputs"])}))


def verify_existing(args):
    existing = json.loads(Path(args.existing_report).read_text(encoding="utf-8-sig"))
    with httpx.Client(base_url=args.api, timeout=60) as client:
        job = client.get("/audio/remix/ai/" + existing["job_id"]).raise_for_status().json()
        report = {**existing, **validate_job(client, job, existing["request"])}
        report.pop("error", None)
        report.pop("error_type", None)
        report.update(status="PASS", previous_attempt=args.existing_report, new_generation=False)
        assert existing["preview"]["operations"]["timeline"] == job["operations"]["timeline"]
        preview_parameters = {key: value for key, value in existing["preview"]["effective_parameters"].items() if key != "src_audio_path"}
        assert preview_parameters == {key: value for key, value in job["effective_parameters"].items() if key != "src_audio_path"}
        save(args.report, report)
        print(json.dumps({"status": "PASS", "report": args.report, "job_id": job["job_id"], "outputs": len(report["outputs"]), "new_generation": False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "verify-ui", "mixed", "full", "verify-job"])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--original")
    parser.add_argument("--offset", type=float, default=10)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--target-seconds", type=float, default=35)
    parser.add_argument("--tempo-ratio", type=float, default=1.2)
    parser.add_argument("--transition", type=float, default=0.1)
    parser.add_argument("--manifest")
    parser.add_argument("--ui-result")
    parser.add_argument("--existing-report")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    assert httpx.URL(args.api).host in {"127.0.0.1", "localhost"}
    try:
        {"prepare": prepare, "verify-ui": verify_ui, "mixed": mixed, "full": mixed, "verify-job": verify_existing}[args.mode](args)
    except Exception as error:
        existing = json.loads(Path(args.report).read_text(encoding="utf-8-sig")) if Path(args.report).is_file() else {}
        existing.update(status="FAIL", error=str(error), error_type=type(error).__name__)
        save(args.report, existing)
        raise


if __name__ == "__main__":
    main()
