"""B6 real HTTP/audio evidence. Never substitutes the music engine or responses."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import hashlib
import math
from pathlib import Path
import re
import subprocess
import time
import uuid

from probe_remix_timeline import ROOT, audio_evidence, idle, pcm, save
import httpx
from audio_analysis import detect_groove
from config import get_settings


def request_from_manifest(manifest, scope):
    keys = ("source_name", "source_kind", "bpm", "duration_seconds", "repeat_start", "repeat_end", "transition_seconds")
    request = {key: manifest[key] for key in keys}
    request.update(scope=scope, output_name=f"prueba-b6-{scope}-{uuid.uuid4().hex[:8]}")
    if scope == "full":
        request.update(prompt="A track with gabber", seed=42)
    else:
        request.update(prompt="", groups={item["id"]: "keep" for item in get_settings().remix.groups})
    return request


def measured(path):
    groove = detect_groove(Path(path))
    return {"bpm_measured": round(groove["bpm"], 2), "bpm_confidence": groove["confidence"], "groove": groove}


def snapshot(report):
    return {"status": report["status"], "job_id": report.get("job_id"), "report": report["report"]}


def originals(args, report):
    settings = get_settings()
    paths = [settings.outputs_dir / "uploads" / name for name in args.original]
    report["originals"] = []
    with httpx.Client(base_url=args.api, timeout=120) as client:
        idle(client)
        for path in paths:
            assert path.is_file(), path
            response = client.get("/audio/groove/" + path.name, params={"source_kind": "upload"})
            response.raise_for_status()
            groove = response.json()
            limits = settings.remix.parameters["bpm"]
            assert limits["min"] <= groove["bpm"] <= limits["max"] and groove["confidence"] >= settings.remix.timeline_min_groove_confidence, groove
            assert measured(path)["groove"] == groove, "HTTP and disk measurement disagree"
            request = {"source_name": path.name, "source_kind": "upload", "scope": "groups", "prompt": "", "bpm": args.target_bpm,
                       "groups": {item["id"]: "keep" for item in settings.remix.groups}}
            preview = client.post("/music/remix/preview", json=request).raise_for_status().json()
            plan = preview["operations"]["timeline"]
            assert plan["source_bpm_origin"] == "measurement", plan
            assert plan["source_bpm"] == groove["bpm"], "Automatic timeline must preserve the groove precision shown in the UI"
            expected = groove["duration_seconds"] * plan["source_bpm"] / args.target_bpm
            assert math.isclose(plan["natural_duration_seconds"], expected, abs_tol=0.02), plan
            short = {**request, "duration_seconds": min(60, max(settings.remix.timeline_min_duration_seconds, math.floor(expected) - 1))}
            rejected = client.post("/music/remix/preview", json=short)
            assert rejected.status_code == 422, rejected.text
            error = rejected.json()["detail"]
            assert re.search(r"mínim|al menos", error, re.IGNORECASE) and re.search(r"\d", error), error
            manual = client.post("/music/remix/preview", json={**request, "source_bpm": round(groove["bpm"] + 1, 2)}).raise_for_status().json()
            assert manual["operations"]["timeline"]["source_bpm_origin"] == "manual", manual
            report["originals"].append({"source": str(path), "groove_http": groove, "preview_automatic": preview,
                                        "too_short_request": short, "too_short_http": rejected.status_code, "too_short_error": error, "preview_manual": manual})
            save(args.report, report)
    # Actual nonmusical PCM fixture tests the error, without pretending an engine returned it.
    fixture = Path(args.report).with_suffix(".silent-fixture.wav")
    command = ["ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i", f"anullsrc=r={settings.remix.sample_rate}:cl=stereo", "-t", "10", "-c:a", "pcm_f32le", str(fixture)]
    subprocess.run(command, check=True, capture_output=True)
    report["uncertain_measurement"] = {"fixture": str(fixture), "command": command, "fixture_kind": "actual silent PCM for negative test, never a generated song"}
    try:
        measured(fixture)
    except ValueError as error:
        report["uncertain_measurement"].update(status="PASS", error=str(error))
    else:
        raise AssertionError("Silent PCM incorrectly measured as musical tempo")
    from remix_project import full_variant_plan, RemixProjectRequest
    try:
        full_variant_plan(RemixProjectRequest(source_name=paths[0].name, scope="full", prompt="gabber", bpm=args.target_bpm), 10, 10, settings, None)
    except ValueError as error:
        report["uncertain_measurement"]["contract_error"] = str(error)
    else:
        raise AssertionError("Full tempo contract accepted an unavailable measurement")


def repetitions(base_path, intermediate, plan, arrangement):
    base, _ = pcm(base_path)
    extended, _ = pcm(intermediate)
    rate, channels = get_settings().remix.sample_rate, 2
    fade = round(plan["transition_seconds"] * rate) * channels
    prefix = round(arrangement["first_join_start_seconds"] * rate) * channels
    assert prefix > 0 and len(extended) > len(base)
    assert prefix == len(base) - fade
    prefix_delta = max(abs(a - b) for a, b in zip(base[:prefix], extended[:prefix]))
    actual_start = arrangement["effective_repeat_start_seconds"]
    actual_end = arrangement["effective_repeat_end_seconds"]
    assert plan["mapped_repeat_start"] - 1 / rate <= actual_start < actual_end <= plan["mapped_repeat_end"] + 1 / rate
    assert arrangement["requested_repeat_start_seconds"] == plan["mapped_repeat_start"]
    assert arrangement["requested_repeat_end_seconds"] == plan["mapped_repeat_end"]
    assert arrangement["seam_method"] == "beat_clock_aligned", arrangement
    period = 60 / arrangement["beat_clock_bpm"]
    first_join_cycles = (arrangement["first_join_start_seconds"] - actual_start) / period
    stride_cycles = arrangement["repetition_stride_seconds"] / period
    tolerance = 1 / rate / period
    assert abs(first_join_cycles - round(first_join_cycles)) <= tolerance
    assert abs(stride_cycles - round(stride_cycles)) <= tolerance
    assert round(stride_cycles) == arrangement["beats_per_repetition"]
    start = round(actual_start * rate) * channels + fade
    stop = round(actual_end * rate) * channels
    count = min(stop - start - fade, len(extended) - len(base), rate * channels * 2)
    assert count > 0, plan
    repeat_delta = max(abs(a - b) for a, b in zip(base[start:start + count], extended[len(base):len(base) + count]))
    assert prefix_delta == 0 and repeat_delta == 0, (prefix_delta, repeat_delta)
    return {"preserved_prefix_max_abs_delta": prefix_delta, "repeated_copy_max_abs_delta": repeat_delta, "repeated_samples_compared": count,
            "effective_subset_within_requested": True, "first_join_clock_cycles": first_join_cycles,
            "stride_clock_cycles": stride_cycles, "beats_per_repetition": arrangement["beats_per_repetition"],
            "clock_cycles_tolerance_one_sample": tolerance}


def group_sum_checks(job, request):
    originals = {key: pcm(path)[0] for key, path in job["operations"]["prepared_groups"].items()}
    assert len({len(samples) for samples in originals.values()}) == 1
    work = get_settings().outputs_dir / "_remix" / job["job_id"]
    mixture, _ = pcm(work / "mezcla-1.wav")
    parts = [(samples, 10 ** (request.get("gains_db", {}).get(key, 0) / 20)) for key, samples in originals.items()
             if request["groups"][key] == "keep"]
    assert parts and all(action in {"keep", "remove"} for action in request["groups"].values())
    delta = max(abs(actual - sum((samples[i] if i < len(samples) else 0) * gain for samples, gain in parts)) for i, actual in enumerate(mixture))
    assert delta < .000002
    return {"mixture_max_abs_delta_vs_independent_sum": delta, "prepared_group_sample_lengths": {key: len(samples) for key,samples in originals.items()}}


def validate_job(client, job, request):
    settings = get_settings()
    assert job["status"] == "succeeded", {"status": job["status"], "error": job.get("error")}
    work = settings.outputs_dir / "_remix" / job["job_id"]
    source_path = settings.outputs_dir / ("uploads" if request.get("source_kind") == "upload" else "") / request["source_name"]
    current_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert current_digest == job["source_digest"] == job["operations"]["source_digest"], "Original source changed"
    variants = job["result"]["metadata"]
    assert len(variants) == (settings.generation.batch_size if request["scope"] == "full" else 1), variants
    evidence = []
    for index, variant in enumerate(variants, 1):
        output = settings.outputs_dir / variant["file_name"]
        audio = audio_evidence(output, client)
        assert abs(float(audio["ffprobe"]["format"]["duration"]) - request["duration_seconds"]) <= settings.remix.duration_tolerance_seconds
        audio["ficha"] = json.loads(output.with_suffix(".ficha.json").read_text(encoding="utf-8-sig"))
        audio["measured_final"] = measured(output)
        plan = variant["timeline"]
        assert audio["ficha"]["operations"]["timeline"] == plan
        assert audio["ficha"]["arrangement"] == variant["arrangement"]
        assert audio["ficha"]["source_digest"] == current_digest
        assert abs(audio["measured_final"]["bpm_measured"] - request["bpm"]) <= settings.remix.tempo_verify_tolerance_bpm, audio["measured_final"]
        if request["scope"] == "full":
            before_path, adjusted_path = work / f"variante-{index}.wav", work / f"tempo-variante-{index}.wav"
            audio["engine_pcm"] = audio_evidence(before_path)
            audio["adjusted_pcm"] = audio_evidence(adjusted_path)
            before, adjusted = measured(before_path), measured(adjusted_path)
            audio["independent_before"] = before
            audio["independent_adjusted"] = adjusted
            assert {key: before[key] for key in ("bpm_measured", "bpm_confidence")} == variant["tempo_before"]
            assert plan["source_bpm_origin"] == "generated_measurement" and plan["tempo_method"] == "measured_pcm_atempo", plan
            assert plan["status"] == "resolved" and plan["engine_tempo_method"] == "engine_conditioning"
            assert math.isclose(plan["tempo_ratio"], request["bpm"] / before["bpm_measured"], rel_tol=1e-12)
            assert abs(adjusted["bpm_measured"] - request["bpm"]) <= settings.remix.tempo_verify_tolerance_bpm, adjusted
            assert {key: adjusted[key] for key in ("bpm_measured", "bpm_confidence")} == variant["tempo_after_adjust"]
            assert plan["beat_clock_bpm"] == adjusted["bpm_measured"]
            assert plan["beat_clock_origin"] == variant["arrangement"]["beat_clock_origin"] == "adjusted_audio_measurement"
            assert variant["arrangement"]["beat_clock_bpm"] == adjusted["bpm_measured"]
            assert math.isclose(plan["natural_duration_seconds"], plan["engine_duration_seconds"] / plan["tempo_ratio"], abs_tol=1 / settings.remix.sample_rate)
            scale = plan["engine_duration_seconds"] / plan["source_duration_seconds"]
            for boundary in ("start", "end"):
                assert math.isclose(plan[f"mapped_repeat_{boundary}"], request[f"repeat_{boundary}"] * scale / plan["tempo_ratio"], rel_tol=1e-10)
            assert variant["tempo_processing"]["pitch_preserved"] is True
            audio["raw_atempo_pcm"] = audio_evidence(variant["tempo_processing"]["raw_output_path"])
            boundary_correction = plan["natural_duration_seconds"] - float(audio["raw_atempo_pcm"]["ffprobe"]["format"]["duration"])
            assert abs(boundary_correction) <= settings.remix.duration_tolerance_seconds
            assert math.isclose(boundary_correction, variant["tempo_processing"]["boundary_duration_correction_seconds"], abs_tol=1 / settings.remix.sample_rate)
            assert audio["ficha"]["operations"]["tempo_before"] == variant["tempo_before"]
            assert audio["ficha"]["operations"]["tempo_processing"] == variant["tempo_processing"]
            assert variant["seed"] is not None and variant["seed_origin"] != "not_applicable"
            audio["repetition_oracle"] = repetitions(adjusted_path, variant["intermediate_path"], plan, variant["arrangement"])
        else:
            assert plan["beat_clock_origin"] == variant["arrangement"]["beat_clock_origin"] == "requested_common_tempo"
            assert plan["beat_clock_bpm"] == variant["arrangement"]["beat_clock_bpm"] == request["bpm"]
            audio["repetition_oracle"] = repetitions(work / f"mezcla-{index}.wav", variant["intermediate_path"], plan, variant["arrangement"])
        evidence.append(audio)
    history = json.loads((ROOT / "backend/job_history.json").read_text(encoding="utf-8-sig"))
    persisted = next(item for item in history["remix"] if item["job_id"] == job["job_id"])
    assert persisted["status"] == "succeeded" and persisted["result"]["metadata"] == variants
    if request["scope"] == "full":
        parameters = job["effective_parameters"]
        assert parameters["model"] == "acestep-v15-sft" and parameters["inference_steps"] == 50 and parameters["guidance_scale"] == 9
        assert parameters["batch_size"] == 2 and not parameters["thinking"] and not parameters["use_format"]
        if request.get("seed") is not None:
            assert parameters["seed"] == request["seed"] and parameters["use_random_seed"] is False
            assert variants[0]["seed"] == request["seed"], "First actual seed differs from the explicit requested seed"
        assert len({variant["seed"] for variant in variants}) == len(variants), "Variants lost actual independent seed trace"
    result = {"outputs": evidence, "persisted_job": persisted, "original_source_sha256_after": current_digest}
    if request["scope"] == "groups":
        result["independent_group_pcm_checks"] = group_sum_checks(job, request)
    return result


def generation(args, report):
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
    request = request_from_manifest(manifest, args.mode)
    report["request"] = request
    with httpx.Client(base_url=args.api, timeout=120) as client:
        idle(client)
        report["preview"] = client.post("/music/remix/preview", json=request).raise_for_status().json()
        if args.mode == "full":
            plan = report["preview"]["operations"]["timeline"]
            assert plan["tempo_ratio"] is None and plan["natural_duration_seconds"] is None, plan
            assert plan["tempo_method"] == "measured_pcm_atempo", plan
        accepted = client.post("/music/remix/project", json=request).raise_for_status().json()
        report["job_id"] = accepted["job_id"]
        save(args.report, report)
        print(f"JOB_ID={accepted['job_id']}", flush=True)
        deadline = time.monotonic() + get_settings().acestep.job_timeout
        while time.monotonic() < deadline:
            report["job"] = client.get("/audio/remix/ai/" + accepted["job_id"]).raise_for_status().json()
            save(args.report, report)
            if report["job"]["status"] in {"failed", "succeeded", "cancelled"}:
                break
            time.sleep(2)
        report.update(validate_job(client, report["job"], request))


def verify(args, report):
    source = json.loads(Path(args.existing_report).read_text(encoding="utf-8-sig"))
    request = source["full_project_request"] if args.full_ui else source.get("request", source.get("project_request"))
    job_id = source["full_job_id"] if args.full_ui else source["job_id"]
    report.update(request=request, job_id=job_id, previous_report=args.existing_report, new_generation=False)
    with httpx.Client(base_url=args.api, timeout=120) as client:
        report["job"] = client.get("/audio/remix/ai/" + report["job_id"]).raise_for_status().json()
        report.update(validate_job(client, report["job"], request))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("originals", "groups", "full", "verify"))
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--original", action="append", default=[])
    parser.add_argument("--target-bpm", type=int, default=199)
    parser.add_argument("--manifest")
    parser.add_argument("--existing-report")
    parser.add_argument("--full-ui", action="store_true")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    assert httpx.URL(args.api).host in {"127.0.0.1", "localhost"}
    assert not Path(args.report).exists(), "Use a fresh report path; preserve failed evidence"
    report = {"status": "RUNNING", "at": datetime.now(timezone.utc).isoformat(), "report": args.report}
    try:
        {"originals": originals, "groups": generation, "full": generation, "verify": verify}[args.mode](args, report)
        report["status"] = "PASS"
        save(args.report, report)
        print(json.dumps(snapshot(report)))
    except Exception as error:
        report.update(status="FAIL", error=str(error), error_type=type(error).__name__)
        save(args.report, report)
        raise


if __name__ == "__main__":
    main()
