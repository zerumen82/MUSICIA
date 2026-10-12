"""B1: API HTTP real con bloqueo Windows sobre MP3 aislados, sin GPU."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def request(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=3)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


def serve(outputs, port):
    os.environ["MUSICIA_PATHS__OUTPUTS_DIR"] = str(outputs)
    sys.path.insert(0, str(ROOT / "backend"))
    import main
    import uvicorn
    main.HISTORY_FILE = outputs.parent / "job_history.json"
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="info")


def probe():
    if os.name != "nt":
        raise RuntimeError("La comprobación requiere Windows real")
    work = ROOT / "logs" / "fix-20261012-b1-real"
    outputs = work / "outputs"
    outputs.mkdir(parents=True, exist_ok=False)
    locked = outputs / "ocupado.mp3"
    free = outputs / "libre.mp3"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg no disponible")
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=1", "-c:a", "libmp3lame", str(locked)], check=True)
    shutil.copyfile(locked, free)
    for path in (locked, free):
        path.with_suffix(".ficha.json").write_text(json.dumps({"probe": "B1", "name": path.name}), encoding="utf-8")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    # GENERIC_READ, FILE_SHARE_READ (sin FILE_SHARE_DELETE), OPEN_EXISTING.
    handle = kernel.CreateFileW(str(locked), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    child = None
    evidence = {"base": base, "outputs": str(outputs), "lock": "CreateFileW: FILE_SHARE_READ; sin FILE_SHARE_DELETE"}
    try:
        with (work / "api.log").open("w", encoding="utf-8") as logfile:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                      "--serve", str(outputs), "--port", str(port)],
                                     cwd=ROOT, stdout=logfile, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 20
            while True:
                if child.poll() is not None:
                    raise RuntimeError(f"API terminó: {child.returncode}")
                try:
                    ready, _ = request(base, "GET", "/music/library")
                    if ready == 200:
                        break
                except (OSError, urllib.error.URLError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("API no preparada en 20 s")
                time.sleep(0.1)
            code, data = request(base, "DELETE", "/music/audio/ocupado.mp3")
            evidence["individual"] = {"http": code, "body": data}
            assert code == 409 and "otro proceso" in data["detail"], evidence
            assert locked.exists() and locked.with_suffix(".ficha.json").exists()
            code, data = request(base, "POST", "/music/audio/delete_many",
                                 {"names": ["ocupado.mp3", "libre.mp3", "ausente.mp3"]})
            evidence["batch"] = {"http": code, "body": data}
            assert code == 200 and data["status"] == "partial", evidence
            assert data["blocked"] == [locked.name] and data["deleted"] == [free.name], evidence
            assert data["not_found"] == ["ausente.mp3"] and data["failed"] == [], evidence
            assert locked.exists() and locked.with_suffix(".ficha.json").exists()
            assert not free.exists() and not free.with_suffix(".ficha.json").exists()
            kernel.CloseHandle(handle)
            handle = None
            code, data = request(base, "DELETE", "/music/audio/ocupado.mp3")
            evidence["released"] = {"http": code, "body": data}
            assert code == 200 and data["status"] == "deleted", evidence
            assert not locked.exists() and not locked.with_suffix(".ficha.json").exists()
            evidence["verdict"] = "PASS"
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        (work / "result.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", type=Path)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.port)
    else:
        probe()
