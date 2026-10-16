"""Independent real API/audio probe for R9/R10; no mocks or installations.

Run one mode at a time to serialize the installed engine. Every run retains
its actual terminal job and errors, including failures. Artifacts are local.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from config import get_settings
from mixer_service import MixerService
from music_service import GenerationRequest, MusicService
from prompt_style import style_caption
from style_translator import style_for_engine


def request(api, method, route, body=None):
    response = requests.request(method, api + route, json=body, timeout=60)
    response.raise_for_status()
    return response.json()


def poll(api, route, deadline):
    last_phase = None
    while time.monotonic() < deadline:
        job = request(api, "GET", route)
        if job.get("phase") != last_phase:
            print(job.get("phase"), flush=True)
            last_phase = job.get("phase")
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(3)
    raise TimeoutError(route)


def probe_file(path):
    output = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration,size:stream=codec_name,sample_rate,channels",
                             "-of", "json", str(path)], capture_output=True, text=True, check=True)
    metadata = json.loads(output.stdout)
    assert path.is_file() and path.stat().st_size > 0
    assert float(metadata["format"]["duration"]) > 0
    return metadata


def pcm(path, sample_rate):
    output = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2",
                             "-ar", str(sample_rate), "-f", "f32le", "-acodec", "pcm_f32le", "-"],
                            capture_output=True, check=True)
    return np.frombuffer(output.stdout, dtype="<f4").reshape(-1, 2).astype(np.float64)


def delta(actual, expected):
    assert actual.shape == expected.shape, (actual.shape, expected.shape)
    error = actual - expected
    rms = float(np.sqrt(np.mean(error ** 2)))
    reference_rms = float(np.sqrt(np.mean(expected ** 2)))
    return {"samples": len(actual), "max_absolute": float(np.max(np.abs(error))),
            "rms": rms, "relative_rms": rms / max(reference_rms, np.finfo(float).eps)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prompt", "validation", "analysis", "full", "region", "groups", "dsp", "recovery"])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--source", default="pista-sin-nombre (2).mp3")
    parser.add_argument("--kind", default="output", choices=["upload", "output"])
    parser.add_argument("--timeout", default=1800, type=float)
    parser.add_argument("--job-id")
    args = parser.parse_args()
    settings = get_settings()
    evidence = ROOT / "logs" / f"remix-integral-{args.mode}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    report = {"mode": args.mode, "status": "RUNNING", "source": args.source,
              "started_at": time.strftime('%Y-%m-%d %H:%M:%S'),
              "artistic_fidelity": "Not certified by this technical probe"}
    deadline = time.monotonic() + args.timeout
    try:
        caps = request(args.api, "GET", "/music/remix/capabilities")
        report["capabilities"] = caps
        assert {group["id"] for group in caps["groups"]} == {"drums", "bass", "other", "vocals"}
        assert caps["defaults"]["batch_size"] == 2
        if args.mode == "prompt":
            prompts = ["Batería suave al fondo", "techno", "jazz con contrabajo",
                       "Bajo potente sin voz", "Mantén la voz; cambia únicamente la batería"]
            module_uri = (ROOT / "frontend" / "src" / "prompt_gloss.js").as_uri()
            program = ("import {glossPrompt} from " + json.dumps(module_uri) + ";"
                       + "process.stdout.write(JSON.stringify(" + json.dumps(prompts)
                       + ".map(glossPrompt)));")
            node = subprocess.run(["node", "--input-type=module", "-e", program],
                                  capture_output=True, text=True, encoding="utf-8", check=True)
            previews = json.loads(node.stdout)
            service = MusicService(settings)
            rows = []
            for original, preview in zip(prompts, previews):
                for task in ("text2music", "cover", "repaint"):
                    engine = style_for_engine(style_caption(preview), settings)
                    payload = service.build_payload(GenerationRequest(
                        prompt=engine, constraint_prompt=style_caption(preview), task_type=task,
                        source_path=None if task == "text2music" else str(settings.outputs_dir / args.source),
                        instrumental=None))
                    assert style_caption(preview) == original == preview
                    assert payload["prompt"] == engine
                    assert not payload["thinking"] and not payload["use_format"]
                    rows.append({"original": original, "preview": preview, "task": task,
                                 "effective_prompt": payload["prompt"], "lyrics": payload["lyrics"]})
            report["prompt_wire"] = rows
        elif args.mode == "validation":
            base = {"source_name": args.source, "source_kind": args.kind, "prompt": "Cambiar suavemente"}
            cases = [
                {"scope": "region", "region_start": 5, "region_end": 31},
                {"scope": "full", "region_start": 5, "region_end": 12},
                {"scope": "groups", "groups": {"drums": "keep", "bass": "keep", "other": "keep", "vocals": "remove", "guitar": "keep"}},
                {"scope": "groups", "groups": {"drums": "remove", "bass": "remove", "other": "remove", "vocals": "remove"}},
                {"scope": "groups", "groups": {"drums": "transform", "bass": "keep", "other": "keep", "vocals": "remove"}, "bpm": 180},
                {"cover_strength": 2},
            ]
            report["rejections"] = []
            for invalid in cases:
                response = requests.post(args.api + "/music/remix/project", json={**base, **invalid}, timeout=60)
                report["rejections"].append({"request": invalid, "status_code": response.status_code, "response": response.json()})
                assert response.status_code == 422
        elif args.mode == "analysis":
            body = {"source_name": args.source, "source_kind": args.kind}
            accepted = request(args.api, "POST", "/music/remix/analyze", body)
            report["accepted"] = accepted
            job = poll(args.api, "/music/remix/analyze/" + accepted["job_id"], deadline)
            report["job"] = job
            assert job["status"] == "succeeded", job.get("error")
            assert job["result"]["method"] == "ACE-Step full_analysis_only"
            assert job["result"]["confidence"] is None
            second = request(args.api, "POST", "/music/remix/analyze", body)
            report["second_request"] = second
            assert second["cached"] and second["job_id"] == accepted["job_id"]
        elif args.mode == "recovery":
            assert args.job_id, "--job-id required"
            job = request(args.api, "GET", "/audio/remix/ai/" + args.job_id)
            report["job"] = job
            assert job["status"] == "succeeded"
            assert job["project"]["source_classification"] == "electronic"
            for variant in job["result"]["variants"]:
                probe_file(settings.outputs_dir / variant)
        else:
            source = settings.outputs_dir / args.source
            duration = float(probe_file(source)["format"]["duration"])
            body = {"source_name": args.source, "source_kind": args.kind,
                    "prompt": "Conserva el carácter del original con batería suave al fondo, sin añadir instrumentos",
                    "scope": args.mode if args.mode != "dsp" else "groups",
                    "output_name": "prueba-remix-integral-" + args.mode,
                    "source_classification": "electronic", "seed": 123456}
            if args.mode == "full":
                body.update(reference_name=args.source, reference_kind=args.kind)
            if args.mode == "region":
                body.update(region_start=6, region_end=18, repaint_mode="conservative",
                            repaint_wav_crossfade_sec=0.1)
            if args.mode in {"groups", "dsp"}:
                body["groups"] = {"drums": "transform" if args.mode == "groups" else "keep",
                                  "bass": "keep", "other": "keep", "vocals": "remove"}
                if args.mode == "dsp":
                    body["prompt"] = ""
            report["request"] = body
            accepted = request(args.api, "POST", "/music/remix/project", body)
            report["accepted"] = accepted
            job = poll(args.api, "/audio/remix/ai/" + accepted["job_id"], deadline)
            report["job"] = job
            assert job["status"] == "succeeded", job.get("error")
            assert job["project"] == body or all(job["project"].get(k) == v for k, v in body.items())
            expected_variants = 1 if args.mode == "dsp" else 2
            assert len(job["result"]["variants"]) == expected_variants
            if args.mode != "dsp":
                payload = job["effective_parameters"]
                assert payload["prompt"] == body["prompt"]
                assert payload["batch_size"] == 2 and payload["inference_steps"] == 50
                assert payload["guidance_scale"] == 9 and not payload["thinking"] and not payload["use_format"]
                assert payload["audio_format"] == settings.remix.intermediate_format
                assert payload["lyrics"] != settings.generation.instrumental_marker
                if args.mode == "full":
                    assert Path(payload["reference_audio_path"]) == source
            report["audio"] = []
            source_pcm = pcm(source, settings.remix.sample_rate) if args.mode == "region" else None
            for metadata in job["result"]["metadata"]:
                output = settings.outputs_dir / metadata["file_name"]
                intermediate = Path(metadata["intermediate_path"])
                audio_info = {"output": probe_file(output), "intermediate": probe_file(intermediate),
                              "mastering": metadata}
                report["audio"].append(audio_info)
                assert abs(float(audio_info["output"]["format"]["duration"]) - duration) <= settings.remix.duration_tolerance_seconds
                assert metadata["loudness"]["input_tp"] <= 0, "clipping in final export"
                if args.mode == "region":
                    actual = pcm(intermediate, settings.remix.sample_rate)
                    boundary = settings.remix.sample_rate
                    outside_actual = np.concatenate([actual[:int(5.9 * boundary)], actual[int(18.1 * boundary):]])
                    outside_source = np.concatenate([source_pcm[:int(5.9 * boundary)], source_pcm[int(18.1 * boundary):]])
                    # El motor normaliza el audio antes de repintar y el splice
                    # reinserta esa onda normalizada (2026-10-12, diag: ganancia
                    # 0.891, residuo de forma 8.8e-7). Se declara el factor y se
                    # verifica la FORMA, no el nivel global (spec/06: no confundir
                    # cambios globales de nivel con conservación exacta).
                    flat_a = outside_actual.reshape(-1).astype(np.float64)
                    flat_s = outside_source.reshape(-1).astype(np.float64)
                    gain = float(np.dot(flat_a, flat_s) / max(np.dot(flat_s, flat_s), np.finfo(float).eps))
                    comparison = delta(outside_actual, gain * outside_source)
                    comparison["engine_gain"] = gain
                    audio_info["outside_region"] = comparison
                    audio_info["preservation_tolerance"] = {
                        "max_absolute": 1 / 128, "relative_rms": 0.008,
                        "gain_range": [0.5, 2.0],
                        "reason": "Native original waveform traverses bfloat16 conditioning and engine peak normalization; verify shape after optimal scalar (declared gain), exclude explicit 100 ms crossfades; compare lossless PCM before export attenuation."}
                    assert comparison["max_absolute"] <= 1 / 128 and comparison["relative_rms"] <= 0.008, comparison
                    assert 0.5 <= gain <= 2.0, comparison
            if args.mode in {"groups", "dsp"}:
                report["preserved_groups"] = job["result"]["preserved_groups"]
                assert set(job["result"]["preserved_groups"]) == ({"bass", "other"} if args.mode == "groups" else {"bass", "other", "drums"})
                work = settings.outputs_dir / "_remix" / job["job_id"]
                original_groups = {key: work / f"original-{key}.wav" for key in body["groups"]}
                if not all(path.is_file() for path in original_groups.values()):
                    history = json.loads((ROOT / "backend" / "job_history.json").read_text(encoding="utf-8"))
                    cached = next((item for item in reversed(history["separate"])
                                   if item.get("status") == "succeeded" and item.get("source_digest") == job["source_digest"]
                                   and item.get("result", {}).get("groups")), None)
                    assert cached, "Original groups missing from both work and cache"
                    report["original_group_cache_job"] = cached["job_id"]
                    original_groups = {item["id"]: settings.outputs_dir / item["file_name"]
                                       for item in cached["result"]["groups"]}
                for index, metadata in enumerate(job["result"]["metadata"], 1):
                    single = sum(action == "transform" for action in body["groups"].values()) == 1
                    parts = []
                    for key, action in body["groups"].items():
                        if action == "remove":
                            continue
                        if action == "keep":
                            source = original_groups[key]
                        elif single:
                            source = work / f"pista-transformada-{index}.wav"
                        else:
                            source = work / f"transformada-{index}-{key}.wav"
                        parts.append((source, 0))
                    expected = work / f"tester-expected-{index}.wav"
                    MixerService.mix_groups(parts, expected, job["duration_seconds"], settings.remix.sample_rate)
                    comparison = delta(pcm(Path(metadata["intermediate_path"]), settings.remix.sample_rate),
                                       pcm(expected, settings.remix.sample_rate))
                    report["audio"][index - 1]["recombination_delta"] = comparison
                    assert comparison["max_absolute"] <= 1e-6, comparison
            disk = json.loads((ROOT / "backend" / "job_history.json").read_text(encoding="utf-8"))
            report["persisted_job_found"] = job["job_id"] in json.dumps(disk)
            assert report["persisted_job_found"]
        report["status"] = "PASS"
    except BaseException as exc:
        report.update(status="FAIL", error=repr(exc))
        raise
    finally:
        evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status": report["status"], "evidence": str(evidence)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
