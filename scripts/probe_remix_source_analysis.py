"""Native local audio understanding probe; preserves real failure evidence."""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from config import get_settings
from music_service import MusicService
from source_understanding import SourceAnalysisSettings, analyze_source


async def main():
    evidence = ROOT / "logs" / "remix-source-analysis-real.json"
    source = ROOT / "backend" / "outputs" / "pista-sin-nombre (2).mp3"
    if len(sys.argv) > 1:
        source = Path(sys.argv[1]).resolve()
    report = {"source": str(source), "kind": "actual ACE-Step full_analysis_only"}
    music = MusicService(get_settings())
    await music.start()
    try:
        result = await analyze_source(music, source, SourceAnalysisSettings(),
                                      lambda phase: print(phase, flush=True))
        report.update(status="PASS", result=result)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except Exception as exc:
        report.update(status="FAIL", error=str(exc))
        raise
    finally:
        evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        await music.aclose()


asyncio.run(main())
