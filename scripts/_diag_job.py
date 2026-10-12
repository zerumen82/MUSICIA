"""Localiza el último job remix de ámbito región en el historial (auxiliar de diagnóstico)."""
import json
from pathlib import Path

history = json.loads(Path(__file__).resolve().parents[1].joinpath("backend", "job_history.json").read_text(encoding="utf-8"))
jobs = [job for job in history.get("remix", []) if (job.get("project") or {}).get("scope") == "region"]
job = jobs[-1]
print(job["job_id"])
print(job["result"]["metadata"][0]["intermediate_path"])
print(job["source"])